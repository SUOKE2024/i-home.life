import { test, expect } from '@playwright/test';

/**
 * 业务页视觉回归 + 交互 — 批次 12
 *
 * 验证 CADPage（CAD 导入）/ Sketch3DPage（草图转 3D）/ IFCExportPage（BIM 导出）：
 *   1. 文件选择区 + 上传交互（mock multipart 响应）
 *   2. 解析结果展示（实体统计网格 / 草图检测 / 3D 建议）
 *   3. tab 切换（sketch 分析/生成、IFC 结构/设计）
 *   4. 错误降级（501 ezdxf/ifcopenshell 未装）
 *
 * mock 策略同 batch11：localStorage 预设 paseto_token，page.route 拦截 /api/*。
 * 后端响应字段严格对齐 app/api/cad_import.py / sketch_to_3d.py / schemas/ifc_export.py（snake_case）。
 */

const MOCK_PROJECTS = [
  {
    id: 'proj-1',
    name: '三居室整装',
    address: '上海市浦东新区世纪大道 100 号',
    total_area: 120,
    status: 'construction',
    project_type: 'full_renovation',
    owner_id: 'user-1',
    created_at: '2026-06-15T10:00:00Z',
    updated_at: '2026-07-20T14:30:00Z',
  },
];

const MOCK_FLOORPLANS = [
  { id: 'plan-1', project_id: 'proj-1', name: '一层平面图', version: 1, status: 'active', area_m2: 95.5 },
];

// ════════════════════════════════════════════
// CADPage CAD 导入
// ════════════════════════════════════════════

const MOCK_CAD_RESULT = {
  file_type: 'dxf',
  entity_count: 42,
  lines: [{ x1: 0, y1: 0, x2: 10, y2: 10 }, { x1: 10, y1: 0, x2: 10, y2: 10 }],
  polylines: [[{ x: 0, y: 0 }, { x: 5, y: 5 }]],
  circles: [{ x: 5, y: 5, r: 3 }],
  arcs: [{ x: 0, y: 0, r: 5, start_angle: 0, end_angle: 90 }],
  texts: [{ x: 1, y: 1, text: '客厅', height: 2.5 }],
  bounds: { min_x: 0, min_y: 0, max_x: 10, max_y: 10, width: 10, height: 10 },
  converted_from_dwg: false,
};

test.describe('CADPage CAD 导入', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'mock-token-cad');
    });
    // AuthGate 校验 token（/api/auth/me），未 mock 则 401 重定向 login.html
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
        id: 'user-1', phone: '13800138000', name: '张业主', role: 'homeowner',
        sub_role: null, avatar_url: null, is_active: true, is_verified: true,
        created_at: '2026-01-01T00:00:00Z',
      }) });
    });
    await page.route('**/api/projects**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
  });

  test('渲染文件选择区 + 提示文案', async ({ page }) => {
    await page.goto('./cad');
    await expect(page.getByTestId('wb-cad-page')).toBeVisible();
    await expect(page.getByTestId('wb-cad-upload-zone')).toBeVisible();
    await expect(page.getByTestId('wb-cad-file-name')).toContainText('支持 .dxf / .dwg 格式');
    await expect(page.getByText('📐 CAD 导入')).toBeVisible();
  });

  test('上传 DXF → 展示解析结果（实体统计 + 边界）', async ({ page }) => {
    await page.route('**/api/cad-import/dxf', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CAD_RESULT) });
    });
    await page.goto('./cad');
    await expect(page.getByTestId('wb-cad-pick-btn')).toBeVisible();
    // 上传一个最小 DXF 文本（后端 mock 不解析内容，只校验流程）
    await page.getByTestId('wb-cad-file-input').setInputFiles({
      name: 'test.dxf',
      mimeType: 'application/dxf',
      buffer: Buffer.from('0\r\nSECTION\r\n'),
    });
    await expect(page.getByTestId('wb-cad-file-name')).toContainText('test.dxf');
    await expect(page.getByTestId('wb-cad-upload-btn')).toBeVisible();
    await page.getByTestId('wb-cad-upload-btn').click();
    // 结果展示
    await expect(page.getByTestId('wb-cad-result')).toBeVisible();
    await expect(page.getByTestId('wb-cad-file-type')).toContainText('DXF');
    await expect(page.getByTestId('wb-cad-entity-count')).toContainText('42');
    await expect(page.getByTestId('wb-cad-entity--lines')).toContainText('2');
    await expect(page.getByTestId('wb-cad-entity--circles')).toContainText('1');
    await expect(page.getByTestId('wb-cad-entity--texts')).toContainText('1');
    await expect(page.getByTestId('wb-cad-bounds')).toContainText('minX');
    await expect(page.getByTestId('wb-cad-converted')).toContainText('否');
  });

  test('501 ezdxf 未装 → 错误降级提示', async ({ page }) => {
    await page.route('**/api/cad-import/dxf', async (route) => {
      await route.fulfill({ status: 501, contentType: 'application/json', body: JSON.stringify({ detail: '服务端未安装 ezdxf 库' }) });
    });
    await page.goto('./cad');
    await page.getByTestId('wb-cad-file-input').setInputFiles({
      name: 'bad.dxf', mimeType: 'application/dxf', buffer: Buffer.from('x'),
    });
    await page.getByTestId('wb-cad-upload-btn').click();
    await expect(page.getByTestId('wb-cad-error')).toBeVisible();
    await expect(page.getByTestId('wb-cad-error')).toContainText('ezdxf');
  });
});

// ════════════════════════════════════════════
// Sketch3DPage 草图转 3D
// ════════════════════════════════════════════

const MOCK_SKETCH_ANALYSIS = {
  sketch_id: 'sketch-1',
  detected_walls: [{ id: 'w1' }, { id: 'w2' }],
  detected_doors: [{ id: 'd1' }],
  detected_windows: [{ id: 'win1' }, { id: 'win2' }, { id: 'win3' }],
  estimated_area: 95.5,
  room_count: 3,
  confidence: 0.88,
  raw_layout: {},
};

const MOCK_SKETCH_3D = {
  sketch_id: 'sketch-1',
  analysis: MOCK_SKETCH_ANALYSIS,
  layout_3d: { recommendation: '建议增加储物空间', bim_compatible: true },
  suggestions: ['优化采光', '增加插座'],
};

test.describe('Sketch3DPage 草图转 3D', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'mock-token-sketch');
    });
    // AuthGate 校验 token（/api/auth/me），未 mock 则 401 重定向 login.html
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
        id: 'user-1', phone: '13800138000', name: '张业主', role: 'homeowner',
        sub_role: null, avatar_url: null, is_active: true, is_verified: true,
        created_at: '2026-01-01T00:00:00Z',
      }) });
    });
    await page.route('**/api/sketch-to-3d/supported-formats', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ image_formats: ['PNG', 'JPG', 'JPEG'], max_file_size_mb: 10, recommended_resolution: '1024x768 以上', tips: [] }),
      });
    });
  });

  test('渲染 tab + 文件选择区 + 支持格式', async ({ page }) => {
    await page.goto('./sketch-3d');
    await expect(page.getByTestId('wb-sketch-page')).toBeVisible();
    await expect(page.getByTestId('wb-sketch-tabs')).toBeVisible();
    await expect(page.getByTestId('wb-sketch-tab--analyze')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('wb-sketch-file-name')).toContainText('PNG');
  });

  test('分析模式 → 上传草图 → 展示检测结果统计', async ({ page }) => {
    await page.route('**/api/sketch-to-3d/analyze', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SKETCH_ANALYSIS) });
    });
    await page.goto('./sketch-3d');
    await page.getByTestId('wb-sketch-file-input').setInputFiles({
      name: 'sketch.png', mimeType: 'image/png', buffer: Buffer.from([0x89, 0x50, 0x4e, 0x47]),
    });
    await page.getByTestId('wb-sketch-desc-input').fill('三室两厅户型');
    await page.getByTestId('wb-sketch-submit-btn').click();
    await expect(page.getByTestId('wb-sketch-analysis-result')).toBeVisible();
    await expect(page.getByTestId('wb-sketch-walls')).toContainText('2');
    await expect(page.getByTestId('wb-sketch-doors')).toContainText('1');
    await expect(page.getByTestId('wb-sketch-windows')).toContainText('3');
    await expect(page.getByTestId('wb-sketch-rooms')).toContainText('3');
    await expect(page.getByTestId('wb-sketch-area')).toContainText('95.5');
    await expect(page.getByTestId('wb-sketch-confidence')).toContainText('88%');
  });

  test('切换到生成 3D tab → 风格选择可见 → 生成结果展示', async ({ page }) => {
    await page.route('**/api/sketch-to-3d/generate-3d', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SKETCH_3D) });
    });
    await page.goto('./sketch-3d');
    await page.getByTestId('wb-sketch-tab--generate').click();
    await expect(page.getByTestId('wb-sketch-tab--generate')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('wb-sketch-style-select')).toBeVisible();
    await page.getByTestId('wb-sketch-file-input').setInputFiles({
      name: 'sketch.jpg', mimeType: 'image/jpeg', buffer: Buffer.from([0xff, 0xd8, 0xff]),
    });
    await page.getByTestId('wb-sketch-submit-btn').click();
    await expect(page.getByTestId('wb-sketch-generate-result')).toBeVisible();
    await expect(page.getByTestId('wb-sketch-3d-recommendation')).toContainText('储物空间');
    await expect(page.getByTestId('wb-sketch-3d-suggestion--0')).toContainText('采光');
  });

  test('分析 501 → 错误降级', async ({ page }) => {
    await page.route('**/api/sketch-to-3d/analyze', async (route) => {
      await route.fulfill({ status: 501, contentType: 'application/json', body: JSON.stringify({ detail: 'vision model not configured' }) });
    });
    await page.goto('./sketch-3d');
    await page.getByTestId('wb-sketch-file-input').setInputFiles({
      name: 's.png', mimeType: 'image/png', buffer: Buffer.from([0x89, 0x50]),
    });
    await page.getByTestId('wb-sketch-submit-btn').click();
    await expect(page.getByTestId('wb-sketch-error')).toBeVisible();
    await expect(page.getByTestId('wb-sketch-error')).toContainText('视觉模型');
  });
});

// ════════════════════════════════════════════
// IFCExportPage BIM 导出
// ════════════════════════════════════════════

test.describe('IFCExportPage BIM 导出', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'mock-token-ifc');
    });
    // AuthGate 校验 token（/api/auth/me），未 mock 则 401 重定向 login.html
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
        id: 'user-1', phone: '13800138000', name: '张业主', role: 'homeowner',
        sub_role: null, avatar_url: null, is_active: true, is_verified: true,
        created_at: '2026-01-01T00:00:00Z',
      }) });
    });
    await page.route('**/api/projects**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
  });

  test('渲染项目选择 + 结构/设计 tab + 选项区', async ({ page }) => {
    await page.goto('./ifc-export');
    await expect(page.getByTestId('wb-ifc-page')).toBeVisible();
    await expect(page.getByTestId('wb-ifc-tabs')).toBeVisible();
    await expect(page.getByTestId('wb-ifc-tab--structural')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('wb-ifc-project-select')).toBeVisible();
    await expect(page.getByTestId('wb-ifc-options')).toBeVisible();
    await expect(page.getByTestId('wb-ifc-furniture')).toBeVisible();
    await expect(page.getByTestId('wb-ifc-lod')).toBeVisible();
  });

  test('选项交互：含家具 checkbox + LOD 切换', async ({ page }) => {
    await page.goto('./ifc-export');
    const furniture = page.getByTestId('wb-ifc-furniture').locator('input[type="checkbox"]');
    await expect(furniture).not.toBeChecked();
    await furniture.check();
    await expect(furniture).toBeChecked();
    await page.getByTestId('wb-ifc-lod').selectOption('LOD350');
    await expect(page.getByTestId('wb-ifc-lod')).toHaveValue('LOD350');
  });

  test('结构导出 501 ifcopenshell 未装 → 降级提示', async ({ page }) => {
    await page.route('**/api/bim/export/structural/**', async (route) => {
      await route.fulfill({ status: 501, contentType: 'application/json', body: JSON.stringify({ detail: 'IFC 导出需要安装 ifcopenshell' }) });
    });
    await page.goto('./ifc-export');
    // 等项目加载后选中
    await page.getByTestId('wb-ifc-project-select').selectOption('proj-1');
    await page.getByTestId('wb-ifc-export-btn').click();
    await expect(page.getByTestId('wb-ifc-error')).toBeVisible();
    await expect(page.getByTestId('wb-ifc-error')).toContainText('ifcopenshell');
  });

  test('切换到设计导出 → 加载户型方案 + 方案选择可见', async ({ page }) => {
    await page.route('**/api/floorplans**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_FLOORPLANS) });
    });
    await page.goto('./ifc-export');
    await page.getByTestId('wb-ifc-tab--design').click();
    await expect(page.getByTestId('wb-ifc-tab--design')).toHaveAttribute('aria-selected', 'true');
    await page.getByTestId('wb-ifc-project-select').selectOption('proj-1');
    await expect(page.getByTestId('wb-ifc-plan-select')).toBeVisible();
    await expect(page.getByTestId('wb-ifc-plan-select')).toContainText('一层平面图');
  });
});

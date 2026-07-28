import { test, expect } from '@playwright/test';

/**
 * 业务页视觉回归 + 交互 — 批次 11
 *
 * 验证 CustomFurniturePage（定制家具）/ QualityPage（质检）/ AIRenderPage（AI 渲染）：
 *   1. 列表/能力渲染正确（mock API）
 *   2. 详情展开 + tab 切换（custom-furniture）
 *   3. 阶段 tab + 视图切换（quality）
 *   4. 空状态 / 错误降级
 *
 * mock 策略同 batch8.spec.ts：localStorage 预设 paseto_token，拦截 /api/* 返回固定数据。
 * 后端响应字段严格对齐 app/schemas/（snake_case）。
 * 注意 quality 端点位于 /api/construction/quality-* （非 /api/quality）。
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

// ════════════════════════════════════════════
// CustomFurniturePage 定制家具
// ════════════════════════════════════════════

const MOCK_DESIGNS = [
  {
    id: 'design-1',
    project_id: 'proj-1',
    room_name: '主卧',
    furniture_type: 'wardrobe',
    total_width: 2800,
    total_height: 2700,
    total_depth: 600,
    panel_material: '颗粒板',
    panel_thickness: 18,
    edge_banding: 'PVC',
    hardware_brand: '海蒂诗',
    color: '暖白',
    style: 'modern',
    total_price: 12800,
    status: 'quoted',
    notes: null,
    created_at: '2026-07-10T10:00:00Z',
    updated_at: '2026-07-12T10:00:00Z',
  },
  {
    id: 'design-2',
    project_id: 'proj-1',
    room_name: '厨房',
    furniture_type: 'kitchen_cabinet',
    total_width: 3600,
    total_height: 2400,
    total_depth: 600,
    panel_material: '多层实木板',
    panel_thickness: 18,
    edge_banding: 'ABS',
    hardware_brand: '百隆',
    color: null,
    style: 'nordic',
    total_price: 0,
    status: 'draft',
    notes: '待估价',
    created_at: '2026-07-15T10:00:00Z',
    updated_at: '2026-07-15T10:00:00Z',
  },
];

const MOCK_MODULES = [
  {
    id: 'm1', design_id: 'design-1', module_type: '顶柜', position_index: 0,
    width: 800, height: 400, depth: 600, quantity: 3,
    material: '颗粒板', color: '暖白', hardware_specs: null, price: 1200,
    created_at: '', updated_at: '',
  },
  {
    id: 'm2', design_id: 'design-1', module_type: '下柜', position_index: 1,
    width: 800, height: 2100, depth: 600, quantity: 3,
    material: '颗粒板', color: '暖白', hardware_specs: null, price: 1800,
    created_at: '', updated_at: '',
  },
];

const MOCK_BOM = [
  {
    id: 'b1', design_id: 'design-1', item_name: '颗粒板 18mm', item_type: 'panel',
    spec: '2440×1220', material: '颗粒板', quantity: 8, unit: '张',
    unit_price: 180, total_price: 1440, supplier: '某克', notes: null,
    created_at: '', updated_at: '',
  },
  {
    id: 'b2', design_id: 'design-1', item_name: '铰链', item_type: 'hardware',
    spec: '全阻尼', material: '钢', quantity: 12, unit: '个',
    unit_price: 25, total_price: 300, supplier: '海蒂诗', notes: null,
    created_at: '', updated_at: '',
  },
];

const MOCK_PRICE = {
  panel_cost: 4400,
  hardware_cost: 1800,
  door_cost: 3200,
  process_cost: 3400,
  total_price: 12800,
};

const MOCK_PANELS = {
  total_panel_area_m2: 24.5,
  panel_sheets: 8.2,
  hardware_list: [{ name: '铰链', count: 12 }, { name: '导轨', count: 6 }],
};

const MOCK_VALIDATION_OK = { valid: true, issues: [] };
const MOCK_VALIDATION_ISSUES = {
  valid: false,
  issues: [
    { field: 'total_height', message: '高度超过房间层高' },
    { field: 'panel_thickness', message: '板材厚度与承重不匹配' },
  ],
};

test.describe('CustomFurniturePage 定制家具', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'test-paseto-token-batch11');
    });
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_PROJECTS),
      });
    });
    await page.route('**/api/voice/tasks', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('设计列表渲染 + 展开详情 price tab', async ({ page }) => {
    await page.route('**/api/custom-furniture/designs/project/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_DESIGNS),
      });
    });
    // 详情懒加载拦截（统一返回 design-1 的数据）
    await page.route('**/api/custom-furniture/designs/design-1/modules', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_MODULES) });
    });
    await page.route('**/api/custom-furniture/designs/design-1/bom', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_BOM) });
    });
    await page.route('**/api/custom-furniture/designs/design-1/price', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PRICE) });
    });
    await page.route('**/api/custom-furniture/designs/design-1/panels', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PANELS) });
    });
    await page.route('**/api/custom-furniture/designs/design-1/validation', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_VALIDATION_OK) });
    });

    await page.goto('./custom-furniture');
    await expect(page.getByTestId('wb-customfurniture-content')).toBeVisible({ timeout: 5000 });

    // 2 个设计
    await expect(page.locator('[data-testid^="wb-customfurniture-item--"]')).toHaveCount(2);
    // 第一个：衣柜 + 主卧 + 总价
    await expect(page.getByTestId('wb-customfurniture-item--0')).toContainText('衣柜');
    await expect(page.getByTestId('wb-customfurniture-item--0')).toContainText('主卧');
    await expect(page.getByTestId('wb-customfurniture-item--0')).toContainText('12,800');
    // 状态徽章
    await expect(page.getByTestId('wb-customfurniture-status--0')).toContainText('已报价');

    // 展开第一个设计
    await page.getByTestId('wb-customfurniture-toggle--0').click();
    await expect(page.getByTestId('wb-customfurniture-detail--0')).toBeVisible({ timeout: 5000 });

    // 默认 price tab，5 个统计
    await expect(page.getByTestId('wb-customfurniture-price--0')).toBeVisible();
    const stats = page.locator('.wb-takeoff-stat');
    await expect(stats).toHaveCount(5);
    await expect(page.getByTestId('wb-customfurniture-price--0')).toContainText('12,800');

    await expect(page).toHaveScreenshot('customfurniture-price.png');
  });

  test('tab 切换到 modules / bom / panels / validation', async ({ page }) => {
    await page.route('**/api/custom-furniture/designs/project/**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_DESIGNS) });
    });
    await page.route('**/api/custom-furniture/designs/design-1/modules', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_MODULES) });
    });
    await page.route('**/api/custom-furniture/designs/design-1/bom', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_BOM) });
    });
    await page.route('**/api/custom-furniture/designs/design-1/price', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PRICE) });
    });
    await page.route('**/api/custom-furniture/designs/design-1/panels', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PANELS) });
    });
    await page.route('**/api/custom-furniture/designs/design-1/validation', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_VALIDATION_OK) });
    });

    await page.goto('./custom-furniture');
    await expect(page.getByTestId('wb-customfurniture-content')).toBeVisible({ timeout: 5000 });
    await page.getByTestId('wb-customfurniture-toggle--0').click();
    await expect(page.getByTestId('wb-customfurniture-detail--0')).toBeVisible({ timeout: 5000 });

    // modules tab
    await page.getByTestId('wb-customfurniture-tab--modules').click();
    await expect(page.getByTestId('wb-customfurniture-modules--0')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-customfurniture-module--"]')).toHaveCount(2);
    await expect(page.getByTestId('wb-customfurniture-module--0')).toContainText('顶柜');

    // bom tab
    await page.getByTestId('wb-customfurniture-tab--bom').click();
    await expect(page.getByTestId('wb-customfurniture-bom--0')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-customfurniture-bomitem--"]')).toHaveCount(2);
    await expect(page.getByTestId('wb-customfurniture-bomitem--0')).toContainText('颗粒板');

    // panels tab
    await page.getByTestId('wb-customfurniture-tab--panels').click();
    await expect(page.getByTestId('wb-customfurniture-panels--0')).toBeVisible();
    await expect(page.getByTestId('wb-customfurniture-panels--0')).toContainText('24.50');
    await expect(page.getByTestId('wb-customfurniture-panels--0')).toContainText('8.2');

    // validation tab（通过）
    await page.getByTestId('wb-customfurniture-tab--validation').click();
    await expect(page.getByTestId('wb-customfurniture-validation-ok--0')).toBeVisible();
    await expect(page.getByTestId('wb-customfurniture-validation-ok--0')).toContainText('通过');
  });

  test('validation 有问题分支', async ({ page }) => {
    await page.route('**/api/custom-furniture/designs/project/**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_DESIGNS) });
    });
    await page.route('**/api/custom-furniture/designs/design-1/modules', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
    await page.route('**/api/custom-furniture/designs/design-1/bom', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
    await page.route('**/api/custom-furniture/designs/design-1/price', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PRICE) });
    });
    await page.route('**/api/custom-furniture/designs/design-1/panels', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PANELS) });
    });
    await page.route('**/api/custom-furniture/designs/design-1/validation', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_VALIDATION_ISSUES) });
    });

    await page.goto('./custom-furniture');
    await expect(page.getByTestId('wb-customfurniture-content')).toBeVisible({ timeout: 5000 });
    await page.getByTestId('wb-customfurniture-toggle--0').click();
    await expect(page.getByTestId('wb-customfurniture-detail--0')).toBeVisible({ timeout: 5000 });

    await page.getByTestId('wb-customfurniture-tab--validation').click();
    await expect(page.getByTestId('wb-customfurniture-validation-issues--0')).toBeVisible();
    await expect(page.getByTestId('wb-customfurniture-validation-issues--0')).toContainText('2 个问题');
    await expect(page.locator('[data-testid^="wb-customfurniture-issue--"]')).toHaveCount(2);
    await expect(page.getByTestId('wb-customfurniture-issue--0')).toContainText('total_height');
  });

  test('空状态', async ({ page }) => {
    await page.route('**/api/custom-furniture/designs/project/**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.goto('./custom-furniture');
    await expect(page.getByTestId('wb-customfurniture-empty')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('wb-customfurniture-empty')).toContainText('暂无定制家具设计');
  });
});

// ════════════════════════════════════════════
// QualityPage 质检
// ════════════════════════════════════════════

const MOCK_CHECKLIST_WE = {
  phase: 'water_electricity',
  total_items: 3,
  checklist: [
    { item: '线管敷设', standard: '横平竖直，固定间距≤80cm', method: '目视+尺量' },
    { item: '强弱电分离', standard: '间距≥30cm', method: '尺量' },
    { item: '线径匹配', standard: '照明 1.5mm² / 插座 2.5mm²', method: '查验线缆标识' },
  ],
  reply: '「water_electricity」阶段质检清单：共 3 项检查点',
};

const MOCK_CHECKLIST_MASONRY = {
  phase: 'masonry',
  total_items: 2,
  checklist: [
    { item: '瓷砖空鼓', standard: '空鼓率＜5%', method: '敲击听音' },
    { item: '平整度', standard: '≤3mm/2m', method: '靠尺+塞尺' },
  ],
  reply: '「masonry」阶段质检清单：共 2 项检查点',
};

const MOCK_QUALITY_ISSUES = [
  {
    id: 'qi-1', project_id: 'proj-1', task_id: null, inspection_id: null,
    phase: 'water_electricity', category: '强弱电混敷',
    description: '主卧强弱电线管交叉未做屏蔽处理',
    severity: 'medium', status: 'open', images: null,
    detected_by: 'manual', standard: '强弱电间距≥30cm', location: '主卧',
    resolution: null, resolved_at: null, resolved_by: null,
    verified_by: null, verified_at: null,
    created_at: '2026-07-20T10:00:00Z', updated_at: '2026-07-20T10:00:00Z',
  },
  {
    id: 'qi-2', project_id: 'proj-1', task_id: null, inspection_id: null,
    phase: 'water_electricity', category: '线径不符',
    description: '厨房插座回路使用 1.5mm² 线缆',
    severity: 'high', status: 'resolved', images: null,
    detected_by: 'ai', standard: '插座回路 2.5mm²', location: '厨房',
    resolution: '已更换为 2.5mm² 线缆', resolved_at: '2026-07-22T10:00:00Z',
    resolved_by: '王师傅', verified_by: null, verified_at: null,
    created_at: '2026-07-19T10:00:00Z', updated_at: '2026-07-22T10:00:00Z',
  },
];

test.describe('QualityPage 质检', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'test-paseto-token-batch11');
    });
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/voice/tasks', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('质检清单渲染（默认水电阶段）+ 阶段切换至泥瓦', async ({ page }) => {
    await page.route('**/api/construction/quality-checklist/water_electricity', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CHECKLIST_WE) });
    });
    await page.route('**/api/construction/quality-checklist/masonry', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CHECKLIST_MASONRY) });
    });

    await page.goto('./quality');
    await expect(page.getByTestId('wb-quality-checklist-content')).toBeVisible({ timeout: 5000 });

    // 默认水电：3 项清单
    await expect(page.locator('[data-testid^="wb-quality-checklist-item--"]')).toHaveCount(3);
    await expect(page.getByTestId('wb-quality-checklist-item--0')).toContainText('线管敷设');
    await expect(page.getByTestId('wb-quality-checklist-item--0')).toContainText('横平竖直');
    await expect(page.getByTestId('wb-quality-checklist-item--0')).toContainText('目视+尺量');

    // 切换至泥瓦
    await page.getByTestId('wb-quality-phase--masonry').click();
    await expect(page.getByTestId('wb-quality-checklist-content')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('[data-testid^="wb-quality-checklist-item--"]')).toHaveCount(2);
    await expect(page.getByTestId('wb-quality-checklist-item--0')).toContainText('瓷砖空鼓');

    await expect(page).toHaveScreenshot('quality-checklist.png');
  });

  test('切换到质量问题视图 + 列表渲染', async ({ page }) => {
    await page.route('**/api/construction/quality-checklist/**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CHECKLIST_WE) });
    });
    await page.route('**/api/construction/quality-issues/**', async (route) => {
      const url = route.request().url();
      if (url.includes('phase=water_electricity')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_QUALITY_ISSUES) });
      } else {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
      }
    });

    await page.goto('./quality');
    await expect(page.getByTestId('wb-quality-checklist-content')).toBeVisible({ timeout: 5000 });

    // 切换到质量问题视图
    await page.getByTestId('wb-quality-view--issues').click();
    await expect(page.getByTestId('wb-quality-issues-content')).toBeVisible({ timeout: 5000 });

    // 2 个问题
    await expect(page.locator('[data-testid^="wb-quality-issue--"]')).toHaveCount(2);
    await expect(page.getByTestId('wb-quality-issue--0')).toContainText('强弱电混敷');
    await expect(page.getByTestId('wb-quality-issue--0')).toContainText('主卧');
    // 严重度徽章
    await expect(page.getByTestId('wb-quality-issue-severity--0')).toContainText('中等');
    await expect(page.getByTestId('wb-quality-issue-severity--1')).toContainText('严重');
    // 状态徽章
    await expect(page.getByTestId('wb-quality-issue-status--0')).toContainText('待处理');
    await expect(page.getByTestId('wb-quality-issue-status--1')).toContainText('已整改');
    // 第二个有整改说明
    await expect(page.getByTestId('wb-quality-issue--1')).toContainText('已更换为');
    // AI 检测标记
    await expect(page.getByTestId('wb-quality-issue--1')).toContainText('🤖');

    await expect(page).toHaveScreenshot('quality-issues.png');
  });

  test('质量问题空状态（阶段无问题）', async ({ page }) => {
    await page.route('**/api/construction/quality-checklist/**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CHECKLIST_WE) });
    });
    await page.route('**/api/construction/quality-issues/**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.goto('./quality');
    await expect(page.getByTestId('wb-quality-checklist-content')).toBeVisible({ timeout: 5000 });
    await page.getByTestId('wb-quality-view--issues').click();
    await expect(page.getByTestId('wb-quality-issues-empty')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('wb-quality-issues-empty')).toContainText('暂无质量问题');
  });
});

// ════════════════════════════════════════════
// AIRenderPage AI 渲染
// ════════════════════════════════════════════

const MOCK_CAPS = {
  styles: ['modern', 'nordic', 'japanese', 'luxury', 'chinese', 'industrial', 'coastal'],
  restage_modes: ['inpainting', 'full_regen'],
  render_types: ['2d', '3d', 'restage'],
  note: 'style 字段允许自由文本，列表仅为推荐项；mode 字段必须取自 restage_modes',
};

test.describe('AIRenderPage AI 渲染', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'test-paseto-token-batch11');
    });
    await page.route('**/api/voice/tasks', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('能力展示：渲染类型 + 风格 chips + 重布置模式', async ({ page }) => {
    await page.route('**/api/ai-render/capabilities', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CAPS) });
    });

    await page.goto('./ai-render');
    await expect(page.getByTestId('wb-airender-content')).toBeVisible({ timeout: 5000 });

    // 3 个渲染类型
    await expect(page.locator('[data-testid^="wb-airender-type--"]')).toHaveCount(3);
    await expect(page.getByTestId('wb-airender-type--0')).toContainText('2D 效果图');
    await expect(page.getByTestId('wb-airender-type--1')).toContainText('3D 场景');
    await expect(page.getByTestId('wb-airender-type--2')).toContainText('照片重布置');
    // 端点说明
    await expect(page.getByTestId('wb-airender-type--0')).toContainText('POST /api/ai-render/2d');

    // 7 个风格 chips
    await expect(page.locator('[data-testid^="wb-airender-style--"]')).toHaveCount(7);
    await expect(page.getByTestId('wb-airender-style--0')).toContainText('现代');
    await expect(page.getByTestId('wb-airender-style--1')).toContainText('北欧');

    // 2 个重布置模式
    await expect(page.locator('[data-testid^="wb-airender-restage--"]')).toHaveCount(2);
    await expect(page.getByTestId('wb-airender-restage--0')).toContainText('inpainting');
    await expect(page.getByTestId('wb-airender-restage--0')).toContainText('局部重绘');
    await expect(page.getByTestId('wb-airender-restage--1')).toContainText('full_regen');
    await expect(page.getByTestId('wb-airender-restage--1')).toContainText('完全重生');

    // 引导卡片
    await expect(page.getByTestId('wb-airender-guide')).toBeVisible();
    await expect(page.getByTestId('wb-airender-guide')).toContainText('工作台');

    await expect(page).toHaveScreenshot('airender-caps.png');
  });

  test('错误降级', async ({ page }) => {
    await page.route('**/api/ai-render/capabilities', async (route) => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: '服务异常' }) });
    });

    await page.goto('./ai-render');
    await expect(page.getByTestId('wb-airender-error')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('wb-airender-error')).toContainText('HTTP 500');
  });
});

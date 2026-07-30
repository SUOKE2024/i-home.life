import { test, expect } from '@playwright/test';

/**
 * 业务页视觉回归 + 交互 — 批次 8
 *
 * 验证 TakeoffPage（工程量计算）：
 *   1. 正向算量结果渲染（reply 汇总 + summary 统计网格 + 墙体明细）
 *   2. 503 降级（forward_takeoff_enabled=False）展示禁用提示
 *   3. 404 降级（无 floorplan）展示去创建户型引导
 *
 * mock 策略：localStorage 预设 paseto_token，拦截 /api/projects + /api/takeoff/project/{id}。
 * 后端响应字段严格对齐 app/services/quantity_takeoff_service.py:ForwardTakeoffResult（snake_case）。
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

// ── 正向算量结果（对齐 ForwardTakeoffResult）──
const MOCK_TAKEOFF = {
  project_id: 'proj-1',
  floorplan_id: 'fp-1',
  floorplan_name: '三居室方案A',
  walls: [
    {
      name: '客厅北墙',
      length: 5.2,
      height: 2.8,
      thickness: 0.24,
      volume: 3.49,
      area: 14.56,
      brick_count: 1820,
      mortar_volume: 1.05,
      paint_area: 29.12,
    },
    {
      name: '主卧南墙',
      length: 4.1,
      height: 2.8,
      thickness: 0.24,
      volume: 2.75,
      area: 11.48,
      brick_count: 1435,
      mortar_volume: 0.83,
      paint_area: 22.96,
    },
  ],
  floors: [
    {
      name: '客厅',
      area: 28.5,
      tile_size: '800x800',
      tile_count: 45,
      mortar_volume: 0.85,
    },
  ],
  ceilings: [
    {
      name: '客厅',
      area: 29.97,
      board_count: 42,
    },
  ],
  paints: [
    {
      name: '墙面乳胶漆',
      area: 52.08,
      primer_count: 2,
      finish_count: 4,
      total_paint_liters: 15.6,
    },
  ],
  summary: {
    total_brick_count: 3255,
    total_mortar_m3: 1.88,
    total_tile_count: 45,
    total_paint_area_m2: 52.08,
    total_ceiling_area_m2: 29.97,
    total_wall_length_m: 9.3,
    total_floor_area_m2: 28.5,
    wall_height_m: 2.8,
    door_count: 2,
    window_count: 3,
  },
  reply:
    '正向算量（基于 floorplan「三居室方案A」几何）：墙体 9.3m / 砖 3255 块 / 砂浆 1.88 m³ / 瓷砖 45 块 / 涂料面积 52.08 m² / 吊顶 29.97 m² / 门 2 樘 / 窗 3 樘',
  geometry: {},
};

test.describe('TakeoffPage 工程量计算', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'test-paseto-token-batch8');
    });
    // 拦截项目列表
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_PROJECTS),
      });
    });
    // 拦截语音任务（WorkbenchPage/SuokeLayout 可能请求）
    await page.route('**/api/voice/orchestrate/tasks', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('正向算量结果渲染：reply + summary 统计 + 墙体明细', async ({ page }) => {
    await page.route('**/api/takeoff/project/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_TAKEOFF),
      });
    });

    await page.goto('./takeoff');
    // 等待内容渲染
    await expect(page.getByTestId('wb-takeoff-content')).toBeVisible({ timeout: 5000 });

    // reply 汇总卡片含 floorplan 名称
    await expect(page.getByTestId('wb-takeoff-reply')).toContainText('三居室方案A');

    // summary 统计网格 8 个 stat
    const stats = page.locator('.wb-takeoff-stat');
    await expect(stats).toHaveCount(8);
    // 砖用量统计值
    await expect(page.getByTestId('wb-takeoff-summary')).toContainText('3,255');

    // 墙体明细 2 项
    const walls = page.locator('[data-testid^="wb-takeoff-wall--"]');
    await expect(walls).toHaveCount(2);
    await expect(page.getByTestId('wb-takeoff-wall--0')).toContainText('客厅北墙');
    await expect(page.getByTestId('wb-takeoff-wall--0')).toContainText('1,820');

    // 地面明细 1 项
    await expect(page.locator('[data-testid^="wb-takeoff-floor--"]')).toHaveCount(1);
    // 涂料明细 1 项
    await expect(page.locator('[data-testid^="wb-takeoff-paint--"]')).toHaveCount(1);

    // 截图
    await expect(page).toHaveScreenshot('takeoff-result.png');
  });

  test('503 降级：forward_takeoff_enabled=False 展示禁用提示', async ({ page }) => {
    await page.route('**/api/takeoff/project/**', async (route) => {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '正向算量未启用' }),
      });
    });

    await page.goto('./takeoff');
    await expect(page.getByTestId('wb-takeoff-disabled')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('wb-takeoff-disabled')).toContainText('正向算量未启用');
    // 引导返回工作台
    await expect(page.getByTestId('wb-takeoff-disabled')).toContainText('返回工作台');
  });

  test('404 降级：无 floorplan 展示去创建户型引导', async ({ page }) => {
    await page.route('**/api/takeoff/project/**', async (route) => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '无法计算工程量' }),
      });
    });

    await page.goto('./takeoff');
    await expect(page.getByTestId('wb-takeoff-no-floorplan')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('wb-takeoff-no-floorplan')).toContainText('去创建户型');
  });

  test('项目选择器切换', async ({ page }) => {
    const MOCK_PROJECTS_2 = [
      ...MOCK_PROJECTS,
      {
        id: 'proj-2',
        name: '别墅精装',
        address: '杭州市西湖区',
        total_area: 320,
        status: 'design',
        project_type: 'full_renovation',
        owner_id: 'user-1',
        created_at: '2026-07-01T10:00:00Z',
        updated_at: '2026-07-25T14:30:00Z',
      },
    ];
    // 重新拦截项目列表（2 个项目）
    await page.unroute('**/api/projects');
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_PROJECTS_2),
      });
    });
    await page.route('**/api/takeoff/project/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_TAKEOFF),
      });
    });

    await page.goto('./takeoff');
    await expect(page.getByTestId('wb-takeoff-content')).toBeVisible({ timeout: 5000 });

    // 项目选择器有 2 个选项
    const options = page.locator('[data-testid="wb-takeoff-project-select"] option');
    await expect(options).toHaveCount(3); // 含"选择项目…"占位
  });
});

// ════════════════════════════════════════════
// StructuralPage 土建结构
// ════════════════════════════════════════════

const MOCK_WALLS = [
  {
    id: 'w1', project_id: 'proj-1', room_id: null,
    wall_name: '客厅北墙', is_load_bearing: true,
    thickness_mm: 240, length_m: 5.2, height_m: 2.8,
    material: '钢筋混凝土', notes: null,
    created_at: '2026-06-20T10:00:00Z', updated_at: '2026-06-20T10:00:00Z',
  },
  {
    id: 'w2', project_id: 'proj-1', room_id: 'room-1',
    wall_name: '主卧隔墙', is_load_bearing: false,
    thickness_mm: 120, length_m: 3.5, height_m: 2.8,
    material: '轻钢龙骨石膏板', notes: '隔音要求',
    created_at: '2026-06-21T10:00:00Z', updated_at: '2026-06-21T10:00:00Z',
  },
];

const MOCK_BEAMS = [
  {
    id: 'b1', project_id: 'proj-1', beam_name: '客厅主梁', beam_type: 'main_beam',
    width_mm: 300, height_mm: 500, length_m: 6.0,
    material: 'reinforced_concrete', concrete_grade: 'C30',
    position_desc: '轴线A-B', notes: null,
    created_at: '2026-06-20T10:00:00Z', updated_at: '2026-06-20T10:00:00Z',
  },
];

test.describe('StructuralPage 土建结构', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'test-paseto-token-batch8');
    });
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/voice/orchestrate/tasks', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('承重墙列表渲染 + tab 切换至梁', async ({ page }) => {
    await page.route('**/api/structural/projects/**/walls', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_WALLS) });
    });
    await page.route('**/api/structural/projects/**/beams', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_BEAMS) });
    });

    await page.goto('./structural');
    await expect(page.getByTestId('wb-structural-content')).toBeVisible({ timeout: 5000 });

    // 默认 walls tab，2 个墙体
    const items = page.locator('[data-testid^="wb-structural-item--"]');
    await expect(items).toHaveCount(2);
    await expect(page.getByTestId('wb-structural-item--0')).toContainText('客厅北墙');
    await expect(page.getByTestId('wb-structural-item--0')).toContainText('承重');
    await expect(page.getByTestId('wb-structural-item--1')).toContainText('非承重');

    // 切换至 beams tab
    await page.getByTestId('wb-structural-tab--beams').click();
    await expect(page.locator('[data-testid^="wb-structural-item--"]')).toHaveCount(1);
    await expect(page.getByTestId('wb-structural-item--0')).toContainText('客厅主梁');

    await expect(page).toHaveScreenshot('structural-beams.png');
  });

  test('空状态', async ({ page }) => {
    await page.route('**/api/structural/projects/**/walls', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.goto('./structural');
    await expect(page.getByTestId('wb-structural-empty')).toBeVisible({ timeout: 5000 });
  });
});

// ════════════════════════════════════════════
// AppliancePage 家电管理
// ════════════════════════════════════════════

const MOCK_APP_CATEGORIES = [
  { id: 'cat-1', name: '厨电', code: 'kitchen', description: null, created_at: '', updated_at: '' },
  { id: 'cat-2', name: '空调', code: 'ac', description: null, created_at: '', updated_at: '' },
];

const MOCK_APPLIANCES = [
  {
    id: 'a1', category_id: 'cat-1', name: '变频油烟机', brand: '老板', model: '27A1',
    subcategory: 'range_hood', spec: '22m³/min', power_rating: 260, energy_label: '一级',
    price: 3299, install_requirements: null, dimensions: null, weight_kg: 25,
    image_url: null, tags: ['静音'], status: 'active',
    created_at: '', updated_at: '',
  },
  {
    id: 'a2', category_id: 'cat-2', name: '中央空调', brand: '大金', model: 'VRV-X',
    subcategory: 'air_conditioner', spec: '5匹一拖四', power_rating: 4500, energy_label: '一级',
    price: 28000, install_requirements: null, dimensions: null, weight_kg: null,
    image_url: null, tags: null, status: 'active',
    created_at: '', updated_at: '',
  },
];

test.describe('AppliancePage 家电管理', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'test-paseto-token-batch8');
    });
    await page.route('**/api/appliances/categories', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_APP_CATEGORIES) });
    });
    await page.route('**/api/voice/orchestrate/tasks', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('家电列表渲染 + 分类筛选交互', async ({ page }) => {
    // 默认全部：返回 2 个
    await page.route('**/api/appliances/search**', async (route) => {
      const url = route.request().url();
      const body = url.includes('category_id=cat-1') ? [MOCK_APPLIANCES[0]] : MOCK_APPLIANCES;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    });

    await page.goto('./appliance');
    await expect(page.getByTestId('wb-appliance-content')).toBeVisible({ timeout: 5000 });

    // 默认全部 2 个
    await expect(page.locator('[data-testid^="wb-appliance-item--"]')).toHaveCount(2);
    await expect(page.getByTestId('wb-appliance-item--0')).toContainText('油烟机');
    await expect(page.getByTestId('wb-appliance-item--1')).toContainText('中央空调');

    // 点击厨电筛选 → 1 个
    await page.getByTestId('wb-appliance-filter--kitchen').click();
    await expect(page.locator('[data-testid^="wb-appliance-item--"]')).toHaveCount(1);
    await expect(page.getByTestId('wb-appliance-item--0')).toContainText('油烟机');

    await expect(page).toHaveScreenshot('appliance-filtered.png');
  });

  test('空状态', async ({ page }) => {
    await page.route('**/api/appliances/search**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.goto('./appliance');
    await expect(page.getByTestId('wb-appliance-empty')).toBeVisible({ timeout: 5000 });
  });
});

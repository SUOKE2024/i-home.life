import { test, expect } from '@playwright/test';

/**
 * 业务页视觉回归 + 交互 — 批次 7
 *
 * 验证 FloorplansPage / LightingPage / SoftFurnishingPage / KitchenPage /
 *          BathroomPage / DoorWindowPage：
 *   1. 列表渲染正确（mock API）
 *   2. 类型/风格/布局筛选 + 视图切换交互
 *   3. 软装预算进度 / 卫浴通风合规校验 / 门窗防水双视图
 *
 * mock 策略同 batch5/batch6。后端响应字段严格对齐 app/schemas/（snake_case）。
 * 配置默认跑 desktop(1440) + mobile(375) 两断点（playwright.config.ts projects）。
 */

const MOCK_PROJECTS = [
  {
    id: 'proj-1',
    name: '三居室整装',
    address: '上海市浦东新区',
    total_area: 120,
    status: 'construction',
    project_type: 'full_renovation',
    owner_id: 'user-1',
    created_at: '2026-06-15T10:00:00Z',
    updated_at: '2026-07-20T14:30:00Z',
  },
];

// ── 户型（对齐 app/schemas/floorplan.py:FloorPlanListItem）──
const MOCK_FLOORPLANS = [
  {
    id: 'fp-1', project_id: 'proj-1', name: '三居室标准户型',
    total_area: 120, room_count: 3, wall_height: 2.8,
    updated_at: '2026-07-01T10:00:00Z',
  },
  {
    id: 'fp-2', project_id: 'proj-1', name: '改造后开放户型',
    total_area: 118, room_count: 2, wall_height: 2.8,
    updated_at: '2026-07-15T10:00:00Z',
  },
];

// ── 灯光（对齐 app/schemas/lighting.py:LightingSchemeResponse）──
const MOCK_LIGHTING = [
  {
    id: 'lt-1', project_id: 'proj-1', room_name: '客厅', scheme_type: 'main_light',
    room_area: 25, ceiling_height: 2.8, total_lumens: 4500, total_power_w: 120,
    color_temp_k: 4000, cri: 90, ugpr: null, status: 'draft', notes: '主灯 + 辅助光源',
    created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-10T00:00:00Z',
  },
  {
    id: 'lt-2', project_id: 'proj-1', room_name: '主卧', scheme_type: 'none_main',
    room_area: 18, ceiling_height: 2.7, total_lumens: 2400, total_power_w: 60,
    color_temp_k: 3000, cri: 95, ugpr: null, status: 'draft', notes: null,
    created_at: '2026-07-02T00:00:00Z', updated_at: '2026-07-11T00:00:00Z',
  },
  {
    id: 'lt-3', project_id: 'proj-1', room_name: '书房', scheme_type: 'scene',
    room_area: 12, ceiling_height: 2.7, total_lumens: 1800, total_power_w: 45,
    color_temp_k: 3500, cri: 92, ugpr: null, status: 'draft', notes: '阅读/休闲场景',
    created_at: '2026-07-03T00:00:00Z', updated_at: '2026-07-12T00:00:00Z',
  },
];

// ── 软装（对齐 app/schemas/soft_furnishing.py:SoftFurnishingSchemeResponse）──
const MOCK_SOFT = [
  {
    id: 'sf-1', project_id: 'proj-1', room_name: '客厅', style: 'modern',
    color_scheme: null, budget_total: 50000, budget_used: 42000, status: 'draft',
    notes: '现代简约风', created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-10T00:00:00Z',
  },
  {
    id: 'sf-2', project_id: 'proj-1', room_name: '主卧', style: '北欧',
    color_scheme: null, budget_total: 30000, budget_used: 9000, status: 'draft',
    notes: null, created_at: '2026-07-02T00:00:00Z', updated_at: '2026-07-11T00:00:00Z',
  },
];

// ── 厨房（对齐 app/schemas/kitchen.py:KitchenDesignResponse）──
const MOCK_KITCHEN = [
  {
    id: 'kd-1', project_id: 'proj-1', room_name: '厨房', layout_type: 'L',
    room_width: 3.0, room_length: 4.0, ceiling_height: 2.7,
    counter_height: 85, counter_depth: 60,
    water_inlet_pos: '左下角', drain_pos: '右下角', gas_pos: '右侧中', vent_pos: '上方靠窗',
    status: 'draft', created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-10T00:00:00Z',
  },
  {
    id: 'kd-2', project_id: 'proj-1', room_name: '开放式西厨', layout_type: 'island',
    room_width: 4.0, room_length: 5.0, ceiling_height: 2.8,
    counter_height: 90, counter_depth: 65,
    water_inlet_pos: '岛台下', drain_pos: '岛台下', gas_pos: null, vent_pos: '上方中央',
    status: 'draft', created_at: '2026-07-02T00:00:00Z', updated_at: '2026-07-11T00:00:00Z',
  },
];

// ── 卫浴（对齐 app/schemas/bathroom.py:BathroomDesignResponse）──
// 设计 1：干湿分离，有窗 0.5㎡（≥ 6/20=0.3 合规），机械风量 90（≥80 合规）→ good
// 设计 2：传统，无窗，机械风量 60（<80 不达标）→ insufficient
const MOCK_BATHROOM = [
  {
    id: 'bd-1', project_id: 'proj-1', room_name: '主卫', layout_type: 'dry_wet_separation',
    room_width: 2.0, room_length: 3.0, ceiling_height: 2.6,
    dry_area: 4.0, wet_area: 2.0, floor_drain_count: 2,
    waterproof_height_mm: 1800, drain_slope_percent: 1.5, status: 'draft',
    has_natural_window: true, window_area_m2: 0.5, mechanical_vent_airflow: 90,
    created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-10T00:00:00Z',
  },
  {
    id: 'bd-2', project_id: 'proj-1', room_name: '客卫', layout_type: 'traditional',
    room_width: 1.5, room_length: 2.0, ceiling_height: 2.5,
    dry_area: null, wet_area: null, floor_drain_count: 1,
    waterproof_height_mm: 1800, drain_slope_percent: 1.5, status: 'draft',
    has_natural_window: false, window_area_m2: null, mechanical_vent_airflow: 60,
    created_at: '2026-07-02T00:00:00Z', updated_at: '2026-07-11T00:00:00Z',
  },
];

// ── 门窗规格（对齐 app/schemas/door_window_waterproof.py:DoorWindowSpecResponse）──
const MOCK_DOORWINDOW = [
  {
    id: 'dw-1', project_id: 'proj-1', room_name: '入户', location: '玄关',
    spec_type: 'entry_door', material: 'steel', width: 100, height: 210, thickness: 9,
    opening_direction: '内开', glass_type: null, brand: '步阳', model: 'BY-01',
    price: 3800, has_screen: false, has_lock: true, notes: '甲级防盗门',
    created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
  },
  {
    id: 'dw-2', project_id: 'proj-1', room_name: '客厅', location: '阳台',
    spec_type: 'sliding_door', material: 'aluminum', width: 240, height: 210, thickness: 7,
    opening_direction: '推拉', glass_type: '中空钢化', brand: '凤铝', model: 'FL-789',
    price: 5200, has_screen: true, has_lock: false, notes: null,
    created_at: '2026-07-02T00:00:00Z', updated_at: '2026-07-02T00:00:00Z',
  },
];

// ── 防水方案（对齐 app/schemas/door_window_waterproof.py:WaterproofPlanResponse）──
const MOCK_WATERPROOF = [
  {
    id: 'wp-1', project_id: 'proj-1', room_name: '主卫', room_type: 'bathroom',
    wall_height_mm: 1800, floor_area: 6.0, wall_area: 18.0,
    waterproof_material: '聚合物水泥基防水涂料', coating_layers: 3, thickness_mm: 1.5,
    closure_test_hours: 48, material_quantity: 36, unit_price: 35, total_price: 1260,
    status: 'draft', notes: '闭水试验 48 小时', created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-10T00:00:00Z',
  },
  {
    id: 'wp-2', project_id: 'proj-1', room_name: '厨房', room_type: 'kitchen',
    wall_height_mm: 300, floor_area: 12.0, wall_area: 8.0,
    waterproof_material: '聚氨酯防水涂料', coating_layers: 2, thickness_mm: 1.2,
    closure_test_hours: 24, material_quantity: 24, unit_price: 48, total_price: 1152,
    status: 'draft', notes: null, created_at: '2026-07-02T00:00:00Z', updated_at: '2026-07-11T00:00:00Z',
  },
];

// ════════════════════════════════════════════
//  FloorplansPage
// ════════════════════════════════════════════
test.describe('FloorplansPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch7'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/floorplans/project/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_FLOORPLANS) });
    });
  });

  test('户型方案列表渲染 + 截图', async ({ page }) => {
    await page.goto('./floorplans');
    await expect(page.getByTestId('wb-floorplans-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-floorplans-item--"]')).toHaveCount(2);
    await expect(page.getByText('三居室标准户型')).toBeVisible();
    await expect(page.getByText('120㎡')).toBeVisible();
    await expect(page).toHaveScreenshot('floorplans.png');
  });
});

// ════════════════════════════════════════════
//  LightingPage
// ════════════════════════════════════════════
test.describe('LightingPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch7'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/lighting/schemes/project/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_LIGHTING) });
    });
  });

  test('灯光方案列表 + 光参数展示 + 截图', async ({ page }) => {
    await page.goto('./lighting');
    await expect(page.getByTestId('wb-lighting-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-lighting-item--"]')).toHaveCount(3);
    await expect(page.getByText('客厅')).toBeVisible();
    await expect(page.getByText('4500lm')).toBeVisible();
    await expect(page).toHaveScreenshot('lighting.png');
  });

  test('scheme_type 筛选交互', async ({ page }) => {
    await page.goto('./lighting');
    await expect(page.getByTestId('wb-lighting-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-lighting-item--"]')).toHaveCount(3);
    // 筛选无主灯 → 1 条
    await page.getByTestId('wb-lighting-filter--none_main').click();
    await expect(page.locator('[data-testid^="wb-lighting-item--"]')).toHaveCount(1);
    await expect(page.getByText('主卧')).toBeVisible();
    // 切回全部
    await page.getByTestId('wb-lighting-filter--all').click();
    await expect(page.locator('[data-testid^="wb-lighting-item--"]')).toHaveCount(3);
  });
});

// ════════════════════════════════════════════
//  SoftFurnishingPage
// ════════════════════════════════════════════
test.describe('SoftFurnishingPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch7'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/soft-furnishing/schemes/project/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SOFT) });
    });
  });

  test('软装方案列表 + 预算进度 + 截图', async ({ page }) => {
    await page.goto('./soft-furnishing');
    await expect(page.getByTestId('wb-softfurnishing-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-softfurnishing-item--"]')).toHaveCount(2);
    await expect(page.getByText('客厅')).toBeVisible();
    // 预算 ¥50,000 / 已用 ¥42,000 (84%)
    await expect(page.getByText(/预算 ¥50,000/)).toBeVisible();
    await expect(page.getByText(/已用 ¥42,000 \(84%\)/)).toBeVisible();
    await expect(page).toHaveScreenshot('softfurnishing.png');
  });

  test('风格筛选交互', async ({ page }) => {
    await page.goto('./soft-furnishing');
    await expect(page.getByTestId('wb-softfurnishing-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-softfurnishing-item--"]')).toHaveCount(2);
    // 筛选北欧 → 1 条（主卧）
    await page.getByTestId('wb-softfurnishing-filter--北欧').click();
    await expect(page.locator('[data-testid^="wb-softfurnishing-item--"]')).toHaveCount(1);
    await expect(page.getByText('主卧')).toBeVisible();
  });
});

// ════════════════════════════════════════════
//  KitchenPage
// ════════════════════════════════════════════
test.describe('KitchenPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch7'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/kitchen/designs/project/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_KITCHEN) });
    });
  });

  test('厨房设计列表 + 布局/点位展示 + 截图', async ({ page }) => {
    await page.goto('./kitchen');
    await expect(page.getByTestId('wb-kitchen-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-kitchen-item--"]')).toHaveCount(2);
    // 限定内容区，避免与桌面端 sidenav 导航项“厨房”歧义
    await expect(page.getByTestId('wb-kitchen-content').getByText('厨房', { exact: true })).toBeVisible();
    // L 型布局徽章
    await expect(page.getByText('L 型', { exact: true })).toBeVisible();
    // 关键点位
    await expect(page.getByText(/进水 左下角/)).toBeVisible();
    await expect(page).toHaveScreenshot('kitchen.png');
  });

  test('布局类型筛选交互', async ({ page }) => {
    await page.goto('./kitchen');
    await expect(page.getByTestId('wb-kitchen-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-kitchen-item--"]')).toHaveCount(2);
    // 筛选岛台型 → 1 条
    await page.getByTestId('wb-kitchen-filter--island').click();
    await expect(page.locator('[data-testid^="wb-kitchen-item--"]')).toHaveCount(1);
    await expect(page.getByText('开放式西厨')).toBeVisible();
  });
});

// ════════════════════════════════════════════
//  BathroomPage
// ════════════════════════════════════════════
test.describe('BathroomPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch7'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/bathroom/designs/project/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_BATHROOM) });
    });
  });

  test('卫浴设计列表 + 通风合规校验 + 截图', async ({ page }) => {
    await page.goto('./bathroom');
    await expect(page.getByTestId('wb-bathroom-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-bathroom-item--"]')).toHaveCount(2);
    await expect(page.getByText('主卫')).toBeVisible();
    // 设计 1：通风良好（自然+机械均合规）
    await expect(page.getByTestId('wb-bathroom-vent-rating--0')).toHaveText('通风良好');
    await expect(page.getByText('自然通风：✓ 合规').first()).toBeVisible();
    // 设计 2：通风不足（无窗 + 风量 60<80）
    await expect(page.getByTestId('wb-bathroom-vent-rating--1')).toHaveText('通风不足');
    await expect(page.getByText('风量 60m³/h')).toBeVisible();
    await expect(page).toHaveScreenshot('bathroom.png');
  });

  test('布局类型筛选交互', async ({ page }) => {
    await page.goto('./bathroom');
    await expect(page.getByTestId('wb-bathroom-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-bathroom-item--"]')).toHaveCount(2);
    // 筛选干湿分离 → 1 条
    await page.getByTestId('wb-bathroom-filter--dry_wet_separation').click();
    await expect(page.locator('[data-testid^="wb-bathroom-item--"]')).toHaveCount(1);
    await expect(page.getByText('主卫')).toBeVisible();
  });
});

// ════════════════════════════════════════════
//  DoorWindowPage — 门窗规格 + 防水方案双视图
// ════════════════════════════════════════════
test.describe('DoorWindowPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch7'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/door-window-waterproof/door-windows/project/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_DOORWINDOW) });
    });
    await page.route('**/api/door-window-waterproof/waterproof/project/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_WATERPROOF) });
    });
  });

  test('门窗规格列表 + 材质/价格展示 + 截图', async ({ page }) => {
    await page.goto('./door-window');
    await expect(page.getByTestId('wb-doorwindow-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-doorwindow-item--"]')).toHaveCount(2);
    await expect(page.getByText('入户').first()).toBeVisible();
    // 钢制入户门
    await expect(page.getByText('钢制')).toBeVisible();
    await expect(page.getByText('¥3,800')).toBeVisible();
    await expect(page).toHaveScreenshot('doorwindow.png');
  });

  test('视图切换：门窗规格 → 防水方案', async ({ page }) => {
    await page.goto('./door-window');
    await expect(page.getByTestId('wb-doorwindow-content')).toBeVisible();
    // 切换到防水方案视图
    await page.getByTestId('wb-doorwindow-view--waterproof').click();
    await expect(page.getByTestId('wb-waterproof-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-waterproof-item--"]')).toHaveCount(2);
    await expect(page.getByText('聚合物水泥基防水涂料')).toBeVisible();
    // 闭水试验时长 + 总价
    await expect(page.getByText(/闭水 48h/)).toBeVisible();
    await expect(page.getByText('¥1,260')).toBeVisible();
    // 切回门窗规格
    await page.getByTestId('wb-doorwindow-view--doorwindow').click();
    await expect(page.getByTestId('wb-doorwindow-content')).toBeVisible();
  });
});

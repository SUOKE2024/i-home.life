import { test, expect } from '@playwright/test';

/**
 * 业务页视觉回归 + 交互 — 批次 6
 *
 * 验证 MaterialsPage / ChangeOrdersPage / CrewsPage / SmartHomePage / ScenePage：
 *   1. 列表渲染正确（mock API）
 *   2. 分类/状态/类型筛选 + 视图切换交互
 *   3. 匹配度/影响评估/启用状态展示
 *
 * mock 策略同 batch5.spec.ts。后端响应字段严格对齐 app/schemas/（snake_case）。
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

// ── 物料（对齐 app/schemas/material.py）──
const MOCK_CATEGORIES = [
  { id: 'cat-1', name: '瓷砖', code: 'tile', description: null, created_at: '2026-01-01T00:00:00Z' },
  { id: 'cat-2', name: '卫浴', code: 'bathroom', description: null, created_at: '2026-01-01T00:00:00Z' },
];

const MOCK_MATERIALS = [
  {
    id: 'mat-1', category_id: 'cat-1', name: '仿大理石瓷砖 800x800', sku: 'TILE-001', unit: '片',
    unit_price: 85, brand: '马可波罗', spec: '800x800mm', image_url: null, description: null,
    is_active: true, category: MOCK_CATEGORIES[0], created_at: '2026-06-01T00:00:00Z', updated_at: '2026-06-01T00:00:00Z',
  },
  {
    id: 'mat-2', category_id: 'cat-2', name: '智能马桶', sku: 'WC-001', unit: '个',
    unit_price: 3500, brand: 'TOTO', spec: 'CW988B', image_url: null, description: '自动冲水',
    is_active: true, category: MOCK_CATEGORIES[1], created_at: '2026-06-02T00:00:00Z', updated_at: '2026-06-02T00:00:00Z',
  },
  {
    id: 'mat-3', category_id: 'cat-1', name: '木纹砖 200x1000', sku: 'TILE-002', unit: '片',
    unit_price: 45, brand: '东鹏', spec: '200x1000mm', image_url: null, description: null,
    is_active: false, category: MOCK_CATEGORIES[0], created_at: '2026-06-03T00:00:00Z', updated_at: '2026-06-03T00:00:00Z',
  },
];

// ── 变更单（对齐 app/schemas/change_order.py）──
const MOCK_CHANGE_ORDERS = [
  {
    id: 'co-1', project_id: 'proj-1', title: '增加卫生间地暖',
    description: '业主要求在主卫增加地暖系统', change_type: 'owner_request',
    feasibility: 'feasible', feasibility_note: '需调整地面高度',
    cost_impact: 8000, schedule_impact_days: 3, design_impact: null,
    status: 'approved', submitted_by: 'user-1', reviewed_by: 'designer-1', approved_by: 'manager-1',
    submitted_at: '2026-07-10T10:00:00Z', reviewed_at: '2026-07-11T10:00:00Z', approved_at: '2026-07-12T10:00:00Z',
    items: [
      { id: 'ci-1', change_order_id: 'co-1', name: '地暖管材', action: 'add', target_type: 'room', target_id: null, before_data: null, after_data: null, quantity: 15, unit_price: 120, amount: 1800 },
      { id: 'ci-2', change_order_id: 'co-1', name: '分水器', action: 'add', target_type: 'room', target_id: null, before_data: null, after_data: null, quantity: 1, unit_price: 6200, amount: 6200 },
    ],
    created_at: '2026-07-10T10:00:00Z', updated_at: '2026-07-12T10:00:00Z',
  },
  {
    id: 'co-2', project_id: 'proj-1', title: '修改厨房布局',
    description: '将开放式厨房改为半开放式', change_type: 'design_adjust',
    feasibility: 'partial', feasibility_note: '需增加隔断',
    cost_impact: 5000, schedule_impact_days: 2, design_impact: '需重出效果图',
    status: 'reviewing', submitted_by: 'user-1', reviewed_by: null, approved_by: null,
    submitted_at: '2026-07-15T10:00:00Z', reviewed_at: null, approved_at: null,
    items: [],
    created_at: '2026-07-15T10:00:00Z', updated_at: '2026-07-15T10:00:00Z',
  },
];

// ── 工程队（对齐 app/schemas/construction_crew.py）──
const MOCK_CREWS = [
  {
    id: 'crew-1', name: '张工水电队', leader: '张师傅', phone: '13800001111',
    city: '上海', district: '浦东', qualification: 'A',
    specialties: ['水电', '防水'], rating: 4.8, completed_projects: 120,
    avg_duration: 45, daily_rate: 1200, status: 'available',
    introduction: '专注水电 15 年', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
  },
  {
    id: 'crew-2', name: '李工泥瓦队', leader: '李师傅', phone: '13800002222',
    city: '上海', district: '徐汇', qualification: 'B',
    specialties: ['泥瓦', '贴砖'], rating: 4.5, completed_projects: 80,
    avg_duration: 60, daily_rate: 900, status: 'busy',
    introduction: null, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
  },
];

const MOCK_CREW_MATCHES = [
  {
    id: 'cm-1', project_id: 'proj-1', crew_id: 'crew-1', match_score: 92,
    score_breakdown: {}, recommendation: '评分高，专长匹配，推荐',
    status: 'matched', crew: MOCK_CREWS[0],
    created_at: '2026-07-20T10:00:00Z', updated_at: '2026-07-20T10:00:00Z',
  },
  {
    id: 'cm-2', project_id: 'proj-1', crew_id: 'crew-2', match_score: 65,
    score_breakdown: {}, recommendation: '价格较低但工期偏长',
    status: 'matched', crew: MOCK_CREWS[1],
    created_at: '2026-07-20T10:00:00Z', updated_at: '2026-07-20T10:00:00Z',
  },
];

// ── 智能家居方案（对齐 app/schemas/smart_home.py）──
const MOCK_SMART_SCHEMES = [
  {
    id: 'sh-1', project_id: 'proj-1', room_name: '客厅', room_type: 'living_room',
    protocol: 'zigbee', hub_brand: 'Aqara', device_count: 8, total_price: 12500,
    status: 'planned', notes: '含灯光、窗帘、空调控制',
    created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-10T00:00:00Z',
  },
  {
    id: 'sh-2', project_id: 'proj-1', room_name: '主卧', room_type: 'bedroom',
    protocol: 'matter', hub_brand: 'Apple', device_count: 4, total_price: 6800,
    status: 'completed', notes: null,
    created_at: '2026-07-05T00:00:00Z', updated_at: '2026-07-20T00:00:00Z',
  },
];

// ── 场景自动化（对齐 app/schemas/scene_automation.py）──
const MOCK_SCENES = [
  {
    id: 'sc-1', project_id: 'proj-1', scheme_id: 'sh-1', scene_name: '回家模式',
    scene_type: 'geo', trigger_condition: '距离家 500m',
    actions: [{ device_name: '客厅灯', action: 'on' }, { device_name: '空调', action: 'on' }],
    enabled: true, priority: 1,
    created_at: '2026-07-15T00:00:00Z', updated_at: '2026-07-15T00:00:00Z',
  },
  {
    id: 'sc-2', project_id: 'proj-1', scheme_id: 'sh-1', scene_name: '睡眠模式',
    scene_type: 'scheduled', trigger_condition: '每天 23:00',
    actions: [{ device_name: '全屋灯', action: 'off' }],
    enabled: false, priority: 2,
    created_at: '2026-07-16T00:00:00Z', updated_at: '2026-07-16T00:00:00Z',
  },
];

// ════════════════════════════════════════════
//  MaterialsPage
// ════════════════════════════════════════════
test.describe('MaterialsPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch6'));
    await page.route('**/api/materials/categories', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CATEGORIES) });
    });
    await page.route('**/api/materials', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_MATERIALS) });
    });
  });

  test('物料列表渲染 + 分类筛选 + 截图', async ({ page }) => {
    await page.goto('./materials');
    await expect(page.getByTestId('wb-materials-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-materials-item--"]')).toHaveCount(3);
    await expect(page.getByText('仿大理石瓷砖 800x800')).toBeVisible();
    await expect(page.getByText('¥85')).toBeVisible();
    await expect(page).toHaveScreenshot('materials.png');
  });

  test('分类筛选交互', async ({ page }) => {
    await page.goto('./materials');
    await expect(page.getByTestId('wb-materials-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-materials-item--"]')).toHaveCount(3);
    // 筛选瓷砖分类 → 2 条
    await page.getByTestId('wb-materials-filter--tile').click();
    await expect(page.locator('[data-testid^="wb-materials-item--"]')).toHaveCount(2);
    // 切回全部
    await page.getByTestId('wb-materials-filter--all').click();
    await expect(page.locator('[data-testid^="wb-materials-item--"]')).toHaveCount(3);
  });
});

// ════════════════════════════════════════════
//  ChangeOrdersPage
// ════════════════════════════════════════════
test.describe('ChangeOrdersPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch6'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/change-orders/project/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CHANGE_ORDERS) });
    });
  });

  test('变更单列表 + 影响评估 + 截图', async ({ page }) => {
    await page.goto('./change-orders');
    await expect(page.getByTestId('wb-changeorders-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-changeorders-item--"]')).toHaveCount(2);
    await expect(page.getByText('增加卫生间地暖')).toBeVisible();
    // 费用影响
    await expect(page.getByText(/费用影响 ¥8,000/)).toBeVisible();
    await expect(page).toHaveScreenshot('changeorders.png');
  });

  test('状态筛选 + 变更项明细展示', async ({ page }) => {
    await page.goto('./change-orders');
    await expect(page.getByTestId('wb-changeorders-content')).toBeVisible();
    // 默认全部 2 条
    await expect(page.locator('[data-testid^="wb-changeorders-item--"]')).toHaveCount(2);
    // 第一单有 2 个变更项
    await expect(page.getByText('[新增] 地暖管材')).toBeVisible();
    // 筛选已批准 → 1 条
    await page.getByTestId('wb-changeorders-filter--approved').click();
    await expect(page.locator('[data-testid^="wb-changeorders-item--"]')).toHaveCount(1);
  });
});

// ════════════════════════════════════════════
//  CrewsPage
// ════════════════════════════════════════════
test.describe('CrewsPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch6'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/crews', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CREWS) });
    });
    await page.route('**/api/crews/matches/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CREW_MATCHES) });
    });
  });

  test('工程队列表 + 评分展示 + 截图', async ({ page }) => {
    await page.goto('./crews');
    await expect(page.getByTestId('wb-crews-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-crews-item--"]')).toHaveCount(2);
    await expect(page.getByText('张工水电队')).toBeVisible();
    await expect(page.getByText('⭐ 4.8')).toBeVisible();
    await expect(page).toHaveScreenshot('crews.png');
  });

  test('视图切换：列表 → 项目匹配', async ({ page }) => {
    await page.goto('./crews');
    await expect(page.getByTestId('wb-crews-content')).toBeVisible();
    // 切换到匹配视图
    await page.getByTestId('wb-crews-view--matches').click();
    await expect(page.getByTestId('wb-crews-matches-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-crews-match--"]')).toHaveCount(2);
    // 匹配度展示
    await expect(page.getByTestId('wb-crews-match-score--0')).toContainText('92');
    await expect(page.getByTestId('wb-crews-match-score--1')).toContainText('65');
  });
});

// ════════════════════════════════════════════
//  SmartHomePage
// ════════════════════════════════════════════
test.describe('SmartHomePage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch6'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/smart-home/schemes/project/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SMART_SCHEMES) });
    });
  });

  test('方案列表 + 协议/价格展示 + 截图', async ({ page }) => {
    await page.goto('./smart-home');
    await expect(page.getByTestId('wb-smarthome-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-smarthome-item--"]')).toHaveCount(2);
    await expect(page.getByText('客厅')).toBeVisible();
    await expect(page.getByText('Zigbee')).toBeVisible();
    await expect(page.getByText('¥12,500')).toBeVisible();
    await expect(page).toHaveScreenshot('smarthome.png');
  });

  test('状态筛选交互', async ({ page }) => {
    await page.goto('./smart-home');
    await expect(page.getByTestId('wb-smarthome-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-smarthome-item--"]')).toHaveCount(2);
    // 筛选已完成 → 1 条
    await page.getByTestId('wb-smarthome-filter--completed').click();
    await expect(page.locator('[data-testid^="wb-smarthome-item--"]')).toHaveCount(1);
    await expect(page.getByText('主卧')).toBeVisible();
  });
});

// ════════════════════════════════════════════
//  ScenePage
// ════════════════════════════════════════════
test.describe('ScenePage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch6'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/scene-automation/scenes/project/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SCENES) });
    });
  });

  test('场景列表 + 启用状态 + 截图', async ({ page }) => {
    await page.goto('./scene');
    await expect(page.getByTestId('wb-scene-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-scene-item--"]')).toHaveCount(2);
    await expect(page.getByText('回家模式')).toBeVisible();
    // 第一场景已启用
    await expect(page.getByTestId('wb-scene-enabled--0')).toHaveText(/已启用/);
    // 第二场景已禁用
    await expect(page.getByTestId('wb-scene-enabled--1')).toHaveText(/已禁用/);
    await expect(page).toHaveScreenshot('scene.png');
  });

  test('类型筛选交互', async ({ page }) => {
    await page.goto('./scene');
    await expect(page.getByTestId('wb-scene-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-scene-item--"]')).toHaveCount(2);
    // 筛选地理触发 → 1 条
    await page.getByTestId('wb-scene-filter--geo').click();
    await expect(page.locator('[data-testid^="wb-scene-item--"]')).toHaveCount(1);
    await expect(page.getByText('回家模式')).toBeVisible();
  });
});

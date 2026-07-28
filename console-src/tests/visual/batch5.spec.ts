import { test, expect } from '@playwright/test';

/**
 * 业务页视觉回归 + 交互 — 批次 5
 *
 * 验证 ConstructionPage / ProcurementPage / SettlementPage / TasksPage：
 *   1. 列表/明细渲染正确（mock API）
 *   2. 状态筛选 / 范围切换交互
 *   3. 异常标记 / 物流状态 / 优先级指示器展示
 *
 * mock 策略同 pages.spec.ts：localStorage 预设 paseto_token，拦截 /api/* 返回固定数据。
 * 后端响应字段严格对齐 app/schemas/（snake_case）。
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

// ── 施工任务（对齐 app/schemas/construction.py:TaskResponse）──
const MOCK_CONSTRUCTION_TASKS = [
  {
    id: 'ct-1',
    project_id: 'proj-1',
    name: '水电开槽布管',
    phase: 'water_electricity',
    assigned_to: '王师傅',
    status: 'in_progress',
    priority: 8,
    start_date: '2026-07-01T08:00:00Z',
    end_date: '2026-07-10T18:00:00Z',
    description: '全屋水电管线开槽与布管',
    created_at: '2026-06-28T10:00:00Z',
    updated_at: '2026-07-05T10:00:00Z',
  },
  {
    id: 'ct-2',
    project_id: 'proj-1',
    name: '卫生间防水',
    phase: 'waterproof',
    assigned_to: '李师傅',
    status: 'pending',
    priority: 5,
    start_date: null,
    end_date: null,
    description: null,
    created_at: '2026-07-02T10:00:00Z',
    updated_at: '2026-07-02T10:00:00Z',
  },
  {
    id: 'ct-3',
    project_id: 'proj-1',
    name: '客厅贴砖',
    phase: 'masonry',
    assigned_to: '赵师傅',
    status: 'completed',
    priority: 3,
    start_date: '2026-06-20T08:00:00Z',
    end_date: '2026-06-25T18:00:00Z',
    description: '客厅地砖铺贴',
    created_at: '2026-06-18T10:00:00Z',
    updated_at: '2026-06-26T10:00:00Z',
  },
];

// ── 采购订单（对齐 app/schemas/procurement.py:OrderResponse）──
const MOCK_ORDERS = [
  {
    id: 'order-1-abc12345',
    project_id: 'proj-1',
    supplier_id: 'sup-1',
    total_amount: 38500,
    status: 'shipped',
    expected_delivery: '2026-07-15T00:00:00Z',
    note: '主材批次 1',
    lines: [
      { id: 'ol-1', material_id: 'mat-001', quantity: 50, unit_price: 320, total_price: 16000, note: null },
      { id: 'ol-2', material_id: 'mat-002', quantity: 15, unit_price: 1500, total_price: 22500, note: '含运费' },
    ],
    delivery_status: 'in_transit',
    tracking_number: 'SF1234567890',
    carrier: '顺丰速运',
    estimated_delivery_date: '2026-07-15T18:00:00Z',
    actual_delivery_date: null,
    delivery_address: '上海市浦东新区世纪大道 100 号',
    assembly_required: true,
    assembly_difficulty: 'medium',
    delivery_notes: null,
    created_at: '2026-07-05T10:00:00Z',
    updated_at: '2026-07-08T10:00:00Z',
  },
  {
    id: 'order-2-def67890',
    project_id: 'proj-1',
    supplier_id: 'sup-2',
    total_amount: 8800,
    status: 'draft',
    expected_delivery: null,
    note: null,
    lines: [
      { id: 'ol-3', material_id: 'mat-003', quantity: 10, unit_price: 880, total_price: 8800, note: null },
    ],
    delivery_status: null,
    tracking_number: null,
    carrier: null,
    estimated_delivery_date: null,
    actual_delivery_date: null,
    delivery_address: null,
    assembly_required: false,
    assembly_difficulty: null,
    delivery_notes: null,
    created_at: '2026-07-09T10:00:00Z',
    updated_at: '2026-07-09T10:00:00Z',
  },
];

// ── 结算单（对齐 app/schemas/settlement.py:SettlementResponse）──
const MOCK_SETTLEMENT = {
  id: 'settle-1',
  project_id: 'proj-1',
  milestone: '水电阶段结算',
  contract_amount: 80000,
  actual_amount: 92000,
  payable_amount: 88000,
  status: 'confirmed',
  anomaly_count: 2,
  critical_anomaly_count: 1,
  suggested_deduction: 4000,
  review_required: true,
  review_reason: '存在严重异常项需人工确认',
  lines: [
    {
      id: 'sl-1',
      category: '水电工程',
      name: '强弱电改造',
      contract_amount: 30000,
      change_amount: 0,
      actual_amount: 30000,
      status: 'confirmed',
      note: null,
      is_anomaly: false,
      anomaly_type: null,
      anomaly_severity: null,
      anomaly_detail: null,
    },
    {
      id: 'sl-2',
      category: '水电工程',
      name: '给排水改造',
      contract_amount: 20000,
      change_amount: 8000,
      actual_amount: 28000,
      status: 'pending',
      note: '增加卫生间数量',
      is_anomaly: true,
      anomaly_type: 'over_budget',
      anomaly_severity: 'medium',
      anomaly_detail: '实际超合同 40%',
    },
    {
      id: 'sl-3',
      category: '防水工程',
      name: '卫生间防水',
      contract_amount: 30000,
      change_amount: 4000,
      actual_amount: 34000,
      status: 'pending',
      note: null,
      is_anomaly: true,
      anomaly_type: 'unauthorized_change',
      anomaly_severity: 'critical',
      anomaly_detail: '未经确认的变更',
    },
  ],
  settled_at: null,
  created_at: '2026-07-10T10:00:00Z',
  updated_at: '2026-07-10T10:00:00Z',
};

// ── 任务协调（对齐 app/schemas/task.py:TaskListResponse { tasks, total }）──
const MOCK_PROJECT_TASKS = {
  tasks: [
    {
      id: 'task-1',
      project_id: 'proj-1',
      task_type: 'quality_check',
      title: '水电验收',
      description: '完成水电管线验收并出具报告',
      assigned_agent: 'quality',
      assigned_user_id: null,
      assigned_user_name: null,
      priority: 9,
      status: 'in_progress',
      claimable: false,
      claim_deadline: '2026-07-30T18:00:00Z',
      result: null,
      created_by: 'master',
      created_at: '2026-07-20T10:00:00Z',
      started_at: '2026-07-21T10:00:00Z',
      completed_at: null,
    },
    {
      id: 'task-2',
      project_id: 'proj-1',
      task_type: 'procurement',
      title: '主材下单',
      description: '瓷砖与卫浴主材采购下单',
      assigned_agent: 'procurement',
      assigned_user_id: 'user-1',
      assigned_user_name: '张业主',
      priority: 5,
      status: 'pending',
      claimable: true,
      claim_deadline: '2026-08-05T18:00:00Z',
      result: null,
      created_by: 'master',
      created_at: '2026-07-22T10:00:00Z',
      started_at: null,
      completed_at: null,
    },
    {
      id: 'task-3',
      project_id: 'proj-1',
      task_type: 'design',
      title: '确认效果图',
      description: null,
      assigned_agent: 'design',
      assigned_user_id: null,
      assigned_user_name: null,
      priority: 2,
      status: 'completed',
      claimable: false,
      claim_deadline: null,
      result: { approved: true },
      created_by: 'master',
      created_at: '2026-07-10T10:00:00Z',
      started_at: '2026-07-10T10:00:00Z',
      completed_at: '2026-07-12T10:00:00Z',
    },
  ],
  total: 3,
};

const MOCK_MY_TASKS = {
  tasks: [
    {
      id: 'task-mine-1',
      project_id: 'proj-1',
      task_type: 'procurement',
      title: '主材下单（我的）',
      description: '待你确认的采购任务',
      assigned_agent: 'procurement',
      assigned_user_id: 'user-1',
      assigned_user_name: '张业主',
      priority: 5,
      status: 'pending',
      claimable: false,
      claim_deadline: '2026-08-05T18:00:00Z',
      result: null,
      created_by: 'master',
      created_at: '2026-07-22T10:00:00Z',
      started_at: null,
      completed_at: null,
    },
  ],
  total: 1,
};

// ════════════════════════════════════════════
//  ConstructionPage
// ════════════════════════════════════════════
test.describe('ConstructionPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch5'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/construction/tasks/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CONSTRUCTION_TASKS) });
    });
  });

  test('施工任务列表渲染 + 状态徽章 + 截图', async ({ page }) => {
    await page.goto('./construction');
    await expect(page.getByTestId('wb-construction-content')).toBeVisible();
    // 3 个任务
    await expect(page.locator('[data-testid^="wb-construction-task--"]')).toHaveCount(3);
    // 进行中状态徽章
    await expect(page.getByTestId('wb-construction-task-status--0')).toHaveText(/进行中/);
    await expect(page.getByText('水电开槽布管')).toBeVisible();
    await expect(page.getByText('王师傅')).toBeVisible();
    await expect(page).toHaveScreenshot('construction.png');
  });

  test('状态筛选交互', async ({ page }) => {
    await page.goto('./construction');
    await expect(page.getByTestId('wb-construction-content')).toBeVisible();
    // 默认全部 3 条
    await expect(page.locator('[data-testid^="wb-construction-task--"]')).toHaveCount(3);
    // 筛选已完成 → 1 条
    await page.getByTestId('wb-construction-filter--completed').click();
    await expect(page.locator('[data-testid^="wb-construction-task--"]')).toHaveCount(1);
    await expect(page.getByText('客厅贴砖')).toBeVisible();
    // 切回全部
    await page.getByTestId('wb-construction-filter--all').click();
    await expect(page.locator('[data-testid^="wb-construction-task--"]')).toHaveCount(3);
  });
});

// ════════════════════════════════════════════
//  ProcurementPage
// ════════════════════════════════════════════
test.describe('ProcurementPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch5'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/procurement/orders/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_ORDERS) });
    });
  });

  test('采购订单列表 + 物流状态 + 截图', async ({ page }) => {
    await page.goto('./procurement');
    await expect(page.getByTestId('wb-procurement-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-procurement-order--"]')).toHaveCount(2);
    // 第一单物流区块可见
    await expect(page.getByTestId('wb-procurement-order-logistics--0')).toBeVisible();
    await expect(page.getByText('顺丰速运')).toBeVisible();
    await expect(page.getByText('SF1234567890')).toBeVisible();
    // 需安装标记
    await expect(page.getByText(/需安装/)).toBeVisible();
    await expect(page).toHaveScreenshot('procurement.png');
  });

  test('订单状态徽章展示', async ({ page }) => {
    await page.goto('./procurement');
    await expect(page.getByTestId('wb-procurement-content')).toBeVisible();
    // 第一单 shipped → 已发货
    await expect(page.getByTestId('wb-procurement-order-status--0')).toHaveText(/已发货/);
    // 第二单 draft → 草稿
    await expect(page.getByTestId('wb-procurement-order-status--1')).toHaveText(/草稿/);
  });
});

// ════════════════════════════════════════════
//  SettlementPage
// ════════════════════════════════════════════
test.describe('SettlementPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch5'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/settlements/project/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SETTLEMENT) });
    });
  });

  test('结算概览 + 异常预警 + 分项明细 + 截图', async ({ page }) => {
    await page.goto('./settlement');
    await expect(page.getByTestId('wb-settlement-content')).toBeVisible();
    // 概览金额
    await expect(page.getByText('¥80,000')).toBeVisible(); // 合同
    await expect(page.getByText('¥92,000')).toBeVisible(); // 实际
    await expect(page.getByText('¥88,000')).toBeVisible(); // 应付
    // 异常预警
    await expect(page.getByTestId('wb-settlement-anomaly-alert')).toBeVisible();
    await expect(page.getByTestId('wb-settlement-anomaly-alert')).toContainText('2 项异常');
    // 复核提示
    await expect(page.getByTestId('wb-settlement-review-alert')).toBeVisible();
    // 3 个分项
    await expect(page.locator('[data-testid^="wb-settlement-line--"]')).toHaveCount(3);
    await expect(page).toHaveScreenshot('settlement.png');
  });

  test('异常行高亮 + 严重度展示', async ({ page }) => {
    await page.goto('./settlement');
    await expect(page.getByTestId('wb-settlement-content')).toBeVisible();
    // 第二、三行为异常行（is_anomaly=true）
    const anomalyLine1 = page.getByTestId('wb-settlement-line--1');
    await expect(anomalyLine1).toHaveClass(/wb-sline--anomaly/);
    await expect(anomalyLine1).toContainText('异常');
    await expect(anomalyLine1).toContainText('中');
    // 严重异常
    const anomalyLine2 = page.getByTestId('wb-settlement-line--2');
    await expect(anomalyLine2).toContainText('严重');
  });
});

// ════════════════════════════════════════════
//  TasksPage
// ════════════════════════════════════════════
test.describe('TasksPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch5'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/tasks/project/*', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECT_TASKS) });
    });
    await page.route('**/api/tasks/mine', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_MY_TASKS) });
    });
  });

  test('项目任务列表 + 优先级色条 + 截图', async ({ page }) => {
    await page.goto('./tasks');
    await expect(page.getByTestId('wb-tasks-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-tasks-item--"]')).toHaveCount(3);
    // 高优先级任务（priority=9）
    await expect(page.getByText('水电验收')).toBeVisible();
    // 状态徽章
    await expect(page.getByTestId('wb-tasks-item-status--0')).toHaveText(/进行中/);
    await expect(page).toHaveScreenshot('tasks.png');
  });

  test('范围切换：项目任务 → 我的任务', async ({ page }) => {
    await page.goto('./tasks');
    await expect(page.getByTestId('wb-tasks-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-tasks-item--"]')).toHaveCount(3);
    // 切换到我的任务
    await page.getByTestId('wb-tasks-scope--mine').click();
    await expect(page.locator('[data-testid^="wb-tasks-item--"]')).toHaveCount(1);
    await expect(page.getByText('主材下单（我的）')).toBeVisible();
  });

  test('优先级筛选交互', async ({ page }) => {
    await page.goto('./tasks');
    await expect(page.getByTestId('wb-tasks-content')).toBeVisible();
    await expect(page.locator('[data-testid^="wb-tasks-item--"]')).toHaveCount(3);
    // 筛选高优先级 → 1 条（priority=9）
    await page.getByTestId('wb-tasks-priority-filter--high').click();
    await expect(page.locator('[data-testid^="wb-tasks-item--"]')).toHaveCount(1);
    await expect(page.getByText('水电验收')).toBeVisible();
    // 筛选低优先级 → 1 条（priority=2）
    await page.getByTestId('wb-tasks-priority-filter--low').click();
    await expect(page.locator('[data-testid^="wb-tasks-item--"]')).toHaveCount(1);
    await expect(page.getByText('确认效果图')).toBeVisible();
  });
});

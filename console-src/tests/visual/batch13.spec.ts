import { test, expect } from '@playwright/test';

/**
 * 业务页视觉回归 + 交互 — 批次 13
 *
 * 验证 DesignPage（设计：AI 方案生成 + 动线分析）：
 *   1. 渲染 + tab 切换（设计方案 / 动线分析）
 *   2. 设计方案生成：填表单 → mock POST /api/agents/design → 4 字段卡片 + full_reply 展开
 *   3. 设计方案生成：空需求校验 + 错误降级
 *   4. 动线分析：加载预设 → mock POST /api/agents/design/circulation → 综合评分 + 三动线卡 + 建议
 *   5. 动线分析：空房间校验 + 错误降级
 *
 * mock 策略同 batch12：localStorage 预设 paseto_token，page.route 拦截 /api/*。
 * 响应字段严格对齐 app/api/agents.py:DesignPlanResponse + app/agents/designer.py:analyze_circulation 返回（snake_case）。
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

const MOCK_DESIGN_PLAN = {
  agent_type: 'designer',
  space_planning: '已为您生成 3 套 90㎡ 户型设计方案，推荐方案 B，南北通透，采光更佳。',
  style_suggestion: '方案 B：三室两厅',
  circulation_analysis: '客厅/餐厅：建议 750×1500 大板砖 | 卧室：推荐实木多层地板',
  material_plan:
    '客厅/餐厅：建议750×1500大板砖，耐磨美观\n卧室：推荐实木多层地板，温暖舒适\n厨房/卫生间：防滑地砖 + 防水涂料\n墙面：净味乳胶漆 + 局部艺术漆',
  full_reply:
    '{"plans":[{"name":"方案A","rooms":[],"total_area":88.0},{"name":"方案B","rooms":[],"total_area":90.5}],"recommendation":"方案B","materials":["客厅/餐厅：建议750×1500大板砖","卧室：推荐实木多层地板"],"reply":"已为您生成 3 套方案"}',
};

const MOCK_CIRCULATION_RESULT = {
  rooms_count: 8,
  circulations: [
    {
      type: 'visitor',
      name: '访客动线',
      description: '玄关 → 客厅 → 餐厅 → 客卫',
      path: [
        { name: '玄关', type: 'entryway' },
        { name: '客厅', type: 'living_room' },
        { name: '餐厅', type: 'dining_room' },
      ],
      segments: [
        { from: '玄关', to: '客厅', distance: 3.5 },
        { from: '客厅', to: '餐厅', distance: 2.8 },
      ],
      total_length: 6.3,
      crossed_rooms: [],
      missing_types: ['bathroom'],
      score: 85,
      issues: [
        { type: 'missing_room', severity: 'info', detail: '动线缺少房间类型：bathroom' },
      ],
      suggestions: ['访客动线布局合理，无需调整'],
    },
    {
      type: 'housework',
      name: '家务动线',
      description: '厨房 → 餐厅，阳台 → 晾晒，卫生间 → 洗衣',
      path: [
        { name: '厨房', type: 'kitchen' },
        { name: '餐厅', type: 'dining_room' },
        { name: '阳台', type: 'balcony' },
      ],
      segments: [
        { from: '厨房', to: '餐厅', distance: 2.1 },
        { from: '餐厅', to: '阳台', distance: 7.1 },
      ],
      total_length: 9.2,
      crossed_rooms: ['客厅'],
      missing_types: ['bathroom'],
      score: 55,
      issues: [
        { type: 'too_long', severity: 'warning', detail: '动线总长 9.2m 超过建议值 8.0m' },
        { type: 'cross_room', severity: 'critical', detail: '动线穿越房间：客厅' },
      ],
      suggestions: ['缩短家务动线路径，可调整房间相邻关系', '避免家务动线穿越 客厅'],
    },
    {
      type: 'living',
      name: '居住动线',
      description: '卧室 → 卫生间 → 衣帽间，私密且短捷',
      path: [
        { name: '主卧', type: 'bedroom' },
        { name: '主卫', type: 'bathroom' },
      ],
      segments: [{ from: '主卧', to: '主卫', distance: 2.5 }],
      total_length: 2.5,
      crossed_rooms: [],
      missing_types: ['cloakroom'],
      score: 90,
      issues: [
        { type: 'missing_room', severity: 'info', detail: '动线缺少房间类型：cloakroom' },
      ],
      suggestions: ['居住动线布局合理，无需调整'],
    },
  ],
  overall_score: 76.7,
  rating: 'good',
  rating_text: '良好',
  total_issues: 4,
  critical_count: 1,
  warning_count: 1,
  issues: [
    { type: 'missing_room', severity: 'info', detail: '动线缺少房间类型：bathroom' },
    { type: 'too_long', severity: 'warning', detail: '动线总长 9.2m 超过建议值 8.0m' },
    { type: 'cross_room', severity: 'critical', detail: '动线穿越房间：客厅' },
    { type: 'missing_room', severity: 'info', detail: '动线缺少房间类型：cloakroom' },
  ],
  suggestions: [
    '缩短家务动线路径，可调整房间相邻关系',
    '避免家务动线穿越 客厅',
    '访客动线布局合理，无需调整',
    '居住动线布局合理，无需调整',
  ],
  reply: '动线分析：8 个房间，综合评分 76.7（良好），共 4 个问题（1 严重 / 1 警告）。',
};

// ════════════════════════════════════════════
// DesignPage 设计页
// ════════════════════════════════════════════

test.describe('DesignPage 设计页', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'mock-token-design');
    });
    await page.route('**/api/projects**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/config/feature-flags', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ console_v2_enabled: true }) });
    });
  });

  test('渲染设计页 + 默认设计方案视图', async ({ page }) => {
    await page.goto('./design');
    await expect(page.getByTestId('wb-design-page')).toBeVisible();
    await expect(page.getByText('📐 设计')).toBeVisible();
    // 默认设计方案视图
    await expect(page.getByTestId('wb-design-plan-content')).toBeVisible();
    await expect(page.getByTestId('wb-design-message')).toBeVisible();
    await expect(page.getByTestId('wb-design-generate-btn')).toBeVisible();
  });

  test('tab 切换到动线分析视图', async ({ page }) => {
    await page.goto('./design');
    await expect(page.getByTestId('wb-design-view--circulation')).toBeVisible();
    await page.getByTestId('wb-design-view--circulation').click();
    await expect(page.getByTestId('wb-design-circ-content')).toBeVisible();
    await expect(page.getByTestId('wb-design-rooms')).toBeVisible();
    await expect(page.getByTestId('wb-design-analyze-btn')).toBeVisible();
    // 默认有 1 个房间行
    await expect(page.getByTestId('wb-design-room--0')).toBeVisible();
  });

  test('设计方案生成：填表单 → 4 字段卡片 + full_reply 展开', async ({ page }) => {
    await page.route('**/api/agents/design', async (route) => {
      expect(route.request().method()).toBe('POST');
      const body = JSON.parse(route.request().postData() ?? '{}');
      expect(body.message).toContain('90㎡');
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_DESIGN_PLAN) });
    });
    await page.goto('./design');
    await page.getByTestId('wb-design-message').fill('90㎡ 两居室，南北通透，现代简约风');
    await page.getByTestId('wb-design-roominfo').fill('建筑面积 90㎡，层高 2.8m');
    await page.getByTestId('wb-design-generate-btn').click();
    // 4 字段卡片
    await expect(page.getByTestId('wb-design-plan-result')).toBeVisible();
    await expect(page.getByTestId('wb-design-card--space')).toContainText('南北通透');
    await expect(page.getByTestId('wb-design-card--style')).toContainText('方案 B');
    await expect(page.getByTestId('wb-design-card--circulation')).toContainText('大板砖');
    await expect(page.getByTestId('wb-design-card--material')).toContainText('实木多层地板');
    // full_reply 默认隐藏，点击展开
    await expect(page.getByTestId('wb-design-full-reply')).not.toBeVisible();
    await page.getByTestId('wb-design-toggle-full').click();
    await expect(page.getByTestId('wb-design-full-reply')).toBeVisible();
    await expect(page.getByTestId('wb-design-full-reply')).toContainText('plans');
  });

  test('设计方案生成：空需求校验拦截', async ({ page }) => {
    await page.goto('./design');
    await page.getByTestId('wb-design-generate-btn').click();
    await expect(page.getByTestId('wb-design-plan-error')).toBeVisible();
    await expect(page.getByTestId('wb-design-plan-error')).toContainText('请输入设计需求');
  });

  test('设计方案生成：错误降级', async ({ page }) => {
    await page.route('**/api/agents/design', async (route) => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: '设计 Agent 不可用' }) });
    });
    await page.goto('./design');
    await page.getByTestId('wb-design-message').fill('生成方案');
    await page.getByTestId('wb-design-generate-btn').click();
    await expect(page.getByTestId('wb-design-plan-error')).toBeVisible();
    await expect(page.getByTestId('wb-design-plan-error')).toContainText('设计 Agent 不可用');
  });

  test('动线分析：加载预设 → 综合评分 + 三动线卡 + 建议', async ({ page }) => {
    await page.route('**/api/agents/design/circulation', async (route) => {
      expect(route.request().method()).toBe('POST');
      const body = JSON.parse(route.request().postData() ?? '{}');
      expect(body.rooms.length).toBeGreaterThan(0);
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CIRCULATION_RESULT) });
    });
    await page.goto('./design');
    await page.getByTestId('wb-design-view--circulation').click();
    // 加载预设（8 房间）
    await page.getByTestId('wb-design-preset').click();
    await expect(page.getByTestId('wb-design-room--7')).toBeVisible();
    // 分析
    await page.getByTestId('wb-design-analyze-btn').click();
    // 综合评分卡
    await expect(page.getByTestId('wb-design-score')).toBeVisible();
    await expect(page.getByTestId('wb-design-score')).toContainText('76.7');
    await expect(page.getByTestId('wb-design-score')).toContainText('良好');
    await expect(page.getByTestId('wb-design-score')).toContainText('8 房间');
    await expect(page.getByTestId('wb-design-score')).toContainText('1 严重');
    // 三动线卡
    await expect(page.getByTestId('wb-design-circ-item--0')).toContainText('访客动线');
    await expect(page.getByTestId('wb-design-circ-item--0')).toContainText('85');
    await expect(page.getByTestId('wb-design-circ-item--1')).toContainText('家务动线');
    await expect(page.getByTestId('wb-design-circ-item--1')).toContainText('55');
    await expect(page.getByTestId('wb-design-circ-item--1')).toContainText('穿越房间：客厅');
    await expect(page.getByTestId('wb-design-circ-item--2')).toContainText('居住动线');
    // 全局建议
    await expect(page.getByTestId('wb-design-suggestions')).toBeVisible();
    await expect(page.getByTestId('wb-design-suggestions')).toContainText('缩短家务动线');
  });

  test('动线分析：清空房间名 → 空校验拦截', async ({ page }) => {
    await page.goto('./design');
    await page.getByTestId('wb-design-view--circulation').click();
    // 默认 1 行，名称为空 → 清空后分析应被拦截
    await page.getByTestId('wb-design-analyze-btn').click();
    await expect(page.getByTestId('wb-design-circ-error')).toBeVisible();
    await expect(page.getByTestId('wb-design-circ-error')).toContainText('至少添加一个房间');
  });

  test('动线分析：错误降级', async ({ page }) => {
    await page.route('**/api/agents/design/circulation', async (route) => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: '动线分析服务异常' }) });
    });
    await page.goto('./design');
    await page.getByTestId('wb-design-view--circulation').click();
    await page.getByTestId('wb-design-preset').click();
    await page.getByTestId('wb-design-analyze-btn').click();
    await expect(page.getByTestId('wb-design-circ-error')).toBeVisible();
    await expect(page.getByTestId('wb-design-circ-error')).toContainText('动线分析服务异常');
  });

  test('动线分析：添加/删除房间行', async ({ page }) => {
    await page.goto('./design');
    await page.getByTestId('wb-design-view--circulation').click();
    await expect(page.getByTestId('wb-design-room--0')).toBeVisible();
    await page.getByTestId('wb-design-add-room').click();
    await expect(page.getByTestId('wb-design-room--1')).toBeVisible();
    await page.getByTestId('wb-design-room-del--0').click();
    await expect(page.getByTestId('wb-design-room--1')).not.toBeVisible();
    await expect(page.getByTestId('wb-design-room--0')).toBeVisible();
  });
});

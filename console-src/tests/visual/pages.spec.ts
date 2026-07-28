import { test, expect } from '@playwright/test';

/**
 * 业务页视觉回归 + 交互 — 批次 4
 *
 * 验证 ProjectsPage / SettingsPage / BudgetPage：
 *   1. 列表/表单渲染正确（mock API）
 *   2. 截图匹配 baseline
 *   3. 关键交互（创建项目、切换主题、切换项目）
 *
 * mock 策略：
 *   - localStorage 预设 paseto_token
 *   - 拦截 /api/projects /api/auth/me /api/budgets/project/* 返回固定数据
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
  {
    id: 'proj-2',
    name: '厨房改造',
    address: '上海市徐汇区',
    total_area: 15,
    status: 'design',
    project_type: 'kitchen',
    owner_id: 'user-1',
    created_at: '2026-07-01T09:00:00Z',
    updated_at: '2026-07-25T11:00:00Z',
  },
];

const MOCK_USER = {
  id: 'user-1',
  phone: '13800138000',
  name: '张业主',
  role: 'homeowner',
  sub_role: null,
  avatar_url: null,
  is_active: true,
  is_verified: true,
  created_at: '2026-01-01T00:00:00Z',
};

const MOCK_BUDGET = {
  id: 'budget-1',
  project_id: 'proj-1',
  total_amount: 250000,
  spent_amount: 120000,
  items: [
    { id: 'bi-1', line_name: '水电改造', category: '基础工程', amount: 35000, spent_amount: 35000 },
    { id: 'bi-2', line_name: '瓦工贴砖', category: '泥瓦工程', amount: 45000, spent_amount: 40000 },
    { id: 'bi-3', line_name: '木工定制', category: '木工工程', amount: 80000, spent_amount: 45000 },
    { id: 'bi-4', line_name: '油漆涂刷', category: '油漆工程', amount: 30000, spent_amount: 0 },
    { id: 'bi-5', line_name: '主材采购', category: '材料', amount: 60000, spent_amount: 0 },
  ],
  created_at: '2026-06-16T10:00:00Z',
  updated_at: '2026-07-20T14:30:00Z',
};

test.describe('ProjectsPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch4'));
    await page.route('**/api/projects', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
      } else if (route.request().method() === 'POST') {
        const body = route.request().postDataJSON();
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({ ...body, id: 'proj-new', owner_id: 'user-1', status: 'planning', created_at: new Date().toISOString(), updated_at: new Date().toISOString() }),
        });
      }
    });
  });

  test('项目列表渲染 + 截图', async ({ page }) => {
    await page.goto('./projects');
    await expect(page.getByTestId('wb-projects-list')).toBeVisible();
    await expect(page.getByTestId('wb-project-card--proj-1')).toBeVisible();
    await expect(page.getByTestId('wb-project-card--proj-2')).toBeVisible();
    await expect(page.getByText('三居室整装')).toBeVisible();
    await expect(page).toHaveScreenshot('projects-list.png');
  });

  test('创建项目表单交互', async ({ page }) => {
    await page.goto('./projects');
    await expect(page.getByTestId('wb-projects-list')).toBeVisible();
    // 打开创建表单
    await page.getByTestId('wb-projects-toggle-create').click();
    await expect(page.getByTestId('wb-create-form')).toBeVisible();
    // 填写并提交
    await page.getByTestId('wb-create-name').fill('测试新项目');
    await page.getByTestId('wb-create-submit').click();
    // 表单关闭（创建成功后 reload）
    await expect(page.getByTestId('wb-create-form')).toHaveCount(0);
  });
});

test.describe('SettingsPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch4'));
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USER) });
    });
  });

  test('个人资料 + 主题 + 截图', async ({ page }) => {
    await page.goto('./settings');
    await expect(page.getByTestId('wb-settings-profile')).toBeVisible();
    await expect(page.getByText('张业主')).toBeVisible();
    await expect(page.getByText('13800138000')).toBeVisible();
    await expect(page.getByText('已认证')).toBeVisible();
    // 主题切换
    await page.getByTestId('wb-theme-option--light').click();
    await expect(page.getByTestId('wb-theme-option--light')).toHaveClass(/wb-theme-option--active/);
    await expect(page).toHaveScreenshot('settings.png');
  });

  test('通知开关切换', async ({ page }) => {
    await page.goto('./settings');
    await expect(page.getByTestId('wb-notify-order')).toHaveAttribute('aria-checked', 'true');
    await page.getByTestId('wb-notify-order').click();
    await expect(page.getByTestId('wb-notify-order')).toHaveAttribute('aria-checked', 'false');
  });
});

test.describe('BudgetPage', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch4'));
    await page.route('**/api/projects', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
    });
    await page.route('**/api/budgets/project/*', async (route) => {
      const projectId = route.request().url().split('/').pop();
      if (projectId === 'proj-1') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_BUDGET) });
      } else {
        await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: '预算不存在' }) });
      }
    });
  });

  test('预算概览 + 分项明细 + 截图', async ({ page }) => {
    await page.goto('./budget');
    // 默认选第一个项目，预算加载
    await expect(page.getByTestId('wb-budget-content')).toBeVisible();
    await expect(page.getByText('¥250,000')).toBeVisible();
    await expect(page.getByText('¥120,000')).toBeVisible();
    await expect(page.getByText('¥130,000')).toBeVisible();
    // 5 个分项
    await expect(page.locator('[data-testid^="wb-budget-item--"]')).toHaveCount(5);
    await expect(page.getByText('水电改造')).toBeVisible();
    await expect(page).toHaveScreenshot('budget.png');
  });

  test('切换到无预算项目显示空状态', async ({ page }) => {
    await page.goto('./budget');
    await expect(page.getByTestId('wb-budget-content')).toBeVisible();
    // 切换到 proj-2（无预算）
    await page.getByTestId('wb-budget-project-select').selectOption('proj-2');
    await expect(page.getByTestId('wb-budget-empty')).toBeVisible();
  });
});

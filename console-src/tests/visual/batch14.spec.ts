import { test, expect } from '@playwright/test';

/**
 * 适老改造套餐 + 补贴资格预检 — 批次 14（v1.17.0，政策适老化供给落地）
 *
 * 验证 ElderlyAdaptationPage 新增区块：
 *   1. 套餐目录只渲染适老套餐（elderly_theme=true），含一口价/无障碍标准/适老设计维度
 *   2. 「补贴预估」调用 subsidy-precheck → 展示预估补贴/落地价 + 诚实标注（非资格认定）
 *   3. 预检不可用（flag 关闭 → 404）→ 展示错误提示，不崩溃
 *
 * mock 策略同 batch6.spec.ts（响应字段 snake_case，对齐 app/api/elderly_adaptation.py）。
 * 本批次为交互/契约断言，不做截图回归（视觉快照见 batch5-13）。
 */

const MOCK_PROJECTS = [
  {
    id: 'proj-1',
    name: '三居室整装',
    address: '昆明市五华区',
    total_area: 120,
    status: 'construction',
    project_type: 'full_renovation',
    owner_id: 'user-1',
    created_at: '2026-06-15T10:00:00Z',
    updated_at: '2026-07-20T14:30:00Z',
  },
];

// 含 1 个非适老套餐，用于验证前端只渲染适老套餐（不误标）
const MOCK_PACKAGES = [
  {
    package_code: 'PKG-ELDERLY-BATH',
    name: '适老卫浴改造（48h）',
    scope_type: 'bathroom_refresh',
    duration_hours: 48,
    duration_days: 2,
    fixed_price: 16800,
    dry_construction: true,
    zero_relocation: true,
    inclusions: ['坐便器旁扶手', '湿区防滑处理', '无门槛化'],
    excludes: ['结构改造'],
    warranty: '整包 2 年质保，防水 5 年，扶手五金 5 年',
    elderly_theme: true,
    target_occupant: ['elderly_living', 'semi_selfcare', 'nursing', 'family'],
    accessibility_standard: 'GB 50763-2012',
    subsidy_category: 'fall_prevention',
    elderly_design: { 尺寸适配: '门洞净宽 ≥ 800mm、扶手高度 700mm', 安全性能: '防滑地面 + 夜间感应照明' },
  },
  {
    package_code: 'PKG-ELDERLY-ROOM',
    name: '适老卧室改造（72h）',
    scope_type: 'single_room',
    duration_hours: 72,
    duration_days: 3,
    fixed_price: 12800,
    dry_construction: true,
    zero_relocation: true,
    inclusions: ['床头扶手', '紧急呼叫按钮', '夜间感应地脚照明'],
    excludes: ['护理床设备本体'],
    warranty: '整包 2 年质保，扶手五金 5 年',
    elderly_theme: true,
    target_occupant: ['elderly_living', 'nursing'],
    accessibility_standard: 'GB 50763-2012',
    subsidy_category: 'health_emergency',
    elderly_design: { 操作便利: '大按键实体按钮，无需学习成本' },
  },
  {
    package_code: 'PKG-ELDERLY-FULL',
    name: '全屋适老智能化改造（7 天）',
    scope_type: 'full_renovation',
    duration_hours: 168,
    duration_days: 7,
    fixed_price: 39800,
    dry_construction: true,
    zero_relocation: true,
    inclusions: ['全屋无障碍动线改造', '跌倒报警器', '适老智能家居配置'],
    excludes: ['电梯加装'],
    warranty: '整包 2 年质保，防水 5 年',
    elderly_theme: true,
    target_occupant: ['elderly_living', 'semi_selfcare', 'nursing', 'family'],
    accessibility_standard: 'GB 50763-2012',
    subsidy_category: 'fall_prevention',
    elderly_design: { 方言识别: '语音交互支持方言识别（需网关能力支持）' },
  },
  {
    package_code: 'PKG-48H-KITCHEN',
    name: '48h 厨房快装',
    scope_type: 'kitchen_refresh',
    duration_hours: 48,
    duration_days: 2,
    fixed_price: 19800,
    dry_construction: true,
    zero_relocation: true,
    inclusions: ['干法橱柜定制'],
    excludes: ['旧电器更换'],
    warranty: '整包 2 年质保',
  },
];

const MOCK_PRECHECK = {
  policy_profile: 'national_baseline',
  policy_version: '2026-09-national-baseline',
  region: '昆明市',
  is_estimate: true,
  subsidy_rate: 0.15,
  max_subsidy_per_unit: null,
  source: '2026 年消费品以旧换新适老化补贴（公开报道口径）',
  disclaimer: '本结果为估算值，非补贴资格认定，实际以当地政策与主管部门核定为准。',
  items: [
    {
      name: '适老卫浴改造（48h）',
      category: 'fall_prevention',
      category_label: '防跌倒安全防护',
      unit_price: 16800,
      quantity: 1,
      subtotal: 16800,
      eligible: true,
      subsidy_rate: 0.15,
      subsidy_per_unit: 2520,
      subsidy_amount: 2520,
      cap_applied: false,
      reason: null,
    },
  ],
  total_price: 16800,
  total_subsidy: 2520,
  net_payable: 14280,
  warnings: [
    '未接入 昆明市 官方补贴目录（本平台不内置地方细则），补贴品类/比例/单件上限以当地政策与主管部门核定为准',
    '全国基准（公开报道口径）未设定单件补贴上限，估算未计入地方单件上限',
    '老年人年龄/失能等级等个人资格不参与本确定性判定，个人资格须按当地规定单独核验',
  ],
};

test.beforeEach(async ({ page }) => {
  // AuthGate 校验 token（getCurrentUser → /api/auth/me）
  await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch14'));
  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'user-1', phone: '13800138000', name: '张业主', role: 'homeowner',
        sub_role: null, avatar_url: null, is_active: true, is_verified: true,
        created_at: '2026-01-01T00:00:00Z',
      }),
    });
  });
  await page.route('**/api/projects', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
  });
  await page.route('**/api/elderly-adaptation/schemes/project/*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/partial-renovation/quick-install/packages', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PACKAGES) });
  });
});

test.describe('适老改造套餐目录', () => {
  test('只渲染适老套餐（elderly_theme=true）+ 适老元数据', async ({ page }) => {
    await page.goto('./elderly-adaptation');

    await expect(page.getByTestId('wb-elderly-packages-label')).toContainText('适老改造套餐（3）');
    await expect(page.locator('[data-testid^="wb-elderly-package--"]')).toHaveCount(3);

    const bath = page.getByTestId('wb-elderly-package--0');
    await expect(bath).toContainText('适老卫浴改造（48h）');
    await expect(bath).toContainText('一口价');
    await expect(bath).toContainText('干法施工');
    await expect(bath).toContainText('0 搬家');
    await expect(bath).toContainText('GB 50763-2012');
    await expect(bath).toContainText('尺寸适配');

    // 非适老套餐不得出现在适老套餐区
    await expect(page.getByText('48h 厨房快装')).toHaveCount(0);
  });
});

test.describe('补贴资格预检', () => {
  test('套餐预检 → 预估补贴/落地价 + 诚实标注（非资格认定）', async ({ page }) => {
    const precheckPayloads: unknown[] = [];
    await page.route('**/api/elderly-adaptation/subsidy-precheck', async (route) => {
      precheckPayloads.push(route.request().postDataJSON());
      await route.fulfill({
        status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PRECHECK),
      });
    });

    await page.goto('./elderly-adaptation');
    await page.getByTestId('wb-elderly-subsidy-region-input').fill('昆明市');
    await page.getByTestId('wb-elderly-package-precheck--0').click();

    const result = page.getByTestId('wb-elderly-package-subsidy--0');
    await expect(result).toBeVisible();
    await expect(result).toContainText('预估补贴');
    await expect(result).toContainText('预估落地价');
    await expect(result).toContainText('非资格认定');
    await expect(result).toContainText('防跌倒安全防护');
    // 诚实标注：地方目录未接入 + 单件上限未知 + 个人资格不判定
    await expect(result).toContainText('官方补贴目录');
    await expect(result).toContainText('个人资格');
    await expect(result).toContainText('本结果为估算值，非补贴资格认定');

    // 请求体契约：套餐编码 + 地区透传
    expect(precheckPayloads).toHaveLength(1);
    expect(precheckPayloads[0]).toMatchObject({ package_code: 'PKG-ELDERLY-BATH', region: '昆明市' });
  });

  test('预检不可用（404）→ 展示错误提示，页面不崩溃', async ({ page }) => {
    await page.route('**/api/elderly-adaptation/subsidy-precheck', async (route) => {
      await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: '该功能未启用' }) });
    });

    await page.goto('./elderly-adaptation');
    await page.getByTestId('wb-elderly-package-precheck--0').click();

    await expect(page.getByTestId('wb-elderly-adaptation-form-error')).toBeVisible();
    await expect(page.getByTestId('wb-elderly-package-subsidy--0')).toHaveCount(0);
    // 套餐目录仍然可用（页面未崩溃）
    await expect(page.locator('[data-testid^="wb-elderly-package--"]')).toHaveCount(3);
  });
});

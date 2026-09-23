import { test, expect, type Page } from '@playwright/test';

/**
 * 空间资产台账 — 批次 15（v1.16.0 Phase 3 存量空间资产化）
 *
 * 验证 SpaceAssetsPage 关键契约：
 *   1. 轻资产定位声明（platform_role 恒为 service_provider，资产持有方不得为平台自身）
 *   2. 资产组合汇总（类别/状态分布）
 *   3. 改造状态机流转按钮按当前状态收敛 —— assessed 不得直达 operating（不可跳跃）
 *   4. 流转/登记请求体契约 + 后端错误与 503 诚实降级
 *   5. 筛选条件透传 query、空态、错误态与重试
 *
 * mock 策略同 batch14.spec.ts（响应字段 snake_case，对齐 app/api/space_assets.py）。
 * 本批次为交互/契约断言，不做截图回归（视觉快照见 batch5-13）。
 */

type Fulfill = { status: number; body: unknown };

const LEDGER_DISABLED_DETAIL = '空间资产台账未启用（space_asset_ledger_enabled=False）';

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

const MOCK_ENUMS = {
  asset_categories: ['kangyang', 'healing', 'travel_residence', 'cultural_tourism', 'elderly_housing'],
  business_formats: [
    'herb_food_courtyard',
    'forest_herbal_bath',
    'kangyang_study',
    'seasonal_stay',
    'wellness_resort',
    'cultural_site',
    'elderly_home',
    'other',
  ],
  holder_types: ['private', 'enterprise', 'collective', 'government'],
  renovation_statuses: [
    'pending_assessment',
    'assessed',
    'in_renovation',
    'delivered',
    'operating',
    'suspended',
  ],
  platform_role: 'service_provider',
};

const MOCK_SUMMARY = {
  total_assets: 2,
  by_category: { travel_residence: 1, kangyang: 1 },
  by_status: { assessed: 1, operating: 1 },
  by_city: { 大理白族自治州: 1, 昆明市: 1 },
  avg_smart_readiness: 61.5,
  smart_ready_count: 1,
  total_area_sqm: 420,
  platform_role: 'service_provider',
  note: '轻资产改造服务商：不持有房产、不做物业运营、不做房地产经纪。',
};

const MOCK_ASSET_ASSESSED = {
  id: 'asset-1',
  owner_id: 'user-1',
  project_id: null,
  name: '大理·苍山节气旅居小院 A',
  province: '云南省',
  city: '大理白族自治州',
  district: null,
  address: null,
  latitude: null,
  longitude: null,
  building_area_sqm: 260,
  room_count: null,
  floor_info: null,
  built_year: null,
  structure_type: null,
  asset_category: 'travel_residence',
  business_format: 'seasonal_stay',
  asset_holder: '大理某文旅集团有限公司',
  holder_type: 'enterprise',
  platform_role: 'service_provider',
  renovation_status: 'assessed',
  renovation_scope: null,
  retrofit_package_code: null,
  elderly_scheme_id: null,
  smart_ready: false,
  smart_readiness_score: 45,
  matter_device_count: 0,
  sensor_count: 0,
  scene_automation_count: 0,
  fire_safety_status: 'unknown',
  accessibility_status: 'unknown',
  operation_metrics: null,
  notes: null,
  created_at: '2026-09-01T10:00:00Z',
  updated_at: '2026-09-10T10:00:00Z',
};

const MOCK_ASSET_OPERATING = {
  ...MOCK_ASSET_ASSESSED,
  id: 'asset-2',
  name: '昆明·滇池康养研学中心',
  city: '昆明市',
  asset_category: 'kangyang',
  business_format: 'kangyang_study',
  asset_holder: '云南某康养产业有限公司',
  renovation_status: 'operating',
  smart_ready: true,
  smart_readiness_score: 78,
};

const MOCK_ASSETS = [MOCK_ASSET_ASSESSED, MOCK_ASSET_OPERATING];

interface Captured {
  listUrls: string[];
  createBodies: unknown[];
  statusPosts: { assetId: string; body: unknown }[];
}

interface SetupConfig {
  /** 台账 flag 关闭：enums/summary/list/POST 全部 503（诚实降级） */
  ledgerDisabled?: boolean;
  /** 列表第 N 次调用的响应（N 从 1 起），未提供时回退 MOCK_ASSETS */
  listResponder?: (callIndex: number) => Fulfill;
  createResponder?: () => Fulfill;
  statusResponder?: (assetId: string, newStatus: string) => Fulfill;
}

async function setupSpaceAssets(page: Page, cfg: SetupConfig = {}): Promise<Captured> {
  const captured: Captured = { listUrls: [], createBodies: [], statusPosts: [] };
  let listCall = 0;
  const disabled: Fulfill = { status: 503, body: { detail: LEDGER_DISABLED_DETAIL } };

  // AuthGate 校验 token（getCurrentUser → /api/auth/me）
  await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch15'));
  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USER) });
  });
  await page.route('**/api/projects', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
  });

  await page.route('**/api/space-assets**', async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    const method = req.method();
    const fulfill = async (r: Fulfill) =>
      route.fulfill({ status: r.status, contentType: 'application/json', body: JSON.stringify(r.body) });

    if (cfg.ledgerDisabled) return fulfill(disabled);

    if (path.endsWith('/enums')) return fulfill({ status: 200, body: MOCK_ENUMS });
    if (path.endsWith('/summary')) return fulfill({ status: 200, body: MOCK_SUMMARY });

    const statusMatch = path.match(/\/api\/space-assets\/([^/]+)\/status$/);
    if (statusMatch && method === 'POST') {
      const body = req.postDataJSON() as { new_status: string };
      captured.statusPosts.push({ assetId: statusMatch[1], body });
      return fulfill(
        cfg.statusResponder
          ? cfg.statusResponder(statusMatch[1], body.new_status)
          : { status: 200, body: { ...MOCK_ASSET_ASSESSED, renovation_status: body.new_status } },
      );
    }

    if (method === 'POST') {
      captured.createBodies.push(req.postDataJSON());
      return fulfill(
        cfg.createResponder
          ? cfg.createResponder()
          : {
              status: 201,
              body: {
                ...MOCK_ASSET_ASSESSED,
                id: 'asset-new',
                name: '大理·苍山节气旅居小院 B',
                smart_readiness_score: 62.5,
              },
            },
      );
    }

    // GET 列表
    captured.listUrls.push(req.url());
    listCall += 1;
    return fulfill(cfg.listResponder ? cfg.listResponder(listCall) : { status: 200, body: MOCK_ASSETS });
  });

  return captured;
}

/** 最近一次列表请求 URL（用于断言筛选条件透传） */
function lastListUrl(captured: Captured): string {
  return captured.listUrls[captured.listUrls.length - 1] ?? '';
}

test.describe('空间资产台账 — 轻资产定位与汇总', () => {
  test('定位声明标注 service_provider，不暗示平台持有资产', async ({ page }) => {
    await setupSpaceAssets(page);
    await page.goto('./space-assets');

    const positioning = page.getByTestId('wb-space-assets-positioning');
    await expect(positioning).toContainText('存量空间资产运营');
    await expect(positioning).toContainText('平台角色：service_provider');
    await expect(positioning).toContainText('不持有房产');
    await expect(positioning).toContainText('不做物业运营');

    // 汇总卡：类别/状态分布
    const summary = page.getByTestId('wb-space-assets-summary');
    await expect(summary).toContainText('共 2 处');
    await expect(summary).toContainText('总建筑面积 420 ㎡');
    await expect(summary).toContainText('平均智能化就绪度 61.5 分');
    await expect(summary).toContainText('已就绪 1 处');
    await expect(summary).toContainText('旅居 1');
    await expect(summary).toContainText('康养 1');
    await expect(summary).toContainText('已评估 1');
    await expect(summary).toContainText('运营中 1');
  });
});

test.describe('空间资产台账 — 改造状态机', () => {
  test('流转按钮按当前状态收敛：assessed 不得直达 operating', async ({ page }) => {
    await setupSpaceAssets(page);
    await page.goto('./space-assets');

    await expect(page.getByTestId('wb-space-assets-table')).toBeVisible();

    // assessed：可 → 改造中 / 待评估 / 暂停，不得出现「运营中」
    const assessedRow = page.getByTestId('wb-space-asset-row--asset-1');
    await expect(assessedRow).toContainText('大理·苍山节气旅居小院 A');
    await expect(assessedRow).toContainText('旅居 / 节气旅居');
    await expect(assessedRow).toContainText('已评估');
    await expect(assessedRow).toContainText('企业');
    await expect(assessedRow.getByRole('button')).toHaveText(['→ 改造中', '→ 待评估', '→ 暂停']);
    await expect(assessedRow.getByText('运营中')).toHaveCount(0);
    await expect(assessedRow.getByText('就绪')).toHaveCount(0);

    // operating：仅可 → 暂停（终态收敛）
    const operatingRow = page.getByTestId('wb-space-asset-row--asset-2');
    await expect(operatingRow).toContainText('运营中');
    await expect(operatingRow).toContainText('就绪');
    await expect(operatingRow.getByRole('button')).toHaveText(['→ 暂停']);

    // 轻资产：持有方不得为平台自身
    await expect(operatingRow).toContainText('云南某康养产业有限公司');
  });

  test('流转请求体契约 + 成功后回填 notice 并刷新台账', async ({ page }) => {
    const captured = await setupSpaceAssets(page);
    await page.goto('./space-assets');

    await page.getByTestId('wb-space-asset-row--asset-1').getByRole('button', { name: '→ 改造中' }).click();

    await expect(page.getByTestId('wb-space-assets-notice')).toContainText(
      '「大理·苍山节气旅居小院 A」状态 → 改造中',
    );
    expect(captured.statusPosts).toHaveLength(1);
    expect(captured.statusPosts[0].assetId).toBe('asset-1');
    expect(captured.statusPosts[0].body).toMatchObject({ new_status: 'in_renovation' });
    // 流转后刷新列表 + 汇总（初始 1 次 + 刷新 1 次）
    await expect.poll(() => captured.listUrls.length).toBe(2);
    // 刷新完成后成功提示仍保留（不被自身刷新抹除）
    await expect(page.getByTestId('wb-space-assets-notice')).toContainText('状态 → 改造中');

    // 手动「刷新」清空历史提示
    await page.getByRole('button', { name: '刷新' }).click();
    await expect(page.getByTestId('wb-space-assets-notice')).toHaveCount(0);
  });

  test('非法流转（409）→ 展示后端 detail，页面不崩溃', async ({ page }) => {
    await setupSpaceAssets(page, {
      statusResponder: () => ({
        status: 409,
        body: { detail: '非法状态流转：assessed → operating（须经 in_renovation → delivered）' },
      }),
    });
    await page.goto('./space-assets');

    await page.getByTestId('wb-space-asset-row--asset-1').getByRole('button', { name: '→ 改造中' }).click();

    await expect(page.getByTestId('wb-space-assets-notice')).toContainText('状态流转失败');
    await expect(page.getByTestId('wb-space-assets-notice')).toContainText('非法状态流转');
    // 列表仍可用
    await expect(page.getByTestId('wb-space-assets-table')).toBeVisible();
  });
});

test.describe('空间资产台账 — 筛选与空态', () => {
  test('类别/状态筛选透传 query 参数', async ({ page }) => {
    const captured = await setupSpaceAssets(page);
    await page.goto('./space-assets');
    await expect(page.getByTestId('wb-space-assets-table')).toBeVisible();

    await page.getByTestId('wb-space-assets-filter-category').selectOption('elderly_housing');
    await expect.poll(() => lastListUrl(captured)).toContain('asset_category=elderly_housing');

    await page.getByTestId('wb-space-assets-filter-status').selectOption('operating');
    await expect.poll(() => lastListUrl(captured)).toContain('renovation_status=operating');
    expect(lastListUrl(captured)).toContain('asset_category=elderly_housing');

    // 清空筛选后不再携带类别参数
    await page.getByTestId('wb-space-assets-filter-category').selectOption('');
    await expect.poll(() => lastListUrl(captured)).not.toContain('asset_category=');
  });

  test('台账为空 → 展示空态引导', async ({ page }) => {
    await setupSpaceAssets(page, { listResponder: () => ({ status: 200, body: [] }) });
    await page.goto('./space-assets');

    await expect(page.getByTestId('wb-space-assets-empty')).toContainText('台账暂无资产记录');
    await expect(page.getByTestId('wb-space-assets-table')).toHaveCount(0);
  });
});

test.describe('空间资产台账 — 登记表单', () => {
  test('必填校验：名称/持有方为空 → 拦截提交且不发请求', async ({ page }) => {
    const captured = await setupSpaceAssets(page);
    await page.goto('./space-assets');

    await page.getByTestId('wb-space-assets-toggle-form').click();
    await expect(page.getByTestId('wb-space-assets-form')).toBeVisible();
    // 轻资产红线提示
    await expect(page.getByTestId('wb-space-assets-form')).toContainText('不得为平台自身');

    await page.getByTestId('wb-space-assets-submit').click();
    await expect(page.getByTestId('wb-space-assets-notice')).toContainText('资产名称与持有方为必填项');
    expect(captured.createBodies).toHaveLength(0);
  });

  test('登记成功 → 请求体契约 + notice 回填就绪度 + 表单收起', async ({ page }) => {
    const captured = await setupSpaceAssets(page);
    await page.goto('./space-assets');

    await page.getByTestId('wb-space-assets-toggle-form').click();
    await page.locator('#sa-name').fill('大理·苍山节气旅居小院 B');
    await page.locator('#sa-holder').fill('大理某文旅集团有限公司');
    await page.locator('#sa-city').fill('大理白族自治州');
    await page.locator('#sa-category').selectOption('travel_residence');
    await page.locator('#sa-format').selectOption('seasonal_stay');
    await page.locator('#sa-holder-type').selectOption('enterprise');
    await page.locator('#sa-area').fill('260');
    await page.getByTestId('wb-space-assets-submit').click();

    await expect(page.getByTestId('wb-space-assets-notice')).toContainText(
      '已登记「大理·苍山节气旅居小院 B」，智能化就绪度 62.5 分',
    );
    expect(captured.createBodies).toHaveLength(1);
    expect(captured.createBodies[0]).toMatchObject({
      name: '大理·苍山节气旅居小院 B',
      asset_holder: '大理某文旅集团有限公司',
      city: '大理白族自治州',
      asset_category: 'travel_residence',
      business_format: 'seasonal_stay',
      holder_type: 'enterprise',
      building_area_sqm: 260,
    });
    // 登记成功后表单收起并刷新台账
    await expect(page.getByTestId('wb-space-assets-form')).toHaveCount(0);
    await expect.poll(() => captured.listUrls.length).toBe(2);
  });

  test('登记失败（422）→ 展示后端 detail，表单保留', async ({ page }) => {
    await setupSpaceAssets(page, {
      createResponder: () => ({ status: 422, body: { detail: '资产持有方不得为平台自身' } }),
    });
    await page.goto('./space-assets');

    await page.getByTestId('wb-space-assets-toggle-form').click();
    await page.locator('#sa-name').fill('违规测试资产');
    await page.locator('#sa-holder').fill('索克家居平台');
    await page.getByTestId('wb-space-assets-submit').click();

    await expect(page.getByTestId('wb-space-assets-notice')).toContainText('登记失败');
    await expect(page.getByTestId('wb-space-assets-notice')).toContainText('资产持有方不得为平台自身');
    await expect(page.getByTestId('wb-space-assets-form')).toBeVisible();
  });
});

test.describe('空间资产台账 — 错误与诚实降级', () => {
  test('列表失败 → 错误态 + 重试恢复', async ({ page }) => {
    const captured = await setupSpaceAssets(page, {
      listResponder: (i) => (i === 1 ? { status: 500, body: { detail: '服务器内部错误' } } : { status: 200, body: MOCK_ASSETS }),
    });
    await page.goto('./space-assets');

    const error = page.getByTestId('wb-space-assets-error');
    await expect(error).toContainText('服务器内部错误');
    await expect(page.getByTestId('wb-space-assets-table')).toHaveCount(0);

    await error.getByRole('button', { name: '重试' }).click();
    await expect(page.getByTestId('wb-space-assets-table')).toBeVisible();
    expect(captured.listUrls.length).toBeGreaterThanOrEqual(2);
  });

  test('台账未启用（503）→ 明示 space_asset_ledger_enabled=False，不伪装空数据', async ({ page }) => {
    await setupSpaceAssets(page, { ledgerDisabled: true });
    await page.goto('./space-assets');

    await expect(page.getByTestId('wb-space-assets-error')).toContainText(LEDGER_DISABLED_DETAIL);
    // 不得回退为空态伪装成「无数据」
    await expect(page.getByTestId('wb-space-assets-empty')).toHaveCount(0);
    await expect(page.getByTestId('wb-space-assets-table')).toHaveCount(0);
    // 定位声明仍为轻资产口径（默认文案兜底）
    await expect(page.getByTestId('wb-space-assets-positioning')).toContainText('不持有房产');
  });
});

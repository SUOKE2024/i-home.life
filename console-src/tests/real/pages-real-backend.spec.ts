import { test, expect } from '@playwright/test';

/**
 * 真实后端全局页面冒烟 E2E — 批次 13（item 2：真实后端全链路）
 *
 * 驱动真实浏览器连生产/本地后端，验证全局页面（无项目选择器）渲染契约：
 *   登录 → 访问页面 → 期望 page testid 可见 + content 或 empty 可见（非 error / 非 login 重定向）
 *
 * 覆盖页面：projects / mep / appliance / materials / crews / furniture / products
 * 均为确定性 GET 端点（无 LLM、无外部依赖），适合真实后端 E2E。
 *
 * 价值：捕捉前后端接缝 bug（字段名漂移、schema drift、auth 缺失）。
 *   已发现并修复：products 500（products.deleted_at 列缺失 — schema drift）
 *
 * 前置：
 *   - 后端在跑（默认生产 http://118.31.223.213:8081，可用 E2E_BASE_URL 覆盖）
 *   - 测试用户已注册（13800000002 / E2EVerify123）
 */

const TEST_PHONE = process.env.E2E_LOCAL_PHONE ?? '13800000002';
const TEST_PASSWORD = process.env.E2E_LOCAL_PASSWORD ?? 'E2EVerify123';

async function loginAndInject(page: import('@playwright/test').Page) {
  const loginResp = await page.request.post('/api/auth/login', {
    data: { phone: TEST_PHONE, password: TEST_PASSWORD },
  });
  expect(loginResp.ok(), `登录应成功，实际 ${loginResp.status()}`).toBeTruthy();
  const token = (await loginResp.json()).access_token;
  expect(token, '应返回 access_token').toBeTruthy();
  await page.addInitScript((t) => {
    localStorage.setItem('paseto_token', t);
  }, token);
  return token;
}

/**
 * 断言页面渲染：page testid 可见，且 content 或 empty 之一可见（非 error、非 login 重定向）。
 * 用于全局列表页冒烟：无论有无数据，都不应崩溃或 401 重定向。
 */
async function expectPageRenders(
  page: import('@playwright/test').Page,
  path: string,
  pageTestId: string,
  contentTestId: string,
  emptyTestId: string,
  errorTestId: string,
  timeout = 15000,
) {
  await page.goto(path);
  await expect(page.getByTestId(pageTestId), `${pageTestId} 应可见`).toBeVisible({ timeout });
  // 不应停在 login（401 重定向）
  await expect(page, '不应重定向到 login').not.toHaveURL(/login/);
  // content 或 empty 之一应可见（等待加载完成）
  await expect(
    page.locator(`[data-testid="${contentTestId}"], [data-testid="${emptyTestId}"]`),
    `${contentTestId} 或 ${emptyTestId} 应可见`,
  ).toBeVisible({ timeout });
  // 不应出现 error 状态
  await expect(page.getByTestId(errorTestId), `${errorTestId} 不应出现`).toHaveCount(0);
}

test.describe('真实后端 全局页面冒烟', () => {
  test('projects 页渲染（测试用户 0 项目 → empty 状态）', async ({ page }) => {
    await loginAndInject(page);
    await page.goto('./projects');
    await expect(page.getByTestId('wb-projects-page')).toBeVisible({ timeout: 10000 });
    await expect(page, '不应重定向到 login').not.toHaveURL(/login/);
    // 测试用户无项目 → empty 状态
    await expect(page.getByTestId('wb-projects-empty')).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('wb-projects-error')).toHaveCount(0);
  });

  test('mep 页渲染（静态配置 → 真实数据 content）', async ({ page }) => {
    await loginAndInject(page);
    await page.goto('./mep');
    await expect(page.getByTestId('wb-mep-page')).toBeVisible({ timeout: 10000 });
    await expect(page, '不应重定向到 login').not.toHaveURL(/login/);
    // MEP 房型标准为静态配置（living_room → 客厅），应有真实数据
    await expect(page.getByTestId('wb-mep-content')).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('wb-mep-error')).toHaveCount(0);
    // 统计网格应含数字（开关/插座等点位数）
    await expect(page.getByTestId('wb-mep-stats')).toBeVisible();
  });

  test('appliance 页渲染（家电分类 + 列表）', async ({ page }) => {
    await loginAndInject(page);
    await expectPageRenders(
      page, './appliance', 'wb-appliance-page',
      'wb-appliance-content', 'wb-appliance-empty', 'wb-appliance-error',
    );
  });

  test('materials 页渲染（物料分类 + 列表）', async ({ page }) => {
    await loginAndInject(page);
    await expectPageRenders(
      page, './materials', 'wb-materials-page',
      'wb-materials-content', 'wb-materials-empty', 'wb-materials-error',
    );
  });

  test('crews 页渲染（工程队列表）', async ({ page }) => {
    await loginAndInject(page);
    await expectPageRenders(
      page, './crews', 'wb-crews-page',
      'wb-crews-content', 'wb-crews-empty', 'wb-crews-error',
    );
  });

  test('furniture 页渲染（家具品类库）', async ({ page }) => {
    await loginAndInject(page);
    await expectPageRenders(
      page, './furniture', 'wb-furniture-page',
      'wb-furniture-content', 'wb-furniture-empty', 'wb-furniture-error',
    );
  });

  test('products 页渲染（产品列表 — 验证 deleted_at schema drift 已修复）', async ({ page }) => {
    await loginAndInject(page);
    // 此前 products 500（products.deleted_at 列缺失），已通过 ALTER TABLE 修复
    await expectPageRenders(
      page, './products', 'wb-products-page',
      'wb-products-content', 'wb-products-empty', 'wb-products-error',
    );
  });

  test('未认证访问受保护页 → 401 重定向 login', async ({ page }) => {
    // 不注入 token，直接访问 materials（需认证的 GET）
    await page.goto('./materials');
    // 页面加载后调 /api/materials/categories 返 401 → api-client 重定向 login
    await expect(page).toHaveURL(/login/, { timeout: 10000 });
  });
});

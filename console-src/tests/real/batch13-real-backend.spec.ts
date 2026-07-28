import { test, expect } from '@playwright/test';

/**
 * 真实后端 E2E — 批次 13 设计页
 *
 * 驱动真实浏览器连生产/本地后端，验证 DesignPage → 真实后端两端点：
 *   1. POST /api/agents/design → DesignerAgent.generate_layouts（纯算法、确定性，无 LLM）
 *   2. POST /api/agents/design/circulation → analyze_circulation（纯算法、确定性）
 *
 * 两端点均无 LLM 调用、无超时风险，适合真实后端 E2E（区别于 SSE/LLM 类端点）。
 *
 * 前置：
 *   - 后端在跑（默认生产 http://118.31.223.213:8081，可用 E2E_BASE_URL 覆盖）
 *   - 测试用户已注册（13800000002 / E2EVerify123）
 *
 * 不 mock /api/*，验证真实响应字段（snake_case）+ 前端渲染契约。
 */

const TEST_PHONE = process.env.E2E_LOCAL_PHONE ?? '13800000002';
const TEST_PASSWORD = process.env.E2E_LOCAL_PASSWORD ?? 'E2EVerify123';

/** 登录拿 PASETO token，注入 localStorage */
async function loginAndInject(page: import('@playwright/test').Page) {
  const loginResp = await page.request.post('/api/auth/login', {
    data: { phone: TEST_PHONE, password: TEST_PASSWORD },
  });
  expect(loginResp.ok(), `登录应成功，实际 ${loginResp.status()}`).toBeTruthy();
  const body = await loginResp.json();
  const token = body.access_token;
  expect(token, '应返回 access_token').toBeTruthy();
  await page.addInitScript((t) => {
    localStorage.setItem('paseto_token', t);
  }, token);
  return token;
}

test.describe('真实后端 设计页', () => {
  test('设计方案生成：填需求 → 真实 generate_layouts → 4 字段卡片非空', async ({ page }) => {
    await loginAndInject(page);
    await page.goto('./design');
    await expect(page.getByTestId('wb-design-page')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('wb-design-plan-content')).toBeVisible();

    // 填需求（后端 _detect_area 会从 message 提取面积，无匹配则 fallback 126㎡，均返回有效方案）
    await page.getByTestId('wb-design-message').fill('90平米两居室，南北通透，现代简约');
    await page.getByTestId('wb-design-generate-btn').click();

    // 等待结果（后端纯算法，应快速返回）
    await expect(page.getByTestId('wb-design-plan-result')).toBeVisible({ timeout: 15000 });

    // space_planning 非空（layouts.reply 含"设计方案"关键字）
    await expect(page.getByTestId('wb-design-card--space')).toContainText(/设计方案|户型/);
    // style_suggestion 非空（recommendation = 方案名）
    const styleText = (await page.getByTestId('wb-design-card--style').textContent()) ?? '';
    expect(styleText.trim().length, '风格建议不应为空').toBeGreaterThan(0);
    // material_plan 非空（materials 含"砖"/"地板"/"漆"）
    await expect(page.getByTestId('wb-design-card--material')).toContainText(/砖|地板|漆/);
    // full_reply 展开（JSON 含 plans 字段）
    await page.getByTestId('wb-design-toggle-full').click();
    await expect(page.getByTestId('wb-design-full-reply')).toBeVisible();
    await expect(page.getByTestId('wb-design-full-reply')).toContainText('plans');
  });

  test('动线分析：加载预设 → 真实 analyze_circulation → 三动线评分', async ({ page }) => {
    await loginAndInject(page);
    await page.goto('./design');
    await page.getByTestId('wb-design-view--circulation').click();
    await expect(page.getByTestId('wb-design-circ-content')).toBeVisible();

    // 加载两居室预设（8 房间）
    await page.getByTestId('wb-design-preset').click();
    await expect(page.getByTestId('wb-design-room--7')).toBeVisible();

    // 分析（后端纯算法，快速返回）
    await page.getByTestId('wb-design-analyze-btn').click();
    await expect(page.getByTestId('wb-design-circ-result')).toBeVisible({ timeout: 15000 });

    // 综合评分卡：overall_score 是数字，rating_text ∈ {优秀,良好,一般,需优化}
    await expect(page.getByTestId('wb-design-score')).toBeVisible();
    const scoreText = (await page.getByTestId('wb-design-score').textContent()) ?? '';
    expect(scoreText, '应含数字评分').toMatch(/\d+(\.\d+)?/);
    await expect(page.getByTestId('wb-design-score')).toContainText(/优秀|良好|一般|需优化/);
    await expect(page.getByTestId('wb-design-score')).toContainText('8 房间');

    // 三大动线卡（后端固定返回 visitor/housework/living 三条）
    await expect(page.getByTestId('wb-design-circ-item--0')).toContainText('访客动线');
    await expect(page.getByTestId('wb-design-circ-item--1')).toContainText('家务动线');
    await expect(page.getByTestId('wb-design-circ-item--2')).toContainText('居住动线');

    // 每条动线应有数字评分
    for (const i of [0, 1, 2]) {
      const itemText = (await page.getByTestId(`wb-design-circ-item--${i}`).textContent()) ?? '';
      expect(itemText, `动线 ${i} 应含数字评分`).toMatch(/\d+/);
    }
  });

  test('动线分析：空房间名 → 前端校验拦截（不调后端）', async ({ page }) => {
    await loginAndInject(page);
    await page.goto('./design');
    await page.getByTestId('wb-design-view--circulation').click();

    // 默认 1 行房间，名称为空 → 点分析应被前端拦截
    await page.getByTestId('wb-design-analyze-btn').click();
    await expect(page.getByTestId('wb-design-circ-error')).toBeVisible();
    await expect(page.getByTestId('wb-design-circ-error')).toContainText('至少添加一个房间');
    // 结果区不应出现（证明未调后端）
    await expect(page.getByTestId('wb-design-circ-result')).not.toBeVisible();
  });

  test('未认证调 /api/agents/design → 401 重定向 login', async ({ page }) => {
    // 不注入 token，直接访问并触发设计生成
    await page.goto('./design');
    await expect(page.getByTestId('wb-design-page')).toBeVisible({ timeout: 10000 });
    await page.getByTestId('wb-design-message').fill('测试需求');
    await page.getByTestId('wb-design-generate-btn').click();

    // 401 后应重定向到 login（api-client.ts:67 被动触发）
    await expect(page).toHaveURL(/login/, { timeout: 10000 });
  });
});

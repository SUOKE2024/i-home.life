import { test, expect } from '@playwright/test';

/**
 * 工作台视觉回归 — 对齐设计文档 §9.4 + 批次 2 计划 §6
 *
 * 验证点：
 *   1. WorkbenchPage 空状态截图匹配 baseline（desktop + mobile）
 *   2. 输入栏 5 元素可见且可点击（附件/emoji/语音/语音任务/发送）
 *   3. AgentSelector 渲染 9 个 agent chips
 *   4. 模拟发送消息 → SSE mock → user + agent 消息出现后截图
 *
 * mock 策略：
 *   - localStorage 预设 paseto_token（模拟登录态）
 *   - 拦截 /api/agents/chat/stream SSE 返回固定流（格式对齐后端 agents.py:1255：data:{json}，json.event 标识类型）
 *   - 拦截 /api/voice/orchestrate/tasks 返回空列表
 */

// SSE mock 格式对齐后端真实输出：仅 data: 行，event 类型在 JSON 的 event 字段（非标准 SSE event: 行）
// 对齐基准：后端 agents.py:1192/1202/1253 + Flutter sse_service.dart:142
const SSE_RESPONSE = [
  'data: {"event":"meta","agent_type":"master","session_id":"test-session-batch2"}',
  'data: {"event":"token","content":"你好"}',
  'data: {"event":"token","content":"，我是总控 Agent，随时为你服务。"}',
  'data: {"event":"done","session_id":"test-session-batch2"}',
].join('\n\n') + '\n\n';

test.describe('工作台 WorkbenchPage', () => {
  test.beforeEach(async ({ page }) => {
    // 预设登录态
    await page.addInitScript(() => {
      localStorage.setItem('paseto_token', 'test-paseto-token-batch2');
    });
    // 拦截 SSE 聊天接口（对齐前端 streamChat 调用路径 /api/agents/chat/stream）
    await page.route('**/api/agents/chat/stream', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: SSE_RESPONSE,
      });
    });
    // 拦截语音任务接口
    await page.route('**/api/voice/orchestrate/tasks', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });
  });

  test('空状态截图匹配 baseline', async ({ page }) => {
    await page.goto('/');
    // 等待空状态渲染
    await expect(page.getByTestId('wb-empty')).toBeVisible();
    await expect(page).toHaveScreenshot('workbench-empty.png');
  });

  test('输入栏元素齐全且可点击', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('wb-input-bar')).toBeVisible();
    await expect(page.getByTestId('wb-input-attach')).toBeVisible();
    await expect(page.getByTestId('wb-input-field')).toBeVisible();
    await expect(page.getByTestId('wb-input-emoji')).toBeVisible();
    await expect(page.getByTestId('wb-input-voice')).toBeVisible();
    await expect(page.getByTestId('wb-input-voice-tasks')).toBeVisible();
    await expect(page.getByTestId('wb-input-send')).toBeVisible();
    // 发送按钮初始禁用（无输入）
    await expect(page.getByTestId('wb-input-send')).toBeDisabled();
  });

  test('AgentSelector 渲染 9 个 agent chips', async ({ page }) => {
    await page.goto('/');
    const chips = page.locator('[data-testid^="wb-agent-chip--"]');
    await expect(chips).toHaveCount(9);
    // master 默认选中
    await expect(page.getByTestId('wb-agent-chip--master')).toHaveAttribute('aria-selected', 'true');
    // 点击 design chip 切换选中
    await page.getByTestId('wb-agent-chip--design').click();
    await expect(page.getByTestId('wb-agent-chip--design')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('wb-agent-chip--master')).toHaveAttribute('aria-selected', 'false');
  });

  test('发送消息后 user + agent 消息出现', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('wb-empty')).toBeVisible();

    // 输入并发送
    await page.getByTestId('wb-input-field').fill('帮我看看预算');
    await expect(page.getByTestId('wb-input-send')).toBeEnabled();
    await page.getByTestId('wb-input-send').click();

    // 等待 user 消息出现
    await expect(page.getByTestId('wb-message-list')).toBeVisible();
    // 等待 agent 流式完成（done 事件后内容完整）
    await expect(page.getByText('你好，我是总控 Agent，随时为你服务。')).toBeVisible({ timeout: 5000 });

    // 截图（含消息）
    await expect(page).toHaveScreenshot('workbench-with-messages.png');
  });
});

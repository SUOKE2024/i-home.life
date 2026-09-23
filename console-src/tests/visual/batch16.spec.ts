import { test, expect, type Page } from '@playwright/test';

/**
 * 生态桥接 — 批次 16（2026-09-23 智能家居生态全链路接入修复）
 *
 * 验证 EcosystemPage 关键契约：
 *   1. 真机就绪度按**项目维度**取（GET /api/ecosystem/status?project_id=），不再只看 env 口径
 *   2. 桥接实现（implemented）与项目凭据（project_configured）分列展示，stub 生态显式标注
 *   3. 凭据录入请求体契约（project_id + ecosystem + config）+ 保存后表单清空（不回显凭据）
 *   4. 空凭据前端拦截（不发 POST）；无桥生态不提供录入（选项来自注册表）
 *   5. 生态对接删除路径契约 + status 失败态与重试
 *
 * mock 策略同 batch14/15（响应字段 snake_case，对齐 app/api/ecosystem.py + app/api/scene_automation.py）。
 * 本批次为交互/契约断言，不做截图回归。
 */

type Fulfill = { status: number; body: unknown };

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

const HONEST_NOTE = '桥接未配置真实 API key，实际设备联动端点保持 501（诚实降级，不伪装能力）；当前优先推进米家/鸿蒙真实接入';
const CHANNEL_NOTE = '真机凭据以项目级生态对接（EcosystemIntegration.config，AES-256-GCM 加密）为唯一生效通道；configured 为环境变量历史检测口径，不代表项目可用性';

/** 项目维度状态报告：mijia 真机桥 + 项目已配置凭据；harmonyos 未接真机 + 项目未配置 */
const MOCK_STATUS_WITH_PROJECT = {
  project_id: 'proj-1',
  bridges: [
    {
      key: 'mijia',
      name: '米家',
      priority: 1,
      configured: false,
      status: 'requires_api_key',
      required_env_keys: ['MIJIA_ACCOUNT', 'MIJIA_PASSWORD'],
      note: HONEST_NOTE,
      implemented: true,
      project_configured: true,
      project_auth_status: 'connected',
      has_credentials: true,
      credential_keys: ['password', 'username'],
    },
    {
      key: 'harmonyos',
      name: '华为鸿蒙',
      priority: 2,
      configured: false,
      status: 'requires_api_key',
      required_env_keys: ['HUAWEI_CLIENT_ID', 'HUAWEI_CLIENT_SECRET'],
      note: HONEST_NOTE,
      implemented: false,
      project_configured: false,
      project_auth_status: null,
      has_credentials: false,
      credential_keys: [],
    },
    {
      key: 'homekit',
      name: 'Apple HomeKit',
      priority: 3,
      configured: false,
      status: 'requires_api_key',
      required_env_keys: [],
      note: HONEST_NOTE,
      implemented: false,
      project_configured: false,
      project_auth_status: null,
      has_credentials: false,
      credential_keys: [],
    },
    {
      key: 'tuya',
      name: '涂鸦',
      priority: 4,
      configured: false,
      status: 'requires_api_key',
      required_env_keys: ['TUYA_ACCESS_ID', 'TUYA_ACCESS_SECRET'],
      note: HONEST_NOTE,
      implemented: false,
      project_configured: false,
      project_auth_status: null,
      has_credentials: false,
      credential_keys: [],
    },
  ],
  updated_at: '2026-09-23T10:00:00+08:00',
  honest_note: HONEST_NOTE,
  credential_channel_note: CHANNEL_NOTE,
};

const MOCK_BRIDGES = {
  bridges: [
    { key: 'mijia', name: '米家', priority: 1, required_env_keys: ['MIJIA_ACCOUNT', 'MIJIA_PASSWORD'], bridge: 'mijia', implemented: true },
    { key: 'harmonyos', name: '华为鸿蒙', priority: 2, required_env_keys: ['HUAWEI_CLIENT_ID', 'HUAWEI_CLIENT_SECRET'], bridge: 'harmonyos', implemented: false },
    { key: 'homekit', name: 'Apple HomeKit', priority: 3, required_env_keys: [], bridge: 'homekit', implemented: false },
    { key: 'tuya', name: '涂鸦', priority: 4, required_env_keys: ['TUYA_ACCESS_ID', 'TUYA_ACCESS_SECRET'], bridge: 'tuya', implemented: false },
  ],
  priority_strategy: '优先落地 1-2 个主流生态（米家/华为鸿蒙）真实联动，其余生态保持 stub 诚实标注（PRD v3.1 F46）',
};

const MOCK_INTEGRATION_MIJIA = {
  id: 'eco-1',
  project_id: 'proj-1',
  ecosystem: 'mijia',
  auth_status: 'connected',
  device_count: 1,
  last_synced_at: null,
  config: { redacted: true, keys: ['password', 'username'] },
  notes: null,
  created_at: '2026-09-20T10:00:00Z',
  updated_at: '2026-09-23T10:00:00Z',
};

interface Captured {
  statusUrls: string[];
  createBodies: unknown[];
  deletePaths: string[];
}

interface SetupConfig {
  /** 生态对接列表是否含 mijia 记录 */
  hasIntegration?: boolean;
  /** status 响应（覆盖默认） */
  statusResponder?: () => Fulfill;
  /** 创建响应（覆盖默认 201） */
  createResponder?: () => Fulfill;
}

async function setupEcosystem(page: Page, cfg: SetupConfig = {}): Promise<Captured> {
  const captured: Captured = { statusUrls: [], createBodies: [], deletePaths: [] };

  await page.addInitScript(() => localStorage.setItem('paseto_token', 'test-batch16'));
  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USER) });
  });
  await page.route('**/api/projects', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PROJECTS) });
  });
  await page.route('**/api/ecosystem/status**', async (route) => {
    captured.statusUrls.push(route.request().url());
    const r = cfg.statusResponder
      ? cfg.statusResponder()
      : { status: 200, body: MOCK_STATUS_WITH_PROJECT };
    await route.fulfill({ status: r.status, contentType: 'application/json', body: JSON.stringify(r.body) });
  });
  await page.route('**/api/ecosystem/bridges', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_BRIDGES) });
  });
  await page.route('**/api/scene-automation/ecosystems**', async (route) => {
    const req = route.request();
    const method = req.method();
    const path = new URL(req.url()).pathname;
    const fulfill = async (r: Fulfill) =>
      route.fulfill({ status: r.status, contentType: 'application/json', body: JSON.stringify(r.body) });

    if (method === 'POST') {
      captured.createBodies.push(req.postDataJSON());
      if (cfg.createResponder) return fulfill(cfg.createResponder());
      return fulfill({
        status: 201,
        body: { ...MOCK_INTEGRATION_MIJIA, id: 'eco-new', ecosystem: 'harmonyos' },
      });
    }
    if (method === 'DELETE') {
      captured.deletePaths.push(path);
      return fulfill({ status: 204, body: null });
    }
    return fulfill({
      status: 200,
      body: cfg.hasIntegration === false ? [] : [MOCK_INTEGRATION_MIJIA],
    });
  });

  return captured;
}

function lastStatusUrl(captured: Captured): string {
  return captured.statusUrls[captured.statusUrls.length - 1] ?? '';
}

test.describe('生态桥接 — 项目维度真机就绪度', () => {
  test('按项目取状态（project_id 透传），真机桥与 stub 桥分列标注', async ({ page }) => {
    const captured = await setupEcosystem(page);
    await page.goto('./ecosystem');

    const content = page.getByTestId('wb-ecosystem-content');
    await expect(content).toBeVisible();

    // 项目维度：最近一次 status 请求带 project_id
    expect(lastStatusUrl(captured)).toContain('project_id=proj-1');

    const table = page.getByTestId('wb-ecosystem-table');
    await expect(table).toContainText('米家');
    // 米家已接真机 + 项目已配置凭据（只回露字段名）
    const mijia = page.getByTestId('wb-ecosystem-bridge--mijia');
    await expect(mijia).toContainText('真机桥');
    const mijiaCred = page.getByTestId('wb-ecosystem-credential--mijia');
    await expect(mijiaCred).toContainText('已配置');
    await expect(mijiaCred).toContainText('password');
    await expect(mijiaCred).toContainText('username');

    // 鸿蒙为 stub 且项目未配置凭据
    const harmony = page.getByTestId('wb-ecosystem-bridge--harmonyos');
    await expect(harmony).toContainText('stub（未接真机）');
    await expect(page.getByTestId('wb-ecosystem-credential--harmonyos')).toContainText('项目未配置');

    // 凭据通道澄清条（env 口径 ≠ 真机通道）
    await expect(page.getByTestId('wb-ecosystem-credential-channel')).toContainText('唯一生效通道');
  });

  test('status 失败：展示错误态并可重试（不伪装空数据）', async ({ page }) => {
    // 挂载时会先按「未选择项目」取一次状态，项目列表返回后再按 project_id 取一次；
    // 失败态须持续到显式重试才恢复，避免被第二次请求的自动成功掩盖（用开关而非调用次数）
    let recover = false;
    await setupEcosystem(page, {
      statusResponder: () =>
        recover
          ? { status: 200, body: MOCK_STATUS_WITH_PROJECT }
          : { status: 500, body: { detail: '状态报告生成失败' } },
    });
    await page.goto('./ecosystem');

    const errorState = page.getByTestId('wb-ecosystem-error');
    await expect(errorState).toContainText('状态报告生成失败');
    // 不伪装空数据：失败态下不渲染生态表
    await expect(page.getByTestId('wb-ecosystem-content')).toHaveCount(0);

    recover = true;
    await errorState.getByRole('button', { name: '重试' }).click();
    await expect(page.getByTestId('wb-ecosystem-content')).toBeVisible();
  });
});

test.describe('生态桥接 — 项目凭据通道（真机入口）', () => {
  test('录入米家凭据：请求体契约正确，保存后清空表单且不回显凭据值', async ({ page }) => {
    const captured = await setupEcosystem(page, { hasIntegration: false });
    await page.goto('./ecosystem');

    await expect(page.getByTestId('wb-ecosystem-integrations-empty')).toContainText('暂无生态对接');

    const form = page.getByTestId('wb-ecosystem-credential-form');
    await form.getByTestId('wb-ecosystem-form-ecosystem').selectOption('mijia');
    await form.getByTestId('wb-ecosystem-form-cred--username').fill('mi-user');
    await form.getByTestId('wb-ecosystem-form-cred--password').fill('mi-secret');
    await form.getByTestId('wb-ecosystem-form-notes').fill('业主米家账号');
    await form.getByTestId('wb-ecosystem-form-submit').click();

    await expect(page.getByTestId('wb-ecosystem-notice')).toContainText('加密保存');
    expect(captured.createBodies).toEqual([
      {
        project_id: 'proj-1',
        ecosystem: 'mijia',
        config: { username: 'mi-user', password: 'mi-secret' },
        notes: '业主米家账号',
      },
    ]);
    // 凭据不回显：表单已清空
    await expect(form.getByTestId('wb-ecosystem-form-cred--username')).toHaveValue('');
    await expect(form.getByTestId('wb-ecosystem-form-cred--password')).toHaveValue('');
  });

  test('空凭据前端拦截：不发 POST，提示缺哪个字段', async ({ page }) => {
    const captured = await setupEcosystem(page);
    await page.goto('./ecosystem');

    const form = page.getByTestId('wb-ecosystem-credential-form');
    await form.getByTestId('wb-ecosystem-form-ecosystem').selectOption('mijia');
    await form.getByTestId('wb-ecosystem-form-submit').click();

    await expect(page.getByTestId('wb-ecosystem-form-error')).toContainText('米家账号不可为空');
    expect(captured.createBodies).toEqual([]);
  });

  test('stub 生态显式告警：保存后提示真机联动仍不可用', async ({ page }) => {
    const captured = await setupEcosystem(page);
    await page.goto('./ecosystem');

    const form = page.getByTestId('wb-ecosystem-credential-form');
    await form.getByTestId('wb-ecosystem-form-ecosystem').selectOption('harmonyos');
    await expect(page.getByTestId('wb-ecosystem-stub-warning')).toContainText('未接真机');
    await expect(page.getByTestId('wb-ecosystem-stub-warning')).toContainText('pending');

    await form.getByTestId('wb-ecosystem-form-cred--client_id').fill('cid');
    await form.getByTestId('wb-ecosystem-form-cred--client_secret').fill('csecret');
    await form.getByTestId('wb-ecosystem-form-submit').click();

    await expect(page.getByTestId('wb-ecosystem-notice')).toContainText('stub');
    expect(captured.createBodies[0]).toMatchObject({
      project_id: 'proj-1',
      ecosystem: 'harmonyos',
      config: { client_id: 'cid', client_secret: 'csecret' },
    });
  });

  test('生态选项仅限注册表（无桥生态不可录入），删除对接路径正确', async ({ page }) => {
    const captured = await setupEcosystem(page);
    await page.goto('./ecosystem');

    const options = page.getByTestId('wb-ecosystem-credential-form')
      .getByTestId('wb-ecosystem-form-ecosystem')
      .locator('option');
    await expect(options).toHaveCount(4);
    const values = await options.evaluateAll((els) => els.map((e) => (e as HTMLOptionElement).value));
    expect(values).toEqual(['mijia', 'harmonyos', 'homekit', 'tuya']);
    expect(values).not.toContain('alexa');
    expect(values).not.toContain('google_home');

    // 已存在的对接：删除
    await expect(page.getByTestId('wb-ecosystem-integration--mijia')).toContainText('password');
    await page.getByTestId('wb-ecosystem-remove--mijia').click();
    await expect(page.getByTestId('wb-ecosystem-notice')).toContainText('已删除');
    expect(captured.deletePaths).toEqual(['/api/scene-automation/ecosystems/eco-1']);
  });

  test('创建失败（422 无桥生态/后端拒绝）透出错误，不伪造成功', async ({ page }) => {
    await setupEcosystem(page, {
      createResponder: () => ({ status: 422, body: { detail: '生态类型不受支持' } }),
    });
    await page.goto('./ecosystem');

    const form = page.getByTestId('wb-ecosystem-credential-form');
    await form.getByTestId('wb-ecosystem-form-ecosystem').selectOption('mijia');
    await form.getByTestId('wb-ecosystem-form-cred--username').fill('u');
    await form.getByTestId('wb-ecosystem-form-cred--password').fill('p');
    await form.getByTestId('wb-ecosystem-form-submit').click();

    await expect(page.getByTestId('wb-ecosystem-form-error')).toBeVisible();
    await expect(page.getByTestId('wb-ecosystem-notice')).toHaveCount(0);
  });
});

import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import { fileURLToPath } from 'url';
import * as path from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * 真实后端 E2E — 批次 12 三页（CAD / Sketch-3D / IFC 导出）
 *
 * 连生产/本地后端，验证前端页面 ↔ 后端真实 wire format 接缝。
 * 与 batch12.spec.ts（mock）区别：不 mock /api/*，走真实后端真实文件解析。
 *
 * 前置：
 *   - 后端在跑（默认生产 http://118.31.223.213:8081，可用 E2E_BASE_URL 覆盖）
 *   - 测试用户已注册（13800000002 / E2EVerify123，可用 E2E_LOCAL_PHONE/PASSWORD 覆盖）
 *   - DXF fixture 随仓库提交（tests/fixtures/test_e2e.dxf，含 LINE/CIRCLE/POLYLINE/TEXT/ARC）
 *
 * 验证点（mock 测试无法覆盖的接缝）：
 *   - CAD：真实 ezdxf 解析返回的 bounds 含 width/height（前端 domain.ts 已补字段）
 *   - Sketch：真实文件类型校验（非图片返 415/422）
 *   - IFC：ifcopenshell 未装返 501（真实环境降级）
 */

const TEST_PHONE = process.env.E2E_LOCAL_PHONE ?? '13800000002';
const TEST_PASSWORD = process.env.E2E_LOCAL_PASSWORD ?? 'E2EVerify123';
// 随仓库提交的 DXF fixture（相对测试文件定位，避免依赖 /tmp 外部文件）
const DXF_PATH = path.join(__dirname, '..', 'fixtures', 'test_e2e.dxf');

/** 登录拿 PASETO token，注入 localStorage */
async function loginAndInject(page: import('@playwright/test').Page) {
  const loginResp = await page.request.post('/api/auth/login', {
    data: { phone: TEST_PHONE, password: TEST_PASSWORD },
  });
  expect(loginResp.ok(), `登录应成功，实际 ${loginResp.status()}`).toBeTruthy();
  const body = await loginResp.json();
  const token = body.access_token;
  expect(token).toBeTruthy();
  await page.addInitScript((t) => {
    localStorage.setItem('paseto_token', t);
  }, token);
  return token;
}

test.describe('批次12 真实后端 E2E', () => {
  test.beforeAll(() => {
    // 确认测试 DXF 文件存在
    expect(fs.existsSync(DXF_PATH), `测试 DXF 文件应存在: ${DXF_PATH}`).toBeTruthy();
  });

  test('CADPage 上传真实 DXF → 真实解析结果展示（bounds 含 width/height）', async ({ page }) => {
    await loginAndInject(page);
    await page.goto('./cad');

    await expect(page.getByTestId('wb-cad-page')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('wb-cad-pick-btn')).toBeVisible();

    // 上传真实 DXF 文件（含 LINE/CIRCLE/POLYLINE/TEXT/ARC 5 实体）
    await page.getByTestId('wb-cad-file-input').setInputFiles(DXF_PATH);
    await expect(page.getByTestId('wb-cad-file-name')).toContainText('test_e2e.dxf');
    await page.getByTestId('wb-cad-upload-btn').click();

    // 等待真实解析结果（ezdxf 解析 15KB DXF 应 < 3s）
    await expect(page.getByTestId('wb-cad-result')).toBeVisible({ timeout: 15000 });

    // 真实解析应返回 5 实体（LINE+CIRCLE+POLYLINE+TEXT+ARC）
    await expect(page.getByTestId('wb-cad-file-type')).toContainText('DXF');
    await expect(page.getByTestId('wb-cad-entity-count')).toContainText('5');
    await expect(page.getByTestId('wb-cad-entity--lines')).toContainText('1');
    await expect(page.getByTestId('wb-cad-entity--circles')).toContainText('1');
    await expect(page.getByTestId('wb-cad-entity--polylines')).toContainText('1');
    await expect(page.getByTestId('wb-cad-entity--texts')).toContainText('1');
    await expect(page.getByTestId('wb-cad-entity--arcs')).toContainText('1');

    // bounds 应含 width/height（前端 domain.ts 已补字段，验证接缝）
    await expect(page.getByTestId('wb-cad-bounds')).toBeVisible();
    await expect(page.getByTestId('wb-cad-bounds')).toContainText('宽');
    await expect(page.getByTestId('wb-cad-bounds')).toContainText('高');

    // DWG 转换标记应为否（上传的是 DXF）
    await expect(page.getByTestId('wb-cad-converted')).toContainText('否');
  });

  test('Sketch3DPage 上传非图片文件 → 真实 415/422 错误降级', async ({ page }) => {
    await loginAndInject(page);
    await page.goto('./sketch-3d');

    await expect(page.getByTestId('wb-sketch-page')).toBeVisible({ timeout: 10000 });

    // 上传 DXF 文件（非图片）→ 后端应拒绝
    await page.getByTestId('wb-sketch-file-input').setInputFiles(DXF_PATH);
    await page.getByTestId('wb-sketch-submit-btn').click();

    // 应显示错误降级（后端返 415 不支持类型 或 422 解析失败）
    await expect(page.getByTestId('wb-sketch-error')).toBeVisible({ timeout: 15000 });
    const errText = await page.getByTestId('wb-sketch-error').textContent();
    expect(errText && errText.length > 0, '应有错误信息').toBeTruthy();
  });

  test('IFCExportPage 结构导出 → 真实 501 ifcopenshell 未装降级', async ({ page }) => {
    await loginAndInject(page);
    await page.goto('./ifc-export');

    await expect(page.getByTestId('wb-ifc-page')).toBeVisible({ timeout: 10000 });

    // 需先有项目。检查项目选择器是否有项目可选
    const projectSelect = page.getByTestId('wb-ifc-project-select');
    await expect(projectSelect).toBeVisible();

    // 选中第一个项目（若有）
    const options = await projectSelect.locator('option').count();
    test.skip(options <= 1, '无项目可测，跳过 IFC 导出');

    await projectSelect.selectOption({ index: 1 });
    await page.getByTestId('wb-ifc-export-btn').click();

    // ifcopenshell 未装 → 501 降级提示
    await expect(page.getByTestId('wb-ifc-error')).toBeVisible({ timeout: 15000 });
    await expect(page.getByTestId('wb-ifc-error')).toContainText('ifcopenshell');
  });
});

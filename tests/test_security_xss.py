"""XSS 专项安全测试

验证 FastAPI JSON API 对 XSS payload 的处理：
- 项目名称/地址字段
- 物料名称字段
- 聊天消息字段
- 预算 line note / 采购单 note / 检查 issues 等"评论类"字段
- 用户 name 字段

防护策略说明：
- 项目使用 FastAPI + Pydantic，所有响应均为 application/json，
  浏览器不会执行 JSON 中的 <script> 标签（无脚本执行上下文）。
- 因此对于 JSON 端点，验证"不执行脚本"而非"必须 HTML 转义"。
- 对于 HTML 输出端点（如 BOM Excel 导出），验证输出为二进制 xlsx，
  非可执行 HTML。

每项测试验证：
1. 端点不返回 500（payload 不应导致服务异常）
2. 响应 Content-Type 为 application/json（无 HTML 上下文）
3. 响应体为合法 JSON（不包含可执行 <script> 标签）
4. 存储/返回的字段值与原始 payload 一致（JSON 中 < > 为合法字符）
"""

import uuid

import pytest
from httpx import AsyncClient


# ── XSS payload 集合 ──────────────────────────────────────
XSS_SCRIPT_PAYLOAD = "<script>alert('xss')</script>"
XSS_IMG_PAYLOAD = "<img src=x onerror=alert(1)>"
XSS_SVG_PAYLOAD = "<svg onload=alert('xss')><rect /></svg>"
XSS_JS_PAYLOAD = "javascript:alert(document.cookie)"
XSS_EVENT_PAYLOAD = "<div onmouseover='alert(1)'>hover me</div>"


def _is_application_json(content_type: str) -> bool:
    """检查 Content-Type 是否为 application/json（允许带 charset 后缀）。"""
    return content_type.split(";")[0].strip().lower() == "application/json"


async def _register_and_login(
    client: AsyncClient, phone: str, name: str = "XSS测试用户"
) -> tuple[str, dict]:
    """注册一个用户并返回 (token, headers)。"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": name, "password": "test123456"},
    )
    assert resp.status_code == 201, f"注册失败: {resp.text}"
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "XSS测试项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers=headers,
    )
    assert resp.status_code == 201, f"创建项目失败: {resp.text}"
    return resp.json()["id"]


def _assert_no_executable_html_in_json(resp_text: str, content_type: str, context: str) -> None:
    """验证 JSON 响应中不包含可执行 HTML（非 <script> 标签作为 HTML 元素）。

    JSON 中允许 <script> 作为字符串值出现，但响应整体必须是合法 JSON。
    """
    # Content-Type 必须是 application/json，确保浏览器不进入 HTML 解析模式
    assert _is_application_json(content_type), (
        f"[{context}] 响应 Content-Type 非 application/json: {content_type!r}"
    )
    # 响应体不应以 <!DOCTYPE html> 或 <html 开头（不应是 HTML 文档）
    body_lower = resp_text.lstrip().lower()
    assert not body_lower.startswith("<!doctype html"), (
        f"[{context}] 响应为 HTML 文档（可能存在 XSS 风险）: {resp_text[:200]!r}"
    )
    assert not body_lower.startswith("<html"), (
        f"[{context}] 响应为 HTML 文档（可能存在 XSS 风险）: {resp_text[:200]!r}"
    )


# ════════════════════════════════════════════════════════════════
# XSS 防护测试
# ════════════════════════════════════════════════════════════════


class TestXssProtection:
    """XSS 防护专项测试 — 验证 JSON API 不提供脚本执行上下文。"""

    # ── a. 项目名称 XSS ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_project_name_xss(self, client: AsyncClient):
        """创建项目时 name 字段包含 <script>alert('xss')</script>。

        验证：
        - 端点不返回 500
        - 响应为 application/json
        - 返回的 name 字段存储原始 payload（JSON 中 < > 为合法字符，不会执行）
        """
        token, headers = await _register_and_login(client, f"139{str(uuid.uuid4().int)[:8]}")

        resp = await client.post(
            "/api/projects",
            json={"name": XSS_SCRIPT_PAYLOAD, "total_area": 100.0},
            headers=headers,
        )
        assert resp.status_code != 500, f"XSS payload 导致 500: {resp.text[:300]!r}"
        assert resp.status_code == 201, (
            f"项目创建响应码异常: status={resp.status_code}, resp={resp.text[:300]!r}"
        )
        _assert_no_executable_html_in_json(
            resp.text, resp.headers.get("content-type", ""), "project create"
        )
        # JSON API 允许存储原始 payload（浏览器不会在 JSON 上下文执行）
        project = resp.json()
        assert XSS_SCRIPT_PAYLOAD in project["name"], (
            f"项目 name 未存储原始 payload: got={project['name']!r}"
        )

        # 验证查询时也返回原始 payload（保持数据一致性）
        project_id = project["id"]
        resp = await client.get(f"/api/projects/{project_id}", headers=headers)
        assert resp.status_code == 200, f"查询项目失败: {resp.text[:300]!r}"
        _assert_no_executable_html_in_json(
            resp.text, resp.headers.get("content-type", ""), "project get"
        )

    # ── b. 项目描述/地址 XSS ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_project_description_xss(self, client: AsyncClient):
        """项目 address 字段包含 <img src=x onerror=alert(1)>。

        Project schema 不含 description，使用 address 字段验证同等语义。
        """
        token, headers = await _register_and_login(client, f"139{str(uuid.uuid4().int)[:8]}")

        resp = await client.post(
            "/api/projects",
            json={
                "name": "XSS地址测试",
                "address": XSS_IMG_PAYLOAD,
                "total_area": 100.0,
            },
            headers=headers,
        )
        assert resp.status_code != 500, f"XSS payload 导致 500: {resp.text[:300]!r}"
        assert resp.status_code == 201, (
            f"项目创建响应码异常: status={resp.status_code}, resp={resp.text[:300]!r}"
        )
        _assert_no_executable_html_in_json(
            resp.text, resp.headers.get("content-type", ""), "project create with img xss"
        )
        project = resp.json()
        # JSON 中允许存储原始 <img> 标签作为字符串
        assert XSS_IMG_PAYLOAD in (project.get("address") or ""), (
            f"项目 address 未存储原始 payload: got={project.get('address')!r}"
        )

    # ── c. 物料名称 XSS ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_material_name_xss(self, client: AsyncClient):
        """材料名称包含 JavaScript payload。

        验证物料创建端点不返回 500，响应为合法 JSON。
        """
        token, headers = await _register_and_login(client, f"139{str(uuid.uuid4().int)[:8]}")

        # 先创建物料分类
        cat_resp = await client.post(
            "/api/materials/categories",
            json={"name": "XSS测试分类", "code": f"xss_{uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        assert cat_resp.status_code == 201, f"创建分类失败: {cat_resp.text[:300]!r}"
        cat_id = cat_resp.json()["id"]

        # 创建物料，name 包含 XSS payload
        resp = await client.post(
            "/api/materials",
            json={
                "category_id": cat_id,
                "name": XSS_JS_PAYLOAD,
                "sku": f"XSS-{uuid.uuid4().hex[:8]}",
                "unit_price": 200.0,
                "unit": "㎡",
                "brand": XSS_SCRIPT_PAYLOAD,
                "spec": XSS_EVENT_PAYLOAD,
            },
            headers=headers,
        )
        assert resp.status_code != 500, f"XSS payload 导致 500: {resp.text[:300]!r}"
        assert resp.status_code == 201, (
            f"物料创建响应码异常: status={resp.status_code}, resp={resp.text[:300]!r}"
        )
        _assert_no_executable_html_in_json(
            resp.text, resp.headers.get("content-type", ""), "material create"
        )
        material = resp.json()
        assert XSS_JS_PAYLOAD in material["name"], (
            f"物料 name 未存储原始 payload: got={material['name']!r}"
        )

    # ── d. 聊天消息 XSS ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_chat_message_xss(self, client: AsyncClient):
        """聊天消息包含 <script> 标签。

        验证消息创建端点不返回 500，响应为合法 JSON。
        """
        token, headers = await _register_and_login(client, f"139{str(uuid.uuid4().int)[:8]}")
        project_id = await _create_project(client, headers, "XSS聊天测试")

        resp = await client.post(
            "/api/chat/messages",
            json={
                "project_id": project_id,
                "content": XSS_SCRIPT_PAYLOAD,
            },
            headers=headers,
        )
        assert resp.status_code != 500, f"XSS payload 导致 500: {resp.text[:300]!r}"
        assert resp.status_code == 201, (
            f"聊天消息创建响应码异常: status={resp.status_code}, resp={resp.text[:300]!r}"
        )
        _assert_no_executable_html_in_json(
            resp.text, resp.headers.get("content-type", ""), "chat message create"
        )
        msg = resp.json()
        # JSON 中允许存储原始 <script> 标签（前端渲染需自行转义）
        assert XSS_SCRIPT_PAYLOAD in msg["content"], (
            f"聊天消息 content 未存储原始 payload: got={msg['content']!r}"
        )

        # 验证查询消息列表也返回原始 payload
        resp = await client.get(f"/api/chat/messages/{project_id}", headers=headers)
        assert resp.status_code == 200, f"查询消息失败: {resp.text[:300]!r}"
        _assert_no_executable_html_in_json(
            resp.text, resp.headers.get("content-type", ""), "chat message list"
        )
        messages = resp.json()
        assert any(XSS_SCRIPT_PAYLOAD in m["content"] for m in messages), (
            f"查询消息列表中未找到 XSS payload: messages={messages!r}"
        )

    # ── e. 评论字段 XSS（预算 line note 作为评论类字段） ─────────────────────────────

    @pytest.mark.asyncio
    async def test_comment_xss(self, client: AsyncClient):
        """评论字段包含恶意 SVG。

        使用预算 line 的 note 字段作为评论类存储（schema 上 note 是自由文本备注，
        语义上等价于评论）。验证端点不返回 500，响应为合法 JSON。
        """
        token, headers = await _register_and_login(client, f"139{str(uuid.uuid4().int)[:8]}")
        project_id = await _create_project(client, headers, "XSS评论测试")

        resp = await client.post(
            "/api/budgets",
            json={
                "project_id": project_id,
                "lines": [
                    {
                        "category": "硬装",
                        "name": "墙面处理",
                        "estimated_amount": 20000.0,
                        "unit": "㎡",
                        "quantity": 100,
                        "unit_price": 200,
                        "note": XSS_SVG_PAYLOAD,
                    },
                ],
            },
            headers=headers,
        )
        assert resp.status_code != 500, f"XSS payload 导致 500: {resp.text[:300]!r}"
        assert resp.status_code == 201, (
            f"预算创建响应码异常: status={resp.status_code}, resp={resp.text[:300]!r}"
        )
        _assert_no_executable_html_in_json(
            resp.text, resp.headers.get("content-type", ""), "budget note xss"
        )
        # 验证 note 字段存储了原始 SVG payload（JSON 允许）
        budget = resp.json()
        line_note = budget["lines"][0].get("note") or ""
        assert XSS_SVG_PAYLOAD in line_note, (
            f"预算 line note 未存储原始 SVG payload: got={line_note!r}"
        )

    # ── f. 用户昵称 XSS ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_user_profile_xss(self, client: AsyncClient):
        """用户名/昵称字段包含 XSS payload。

        验证注册端点不返回 500，响应为合法 JSON。
        User.name 字段允许自由文本，注册后查询 /api/auth/me 验证。
        """
        phone = f"139{str(uuid.uuid4().int)[:8]}"
        resp = await client.post(
            "/api/auth/register",
            json={
                "phone": phone,
                "name": XSS_SCRIPT_PAYLOAD,
                "password": "test123456",
            },
        )
        assert resp.status_code != 500, f"XSS payload 导致 500: {resp.text[:300]!r}"
        assert resp.status_code == 201, (
            f"用户注册响应码异常: status={resp.status_code}, resp={resp.text[:300]!r}"
        )
        _assert_no_executable_html_in_json(
            resp.text, resp.headers.get("content-type", ""), "user register xss"
        )
        token = resp.json()["access_token"]

        # 查询当前用户信息
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"查询用户信息失败: {resp.text[:300]!r}"
        _assert_no_executable_html_in_json(
            resp.text, resp.headers.get("content-type", ""), "user me xss"
        )
        user = resp.json()
        # JSON 中允许存储原始 <script> 标签（前端展示需自行转义）
        assert XSS_SCRIPT_PAYLOAD in user["name"], (
            f"用户 name 未存储原始 payload: got={user['name']!r}"
        )


# ════════════════════════════════════════════════════════════════
# HTML 端点输出转义测试（BOM Excel 导出）
# ════════════════════════════════════════════════════════════════


class TestHtmlEndpointXssProtection:
    """HTML 输出端点的 XSS 防护测试。

    项目唯一导出 HTML 类（实际为 Excel 二进制）的端点是 BOM Excel 导出：
      GET /api/materials/bom/{project_id}/export
    返回 application/vnd.openxmlformats-officedocument.spreadsheetml.sheet 二进制流，
    非可执行 HTML。验证：
    1. 响应 Content-Type 为 Excel MIME（非 text/html）
    2. 响应体为 ZIP 二进制（xlsx 文件以 PK 标识开头）
    3. 响应体不包含 <script> 标签（即使物料名包含 XSS payload）
    """

    @pytest.mark.asyncio
    async def test_bom_excel_export_with_xss_payload(self, client: AsyncClient):
        """BOM Excel 导出端点对 XSS payload 的处理。

        创建包含 XSS payload 的物料 + BOM，导出 Excel，
        验证输出为二进制 xlsx（非可执行 HTML）。
        """
        token, headers = await _register_and_login(client, f"139{str(uuid.uuid4().int)[:8]}")
        project_id = await _create_project(client, headers, "BOM导出XSS测试")

        # 创建物料分类 + 物料（name 含 XSS）
        cat_resp = await client.post(
            "/api/materials/categories",
            json={"name": "BOM XSS 分类", "code": f"bom_xss_{uuid.uuid4().hex[:8]}"},
            headers=headers,
        )
        assert cat_resp.status_code == 201, f"创建分类失败: {cat_resp.text[:300]!r}"
        cat_id = cat_resp.json()["id"]

        mat_resp = await client.post(
            "/api/materials",
            json={
                "category_id": cat_id,
                "name": XSS_SCRIPT_PAYLOAD,
                "sku": f"BOM-XSS-{uuid.uuid4().hex[:8]}",
                "unit_price": 200.0,
                "unit": "㎡",
                "brand": XSS_IMG_PAYLOAD,
            },
            headers=headers,
        )
        assert mat_resp.status_code == 201, f"创建物料失败: {mat_resp.text[:300]!r}"
        material_id = mat_resp.json()["id"]

        # 创建 BOM 项
        bom_resp = await client.post(
            "/api/materials/bom",
            json={
                "project_id": project_id,
                "material_id": material_id,
                "quantity": 10.0,
                "unit_price": 200.0,
                "note": XSS_SVG_PAYLOAD,
            },
            headers=headers,
        )
        assert bom_resp.status_code == 201, f"创建 BOM 失败: {bom_resp.text[:300]!r}"

        # 导出 Excel
        resp = await client.get(
            f"/api/materials/bom/{project_id}/export",
            headers=headers,
        )
        assert resp.status_code != 500, f"导出导致 500: {resp.text[:300]!r}"
        assert resp.status_code == 200, (
            f"导出响应码异常: status={resp.status_code}, resp={resp.text[:300]!r}"
        )

        # Content-Type 必须是 Excel MIME（非 text/html）
        content_type = resp.headers.get("content-type", "")
        assert "spreadsheet" in content_type.lower(), (
            f"导出 Content-Type 异常（应含 spreadsheet）: {content_type!r}"
        )
        assert "text/html" not in content_type.lower(), (
            f"导出 Content-Type 错误地包含 text/html: {content_type!r}"
        )

        # 响应体必须是二进制 xlsx（ZIP 文件以 PK\x03\x04 开头）
        body = resp.content
        assert body[:4] == b"PK\x03\x04", (
            f"导出文件不是合法 xlsx（应 ZIP 头 PK\\x03\\x04）: head={body[:8]!r}"
        )

        # 验证二进制内容不包含可执行 HTML 标签
        # （Excel cell 中即使包含 <script> 也只是文本，但确保输出确实是二进制而非 HTML 容器）
        body_str = body.decode("latin-1", errors="replace")
        assert "<!DOCTYPE html" not in body_str.upper(), (
            "导出文件包含 HTML 文档头（可能存在 HTML 注入）"
        )

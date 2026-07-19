"""MCP 端点测试 (/api/mcp/*)

覆盖:
- /manifest            公开端点返回正确格式
- /tools               未认证返回 401，已认证返回 5 个工具
- /tools/call          调用 5 个内置工具，未知工具返回错误
- /tools/call          越权访问其他用户项目返回 403
- /sse                 SSE 端点返回 text/event-stream

注意：本项目约定不修改已有文件，因此 MCP 路由暂未注册到 main.py。
本测试文件参照 test_idor_v1_1_1.py 的引导模式，在测试启动时将路由注册到 app。
"""

import json

import pytest
from httpx import AsyncClient
from starlette.routing import Mount

from app.api import mcp as mcp_api
from app.main import app

# ── 引导注册 MCP 路由（与 test_idor_v1_1_1.py 相同的引导逻辑） ──
_mcp_registered = any(
    getattr(r, "path", "").startswith("/api/mcp") for r in app.routes
)
if not _mcp_registered:
    # 临时移除根路径 StaticFiles 挂载（避免 include_router 时路由顺序冲突）
    _static_mounts = [
        r for r in app.router.routes
        if isinstance(r, Mount) and r.path in ("/", "")
    ]
    app.router.routes = [
        r for r in app.router.routes
        if not (isinstance(r, Mount) and r.path in ("/", ""))
    ]
    app.include_router(mcp_api.router, prefix="/api")
    app.router.routes.extend(_static_mounts)


# ── 辅助函数 ──

async def _register(client: AsyncClient, phone: str = "13900007001") -> str:
    """注册用户并返回 access_token"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "MCP测试用户", "password": "test123456"},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_project(
    client: AsyncClient,
    headers: dict,
    name: str = "MCP测试项目",
) -> str:
    """创建项目并返回 project_id"""
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# === /api/mcp/manifest ===


@pytest.mark.asyncio
async def test_mcp_manifest(client: AsyncClient):
    """公开端点返回正确格式（无需认证）"""
    resp = await client.get("/api/mcp/manifest")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "name" in data
    assert "version" in data
    assert "protocol_version" in data
    assert "tools_count" in data
    # 项目内置 5 个 Agent 工具
    assert data["tools_count"] == 5


# === /api/mcp/tools ===


@pytest.mark.asyncio
async def test_mcp_list_tools_unauth(client: AsyncClient):
    """未认证返回 401"""
    resp = await client.get("/api/mcp/tools")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mcp_list_tools(client: AsyncClient):
    """已认证返回工具列表（5 个工具）"""
    token = await _register(client, "13900007010")
    resp = await client.get("/api/mcp/tools", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "tools" in data
    tools = data["tools"]
    assert len(tools) == 5
    # 验证 MCP 协议字段（name/description/inputSchema）
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert tool["inputSchema"]["type"] == "object"
        assert "properties" in tool["inputSchema"]
    # 验证 5 个工具名一致
    names = {t["name"] for t in tools}
    assert names == {
        "get_budget",
        "get_design_layout",
        "search_materials",
        "get_construction_progress",
        "run_qa_inspection",
    }


# === /api/mcp/tools/call ===


@pytest.mark.asyncio
async def test_mcp_call_budget(client: AsyncClient):
    """调用 get_budget 工具返回预算"""
    token = await _register(client, "13900007020")
    resp = await client.post(
        "/api/mcp/tools/call",
        json={"name": "get_budget", "arguments": {"area": 100, "style": "modern"}},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["isError"] is False
    assert len(data["content"]) >= 1
    assert data["content"][0]["type"] == "text"
    # 解析 content text 为 JSON，验证包含 tiers 分档预算
    payload = json.loads(data["content"][0]["text"])
    assert "tiers" in payload
    assert "economy" in payload["tiers"]
    assert "luxury" in payload["tiers"]


@pytest.mark.asyncio
async def test_mcp_call_design_layout(client: AsyncClient):
    """调用 get_design_layout 工具"""
    token = await _register(client, "13900007021")
    resp = await client.post(
        "/api/mcp/tools/call",
        json={"name": "get_design_layout", "arguments": {"area": 90, "style": "nordic"}},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["isError"] is False
    payload = json.loads(data["content"][0]["text"])
    assert "color_palette" in payload
    assert "design_features" in payload
    assert "rooms" in payload


@pytest.mark.asyncio
async def test_mcp_call_search_materials(client: AsyncClient):
    """调用 search_materials 工具"""
    token = await _register(client, "13900007022")
    resp = await client.post(
        "/api/mcp/tools/call",
        json={"name": "search_materials", "arguments": {"category": "瓷砖", "keyword": ""}},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["isError"] is False
    payload = json.loads(data["content"][0]["text"])
    assert "results" in payload
    assert payload["total"] >= 1
    # 返回的第一条物料应属于瓷砖类别
    assert payload["results"][0]["category"] == "瓷砖"


@pytest.mark.asyncio
async def test_mcp_call_construction_progress(client: AsyncClient):
    """调用 get_construction_progress 工具（含 project_id，需项目归属校验）"""
    token = await _register(client, "13900007023")
    # 先创建项目，再用项目 id 调用工具
    project_id = await _create_project(client, _headers(token))
    resp = await client.post(
        "/api/mcp/tools/call",
        json={
            "name": "get_construction_progress",
            "arguments": {"project_id": project_id},
        },
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["isError"] is False
    payload = json.loads(data["content"][0]["text"])
    assert "overall_progress" in payload
    assert "phases" in payload


@pytest.mark.asyncio
async def test_mcp_call_qa_inspection(client: AsyncClient):
    """调用 run_qa_inspection 工具（含 project_id）"""
    token = await _register(client, "13900007024")
    project_id = await _create_project(client, _headers(token))
    resp = await client.post(
        "/api/mcp/tools/call",
        json={
            "name": "run_qa_inspection",
            "arguments": {"project_id": project_id, "phase": "waterproof"},
        },
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["isError"] is False
    payload = json.loads(data["content"][0]["text"])
    assert "pass_rate" in payload
    assert "items" in payload


@pytest.mark.asyncio
async def test_mcp_call_unknown_tool(client: AsyncClient):
    """未知工具返回错误（MCP 协议：isError=True，HTTP 200）"""
    token = await _register(client, "13900007025")
    resp = await client.post(
        "/api/mcp/tools/call",
        json={"name": "nonexistent_tool", "arguments": {}},
        headers=_headers(token),
    )
    # MCP 协议：工具不存在属于业务错误，返回 200 + isError=True
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["isError"] is True
    assert len(data["content"]) >= 1
    assert "工具不存在" in data["content"][0]["text"]


@pytest.mark.asyncio
async def test_mcp_call_with_project_id_unauth(client: AsyncClient):
    """越权访问其他用户项目返回 403（IDOR 防护）"""
    # 用户 A 创建项目
    token_a = await _register(client, "13900007030")
    project_id = await _create_project(client, _headers(token_a), "用户A项目")

    # 用户 B 尝试用 A 的 project_id 调用工具
    token_b = await _register(client, "13900007031")
    resp = await client.post(
        "/api/mcp/tools/call",
        json={
            "name": "get_construction_progress",
            "arguments": {"project_id": project_id},
        },
        headers=_headers(token_b),
    )
    assert resp.status_code == 403


# === /api/mcp/sse ===


@pytest.mark.asyncio
async def test_mcp_sse_endpoint(client: AsyncClient):
    """SSE 端点返回 text/event-stream 并包含 JSON-RPC 2.0 响应"""
    token = await _register(client, "13900007040")
    resp = await client.post(
        "/api/mcp/sse",
        json={"id": 1, "name": "get_budget", "arguments": {"area": 80}},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    # SSE 响应必须为 text/event-stream
    assert "text/event-stream" in resp.headers.get("content-type", "")
    # 响应体应包含 SSE 事件标记
    body = resp.text
    assert "event:" in body
    assert "data:" in body
    # 应包含 JSON-RPC 2.0 响应（id=1）
    assert '"jsonrpc": "2.0"' in body or '"jsonrpc":"2.0"' in body
    assert '"id": 1' in body or '"id":1' in body

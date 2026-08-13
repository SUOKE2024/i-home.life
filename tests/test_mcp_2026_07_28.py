"""MCP 2026-07-28 规范完整对齐测试（v1.3.0 P1）

逐项验证 MCP 2026-07-28 规范的 8 项核心特性：
- P1-1 stateless 核心（无 initialize/initialized 握手，无 Mcp-Session-Id）
- P1-2 server/discover RPC（POST /api/mcp JSON-RPC 入口）
- P1-3 header-based routing（Mcp-Method / Mcp-Name header）
- P1-4 cacheable list results（ETag + If-None-Match → 304）
- P1-5 MRTR 多轮往返请求（轮询式）
- P1-6 authorization hardening（RFC 9207 issuer / CIMD）
- P1-7 extensions framework + Tasks 扩展
- P1-8 .well-known Server Card

测试引导注册 MCP 路由（与 test_mcp.py 相同模式）。
"""

import json

import pytest
from httpx import AsyncClient
from starlette.routing import Mount

from app.api import mcp as mcp_api
from app.main import app
from app.mcp.server import mcp_server

# ── 引导注册 MCP 路由（与 test_mcp.py 相同的引导逻辑） ──
_mcp_registered = any(
    getattr(r, "path", "").startswith("/api/mcp") for r in app.routes
)
if not _mcp_registered:
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

async def _register(client: AsyncClient, phone: str = "13900007101") -> str:
    """注册用户并返回 access_token"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "MCP2026测试用户", "password": "test123456"},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# === P1-1 stateless 核心 ===


@pytest.mark.asyncio
async def test_stateless_no_session_handshake(client: AsyncClient):
    """stateless 核心：manifest/discover 响应不要求 Mcp-Session-Id，无握手"""
    # 公开 manifest 端点无需认证、无需 session header
    resp = await client.get("/api/mcp/manifest")
    assert resp.status_code == 200
    # 响应不应要求 session（无 WWW-Authenticate: Mcp-Session 等）
    assert "mcp-session" not in {k.lower() for k in resp.headers}
    data = resp.json()
    assert data["protocol_version"] == "2026-07-28"


def test_stateless_protocol_version_constant():
    """协议版本常量为 2026-07-28"""
    assert mcp_server.PROTOCOL_VERSION == "2026-07-28"
    assert mcp_server.SERVER_VERSION == "1.13.5"


# === P1-2 server/discover RPC ===


@pytest.mark.asyncio
async def test_server_discover_via_jsonrpc(client: AsyncClient):
    """server/discover RPC：POST /api/mcp JSON-RPC 入口返回能力清单"""
    token = await _register(client, "13900007102")
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "server/discover"},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    result = data["result"]
    assert result["protocol_version"] == "2026-07-28"
    assert "server" in result
    assert "capabilities" in result
    # discover 声明 tools/resources/prompts cacheable
    assert result["capabilities"]["tools"]["cacheable"] is True
    # authorization 含 RFC 9207 issuer + CIMD 支持
    assert result["authorization"]["issuer"] == "i-home.life"
    assert result["authorization"]["cimd_supported"] is True


@pytest.mark.asyncio
async def test_discover_method_flag_disabled(client: AsyncClient, monkeypatch):
    """mcp_discover_enabled=False 时 server/discover 返回 503"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "mcp_discover_enabled", False)
    token = await _register(client, "13900007103")
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "server/discover"},
        headers=_headers(token),
    )
    assert resp.status_code == 503


# === P1-3 header-based routing ===


@pytest.mark.asyncio
async def test_header_based_routing_mcp_method(client: AsyncClient):
    """Mcp-Method header 可替代 body.method（网关可直接基于 header 路由）"""
    token = await _register(client, "13900007104")
    # body.method 为 tools/list，但 header 覆盖为 server/discover
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        headers={**_headers(token), "Mcp-Method": "server/discover"},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    # header 优先 → 走 discover（含 protocol_version）
    assert result["protocol_version"] == "2026-07-28"


@pytest.mark.asyncio
async def test_header_based_routing_mcp_name_for_tools_call(client: AsyncClient):
    """Mcp-Name header 携带工具名（tools/call 时可用）"""
    token = await _register(client, "13900007105")
    resp = await client.post(
        "/api/mcp",
        json={
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"arguments": {"area": 100, "style": "modern"}},
        },
        headers={**_headers(token), "Mcp-Name": "get_budget"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["result"]
    assert data["isError"] is False
    payload = json.loads(data["content"][0]["text"])
    assert "tiers" in payload


# === P1-4 cacheable list results ===


@pytest.mark.asyncio
async def test_tools_list_returns_etag_and_cache_control(client: AsyncClient):
    """tools/list 响应携带 ETag + Cache-Control（cacheable list results）"""
    token = await _register(client, "13900007106")
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 4, "method": "tools/list"},
        headers=_headers(token),
    )
    assert resp.status_code == 200
    assert "etag" in {k.lower() for k in resp.headers}
    assert "cache-control" in {k.lower() for k in resp.headers}
    result = resp.json()["result"]
    assert "cache_hint" in result
    assert "etag" in result["cache_hint"]
    assert result["cache_hint"]["ttl"] == mcp_server.LIST_CACHE_TTL
    assert result["cache_hint"]["sortable"] is True


@pytest.mark.asyncio
async def test_tools_list_deterministic_order(client: AsyncClient):
    """工具列表确定性排序（按 name 字典序），保证 cacheable list 稳定"""
    token = await _register(client, "13900007107")
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 5, "method": "tools/list"},
        headers=_headers(token),
    )
    tools = resp.json()["result"]["tools"]
    names = [t["name"] for t in tools]
    assert names == sorted(names), "工具列表未按 name 字典序排序"


@pytest.mark.asyncio
async def test_tools_list_304_on_if_none_match(client: AsyncClient):
    """If-None-Match 命中 ETag → 304 Not Modified"""
    token = await _register(client, "13900007108")
    # 首次请求拿 ETag
    resp1 = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 6, "method": "tools/list"},
        headers=_headers(token),
    )
    etag = resp1.headers["etag"]
    # 带 If-None-Match 再请求 → 304
    resp2 = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 7, "method": "tools/list"},
        headers={**_headers(token), "If-None-Match": etag},
    )
    assert resp2.status_code == 304


# === P1-5 MRTR 多轮往返请求 ===


@pytest.mark.asyncio
async def test_mrtr_manager_create_and_submit():
    """MRTR 管理器：创建请求 → 列待响应 → 回传响应（轮询式）"""
    from app.mcp.mrtr import mrtr_manager
    # 创建服务端→客户端请求（如 sampling）
    req = await mrtr_manager.create_request("sampling", {"prompt": "test"})
    assert req.state == "pending"
    # 列待响应
    pending = await mrtr_manager.list_pending()
    assert any(r.id == req.id for r in pending)
    # 回传响应
    ok = await mrtr_manager.submit_response(req.id, {"text": "client response"})
    assert ok is True
    # 回传后状态变更
    updated = await mrtr_manager.get_request(req.id)
    assert updated.state == "completed"
    assert updated.response == {"text": "client response"}


@pytest.mark.asyncio
async def test_mrtr_http_list_pending(client: AsyncClient):
    """MRTR HTTP 端点：GET /api/mcp/mrtr 列待响应请求"""
    from app.mcp.mrtr import mrtr_manager
    token = await _register(client, "13900007109")
    req = await mrtr_manager.create_request("elicitation", {"message": "input?"})
    resp = await client.get("/api/mcp/mrtr", headers=_headers(token))
    assert resp.status_code == 200
    requests = resp.json()["requests"]
    assert any(r["id"] == req.id for r in requests)
    # 清理
    await mrtr_manager.submit_response(req.id, {})


@pytest.mark.asyncio
async def test_mrtr_http_submit_response(client: AsyncClient):
    """MRTR HTTP 端点：POST /api/mcp/mrtr/{request_id} 回传响应"""
    from app.mcp.mrtr import mrtr_manager
    token = await _register(client, "13900007110")
    req = await mrtr_manager.create_request("sampling", {"prompt": "x"})
    resp = await client.post(
        f"/api/mcp/mrtr/{req.id}",
        json={"response": {"text": "ok"}},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_mrtr_http_submit_unknown_returns_404(client: AsyncClient):
    """MRTR 回传不存在的 request_id → 404"""
    token = await _register(client, "13900007111")
    resp = await client.post(
        "/api/mcp/mrtr/nonexistent-id",
        json={"response": {}},
        headers=_headers(token),
    )
    assert resp.status_code == 404


# === P1-6 authorization hardening（RFC 9207 issuer / CIMD）===


@pytest.mark.asyncio
async def test_cimd_registration(client: AsyncClient):
    """CIMD 端点：POST /api/mcp/cimd 注册客户端元数据，返回 issuer 凭证"""
    token = await _register(client, "13900007112")
    resp = await client.post(
        "/api/mcp/cimd",
        json={
            "client_name": "test-mcp-client",
            "client_uri": "https://example.com",
            "redirect_uris": ["https://example.com/callback"],
            "grant_types": ["authorization_code"],
        },
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["issuer"] == "i-home.life"
    assert data["client_name"] == "test-mcp-client"
    assert data["client_id"].startswith("mcp_")


@pytest.mark.asyncio
async def test_discover_declares_issuer_and_cimd(client: AsyncClient):
    """discover 响应声明 RFC 9207 issuer + CIMD 支持"""
    token = await _register(client, "13900007113")
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "server/discover"},
        headers=_headers(token),
    )
    auth = resp.json()["result"]["authorization"]
    assert auth["issuer"] == "i-home.life"
    assert auth["schemes"] == ["bearer"]
    assert auth["cimd_supported"] is True


# === P1-7 extensions framework + Tasks 扩展 ===


@pytest.mark.asyncio
async def test_tasks_extension_create_get_list_update_cancel(client: AsyncClient):
    """Tasks 扩展全流程：create → get → list → update → cancel"""
    token = await _register(client, "13900007114")

    # create
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tasks/create",
              "params": {"name": "long-render", "arguments": {"style": "modern"}, "metadata": {"k": "v"}}},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    task = resp.json()["result"]["task"]
    assert task["state"] == "submitted"
    assert task["name"] == "long-render"
    task_id = task["id"]

    # get
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tasks/get", "params": {"id": task_id}},
        headers=_headers(token),
    )
    assert resp.json()["result"]["task"]["id"] == task_id

    # update → working
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 3, "method": "tasks/update",
              "params": {"id": task_id, "state": "working"}},
        headers=_headers(token),
    )
    assert resp.json()["result"]["task"]["state"] == "working"

    # list
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 4, "method": "tasks/list", "params": {"state": "working"}},
        headers=_headers(token),
    )
    tasks = resp.json()["result"]["tasks"]
    assert any(t["id"] == task_id for t in tasks)

    # cancel
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 5, "method": "tasks/cancel", "params": {"id": task_id}},
        headers=_headers(token),
    )
    assert resp.json()["result"]["task"]["state"] == "canceled"


@pytest.mark.asyncio
async def test_tasks_extension_flag_disabled(client: AsyncClient, monkeypatch):
    """mcp_tasks_extension_enabled=False 时 tasks/* 返回 503"""
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "mcp_tasks_extension_enabled", False)
    token = await _register(client, "13900007115")
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tasks/create", "params": {"name": "x"}},
        headers=_headers(token),
    )
    assert resp.status_code == 503


def test_extensions_framework_registry():
    """扩展框架：Tasks 扩展可被 MCPServer 加载并注册"""
    mcp_server._extensions_loaded = False  # 强制重载
    exts = mcp_server.list_extensions()
    ext_names = [e["name"] for e in exts]
    assert "tasks" in ext_names
    tasks_ext = mcp_server.get_extension("tasks")
    assert tasks_ext is not None
    assert tasks_ext.NAME == "tasks"


# === P1-8 .well-known Server Card ===


@pytest.mark.asyncio
async def test_well_known_mcp_server_card(client: AsyncClient):
    """GET /.well-known/mcp 返回 Server Card（公开端点，无需认证）"""
    resp = await client.get("/.well-known/mcp")
    assert resp.status_code == 200, resp.text
    card = resp.json()
    assert card["mcp_version"] == "2026-07-28"
    assert card["server"]["name"] == mcp_server.SERVER_NAME
    assert card["transport"]["type"] == "streamable_http"
    assert card["transport"]["endpoint"] == "/api/mcp"
    assert card["transport"]["stateless"] is True
    assert card["authorization"]["issuer"] == "i-home.life"
    assert card["authorization"]["cimd_endpoint"] == "/api/mcp/cimd"
    assert "discovered_at" in card


# === JSON-RPC 错误处理 ===


@pytest.mark.asyncio
async def test_jsonrpc_unknown_method_returns_error(client: AsyncClient):
    """未知 method → JSON-RPC error -32601 方法不存在"""
    token = await _register(client, "13900007116")
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "nonexistent/method"},
        headers=_headers(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_jsonrpc_tools_call_missing_name(client: AsyncClient):
    """tools/call 缺 name 参数 → JSON-RPC error -32602"""
    token = await _register(client, "13900007117")
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"arguments": {}}},
        headers=_headers(token),
    )
    assert resp.status_code == 200
    assert resp.json()["error"]["code"] == -32602


# === P1-9 W3C Trace Context（SEP-414） ===


@pytest.mark.asyncio
async def test_jsonrpc_w3c_trace_meta_generated(client: AsyncClient):
    """未携带 traceparent 时，服务端生成根 span 写入响应 _meta（SEP-414）"""
    token = await _register(client, "13900007118")
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "server/discover"},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    meta = data["_meta"]
    assert "traceparent" in meta
    # W3C format: version-00-<trace-id 32hex>-<span-id 16hex>-flags-01
    parts = meta["traceparent"].split("-")
    assert parts[0] == "00"
    assert len(parts[1]) == 32
    assert len(parts[2]) == 16
    assert parts[3] == "01"
    assert meta["trace_id"] == parts[1]
    assert meta["span_id"] == parts[2]


@pytest.mark.asyncio
async def test_jsonrpc_w3c_trace_meta_passthrough(client: AsyncClient):
    """携带 traceparent/tracestate/baggage 时透传至响应 _meta（SEP-414）"""
    token = await _register(client, "13900007119")
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    headers = {
        **_headers(token),
        "traceparent": traceparent,
        "tracestate": "vendor=abc123",
        "baggage": "userId=42",
    }
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "server/discover"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    meta = resp.json()["_meta"]
    assert meta["traceparent"] == traceparent
    assert meta["tracestate"] == "vendor=abc123"
    assert meta["baggage"] == "userId=42"
    # 透传时不生成新的 trace_id/span_id
    assert "trace_id" not in meta
    assert "span_id" not in meta


# === P1-10 Enterprise 扩展（MCP 2026 Roadmap Enterprise Readiness） ===


@pytest.mark.asyncio
async def test_enterprise_status(client: AsyncClient):
    """enterprise/status 返回企业级能力声明（审计/SSO/网关）"""
    token = await _register(client, "13900007120")
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "enterprise/status"},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert result["extension"] == "enterprise"
    er = result["enterprise_readiness"]
    assert "audit" in er and "sso" in er and "gateway" in er
    assert er["audit"]["hmac_integrity"] is True
    assert er["sso"]["session"] == "paseto_v4_local"
    assert er["gateway"]["stateless"] is True


@pytest.mark.asyncio
async def test_enterprise_audit(client: AsyncClient):
    """enterprise/audit 返回审计轨迹（count + entries 结构）"""
    token = await _register(client, "13900007121")
    resp = await client.post(
        "/api/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "enterprise/audit", "params": {"limit": 5}},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["result"]
    assert "count" in result
    assert "entries" in result
    assert isinstance(result["entries"], list)
    # 注册后应存在审计记录（REGISTER/LOGIN）
    assert result["count"] >= 1
    if result["entries"]:
        entry = result["entries"][0]
        assert "action" in entry and "user_id" in entry and "created_at" in entry

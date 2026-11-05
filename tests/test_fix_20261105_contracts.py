"""2026-11-05 全景评估修复契约测试（fix-home）。

覆盖 BUG-21（501 语义 / IFC body 丢弃）、BUG-27（生态公钥读取）、
BUG-28（/health/detail 隐瞒降级）、BUG-29（A2A JSON-RPC 422 边界）、
BUG-30（matter 默认值）、BUG-31（指纹缓存 / A2A message repr）与 B5/B7/B8。

约定：
- 涉及全局异常处理器 / health/detail 的用例走真实 app 的 ``client`` fixture；
- A2A 端点内部行为用独立 FastAPI app（复刻 test_a2a_jsonrpc.py 的依赖覆盖），
  避免与全局 app 的鉴权/DB 初始化耦合。
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.api import a2a as a2a_api
from app.config import get_settings


# ════════════════════════════════════════════════════════════════
# BUG-28 /api/health/detail 隐瞒降级（收紧：配置告警不触发 503）
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_health_detail_exposes_explicit_degraded_flag(client: AsyncClient):
    """显式输出 degraded / warnings / dependency_errors / readiness_impact。

    HTTP 状态码只由 dependency_errors（readiness_impact）决定，配置告警保持 200。
    """
    resp = await client.get("/api/health/detail")
    body = resp.json()
    assert isinstance(body["degraded"], bool)
    for key in ("degraded_reasons", "warnings", "dependency_errors"):
        assert isinstance(body[key], list)
    assert isinstance(body["readiness_impact"], bool)
    assert body["status"] in ("ok", "degraded")
    assert body["degraded"] == (body["status"] != "ok")
    assert body["readiness_impact"] == bool(body["dependency_errors"])
    assert resp.status_code == (503 if body["readiness_impact"] else 200)


@pytest.mark.asyncio
async def test_health_detail_configuration_warning_keeps_http_200(client: AsyncClient, monkeypatch):
    """① vault 未配但依赖全正常 → 200 + degraded=true + warnings 非空 + readiness_impact=false。

    team-lead 收紧规格：配置缺失不得做成生产可用性回退（LB 会因 503 摘除实例）。
    """
    from app.services import secret_manager as sm_mod

    monkeypatch.setattr(sm_mod.settings, "vault_url", "")
    monkeypatch.setattr(sm_mod.settings, "vault_token", "")
    sm_mod.secret_manager._cached_secrets.clear()
    resp = await client.get("/api/health/detail")
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True
    assert body["readiness_impact"] is False
    assert body["dependency_errors"] == []
    assert body["warnings"], "配置告警必须如实列出"
    for reason in (
        "vault_not_configured",
        "no_cached_secrets",
        "ecosystem_public_key_unavailable",
        "secret_manager_inactive",
    ):
        assert reason in body["warnings"]
        assert reason in body["degraded_reasons"]
    assert body["checks"]["database"]["status"] == "ok"


@pytest.mark.asyncio
async def test_health_detail_dependency_error_forces_503(client: AsyncClient, monkeypatch):
    """② secret_manager 抛异常 → 503 + degraded（「依赖异常→503」断言按新语义保留）。"""
    from app.services import secret_manager as sm_mod

    def _boom():
        raise RuntimeError("vault dependency down")

    monkeypatch.setattr(sm_mod.secret_manager, "get_health_info", _boom)
    resp = await client.get("/api/health/detail")
    assert resp.status_code == 503
    body = resp.json()
    assert body["degraded"] is True
    assert body["readiness_impact"] is True
    assert body["checks"]["secret_manager"]["status"] == "error"
    assert "secret_manager_error" in body["dependency_errors"]
    assert "secret_manager_error" in body["degraded_reasons"]
    # secret_manager 依赖本身不可用时，配置态信息不可知，warnings 允许为空
    assert isinstance(body["warnings"], list)


@pytest.mark.asyncio
async def test_health_detail_db_dependency_error_returns_503(client: AsyncClient, monkeypatch):
    """② 补强：模拟 db 依赖抛异常 → 503 + degraded=true + readiness_impact=true。"""

    class _BoomConn:
        async def __aenter__(self):
            raise RuntimeError("db down")

        async def __aexit__(self, *args):
            return False

    class _FakeEngine:
        def connect(self):
            return _BoomConn()

    monkeypatch.setattr("app.database.engine", _FakeEngine())
    resp = await client.get("/api/health/detail")
    assert resp.status_code == 503
    body = resp.json()
    assert body["degraded"] is True
    assert body["readiness_impact"] is True
    assert "database_error" in body["dependency_errors"]
    assert body["checks"]["database"]["status"] == "error"
    # 依赖故障与配置告警并存：503 由依赖故障决定，配置告警仍如实保留
    assert "vault_not_configured" in body["warnings"]


# ════════════════════════════════════════════════════════════════
# BUG-29 A2A JSON-RPC 边界（RequestValidationError → JSON-RPC 错误对象）
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_a2a_missing_method_returns_jsonrpc_invalid_request(client: AsyncClient, auth_headers: dict):
    """缺 method 时不得返回私有 {success,error,...} HTTP 422 信封。"""
    resp = await client.post(
        "/api/a2a",
        json={"jsonrpc": "2.0", "id": 9, "params": {"message": "hi"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 9
    assert body["error"]["code"] == -32600
    assert "success" not in body and "fields" not in body


@pytest.mark.asyncio
async def test_a2a_params_not_dict_returns_jsonrpc_invalid_params(client: AsyncClient, auth_headers: dict):
    """params 非 dict → -32602 Invalid params。"""
    resp = await client.post(
        "/api/a2a",
        json={"jsonrpc": "2.0", "id": 10, "method": "message/send", "params": "oops"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["error"]["code"] == -32602
    assert resp.json()["id"] == 10


@pytest.mark.asyncio
async def test_a2a_jsonrpc_non_string_returns_jsonrpc_invalid_request(client: AsyncClient, auth_headers: dict):
    """jsonrpc 非字符串 → -32600 Invalid Request，且带回请求的 id。"""
    resp = await client.post(
        "/api/a2a",
        json={"jsonrpc": 2, "id": 11, "method": "message/send", "params": {"message": "hi"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["error"]["code"] == -32600
    assert body["id"] == 11


# ════════════════════════════════════════════════════════════════
# B7 / BUG-31 A2A error.message 与 message 结构化文本
# ════════════════════════════════════════════════════════════════


def _a2a_client(monkeypatch, send_impl):
    app = FastAPI()
    app.include_router(a2a_api.router, prefix="/api")
    app.dependency_overrides[a2a_api.get_current_user] = lambda: SimpleNamespace(id="u1", role="user")
    app.dependency_overrides[a2a_api.get_db] = lambda: None
    monkeypatch.setattr(a2a_api, "send_task", send_impl)
    return TestClient(app)


_VALID = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {"message": "hi"},
}


def test_a2a_http_error_detail_dict_has_no_python_repr(monkeypatch):
    """B7：detail 为 dict 时 error.message 不得是 Python repr。"""
    async def _deny(request, user, db):
        raise HTTPException(status_code=403, detail={"message": "handshake required", "code": 7})

    resp = _a2a_client(monkeypatch, _deny).post("/api/a2a", json=_VALID)
    msg = resp.json()["error"]["message"]
    assert "handshake required" in msg
    assert "{'" not in msg
    assert '"code"' not in msg


def test_a2a_http_error_detail_list_is_structured_json(monkeypatch):
    """B7：detail 为 list 时用结构化 JSON 文本而非 str(list) 的 Python repr。"""
    async def _deny(request, user, db):
        raise HTTPException(status_code=403, detail=[{"msg": "a"}, {"msg": "b"}])

    resp = _a2a_client(monkeypatch, _deny).post("/api/a2a", json=_VALID)
    msg = resp.json()["error"]["message"]
    assert json.loads(msg) == [{"msg": "a"}, {"msg": "b"}]
    assert "'msg'" not in msg


def test_a2a_message_nested_object_is_structured_text():
    """BUG-31：message parts[].text 为对象时输出 JSON，不产生 Python repr。"""
    text = a2a_api._extract_message_text(
        {"message": {"parts": [{"text": {"nested": 1}}]}}
    )
    assert text == '{"nested": 1}'
    assert "'nested'" not in text


def test_a2a_message_list_is_structured_text():
    text = a2a_api._extract_message_text({"message": [{"text": "A"}, {"text": "B"}]})
    assert json.loads(text) == [{"text": "A"}, {"text": "B"}]
    assert "'text'" not in text


# ════════════════════════════════════════════════════════════════
# BUG-21 IFC 501 语义 + body 不再静默丢弃（B8 前后端对齐）
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ifc_export_501_semantics_and_body_received(client: AsyncClient, auth_headers: dict, monkeypatch):
    """501 状态码与 body 语义一致；Body() 正常接收前端 include_furniture/lod_level。"""
    import app.api.ifc_export as ifc_mod

    monkeypatch.setattr(ifc_mod, "_IFCOPENSHELL_AVAILABLE", False)
    proj = await client.post(
        "/api/projects", json={"name": "IFC契约", "total_area": 10.0}, headers=auth_headers
    )
    assert proj.status_code in (200, 201)
    pid = proj.json()["id"]

    resp = await client.post(
        f"/api/bim/export/structural/{pid}",
        json={"include_furniture": True, "lod_level": "LOD350"},
        headers=auth_headers,
    )
    assert resp.status_code == 501
    body = resp.json()
    assert body["error"] == "not_implemented"
    assert "ifcopenshell" in str(body["detail"])

    # 非法 body 触发 422 → 证明 Body() 真的在解析，而非 Depends(lambda) 忽略 body
    bad = await client.post(
        f"/api/bim/export/structural/{pid}",
        json={"lod_level": 123},
        headers=auth_headers,
    )
    assert bad.status_code == 422


def test_ifc_export_routes_register_body_params():
    """静态契约：两个 IFC 端点的 request 参数注册在 body_params（非 Depends）。"""
    from app.api.ifc_export import router

    endpoints = [r for r in router.routes if getattr(r, "methods", None) and "POST" in r.methods]
    assert len(endpoints) == 2
    for route in endpoints:
        body_names = [p.name for p in route.dependant.body_params]
        assert "request" in body_names, f"{route.path} 未把 request 注册为 body 参数"


# ════════════════════════════════════════════════════════════════
# BUG-27 生态公钥 env 回退 / source 标注 / 死代码如实标注
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ecosystem_public_key_env_fallback(monkeypatch):
    """Vault 未配时回退读 ECOSYSTEM_PUBLIC_PASERK，health 标 source=env。"""
    from app.services import secret_manager as sm_mod

    placeholder = "k4.public.fix-home-placeholder-not-a-real-key"
    monkeypatch.setattr(sm_mod.settings, "ecosystem_public_paserk", "")
    monkeypatch.setattr(sm_mod.settings, "vault_url", "")
    monkeypatch.setattr(sm_mod.settings, "vault_token", "")
    monkeypatch.setenv("ECOSYSTEM_PUBLIC_PASERK", placeholder)

    assert sm_mod.secret_manager.get_ecosystem_public_key_source() == "env"
    assert await sm_mod.secret_manager.get_ecosystem_public_paserk() == placeholder
    info = sm_mod.secret_manager.get_health_info()
    assert info["ecosystem_public_key_source"] == "env"
    # get_secret() 全 app 零业务调用 → 如实标注，不假装已启用
    assert info["secret_manager_active"] is False


@pytest.mark.asyncio
async def test_ecosystem_public_key_unavailable_when_unset(monkeypatch):
    """未声明 env 且 Vault 未配 → source=unavailable，验签链拿不到公钥（如实）。"""
    from app.services import secret_manager as sm_mod

    monkeypatch.delenv("ECOSYSTEM_PUBLIC_PASERK", raising=False)
    monkeypatch.setattr(sm_mod.settings, "ecosystem_public_paserk", "")
    monkeypatch.setattr(sm_mod.settings, "vault_url", "")
    monkeypatch.setattr(sm_mod.settings, "vault_token", "")

    assert sm_mod.secret_manager.get_ecosystem_public_key_source() == "unavailable"
    assert await sm_mod.secret_manager.get_ecosystem_public_paserk() is None


# ════════════════════════════════════════════════════════════════
# BUG-31 / B5 指纹轮换实时性（health 清缓存调用点）
# ════════════════════════════════════════════════════════════════


def test_fingerprint_reflects_rotation_via_health(monkeypatch):
    """轮换验签公钥后，两次 health 读数必须不同（lru_cache 已由 health 清理）。"""
    import hashlib

    from app.auth import paseto_handler
    from app.services import secret_manager as sm_mod

    keys = iter([b"key-A" * 6, b"key-B" * 6])
    monkeypatch.setattr(
        paseto_handler, "_get_verify_key", lambda: SimpleNamespace(key=next(keys))
    )
    sm_mod.clear_fingerprint_cache()
    first = sm_mod.secret_manager.get_health_info()["paseto_key_fingerprint"]
    second = sm_mod.secret_manager.get_health_info()["paseto_key_fingerprint"]
    assert first == hashlib.sha256(b"key-A" * 6).hexdigest()[:8]
    assert second == hashlib.sha256(b"key-B" * 6).hexdigest()[:8]
    assert first != second


# ════════════════════════════════════════════════════════════════
# BUG-30 matter_enabled 默认诚实关闭
# ════════════════════════════════════════════════════════════════


def test_matter_flag_defaults_false():
    """Matter 下游仍为 stub，默认不得为 True（.env 未覆盖，已核实）。"""
    assert get_settings().matter_enabled is False

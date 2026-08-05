"""GB/Z 185 智能体身份码/ACDL 预研测试（v1.9.0）

覆盖:
- generate_aid: 28 位纯数字 / 幂等 / Luhn 校验位正确（用实现自身反向验证）
- generate_aid: 未知 agent 回退类型码 "00"；非法 security_level 回退 "2"
- build_acdl: schema=GB-Z-185.4 / agent.agent_id 28 位 / capabilities 非空
- get_agent_identity: 组装正确
- list_supported_agents: total > 0
- 端点集成: flag 关闭 404（诚实降级）/ flag 开启 200 且 body.aid 长度 28 / 未认证 401

遵循项目红线：仅用 monkeypatch.setattr(get_settings(), ...) 切换 flag，
禁止调用 get_settings.cache_clear()（会导致跨文件测试隔离失败）。
"""

import pytest
from httpx import AsyncClient

from app.api import agent_identity as agent_identity_api
from app.config import get_settings
from app.main import app
from app.services.agent_identity_card import (
    _luhn_check_digit,
    build_acdl,
    generate_aid,
    get_agent_identity,
    list_supported_agents,
)

# ── 路由注册 ──────────────────────────────────────────────
# 主代理尚未在 main.py 注册 agent_identity 路由，测试时临时挂载
# （与 tests/test_ai_render.py 相同的引导模式）。
_gbz_registered = any(
    getattr(r, "path", "") == "/api/agents/identity/{name}" for r in app.routes
)
if not _gbz_registered:
    app.include_router(agent_identity_api.router, prefix="/api")


# ── 辅助函数 ──────────────────────────────────────────────


async def _auth_headers(client: AsyncClient, phone: str = "13918518501") -> dict:
    """注册用户并返回 Authorization headers（端点测试需通过 PASETO 认证）"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "GBZ185测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── generate_aid：28 位纯数字 / 幂等 / Luhn 校验位 ─────────


def test_generate_aid_28_digits_idempotent_and_luhn():
    """generate_aid("designer") 返回 28 位纯数字；两次调用结果相同（幂等）；
    Luhn 校验位正确（用实现自身反向验证）"""
    aid = generate_aid("designer")
    assert len(aid) == 28
    assert aid.isdigit()
    # 幂等
    assert aid == generate_aid("designer")
    # Luhn：前 27 位计算的校验位 == 第 28 位
    assert _luhn_check_digit(aid[:-1]) == aid[-1]
    # 结构：9 厂商 + 2 类型 + 1 分级 + 15 序列 + 1 校验
    assert aid[9:11] == "01"  # designer 类型码


# ── generate_aid：未知 agent / 非法 security_level 回退 ───


def test_generate_aid_unknown_agent_type_code_00():
    """未知 agent 名回退类型码 "00"（其余结构不变）"""
    aid = generate_aid("no_such_agent")
    assert len(aid) == 28
    assert aid[9:11] == "00"


def test_generate_aid_invalid_security_level_falls_back():
    """非法 security_level 回退 "2"；合法分级（1/4）原样保留"""
    assert generate_aid("designer", security_level="9")[11] == "2"
    assert generate_aid("designer", security_level="4")[11] == "4"
    assert generate_aid("designer", security_level="1")[11] == "1"


# ── build_acdl ────────────────────────────────────────────


def test_build_acdl_structure():
    """build_acdl 返回 schema=GB-Z-185.4、agent.agent_id 长度 28、capabilities 非空"""
    acdl = build_acdl("designer")
    assert acdl["schema"] == "GB-Z-185.4"
    assert acdl["acdl_version"] == "1.0"
    agent = acdl["agent"]
    assert len(agent["agent_id"]) == 28
    assert agent["agent_id"].isdigit()
    assert agent["name"] == "designer"
    assert agent["security_level"] == "L2"
    assert isinstance(agent["capabilities"], list)
    assert agent["capabilities"]
    # interface 契约（GB/Z 185.4）
    assert agent["interface"]["discovery"] == "a2a"
    assert agent["interface"]["transport"] == ["json-rpc"]
    assert agent["interface"]["endpoint_hint"] == "本平台内部"
    # 未知 agent 也给出通用默认能力（诚实降级，非空）
    assert build_acdl("no_such_agent")["agent"]["capabilities"]
    # 显式传入 capabilities 覆盖默认
    assert build_acdl("designer", capabilities=["自定义能力"])["agent"]["capabilities"] == ["自定义能力"]


# ── get_agent_identity ────────────────────────────────────


def test_get_agent_identity_assembly():
    """get_agent_identity 组装正确：aid 28 位且与 acdl.agent.agent_id 一致"""
    card = get_agent_identity("designer")
    assert card["agent_name"] == "designer"
    assert len(card["aid"]) == 28
    assert card["aid"].isdigit()
    assert card["acdl"]["agent"]["agent_id"] == card["aid"]
    assert card["acdl"]["schema"] == "GB-Z-185.4"
    assert card["acdl"]["agent"]["capabilities"]


# ── list_supported_agents ─────────────────────────────────


def test_list_supported_agents():
    """list_supported_agents total > 0，且覆盖 11 个执行/运营 Agent"""
    result = list_supported_agents()
    assert result["total"] > 0
    assert len(result["agents"]) == result["total"]
    names = {a["name"] for a in result["agents"]}
    assert {
        "designer", "budget", "procurement", "construction",
        "qa_inspector", "settlement", "concierge",
        "growth", "marketing", "competitor_research", "finance_recon",
    } <= names
    for a in result["agents"]:
        assert len(a["type_code"]) == 2
        assert a["type_code"].isdigit()
        assert a["security_level"] == "2"


# ── 端点集成测试（flag 门控 + 认证）────────────────────────


@pytest.mark.asyncio
async def test_endpoint_unauthorized(client: AsyncClient):
    """未认证用户不能查询身份卡（401）"""
    resp = await client.get("/api/agents/identity/designer")
    assert resp.status_code == 401

    resp = await client.get("/api/agents/identity")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_endpoint_flag_off_404(client: AsyncClient, monkeypatch):
    """flag 关闭时新 API 端点返回 404，不暴露能力（诚实降级）"""
    monkeypatch.setattr(get_settings(), "gbz185_agent_card_enabled", False)
    headers = await _auth_headers(client)

    resp = await client.get("/api/agents/identity/designer", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "GBZ185 身份卡未启用"

    resp = await client.get("/api/agents/identity", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "GBZ185 身份卡未启用"


@pytest.mark.asyncio
async def test_endpoint_flag_on_200(client: AsyncClient, monkeypatch):
    """flag 开启时 GET /api/agents/identity/designer → 200 且 body.aid 长度 28"""
    monkeypatch.setattr(get_settings(), "gbz185_agent_card_enabled", True)
    headers = await _auth_headers(client, "13918518502")

    resp = await client.get("/api/agents/identity/designer", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["aid"]) == 28
    assert data["aid"].isdigit()
    assert data["acdl"]["agent"]["agent_id"] == data["aid"]
    assert data["acdl"]["agent"]["security_level"] == "L2"
    assert data["acdl"]["schema"] == "GB-Z-185.4"
    assert data["acdl"]["agent"]["capabilities"]


@pytest.mark.asyncio
async def test_endpoint_list_flag_on(client: AsyncClient, monkeypatch):
    """flag 开启时列表端点返回 agents 列表与 total"""
    monkeypatch.setattr(get_settings(), "gbz185_agent_card_enabled", True)
    headers = await _auth_headers(client, "13918518503")

    resp = await client.get("/api/agents/identity", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    assert len(data["agents"]) == data["total"]
    assert data["agents"][0]["type_code"].isdigit()

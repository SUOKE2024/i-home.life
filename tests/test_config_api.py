"""Tests for config API endpoints.

覆盖端点:
- GET /api/config/feature-flags  (获取 feature flags)

注：feature-flags 为公开端点（无认证），Flutter main() 与 Web 控制台
均在登录前调用以决定按需加载策略。详见 app/api/config.py 头注释。
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_config_public_no_auth(client: AsyncClient):
    """未认证请求 feature-flags 返回 200（公开端点，登录前需拉取）"""
    resp = await client.get("/api/config/feature-flags")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_get_feature_flags(client: AsyncClient, auth_headers: dict):
    """获取 feature flags（带 token 仍应 200）"""
    resp = await client.get("/api/config/feature-flags", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_feature_flags_contains_core_keys(client: AsyncClient):
    """feature flags 包含核心 key（公开访问）"""
    resp = await client.get("/api/config/feature-flags")
    assert resp.status_code == 200
    data = resp.json()
    assert "filament_enabled" in data
    assert "opencascade_enabled" in data
    assert isinstance(data["filament_enabled"], bool)


@pytest.mark.asyncio
async def test_feature_flags_contains_eval(client: AsyncClient):
    """feature flags 包含评估相关 key（公开访问）"""
    resp = await client.get("/api/config/feature-flags")
    assert resp.status_code == 200
    data = resp.json()
    assert "eval_enabled" in data
    assert "model_spec_enabled" in data
    assert "agent_learning_enabled" in data


@pytest.mark.asyncio
async def test_feature_flags_contains_mcp(client: AsyncClient):
    """feature flags 包含 MCP 相关 key（公开访问）"""
    resp = await client.get("/api/config/feature-flags")
    assert resp.status_code == 200
    data = resp.json()
    assert "mcp_enabled" in data
    assert "ai_render_enabled" in data
    assert "voice_emotion_routing_enabled" in data


@pytest.mark.asyncio
async def test_feature_flags_public_access(client: AsyncClient):
    """无 token 访问 feature-flags 应成功（登录前客户端需拉取特性标志）"""
    resp = await client.get("/api/config/feature-flags")
    assert resp.status_code == 200
    data = resp.json()
    assert "console_v2_enabled" in data

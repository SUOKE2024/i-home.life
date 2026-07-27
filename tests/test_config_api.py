"""Tests for config API endpoints.

覆盖端点:
- GET /api/config/feature-flags  (获取 feature flags)
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_config_requires_auth(client: AsyncClient):
    """未认证请求配置接口返回 401"""
    resp = await client.get("/api/config/feature-flags")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_feature_flags(client: AsyncClient, auth_headers: dict):
    """获取 feature flags"""
    resp = await client.get("/api/config/feature-flags", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_feature_flags_contains_core_keys(client: AsyncClient, auth_headers: dict):
    """feature flags 包含核心 key"""
    resp = await client.get("/api/config/feature-flags", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "filament_enabled" in data
    assert "opencascade_enabled" in data
    assert isinstance(data["filament_enabled"], bool)


@pytest.mark.asyncio
async def test_feature_flags_contains_eval(client: AsyncClient, auth_headers: dict):
    """feature flags 包含评估相关 key"""
    resp = await client.get("/api/config/feature-flags", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "eval_enabled" in data
    assert "model_spec_enabled" in data
    assert "agent_learning_enabled" in data


@pytest.mark.asyncio
async def test_feature_flags_contains_mcp(client: AsyncClient, auth_headers: dict):
    """feature flags 包含 MCP 相关 key"""
    resp = await client.get("/api/config/feature-flags", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "mcp_enabled" in data
    assert "ai_render_enabled" in data
    assert "voice_emotion_routing_enabled" in data


@pytest.mark.asyncio
async def test_feature_flags_no_auth_rejected(client: AsyncClient):
    """无 token 访问配置端点返回 401"""
    resp = await client.get("/api/config/feature-flags")
    assert resp.status_code == 401

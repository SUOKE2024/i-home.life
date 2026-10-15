"""LLM provider 生命周期一致性测试（AI 产品治理 · 契约 2，app/agents/base.py）。

覆盖：注册表 provider 均已登记生命周期状态 / active provider 配置完整 /
降级链仅引用 active provider / retired provider 误入降级链会被校验器拦截。
外部平台（豆包/千问/元器/扣子/Dify 等）停服时置 retired 即可安全摘除。
"""
from app.agents.base import (
    DEFAULT_FALLBACK_CHAIN,
    PROVIDER_REGISTRY,
    PROVIDER_STATUS,
    validate_provider_config,
)


def test_provider_config_consistent():
    assert validate_provider_config() == []


def test_all_registry_providers_declare_status():
    for name in PROVIDER_REGISTRY:
        assert name in PROVIDER_STATUS, f"provider '{name}' 未登记生命周期状态"


def test_fallback_chain_uses_active_providers_only():
    for name in DEFAULT_FALLBACK_CHAIN:
        assert PROVIDER_STATUS.get(name) == "active", f"降级链引用非 active provider：'{name}'"


def test_retired_provider_in_chain_is_flagged(monkeypatch):
    """退休 provider 仍留在降级链时，校验器必须报出（防"外部平台下线未摘链"）。"""
    monkeypatch.setitem(PROVIDER_STATUS, "doubao", "retired")
    findings = validate_provider_config()
    assert any("doubao" in f for f in findings)


def test_active_provider_missing_config_is_flagged(monkeypatch):
    monkeypatch.delitem(PROVIDER_REGISTRY["glm"], "api_key")
    findings = validate_provider_config()
    assert any("glm" in f and "api_key" in f for f in findings)

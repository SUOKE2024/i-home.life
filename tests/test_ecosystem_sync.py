"""跨品牌供应商同步 helper：未配置跳过、配置后推送 payload。"""
from types import SimpleNamespace

import pytest

from app.config import get_settings
from app.services import ecosystem_sync


def _supplier():
    return SimpleNamespace(
        id="sup-1",
        name="昆明建材",
        category="主材",
        is_active=True,
        is_verified=False,
    )


@pytest.mark.asyncio
async def test_skip_when_not_configured(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ecosystem_sync_url", "", raising=False)
    monkeypatch.setattr(settings, "ecosystem_sync_key", "", raising=False)

    class _Boom:
        def __init__(self, *args, **kwargs):
            raise AssertionError("未配置时不应发起网络请求")

    monkeypatch.setattr(ecosystem_sync.httpx, "AsyncClient", _Boom)
    assert await ecosystem_sync.push_supplier(_supplier()) is False


@pytest.mark.asyncio
async def test_push_payload_when_configured(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ecosystem_sync_url", "https://life.example", raising=False)
    monkeypatch.setattr(settings, "ecosystem_sync_key", "k_test", raising=False)
    captured = {}

    class _Resp:
        status_code = 200

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _Resp()

    monkeypatch.setattr(ecosystem_sync.httpx, "AsyncClient", _Client)
    assert await ecosystem_sync.push_supplier(_supplier()) is True

    assert captured["url"] == "https://life.example/api/v1/ecosystem/suppliers/batch-link"
    item = captured["json"]["items"][0]
    assert item["brand"] == "ihome"
    assert item["local_id"] == "sup-1"
    assert captured["headers"]["X-Ecosystem-Sync-Key"] == "k_test"

"""跨品牌供应商同步 helper：未配置跳过、配置后推送 payload、状态可观测。"""
import hashlib
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


@pytest.fixture(autouse=True)
def _clean_state():
    ecosystem_sync.reset_status()
    yield
    ecosystem_sync.reset_status()


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
    # 关键：跳过要留痕，不能"安静空转"
    assert ecosystem_sync.sync_status()["skipped_unconfigured"] == 1
    assert ecosystem_sync.sync_status()["status"] == "unconfigured"


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

    status = ecosystem_sync.sync_status()
    assert status["status"] == "ok"
    assert status["ok"] == 1 and status["failed"] == 0


@pytest.mark.asyncio
async def test_status_reports_config_and_key_fingerprint_only(monkeypatch):
    """健康详情只暴露配置是否存在 + 密钥指纹，绝不回显密钥明文。"""
    settings = get_settings()
    monkeypatch.setattr(settings, "ecosystem_sync_url", "https://life.example", raising=False)
    monkeypatch.setattr(settings, "ecosystem_sync_key", "super-secret-key", raising=False)

    status = ecosystem_sync.sync_status()
    assert status["configured"] is True
    assert status["status"] == "idle"  # 本进程还没推过
    assert status["target"] == "https://life.example"
    assert status["key_fingerprint"] == hashlib.sha256(b"super-secret-key").hexdigest()[:8]
    assert "super-secret-key" not in str(status)


@pytest.mark.asyncio
async def test_403_marks_degraded_and_points_at_key_mismatch(monkeypatch):
    """403 是配置错（key 不一致）而非瞬时故障，状态要能区分出来。"""
    settings = get_settings()
    monkeypatch.setattr(settings, "ecosystem_sync_url", "https://life.example", raising=False)
    monkeypatch.setattr(settings, "ecosystem_sync_key", "k_test", raising=False)

    class _Resp:
        status_code = 403

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            return _Resp()

    monkeypatch.setattr(ecosystem_sync.httpx, "AsyncClient", _Client)
    assert await ecosystem_sync.push_supplier(_supplier()) is False

    status = ecosystem_sync.sync_status()
    assert status["status"] == "degraded"
    assert status["failed"] == 1
    assert "403" in (status["last_error"] or "")


@pytest.mark.asyncio
async def test_network_error_records_last_error_without_raising(monkeypatch):
    """best-effort 语义不变：网络异常不抛出，但要留下 last_error。"""
    settings = get_settings()
    monkeypatch.setattr(settings, "ecosystem_sync_url", "https://life.example", raising=False)
    monkeypatch.setattr(settings, "ecosystem_sync_key", "k_test", raising=False)

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            raise TimeoutError("connect timeout")

    monkeypatch.setattr(ecosystem_sync.httpx, "AsyncClient", _Client)
    assert await ecosystem_sync.push_supplier(_supplier()) is False
    status = ecosystem_sync.sync_status()
    assert status["status"] == "degraded"
    assert "TimeoutError" in (status["last_error"] or "")

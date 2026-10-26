"""新需求运营提醒契约测试。

两件事必须成立：
  1. 业主提交的线索不能「无声沉底」—— 建单必须触发运营侧提醒，且带上可回访的手机号；
  2. 提醒通道不能绑架业务 —— webhook 挂了、配错了，建单仍要 201，不能回滚业主需求。
"""
import pytest
from httpx import AsyncClient

from app.services import ops_alert_service


def test_mask_phone_for_logs():
    """日志里手机号必须脱敏；非标准号码不打印原值。"""
    assert ops_alert_service.mask_phone("13700137000") == "137****7000"
    assert ops_alert_service.mask_phone(None) == "未填写"
    assert ops_alert_service.mask_phone("") == "未填写"
    assert ops_alert_service.mask_phone("+8613700137000") == "已填写"


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


@pytest.mark.asyncio
async def test_notify_posts_markdown_with_contact(monkeypatch):
    """配置了 webhook 就要真的推出去，且正文含完整手机号（运营要回访）。"""
    settings = ops_alert_service.get_settings()
    monkeypatch.setattr(settings, "ops_alert_enabled", True, raising=False)
    monkeypatch.setattr(settings, "ops_alert_webhook", "https://example.invalid/hook", raising=False)

    posted: list[tuple[str, dict]] = []

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            posted.append((url, json or {}))
            return _FakeResponse({"errcode": 0, "errmsg": "ok"})

    monkeypatch.setattr(ops_alert_service.httpx, "AsyncClient", _FakeClient)

    ok = await ops_alert_service.notify_new_demand(
        project_id="p-1",
        name="春城慧谷 3 栋 1202",
        project_type="bathroom",
        contact_name="王女士",
        contact_phone="13700137000",
        total_area=98.0,
    )

    assert ok is True
    assert len(posted) == 1
    url, payload = posted[0]
    assert url.endswith("/hook")
    assert payload["msgtype"] == "markdown"
    content = payload["markdown"]["content"]
    assert "春城慧谷 3 栋 1202" in content
    assert "卫生间改造" in content
    assert "13700137000" in content


@pytest.mark.asyncio
async def test_notify_without_webhook_is_silent_success(monkeypatch):
    """未配置通道：返回 False 但不抛异常（调用方据此只记日志）。"""
    settings = ops_alert_service.get_settings()
    monkeypatch.setattr(settings, "ops_alert_enabled", True, raising=False)
    monkeypatch.setattr(settings, "ops_alert_webhook", "", raising=False)

    assert await ops_alert_service.notify_new_demand(project_id="p-2", name="无通道需求") is False


@pytest.mark.asyncio
async def test_webhook_failure_does_not_break_notify(monkeypatch):
    """通道 5xx 时 notify 自行吞掉异常，返回 False。"""
    settings = ops_alert_service.get_settings()
    monkeypatch.setattr(settings, "ops_alert_enabled", True, raising=False)
    monkeypatch.setattr(settings, "ops_alert_webhook", "https://example.invalid/hook", raising=False)

    class _BoomClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            raise ops_alert_service.httpx.ConnectError("boom")

    monkeypatch.setattr(ops_alert_service.httpx, "AsyncClient", _BoomClient)

    assert await ops_alert_service.notify_new_demand(project_id="p-3", name="通道故障需求") is False


async def _register(client: AsyncClient, phone: str) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "运营提醒测试", "password": "test123456"},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_project_create_triggers_ops_alert(client: AsyncClient, monkeypatch):
    """小程序提交需求 → 建单即触发运营提醒。"""
    token = await _register(client, "13900004001")
    calls: list[dict] = []

    async def _fake_notify(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr("app.api.projects.notify_new_demand", _fake_notify)

    resp = await client.post(
        "/api/projects",
        json={
            "name": "春城慧谷 5 栋 0901",
            "project_type": "bathroom",
            "contact_name": "李先生",
            "contact_phone": "13700137001",
            "description": "意向套餐：适老卫浴改造",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    assert len(calls) == 1, "建单必须触发一次运营提醒"
    assert calls[0]["project_id"] == resp.json()["id"]
    assert calls[0]["contact_phone"] == "13700137001"


@pytest.mark.asyncio
async def test_project_create_survives_broken_alert_channel(client: AsyncClient, monkeypatch):
    """提醒通道炸了也必须 201：业主需求已落库，不能因通知失败回滚。"""
    token = await _register(client, "13900004002")

    async def _boom(**kwargs):
        raise RuntimeError("webhook exploded")

    monkeypatch.setattr("app.api.projects.notify_new_demand", _boom)

    resp = await client.post(
        "/api/projects",
        json={"name": "通道故障也要建单"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["phase"] == "initiation"

"""微信小程序（业主端）登录与手机号绑定测试。

覆盖：flag 门控 503 / 静默登录建号与复用 / openid 命名空间前缀 / 不泄露 session_key /
微信侧错误 502 / openid 缺失 / 手机号绑定成功 / 非小程序账号拒绝 / 已绑定拒绝 /
access_token 失效自动刷新重试 / 凭证缓存命中。
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.auth.paseto_handler import create_token
from app.config import get_settings
from app.models.user import User
from app.services import wechat_miniprogram_service, wechat_oauth_service
from app.services.user_service import get_or_create_wechat_user


def _enable_miniprogram(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "miniprogram_login_enabled", True)
    monkeypatch.setattr(get_settings(), "miniprogram_phone_enabled", True)
    monkeypatch.setattr(get_settings(), "miniprogram_app_id", "wxtestmp00000001")
    monkeypatch.setattr(get_settings(), "miniprogram_app_secret", "test-mp-secret-not-real")


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_miniprogram_login_disabled_returns_503(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "miniprogram_login_enabled", False)
    resp = await client.post("/api/auth/miniprogram/login", json={"code": "c"})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_miniprogram_login_creates_and_reuses_user(
    client: AsyncClient, db_session, monkeypatch
):
    _enable_miniprogram(monkeypatch)

    async def fake_session(code: str) -> dict:
        assert code in ("code-1", "code-2")
        return {"openid": "mp-openid-001", "unionid": "union-mp-001"}

    monkeypatch.setattr(wechat_miniprogram_service, "code_to_session", fake_session)

    resp = await client.post(
        "/api/auth/miniprogram/login", json={"code": "code-1", "nickname": "小程序业主"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"].startswith("v4.public.")
    assert data["user"]["role"] == "homeowner"
    assert data["user"]["phone"] is None
    assert data["user"]["name"] == "小程序业主"
    assert "session_key" not in data
    first_id = data["user"]["id"]

    # 同 openid 二次登录复用同一账号
    resp2 = await client.post("/api/auth/miniprogram/login", json={"code": "code-2"})
    assert resp2.status_code == 200
    assert resp2.json()["user"]["id"] == first_id

    count = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()
    assert count == 1
    user = (
        await db_session.execute(
            select(User).where(User.wechat_openid == "mp:mp-openid-001")
        )
    ).scalar_one()
    assert user.wechat_unionid == "union-mp-001"
    assert user.hashed_password is None


@pytest.mark.asyncio
async def test_miniprogram_login_wechat_error(client: AsyncClient, monkeypatch):
    _enable_miniprogram(monkeypatch)

    async def fake_session(code: str) -> dict:
        raise wechat_miniprogram_service.WeChatMiniProgramError("微信登录失败(40029): invalid code")

    monkeypatch.setattr(wechat_miniprogram_service, "code_to_session", fake_session)
    resp = await client.post("/api/auth/miniprogram/login", json={"code": "bad"})
    assert resp.status_code == 502
    assert "40029" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_miniprogram_login_missing_openid(client: AsyncClient, monkeypatch):
    _enable_miniprogram(monkeypatch)

    async def fake_session(code: str) -> dict:
        raise wechat_miniprogram_service.WeChatMiniProgramError("微信未返回 openid，登录失败")

    monkeypatch.setattr(wechat_miniprogram_service, "code_to_session", fake_session)
    resp = await client.post("/api/auth/miniprogram/login", json={"code": "c"})
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_miniprogram_bind_phone_success(client: AsyncClient, db_session, monkeypatch):
    _enable_miniprogram(monkeypatch)
    user = await get_or_create_wechat_user(
        db_session, "mp:mp-openid-bind", None, "小程序用户", None
    )
    token = create_token(user.id, user.role)

    async def fake_phone(code: str) -> str:
        assert code == "phone-code-1"
        return "13800138000"

    monkeypatch.setattr(wechat_miniprogram_service, "get_phone_number", fake_phone)
    resp = await client.post(
        "/api/auth/miniprogram/bind-phone",
        json={"code": "phone-code-1"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["phone"] == "13800138000"
    await db_session.refresh(user)
    assert user.phone == "13800138000"


@pytest.mark.asyncio
async def test_miniprogram_bind_phone_rejects_web_account(
    client: AsyncClient, db_session, monkeypatch
):
    """非小程序登录账号（网站应用 openid）不得走小程序手机号链路。"""
    _enable_miniprogram(monkeypatch)
    user = await get_or_create_wechat_user(db_session, "web-openid-x", None, "网站用户", None)
    resp = await client.post(
        "/api/auth/miniprogram/bind-phone",
        json={"code": "phone-code-x"},
        headers=_auth_header(create_token(user.id, user.role)),
    )
    assert resp.status_code == 400
    assert "非小程序" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_miniprogram_bind_phone_already_bound(
    client: AsyncClient, db_session, monkeypatch
):
    _enable_miniprogram(monkeypatch)
    user = User(
        id="user-mp-bound",
        phone="13900139000",
        name="已绑定",
        role="homeowner",
        wechat_openid="mp:mp-openid-bound",
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(
        "/api/auth/miniprogram/bind-phone",
        json={"code": "phone-code-2"},
        headers=_auth_header(create_token(user.id, user.role)),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_miniprogram_bind_phone_requires_auth(client: AsyncClient, monkeypatch):
    _enable_miniprogram(monkeypatch)
    resp = await client.post("/api/auth/miniprogram/bind-phone", json={"code": "c"})
    assert resp.status_code == 401


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    """按顺序回放响应的 httpx.AsyncClient 替身。"""

    def __init__(self, payloads: list[dict], *args, **kwargs):
        self._payloads = payloads
        self.posted_params: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, params=None, json=None):
        self.posted_params.append({"url": url, "params": params, "json": json})
        return _FakeResponse(self._payloads.pop(0))


@pytest.mark.asyncio
async def test_get_phone_number_refreshes_token_on_40001(monkeypatch):
    """access_token 失效（40001）须强制刷新后重试一次，不得直接失败。"""
    _enable_miniprogram(monkeypatch)
    wechat_miniprogram_service.reset_access_token_cache()

    payloads = [
        {"errcode": 40001, "errmsg": "invalid credential"},
        {"errcode": 0, "phone_info": {"purePhoneNumber": "13700137000"}},
    ]
    fake = _FakeClient(payloads)

    monkeypatch.setattr(
        wechat_miniprogram_service.httpx, "AsyncClient", lambda *a, **kw: fake
    )

    calls: list[bool] = []

    async def fake_token(force_refresh: bool = False) -> str:
        calls.append(force_refresh)
        return "token-old" if not force_refresh else "token-new"

    monkeypatch.setattr(wechat_miniprogram_service, "get_access_token", fake_token)

    phone = await wechat_miniprogram_service.get_phone_number("phone-code-retry")
    assert phone == "13700137000"
    assert calls == [False, True]
    assert fake.posted_params[0]["params"]["access_token"] == "token-old"
    assert fake.posted_params[1]["params"]["access_token"] == "token-new"


@pytest.mark.asyncio
async def test_get_phone_number_error_propagates(monkeypatch):
    _enable_miniprogram(monkeypatch)
    fake = _FakeClient([{"errcode": 40029, "errmsg": "invalid code"}])
    monkeypatch.setattr(
        wechat_miniprogram_service.httpx, "AsyncClient", lambda *a, **kw: fake
    )

    async def fake_token(force_refresh: bool = False) -> str:
        return "token"

    monkeypatch.setattr(wechat_miniprogram_service, "get_access_token", fake_token)

    with pytest.raises(wechat_miniprogram_service.WeChatMiniProgramError) as exc:
        await wechat_miniprogram_service.get_phone_number("bad-code")
    assert "40029" in str(exc.value)


def test_sanitize_nickname_shared_with_web():
    """昵称清洗复用网站应用实现，避免两套口径。"""
    assert wechat_oauth_service.sanitize_nickname(" 昵称\u0007\n") == "昵称"


@pytest.mark.asyncio
async def test_access_token_uses_stable_token_and_caches(monkeypatch):
    """凭证必须走 stable_token（否则多 worker 互相作废），且命中缓存不重复请求。"""
    _enable_miniprogram(monkeypatch)
    wechat_miniprogram_service.reset_access_token_cache()

    payloads = [{"access_token": "stable-token", "expires_in": 7200}]
    fake = _FakeClient(payloads)
    monkeypatch.setattr(
        wechat_miniprogram_service.httpx, "AsyncClient", lambda *a, **kw: fake
    )

    first = await wechat_miniprogram_service.get_access_token()
    second = await wechat_miniprogram_service.get_access_token()

    assert first == second == "stable-token"
    assert len(fake.posted_params) == 1, "缓存命中不应再次请求微信"
    assert fake.posted_params[0]["url"].endswith("/cgi-bin/stable_token")
    assert fake.posted_params[0]["json"]["force_refresh"] is False

    wechat_miniprogram_service.reset_access_token_cache()

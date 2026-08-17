"""微信开放平台「网站应用」扫码登录测试。

覆盖：flag 门控 503 / 授权链接生成 + state 防 CSRF / code 换 openid 建号与复用 /
昵称清洗 / 微信侧错误 502 / openid 缺失 / 绑定手机号（复用运营商 H5 sp_token 验真）
/ 手机号冲突 / 已绑定拒绝 / 未登录拒绝。
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.auth.paseto_handler import create_token
from app.config import get_settings
from app.models.user import User
from app.services import phone_number_auth_service, wechat_oauth_service
from app.services.user_service import get_or_create_wechat_user


def _enable_wechat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "wechat_oauth_enabled", True)
    monkeypatch.setattr(get_settings(), "wechat_app_id", "wxtestappid123456")
    monkeypatch.setattr(get_settings(), "wechat_app_secret", "test-secret-not-real")
    monkeypatch.setattr(get_settings(), "wechat_redirect_uri", "https://i-home.life/wechat-callback")


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_wechat_disabled_returns_503(client: AsyncClient):
    resp = await client.get("/api/auth/wechat/authorize-url")
    assert resp.status_code == 503
    resp = await client.post("/api/auth/wechat/login", json={"code": "c", "state": "s"})
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_wechat_authorize_url(client: AsyncClient, monkeypatch):
    _enable_wechat(monkeypatch)
    resp = await client.get("/api/auth/wechat/authorize-url")
    assert resp.status_code == 200
    data = resp.json()
    assert "open.weixin.qq.com/connect/qrconnect" in data["url"]
    assert "appid=wxtestappid123456" in data["url"]
    assert "scope=snsapi_login" in data["url"]
    # state 必须能通过服务端校验（防 CSRF 签名链路自洽）
    assert wechat_oauth_service.verify_oauth_state(data["state"]) is True


@pytest.mark.asyncio
async def test_wechat_login_invalid_state(client: AsyncClient, monkeypatch):
    _enable_wechat(monkeypatch)
    resp = await client.post(
        "/api/auth/wechat/login", json={"code": "fake-code", "state": "forged.state.sig"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wechat_login_creates_and_reuses_user(client: AsyncClient, db_session, monkeypatch):
    _enable_wechat(monkeypatch)

    async def fake_exchange(code: str) -> dict:
        return {"access_token": "AT1", "openid": "openid-001", "unionid": "unionid-001"}

    async def fake_userinfo(access_token: str, openid: str) -> dict:
        return {"nickname": "测试昵称", "headimgurl": "https://wx.qlogo.cn/test.png"}

    monkeypatch.setattr(wechat_oauth_service, "exchange_code", fake_exchange)
    monkeypatch.setattr(wechat_oauth_service, "fetch_userinfo", fake_userinfo)

    state1 = wechat_oauth_service.create_oauth_state()
    resp = await client.post(
        "/api/auth/wechat/login", json={"code": "code-1", "state": state1}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"].startswith("v4.local.")
    assert data["user"]["role"] == "homeowner"
    assert data["user"]["phone"] is None
    assert data["user"]["name"] == "测试昵称"
    first_id = data["user"]["id"]

    # 同 openid 二次登录复用同一账号
    state2 = wechat_oauth_service.create_oauth_state()
    resp2 = await client.post(
        "/api/auth/wechat/login", json={"code": "code-2", "state": state2}
    )
    assert resp2.status_code == 200
    assert resp2.json()["user"]["id"] == first_id

    # 库中仅一个微信用户，openid/unionid 落库
    count = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()
    assert count == 1
    user = (await db_session.execute(select(User).where(User.wechat_openid == "openid-001"))).scalar_one()
    assert user.wechat_unionid == "unionid-001"
    assert user.phone is None
    assert user.hashed_password is None


@pytest.mark.asyncio
async def test_wechat_login_exchange_error(client: AsyncClient, monkeypatch):
    _enable_wechat(monkeypatch)

    async def fake_exchange(code: str) -> dict:
        raise wechat_oauth_service.WeChatOAuthError("微信授权失败(40029): invalid code")

    monkeypatch.setattr(wechat_oauth_service, "exchange_code", fake_exchange)
    resp = await client.post(
        "/api/auth/wechat/login",
        json={"code": "bad", "state": wechat_oauth_service.create_oauth_state()},
    )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_wechat_login_missing_openid(client: AsyncClient, monkeypatch):
    _enable_wechat(monkeypatch)

    async def fake_exchange(code: str) -> dict:
        return {"access_token": "AT"}

    monkeypatch.setattr(wechat_oauth_service, "exchange_code", fake_exchange)
    resp = await client.post(
        "/api/auth/wechat/login",
        json={"code": "c", "state": wechat_oauth_service.create_oauth_state()},
    )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_wechat_nickname_sanitized(client: AsyncClient, db_session, monkeypatch):
    _enable_wechat(monkeypatch)

    async def fake_exchange(code: str) -> dict:
        return {"access_token": "AT", "openid": "openid-ctrl"}

    async def fake_userinfo(access_token: str, openid: str) -> dict:
        return {"nickname": "昵称\u0007带\u200b控制符\n", "headimgurl": "https://x/1.png"}

    monkeypatch.setattr(wechat_oauth_service, "exchange_code", fake_exchange)
    monkeypatch.setattr(wechat_oauth_service, "fetch_userinfo", fake_userinfo)

    resp = await client.post(
        "/api/auth/wechat/login",
        json={"code": "c", "state": wechat_oauth_service.create_oauth_state()},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["name"] == "昵称带控制符"


@pytest.mark.asyncio
async def test_wechat_bind_phone_success(client: AsyncClient, db_session, monkeypatch):
    _enable_wechat(monkeypatch)
    user = await get_or_create_wechat_user(db_session, "openid-bind", None, "微信用户", None)
    token = create_token(user.id, user.role)

    async def fake_get_phone(sp_token: str) -> str:
        assert sp_token == "sp-token-1"
        return "13800138000"

    monkeypatch.setattr(phone_number_auth_service, "get_phone_with_token", fake_get_phone)
    resp = await client.post(
        "/api/auth/wechat/bind-phone",
        json={"sp_token": "sp-token-1"},
        headers=_auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["phone"] == "13800138000"
    await db_session.refresh(user)
    assert user.phone == "13800138000"


@pytest.mark.asyncio
async def test_wechat_bind_phone_conflict(client: AsyncClient, db_session, monkeypatch):
    _enable_wechat(monkeypatch)
    user = await get_or_create_wechat_user(db_session, "openid-conflict", None, "微信用户", None)
    other = User(id="user-other", phone="13800138000", name="已有用户", role="homeowner")
    db_session.add(other)
    await db_session.commit()

    async def fake_get_phone(sp_token: str) -> str:
        return "13800138000"

    monkeypatch.setattr(phone_number_auth_service, "get_phone_with_token", fake_get_phone)
    resp = await client.post(
        "/api/auth/wechat/bind-phone",
        json={"sp_token": "sp-token-2"},
        headers=_auth_header(create_token(user.id, user.role)),
    )
    assert resp.status_code == 400
    assert "已绑定" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_wechat_bind_phone_already_bound(client: AsyncClient, db_session, monkeypatch):
    _enable_wechat(monkeypatch)
    user = User(id="user-bound", phone="13900139000", name="有手机号", role="homeowner")
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(
        "/api/auth/wechat/bind-phone",
        json={"sp_token": "sp-token-3"},
        headers=_auth_header(create_token(user.id, user.role)),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_wechat_bind_phone_requires_auth(client: AsyncClient, monkeypatch):
    _enable_wechat(monkeypatch)
    resp = await client.post("/api/auth/wechat/bind-phone", json={"sp_token": "sp-token-4"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wechat_oauth_state_expiry(monkeypatch):
    """state 过期必须校验失败（时间反推）。"""
    monkeypatch.setattr(get_settings(), "wechat_state_expire_seconds", -1)
    state = wechat_oauth_service.create_oauth_state()
    assert wechat_oauth_service.verify_oauth_state(state) is False

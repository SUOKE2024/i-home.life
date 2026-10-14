"""认证改造 v4.public 回归：刷新令牌轮换 + 生态 SSO（索克生活 → 索克家居）。

覆盖：
- 登录/注册下发 refresh 令牌对（access 前缀 v4.public.、refresh 带 footer typ=rt）
- refresh 令牌不可用于访问接口；access 令牌不可用于刷新
- /auth/refresh 同族轮换；grace 窗口内重放返回轮换后 RT；超窗重放撤销整族
- /auth/ecosystem/login 验签索克生活 v4.public access 令牌、幂等建号、拒绝非法 iss/type
"""
import base64
import uuid
from datetime import datetime, timedelta, timezone

import paseto
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from paseto.keys.asymmetric_key import AsymmetricSecretKey
from paseto.protocols.v4 import ProtocolVersion4 as v4

from app.auth.paseto_handler import _secret64_from_seed
from app.config import get_settings

settings = get_settings()


def _register_payload() -> dict:
    phone = f"139{str(uuid.uuid4().int)[:8]}"
    return {"phone": phone, "name": "刷新测试用户", "password": "test123456"}


async def _register(client) -> dict:
    resp = await client.post("/api/auth/register", json=_register_payload())
    assert resp.status_code == 201, resp.text
    return resp.json()


# ═══════════════════════════════════════════
#  刷新令牌对
# ═══════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_returns_refresh_pair(client):
    data = await _register(client)
    assert data["access_token"].startswith("v4.public.")
    assert data["refresh_token"] and data["refresh_token"].startswith("v4.public.")
    assert len(data["refresh_token"].split(".")) == 4  # 带 footer（typ=rt）
    assert data["expires_in"] == settings.paseto_token_expire_minutes * 60


@pytest.mark.asyncio
async def test_refresh_token_rejected_on_protected(client):
    data = await _register(client)
    resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {data['refresh_token']}"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_access_token_rejected_on_refresh(client):
    data = await _register(client)
    resp = await client.post(
        "/api/auth/refresh", json={"refresh_token": data["access_token"]}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_and_new_access_works(client):
    data = await _register(client)
    resp = await client.post(
        "/api/auth/refresh", json={"refresh_token": data["refresh_token"]}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"] != data["access_token"]
    assert body["refresh_token"] != data["refresh_token"]
    # 新 access 可用
    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200


@pytest.mark.asyncio
async def test_refresh_reuse_within_grace_returns_rotated(client):
    data = await _register(client)
    first = await client.post(
        "/api/auth/refresh", json={"refresh_token": data["refresh_token"]}
    )
    assert first.status_code == 200
    rotated_rt = first.json()["refresh_token"]

    # 立即重放旧 RT（grace 窗口内）→ 返回轮换后的同一 RT
    again = await client.post(
        "/api/auth/refresh", json={"refresh_token": data["refresh_token"]}
    )
    assert again.status_code == 200, again.text
    assert again.json()["refresh_token"] == rotated_rt


@pytest.mark.asyncio
async def test_refresh_reuse_beyond_grace_revokes_family(client, monkeypatch):
    data = await _register(client)
    first = await client.post(
        "/api/auth/refresh", json={"refresh_token": data["refresh_token"]}
    )
    assert first.status_code == 200
    rotated_rt = first.json()["refresh_token"]

    monkeypatch.setattr(settings, "paseto_refresh_grace_seconds", 0)
    replay = await client.post(
        "/api/auth/refresh", json={"refresh_token": data["refresh_token"]}
    )
    assert replay.status_code == 401
    assert "重放" in replay.json()["detail"]

    # 整族已撤销：轮换后的 RT 也不可用
    after = await client.post("/api/auth/refresh", json={"refresh_token": rotated_rt})
    assert after.status_code == 401


# ═══════════════════════════════════════════
#  生态 SSO（索克生活 → 索克家居）
# ═══════════════════════════════════════════


def _life_signer():
    """返回 (paserk, sign)：同一把临时 Ed25519 密钥的公开 PASERK 与签发闭包。

    便于在同一用例内多次签发同密钥令牌（验证幂等/重放），以及跨密钥验证拒绝。
    """
    sk = ed25519.Ed25519PrivateKey.generate()
    seed = sk.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
    key = AsymmetricSecretKey(key_material=_secret64_from_seed(seed), protocol=v4)
    pk_raw = sk.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    paserk = "k4.public." + base64.urlsafe_b64encode(pk_raw).rstrip(b"=").decode()

    def sign(
        *,
        iss: str = "suoke-life-auth",
        typ: str = "access",
        user_id: str = "life-user-1",
        exp_delta_minutes: int = 30,
    ) -> str:
        exp = datetime.now(timezone.utc) + timedelta(minutes=exp_delta_minutes)
        claims = {
            "user_id": user_id,
            "username": "生活用户",
            "roles": ["user"],
            "type": typ,
            "iss": iss,
            "aud": "suoke-life-app",
            "jti": str(uuid.uuid4()),
            "exp": exp.isoformat(),
            "iat": datetime.now(timezone.utc).isoformat(),
        }
        return paseto.create(key=key, purpose="public", claims=claims)

    return paserk, sign


@pytest.mark.asyncio
async def test_ecosystem_login_success_and_idempotent(client, monkeypatch):
    paserk, sign = _life_signer()
    monkeypatch.setattr(settings, "ecosystem_public_paserk", paserk)

    r1 = await client.post("/api/auth/ecosystem/login", json={"ecosystem_token": sign()})
    assert r1.status_code == 200, r1.text
    u1 = r1.json()["user"]
    assert u1["role"] == "homeowner"
    assert r1.json()["refresh_token"]

    # 同 user_id 二次登录（同密钥再签）→ 同 id（幂等）
    r2 = await client.post("/api/auth/ecosystem/login", json={"ecosystem_token": sign()})
    assert r2.status_code == 200, r2.text
    assert r2.json()["user"]["id"] == u1["id"]


@pytest.mark.asyncio
async def test_ecosystem_login_rejects_bad_issuer(client, monkeypatch):
    paserk, sign = _life_signer()
    monkeypatch.setattr(settings, "ecosystem_public_paserk", paserk)
    resp = await client.post(
        "/api/auth/ecosystem/login", json={"ecosystem_token": sign(iss="evil-issuer")}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ecosystem_login_rejects_refresh_type(client, monkeypatch):
    paserk, sign = _life_signer()
    monkeypatch.setattr(settings, "ecosystem_public_paserk", paserk)
    resp = await client.post(
        "/api/auth/ecosystem/login", json={"ecosystem_token": sign(typ="refresh")}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ecosystem_login_rejects_wrong_key(client, monkeypatch):
    # 配置另一把公钥（与签发私钥不匹配）→ 验签失败
    _, sign_issuer = _life_signer()
    other_paserk, _ = _life_signer()
    monkeypatch.setattr(settings, "ecosystem_public_paserk", other_paserk)
    resp = await client.post(
        "/api/auth/ecosystem/login", json={"ecosystem_token": sign_issuer()}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ecosystem_login_missing_key_returns_503(client, monkeypatch):
    _, sign = _life_signer()
    monkeypatch.setattr(settings, "ecosystem_public_paserk", "")
    monkeypatch.setattr(settings, "secret_manager_enabled", False)
    resp = await client.post("/api/auth/ecosystem/login", json={"ecosystem_token": sign()})
    assert resp.status_code == 503

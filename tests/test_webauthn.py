"""WebAuthn / FIDO2 / Passkey 生物识别认证测试

测试覆盖：
- 注册/登录 begin 端点（生成挑战）
- 注册/登录 complete 端点（验证挑战）
- 凭证管理（list/delete）
- 挑战存储层（MemoryChallengeStore 的 TTL 过期、一次性消费）
- 鉴权与权限校验
- 配置正确性
"""

import asyncio
import uuid

import pytest
from httpx import AsyncClient

from app.models.webauthn_credential import WebAuthnCredential
from app.services.webauthn_service import (
    ChallengeStore,
    MemoryChallengeStore,
    _get_challenge_store,
    close_challenge_store,
)


# ═══════════════════════════════════════════
#  辅助 fixture
# ═══════════════════════════════════════════


async def _register_user(client: AsyncClient, phone: str = "13900200001") -> dict:
    """注册测试用户并返回 {token, user}"""
    resp = await client.post(
        "/api/auth/register",
        json={
            "phone": phone,
            "name": f"WebAuthn测试_{phone[-4:]}",
            "password": "test123456",
            "role": "homeowner",
        },
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_credential(
    db_session, user_id: str, cred_id: str = None
) -> WebAuthnCredential:
    """直接在数据库中创建一条 WebAuthn 凭证记录"""
    cred = WebAuthnCredential(
        id=str(uuid.uuid4()),
        user_id=user_id,
        credential_id=cred_id or f"cred-{uuid.uuid4().hex[:16]}",
        public_key="BM1yY2xhbmdlLXB1YmxpYy1rZXktZm9yLXRlc3Q",
        sign_count=0,
        device_name="测试设备",
        credential_type="platform",
        aaguid=None,
        is_passkey=True,
        is_active=True,
    )
    db_session.add(cred)
    await db_session.commit()
    await db_session.refresh(cred)
    return cred


# ═══════════════════════════════════════════
#  挑战存储层单元测试
# ═══════════════════════════════════════════


@pytest.mark.asyncio
async def test_memory_challenge_store_set_get():
    """内存存储 set/get 基本功能"""
    store = MemoryChallengeStore()
    await store.set("k1", "v1", ttl=60)
    assert await store.get("k1") == "v1"


@pytest.mark.asyncio
async def test_memory_challenge_store_ttl_expiry():
    """内存存储 TTL 过期"""
    store = MemoryChallengeStore()
    await store.set("k_expire", "v", ttl=1)
    # 等待过期
    await asyncio.sleep(1.1)
    assert await store.get("k_expire") is None


@pytest.mark.asyncio
async def test_memory_challenge_store_pop_one_time():
    """pop 应一次性消费挑战"""
    store = MemoryChallengeStore()
    await store.set("k_pop", "v_pop", ttl=60)
    # 第一次 pop 应返回值
    assert await store.pop("k_pop") == "v_pop"
    # 第二次 pop 应返回 None（已被删除）
    assert await store.pop("k_pop") is None


@pytest.mark.asyncio
async def test_memory_challenge_store_delete():
    """delete 应删除指定键"""
    store = MemoryChallengeStore()
    await store.set("k_del", "v", ttl=60)
    await store.delete("k_del")
    assert await store.get("k_del") is None


@pytest.mark.asyncio
async def test_memory_challenge_store_cleanup_expired():
    """惰性清理应清除过期项"""
    store = MemoryChallengeStore()
    await store.set("k1", "v1", ttl=1)
    await store.set("k2", "v2", ttl=60)
    await asyncio.sleep(1.1)
    # 访问任一键触发清理
    assert await store.get("k2") == "v2"
    # k1 应已被清理（即使没访问它）
    assert "k1" not in store._store


@pytest.mark.asyncio
async def test_challenge_store_abstract_methods_raise():
    """抽象基类方法应 raise NotImplementedError"""
    store = ChallengeStore()
    with pytest.raises(NotImplementedError):
        await store.set("k", "v", ttl=10)
    with pytest.raises(NotImplementedError):
        await store.get("k")
    with pytest.raises(NotImplementedError):
        await store.delete("k")


@pytest.mark.asyncio
async def test_get_challenge_store_singleton():
    """_get_challenge_store 应返回同一实例（单例）"""
    # 重置全局状态
    await close_challenge_store()
    s1 = _get_challenge_store()
    s2 = _get_challenge_store()
    assert s1 is s2


# ═══════════════════════════════════════════
#  注册 begin 端点
# ═══════════════════════════════════════════


@pytest.mark.asyncio
async def test_webauthn_register_begin_requires_auth(client: AsyncClient):
    """未登录访问注册 begin 应返回 401"""
    resp = await client.post("/api/auth/webauthn/register/begin", json={})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webauthn_register_begin_returns_options(client: AsyncClient):
    """注册 begin 应返回完整的 PublicKeyCredentialCreationOptions"""
    user_data = await _register_user(client)
    token = user_data["access_token"]

    resp = await client.post(
        "/api/auth/webauthn/register/begin",
        json={"device_name": "测试设备 iPhone 16"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 必须包含 WebAuthn 规范要求的字段
    assert "challenge" in data
    assert "rp" in data
    assert "user" in data
    assert "pubKeyCredParams" in data
    assert "timeout" in data
    assert data["timeout"] == 60000
    # rp id 应来自配置
    assert data["rp"]["id"] or "rpId" in data
    # 应返回 user.id（用户标识）
    assert data["user"]["id"]


@pytest.mark.asyncio
async def test_webauthn_register_begin_stores_challenge(client: AsyncClient):
    """注册 begin 应在挑战存储中保存 challenge→user_id 映射"""
    user_data = await _register_user(client, phone="13900200002")
    token = user_data["access_token"]
    user_id = user_data["user"]["id"]

    resp = await client.post(
        "/api/auth/webauthn/register/begin",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    challenge = resp.json()["challenge"]

    # 检查挑战已存储
    store = _get_challenge_store()
    stored = await store.get(challenge)
    assert stored == user_id


# ═══════════════════════════════════════════
#  注册 complete 端点
# ═══════════════════════════════════════════


@pytest.mark.asyncio
async def test_webauthn_register_complete_invalid_challenge(client: AsyncClient):
    """无效挑战应返回 400"""
    user_data = await _register_user(client, phone="13900200003")
    token = user_data["access_token"]

    # 直接提交一个伪造的 credential JSON，不带有效挑战
    resp = await client.post(
        "/api/auth/webauthn/register/complete",
        json={
            "credential": {
                "id": "fake-cred-id",
                "response": {
                    "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uY3JlYXRlIn0",
                    "attestationObject": "fake",
                },
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webauthn_register_complete_requires_auth(client: AsyncClient):
    """未登录访问注册 complete 应返回 401"""
    resp = await client.post(
        "/api/auth/webauthn/register/complete",
        json={"credential": {}},
    )
    assert resp.status_code == 401


# ═══════════════════════════════════════════
#  登录 begin 端点
# ═══════════════════════════════════════════


@pytest.mark.asyncio
async def test_webauthn_login_begin_anonymous_ok(client: AsyncClient):
    """登录 begin 可匿名访问"""
    resp = await client.post("/api/auth/webauthn/login/begin", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert "challenge" in data
    assert "timeout" in data
    assert "rpId" in data


@pytest.mark.asyncio
async def test_webauthn_login_begin_no_phone_returns_empty_allow_credentials(
    client: AsyncClient,
):
    """不传 phone 时走 discoverable credentials 模式（allow_credentials 为空）"""
    resp = await client.post("/api/auth/webauthn/login/begin", json={})
    assert resp.status_code == 200
    data = resp.json()
    allow_creds = data.get("allowCredentials", [])
    assert allow_creds == []


@pytest.mark.asyncio
async def test_webauthn_login_begin_with_phone_returns_credentials(
    client: AsyncClient, db_session
):
    """传 phone 且用户有凭证时，allow_credentials 应包含凭证列表"""
    user_data = await _register_user(client, phone="13900200004")
    user_id = user_data["user"]["id"]
    phone = user_data["user"]["phone"]

    # 创建一条凭证
    await _create_credential(db_session, user_id, cred_id="test-cred-12345")

    resp = await client.post(
        "/api/auth/webauthn/login/begin",
        json={"phone": phone},
    )
    assert resp.status_code == 200
    data = resp.json()
    allow_creds = data.get("allowCredentials", [])
    assert len(allow_creds) == 1
    # 应返回凭证 ID
    assert allow_creds[0]["id"]


@pytest.mark.asyncio
async def test_webauthn_login_begin_stores_challenge(client: AsyncClient):
    """登录 begin 应在挑战存储中保存 login: 前缀的挑战"""
    resp = await client.post("/api/auth/webauthn/login/begin", json={})
    challenge = resp.json()["challenge"]

    store = _get_challenge_store()
    # 登录挑战应存储在 login: 前缀下
    assert await store.get(f"login:{challenge}") == "pending"


# ═══════════════════════════════════════════
#  登录 complete 端点
# ═══════════════════════════════════════════


@pytest.mark.asyncio
async def test_webauthn_login_complete_invalid_challenge(client: AsyncClient):
    """无效登录挑战应返回 401"""
    resp = await client.post(
        "/api/auth/webauthn/login/complete",
        json={
            "credential": {
                "id": "fake-cred",
                "response": {
                    "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uZ2V0In0",
                    "authenticatorData": "fake",
                    "signature": "fake",
                    "userHandle": None,
                },
            },
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webauthn_login_complete_challenge_one_time(client: AsyncClient):
    """登录挑战应一次性消费（直接在存储层验证）"""
    # 生成挑战
    begin_resp = await client.post("/api/auth/webauthn/login/begin", json={})
    challenge = begin_resp.json()["challenge"]

    # 验证挑战存在
    store = _get_challenge_store()
    assert await store.get(f"login:{challenge}") == "pending"

    # 模拟一次性消费：pop 应返回值并删除
    value = await store.pop(f"login:{challenge}")
    assert value == "pending"
    # 再次读取应返回 None
    assert await store.get(f"login:{challenge}") is None


# ═══════════════════════════════════════════
#  凭证管理端点
# ═══════════════════════════════════════════


@pytest.mark.asyncio
async def test_list_credentials_requires_auth(client: AsyncClient):
    """未登录列出凭证应返回 401"""
    resp = await client.get("/api/auth/webauthn/credentials")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_credentials_empty(client: AsyncClient):
    """已登录但无凭证的用户应返回空列表"""
    user_data = await _register_user(client, phone="13900200005")
    token = user_data["access_token"]

    resp = await client.get(
        "/api/auth/webauthn/credentials",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_credentials_with_data(client: AsyncClient, db_session):
    """已登录且有凭证的用户应返回凭证列表"""
    user_data = await _register_user(client, phone="13900200006")
    token = user_data["access_token"]
    user_id = user_data["user"]["id"]

    await _create_credential(db_session, user_id, cred_id="list-test-cred-1")
    await _create_credential(db_session, user_id, cred_id="list-test-cred-2")

    resp = await client.get(
        "/api/auth/webauthn/credentials",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    creds = resp.json()
    assert len(creds) == 2
    # 应包含管理字段
    for c in creds:
        assert "credential_id" in c
        assert "device_name" in c
        assert "is_active" in c
        assert "is_passkey" in c
        assert "last_used_at" in c


@pytest.mark.asyncio
async def test_delete_credential_soft_delete(client: AsyncClient, db_session):
    """删除凭证应为软删除（is_active 由 True 变为 False）"""
    user_data = await _register_user(client, phone="13900200007")
    token = user_data["access_token"]
    user_id = user_data["user"]["id"]

    cred = await _create_credential(db_session, user_id, cred_id="delete-test-cred")

    # 删除前 is_active=True
    list_resp = await client.get(
        "/api/auth/webauthn/credentials",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    creds_before = list_resp.json()
    assert len(creds_before) == 1
    assert creds_before[0]["is_active"] is True

    # 删除
    resp = await client.delete(
        f"/api/auth/webauthn/credentials/{cred.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # 删除后 is_active=False（软删除，记录仍在）
    list_resp2 = await client.get(
        "/api/auth/webauthn/credentials",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp2.status_code == 200
    creds_after = list_resp2.json()
    assert len(creds_after) == 1
    assert creds_after[0]["is_active"] is False


@pytest.mark.asyncio
async def test_delete_credential_not_found(client: AsyncClient):
    """删除不存在的凭证应返回 404"""
    user_data = await _register_user(client, phone="13900200008")
    token = user_data["access_token"]

    resp = await client.delete(
        "/api/auth/webauthn/credentials/nonexistent-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_credential_isolation(client: AsyncClient, db_session):
    """用户 A 不能删除用户 B 的凭证"""
    # 用户 A
    user_a = await _register_user(client, phone="13900200009")
    token_a = user_a["access_token"]

    # 用户 B
    user_b = await _register_user(client, phone="13900200010")
    user_b_id = user_b["user"]["id"]

    # 用户 B 的凭证
    cred_b = await _create_credential(db_session, user_b_id, cred_id="cred-b-12345")

    # 用户 A 尝试删除用户 B 的凭证
    resp = await client.delete(
        f"/api/auth/webauthn/credentials/{cred_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404  # 不属于该用户的凭证视为不存在


# ═══════════════════════════════════════════
#  服务层测试
# ═══════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_begin_exclude_existing_credentials(
    client: AsyncClient, db_session
):
    """注册 begin 时 excludeCredentials 应包含已注册的凭证 ID"""
    user_data = await _register_user(client, phone="13900200011")
    token = user_data["access_token"]
    user_id = user_data["user"]["id"]

    # 已有一条凭证
    await _create_credential(db_session, user_id, cred_id="existing-cred-aaa")

    resp = await client.post(
        "/api/auth/webauthn/register/begin",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    exclude = resp.json().get("excludeCredentials", [])
    assert len(exclude) == 1
    assert exclude[0]["id"]


@pytest.mark.asyncio
async def test_close_challenge_store_resets_singleton():
    """close_challenge_store 应重置单例"""
    s1 = _get_challenge_store()
    await close_challenge_store()
    s2 = _get_challenge_store()
    # 关闭后再次获取应是新实例
    assert s1 is not s2


# ═══════════════════════════════════════════
#  配置测试
# ═══════════════════════════════════════════


def test_webauthn_config_fields_exist():
    """配置应包含 webauthn 相关字段"""
    from app.config import get_settings
    s = get_settings()
    assert hasattr(s, "webauthn_rp_id")
    assert hasattr(s, "webauthn_origin")
    assert hasattr(s, "webauthn_challenge_ttl")
    assert isinstance(s.webauthn_challenge_ttl, int)
    assert s.webauthn_challenge_ttl > 0


def test_webauthn_challenge_ttl_default():
    """挑战 TTL 默认值应为合理范围（60-300 秒）"""
    from app.config import get_settings
    s = get_settings()
    assert 60 <= s.webauthn_challenge_ttl <= 300

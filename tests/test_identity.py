"""Tests for identity verification API endpoints.

覆盖端点:
- POST /api/identity/submit                    (提交实名认证)
- GET  /api/identity/status                    (查询认证状态)
- GET  /api/identity/pending                   (管理员查看待审核列表)
- POST /api/identity/{verification_id}/review  (管理员审核)
"""

import pytest
from httpx import AsyncClient


async def _register_admin(client: AsyncClient) -> dict:
    """直接通过 DB 创建管理员并签发 token（register 已禁止自注册 admin）"""
    import uuid as _uuid
    from app.database import async_session
    from app.models.user import User
    from app.auth.paseto_handler import create_token

    user_id = str(_uuid.uuid4())
    async with async_session() as db:
        db.add(User(id=user_id, phone=f"139{_uuid.uuid4().hex[:8]}", name="管理员测试", role="admin", hashed_password="x"))
        await db.commit()
    return {"Authorization": f"Bearer {create_token(user_id, 'admin')}"}


@pytest.mark.asyncio
async def test_identity_requires_auth(client: AsyncClient):
    """未认证请求身份认证接口返回 401"""
    resp = await client.post(
        "/api/identity/submit",
        json={"real_name": "张三", "id_card": "110101199001011234"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_submit_verification(client: AsyncClient, auth_headers: dict):
    """提交实名认证申请"""
    resp = await client.post(
        "/api/identity/submit",
        json={
            "real_name": "王小明",
            "id_card": "310101198506152345",
            "id_card_front": "https://example.com/front.jpg",
            "id_card_back": "https://example.com/back.jpg",
            "selfie_with_id": "https://example.com/selfie.jpg",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"提交失败: {resp.json()}"
    data = resp.json()
    assert data["real_name"] == "王小明"
    assert data["status"] in ("pending", "approved")
    assert "id" in data


@pytest.mark.asyncio
async def test_submit_verification_missing_real_name(client: AsyncClient, auth_headers: dict):
    """缺少 real_name 应返回 422"""
    resp = await client.post(
        "/api/identity/submit",
        json={"id_card": "310101198506152345"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_verification_status(client: AsyncClient, auth_headers: dict):
    """查询认证状态"""
    # 未提交认证时查询
    resp = await client.get("/api/identity/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "is_verified" in data
    assert "status" in data
    # P2-9：认证历史字段（未提交时为 None）
    assert "review_note" in data
    assert "verified_at" in data
    assert data["review_note"] is None
    assert data["verified_at"] is None


@pytest.mark.asyncio
async def test_pending_requires_admin(client: AsyncClient, auth_headers: dict):
    """普通用户访问待审核列表应被拒绝"""
    resp = await client.get("/api/identity/pending", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_review_requires_admin(client: AsyncClient, auth_headers: dict):
    """普通用户审核认证应被拒绝"""
    resp = await client.post(
        "/api/identity/nonexistent-id/review",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_review_nonexistent_verification(client: AsyncClient):
    """管理员审核不存在的认证记录返回 404"""
    headers = await _register_admin(client)
    resp = await client.post(
        "/api/identity/nonexistent-verification-id/review",
        json={"status": "approved"},
        headers=headers,
    )
    assert resp.status_code == 404

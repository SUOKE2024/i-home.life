"""Tests for admin API endpoints.

覆盖端点:
- GET  /api/admin/users                  (列出用户)
- GET  /api/admin/users/{user_id}        (获取用户详情)
- PUT  /api/admin/users/{user_id}/role   (更新角色)
- PUT  /api/admin/users/{user_id}/status (更新状态)
- GET  /api/admin/permissions            (列出权限)
- GET  /api/admin/roles/{role}/permissions  (查看角色权限)
- PUT  /api/admin/roles/{role}/permissions  (修改角色权限)
- GET  /api/admin/stats                  (平台统计)
- GET  /api/admin/audit-logs             (审计日志)
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
async def test_admin_requires_auth(client: AsyncClient):
    """未认证请求管理后台返回 401"""
    resp = await client.get("/api/admin/users")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_users_requires_admin_role(client: AsyncClient, auth_headers: dict):
    """普通用户访问用户列表应被拒绝"""
    resp = await client.get("/api/admin/users", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats_requires_admin_role(client: AsyncClient, auth_headers: dict):
    """普通用户访问平台统计应被拒绝"""
    resp = await client.get("/api/admin/stats", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_user_detail_requires_admin(client: AsyncClient, auth_headers: dict):
    """普通用户查询其他用户详情应被拒绝"""
    resp = await client.get("/api/admin/users/some-user-id", headers=auth_headers)
    assert resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_admin_permissions_requires_admin(client: AsyncClient, auth_headers: dict):
    """普通用户访问权限列表应被拒绝"""
    resp = await client.get("/api/admin/permissions", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_audit_logs_requires_admin(client: AsyncClient, auth_headers: dict):
    """普通用户访问审计日志应被拒绝"""
    resp = await client.get("/api/admin/audit-logs", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_list_users(client: AsyncClient):
    """管理员查看用户列表"""
    headers = await _register_admin(client)
    resp = await client.get("/api/admin/users", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_admin_get_nonexistent_user(client: AsyncClient):
    """管理员查看不存在的用户返回 404"""
    headers = await _register_admin(client)
    resp = await client.get("/api/admin/users/nonexistent-user-id", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_update_nonexistent_user_role(client: AsyncClient):
    """管理员修改不存在用户的角色返回 404"""
    headers = await _register_admin(client)
    resp = await client.put(
        "/api/admin/users/nonexistent-id/role",
        json={"role": "contractor"},
        headers=headers,
    )
    assert resp.status_code == 404

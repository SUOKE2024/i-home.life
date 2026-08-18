"""供应商工作台 RBAC 权限矩阵测试（v1.15.4）

覆盖:
- 授权缺口修复：任何已认证非供应商角色（含 is_verified）创建产品 → 403
- 供应商角色创建产品放行（行为保持，实名认证属平台审核策略独立管理）
- GET /auth/me/permissions 菜单出口：按角色返回生效权限码
- PermissionChecker 默认映射兜底（无 DB seed 也可用）
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.auth.paseto_handler import create_token
from app.database import async_session
from app.models.user import User
from app.rbac import PermissionChecker


async def _register(client: AsyncClient, role: str) -> dict:
    """注册指定角色用户并返回认证 headers"""
    resp = await client.post(
        "/api/auth/register",
        json={
            "phone": f"139{uuid.uuid4().int % 100000000:08d}",
            "name": f"角色测试{role}",
            "password": "test123456",
            "role": role,
        },
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _set_verified(phone: str, verified: bool = True) -> None:
    """直接置 is_verified（复现「已认证非供应商」授权缺口场景）"""
    async with async_session() as db:
        await db.execute(
            update(User).where(User.phone == phone).values(is_verified=verified)
        )
        await db.commit()


@pytest.mark.asyncio
async def test_create_product_rejects_verified_designer(client: AsyncClient):
    """已认证设计师（非供应商）创建产品 → 403（v1.15.4 修复授权缺口）"""
    headers = await _register(client, "designer")
    me = await client.get("/api/auth/me", headers=headers)
    await _set_verified(me.json()["phone"], True)

    resp = await client.post(
        "/api/products",
        json={"name": "越权瓷砖", "category": "flooring"},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_product_rejects_homeowner(client: AsyncClient):
    """业主创建产品 → 403"""
    headers = await _register(client, "homeowner")
    resp = await client.post(
        "/api/products",
        json={"name": "越权产品", "category": "other"},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_product_allows_supplier(client: AsyncClient):
    """供应商创建产品 → 200/201（行为保持：实名认证由身份认证流程独立管理）"""
    headers = await _register(client, "supplier")
    resp = await client.post(
        "/api/products",
        json={"name": "品牌瓷砖", "category": "flooring", "quantity": 50, "unit": "m2"},
        headers=headers,
    )
    assert resp.status_code in (200, 201)


@pytest.mark.asyncio
async def test_me_permissions_homeowner(client: AsyncClient):
    """业主权限码 = 基线最小集，无写权限"""
    headers = await _register(client, "homeowner")
    resp = await client.get("/api/auth/me/permissions", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "homeowner"
    assert set(body["permissions"]) == {"project:read", "material:read", "budget:read"}


@pytest.mark.asyncio
async def test_me_permissions_supplier(client: AsyncClient):
    """供应商权限码含产品/订单/履约/结算（v1.15.4 扩展）"""
    headers = await _register(client, "supplier")
    resp = await client.get("/api/auth/me/permissions", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    codes = set(body["permissions"])
    assert {"material:write", "product:write", "order:read", "quote:write",
            "fulfillment:update", "settlement:read"} <= codes
    assert "user:manage" not in codes


@pytest.mark.asyncio
async def test_me_permissions_admin(client: AsyncClient):
    """管理员返回全部已知权限码"""
    user_id = str(uuid.uuid4())
    async with async_session() as db:
        db.add(User(
            id=user_id, phone=f"138{uuid.uuid4().hex[:8]}", name="权限管理员",
            role="admin", hashed_password="x",
        ))
        await db.commit()
    headers = {"Authorization": f"Bearer {create_token(user_id, 'admin')}"}

    resp = await client.get("/api/auth/me/permissions", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "admin"
    assert {"user:manage", "material:write", "settlement:read"} <= set(body["permissions"])


@pytest.mark.asyncio
async def test_permission_checker_defaults_fallback(client: AsyncClient):
    """PermissionChecker 默认映射兜底：无 DB seed 时供应商按基线放行/拒绝"""
    from fastapi import HTTPException

    async with async_session() as db:
        supplier = User(role="supplier")

        # 放行：material:write 在 supplier 默认映射中（无 DB 行，走默认映射兜底）
        checker = PermissionChecker("material:write")
        assert await checker(current_user=supplier, db=db) == supplier

        # 拒绝：user:manage 不在 supplier 默认映射且无 DB 行 → 403
        denied = PermissionChecker("user:manage")
        with pytest.raises(HTTPException) as exc:
            await denied(current_user=supplier, db=db)
        assert exc.value.status_code == 403

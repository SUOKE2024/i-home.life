"""审计日志测试

覆盖：
- audit_log_service.log_audit_event 服务层
- /api/admin/audit-logs 端点（admin 角色 + 过滤 + 分页）
- audit_log_enabled=False 时不记录
- 集成：/api/auth/register 和 /api/auth/login 触发审计日志
- 失败安全：异常时不阻断主流程
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.user import User
from app.services import audit_log_service
from app.services.audit_log_service import log_audit_event
from app.services.user_service import _hash_password


# ═══════════════════════════════════════════
#  服务层单元测试
# ═══════════════════════════════════════════


@pytest.mark.asyncio
async def test_log_audit_event_basic(db_session):
    """正常写入一条审计日志"""
    entry = await log_audit_event(
        db=db_session,
        user_id="test-user-1",
        action="LOGIN",
        resource_type="user",
        resource_id="test-user-1",
        details={"role": "homeowner"},
        request_ip="127.0.0.1",
        user_agent="Mozilla/5.0",
    )
    await db_session.commit()

    assert entry is not None
    assert entry.id is not None
    assert entry.user_id == "test-user-1"
    assert entry.action == "LOGIN"
    assert entry.resource_type == "user"
    assert entry.resource_id == "test-user-1"
    # v1.1.29: PII 脱敏为 details 注入 _hmac 签名
    assert entry.details.get("role") == "homeowner"
    assert entry.details.get("_hmac") is not None  # PII HMAC signature
    assert entry.request_ip == "127.0.0.1"
    assert entry.user_agent == "Mozilla/5.0"
    assert entry.created_at is not None


@pytest.mark.asyncio
async def test_log_audit_event_minimal_fields(db_session):
    """resource_id / user_agent / details 可为空"""
    entry = await log_audit_event(
        db=db_session,
        user_id="u2",
        action="LOGOUT",
        resource_type="session",
        request_ip="10.0.0.1",
    )
    await db_session.commit()

    assert entry is not None
    assert entry.resource_id is None
    assert entry.user_agent is None
    # v1.1.29: PII 脱敏为 details 注入 _hmac，原始 details 可能为 None 或空 dict
    assert entry.details is None or entry.details.get("_hmac") is not None


@pytest.mark.asyncio
async def test_log_audit_event_disabled(db_session, monkeypatch):
    """audit_log_enabled=False 时不记录"""
    monkeypatch.setattr(audit_log_service.settings, "audit_log_enabled", False)

    entry = await log_audit_event(
        db=db_session,
        user_id="u3",
        action="LOGIN",
        resource_type="user",
        request_ip="127.0.0.1",
    )
    await db_session.commit()

    assert entry is None

    # 验证数据库无记录
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.user_id == "u3")
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_log_audit_event_action_enum_persistence(db_session):
    """action 枚举值能正确写入并查询"""
    for action in ("CREATE", "UPDATE", "DELETE", "LOGIN", "LOGOUT", "EXPORT", "PERMISSION_CHANGE"):
        await log_audit_event(
            db=db_session,
            user_id="u-enum",
            action=action,
            resource_type="test_resource",
            request_ip="127.0.0.1",
        )
    await db_session.commit()

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.user_id == "u-enum")
    )
    entries = result.scalars().all()
    assert len(entries) == 7
    actions = {e.action for e in entries}
    assert actions == {
        "CREATE", "UPDATE", "DELETE", "LOGIN", "LOGOUT", "EXPORT", "PERMISSION_CHANGE",
    }


@pytest.mark.asyncio
async def test_log_audit_event_details_json(db_session):
    """details 字段支持任意 JSON 结构"""
    payload = {
        "role": "admin",
        "changes": {"role": ["homeowner", "admin"]},
        "metadata": {"ip": "127.0.0.1", "tags": ["a", "b"]},
    }
    entry = await log_audit_event(
        db=db_session,
        user_id="u-json",
        action="PERMISSION_CHANGE",
        resource_type="user",
        resource_id="target-user",
        details=payload,
        request_ip="127.0.0.1",
    )
    await db_session.commit()

    # 重新查询验证
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.id == entry.id)
    )
    fetched = result.scalar_one()
    # v1.1.28: PII 脱敏生效，metadata.ip 中的 127.0.0.1 → 127.0.*.*
    assert fetched.details["role"] == "admin"
    assert fetched.details["changes"]["role"] == ["homeowner", "admin"]
    assert fetched.details["metadata"]["tags"] == ["a", "b"]
    assert fetched.details["metadata"]["ip"] == "127.0.*.*"


# ═══════════════════════════════════════════
#  集成测试：注册/登录触发审计日志
# ═══════════════════════════════════════════


@pytest.mark.asyncio
async def test_register_writes_audit_log(client: AsyncClient, db_session):
    """注册成功后应写入一条 REGISTER 审计日志"""
    phone = f"139{str(uuid.uuid4().int)[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "审计测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    user_id = resp.json()["user"]["id"]

    # 验证审计日志
    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.user_id == user_id,
            AuditLog.action == "REGISTER",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.resource_type == "user"
    assert entry.resource_id == user_id
    assert entry.details["role"] == "homeowner"
    # 手机号后 4 位应记录
    assert entry.details["phone_suffix"] == phone[-4:]


@pytest.mark.asyncio
async def test_login_writes_audit_log(client: AsyncClient, db_session):
    """登录成功后应写入一条 LOGIN 审计日志"""
    phone = f"139{str(uuid.uuid4().int)[:8]}"
    # 先注册
    reg_resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "登录审计", "password": "test123456"},
    )
    assert reg_resp.status_code == 201
    user_id = reg_resp.json()["user"]["id"]

    # 清空之前注册产生的审计日志，便于断言
    await db_session.execute(
        AuditLog.__table__.delete().where(AuditLog.user_id == user_id)
    )
    await db_session.commit()

    # 登录
    login_resp = await client.post(
        "/api/auth/login",
        json={"phone": phone, "password": "test123456"},
    )
    assert login_resp.status_code == 200

    # 验证 LOGIN 审计日志
    result = await db_session.execute(
        select(AuditLog).where(
            AuditLog.user_id == user_id,
            AuditLog.action == "LOGIN",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.resource_type == "user"
    assert entry.resource_id == user_id
    assert entry.details["role"] == "homeowner"


@pytest.mark.asyncio
async def test_audit_log_disabled_skips_writing(client: AsyncClient, db_session, monkeypatch):
    """audit_log_enabled=False 时注册/登录不写审计日志"""
    monkeypatch.setattr(audit_log_service.settings, "audit_log_enabled", False)

    phone = f"139{str(uuid.uuid4().int)[:8]}"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "禁用审计", "password": "test123456"},
    )
    assert reg_resp.status_code == 201
    user_id = reg_resp.json()["user"]["id"]

    # 不应有任何审计日志
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.user_id == user_id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_failed_login_does_not_write_audit(client: AsyncClient, db_session):
    """登录失败（密码错误）不应写审计日志"""
    phone = f"139{str(uuid.uuid4().int)[:8]}"
    await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "失败登录", "password": "test123456"},
    )

    # 错误密码登录
    resp = await client.post(
        "/api/auth/login",
        json={"phone": phone, "password": "wrongpassword"},
    )
    assert resp.status_code == 401

    # LOGIN 类审计日志不应存在
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == "LOGIN")
    )
    assert result.scalar_one_or_none() is None


# ═══════════════════════════════════════════
#  管理员查询端点测试
# ═══════════════════════════════════════════


async def _register_admin(client: AsyncClient, db_session) -> tuple[str, str]:
    """注册一个 admin 用户并返回 (token, user_id)"""
    phone = f"139{str(uuid.uuid4().int)[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "管理员", "password": "test123456"},
    )
    user_id = resp.json()["user"]["id"]
    # 直接通过 DB 升级为 admin
    user = await db_session.get(User, user_id)
    user.role = "admin"
    await db_session.commit()
    token = resp.json()["access_token"]
    return token, user_id


@pytest.mark.asyncio
async def test_admin_list_audit_logs_empty(client: AsyncClient, db_session):
    """admin 查询空审计日志列表"""
    token, _ = await _register_admin(client, db_session)

    resp = await client.get(
        "/api/admin/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["skip"] == 0
    assert data["limit"] == 50


@pytest.mark.asyncio
async def test_admin_list_audit_logs_with_data(client: AsyncClient, db_session):
    """admin 查询审计日志（含数据）"""
    token, admin_user_id = await _register_admin(client, db_session)

    # 写入若干审计日志
    for i in range(3):
        await log_audit_event(
            db=db_session,
            user_id=admin_user_id,
            action="LOGIN",
            resource_type="user",
            request_ip="127.0.0.1",
        )
    # 另一个用户、另一个动作
    await log_audit_event(
        db=db_session,
        user_id="other-user",
        action="DELETE",
        resource_type="project",
        resource_id="p-1",
        request_ip="10.0.0.1",
    )
    await db_session.commit()

    # 查询全部
    resp = await client.get(
        "/api/admin/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # admin 注册本身会写入一条 REGISTER，加上 3 条 LOGIN + 1 条 DELETE = 5
    # 但 admin_user_id 升级前的注册动作未审计，升级后再无动作
    # 实际上注册时 audit_log 已开启（默认 True），所以应该有 1 条 REGISTER
    assert data["total"] >= 4
    assert len(data["items"]) >= 4

    # 按时间倒序，最新在前
    created_ats = [item["created_at"] for item in data["items"]]
    assert created_ats == sorted(created_ats, reverse=True)


@pytest.mark.asyncio
async def test_admin_audit_logs_filter_by_user(client: AsyncClient, db_session):
    """按 user_id 过滤"""
    token, admin_user_id = await _register_admin(client, db_session)

    await log_audit_event(
        db=db_session,
        user_id=admin_user_id,
        action="LOGIN",
        resource_type="user",
        request_ip="127.0.0.1",
    )
    await log_audit_event(
        db=db_session,
        user_id="another-user",
        action="LOGIN",
        resource_type="user",
        request_ip="127.0.0.1",
    )
    await db_session.commit()

    resp = await client.get(
        f"/api/admin/audit-logs?user_id={admin_user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["user_id"] == admin_user_id


@pytest.mark.asyncio
async def test_admin_audit_logs_filter_by_action(client: AsyncClient, db_session):
    """按 action 过滤"""
    token, admin_user_id = await _register_admin(client, db_session)

    await log_audit_event(
        db=db_session,
        user_id=admin_user_id,
        action="EXPORT",
        resource_type="report",
        request_ip="127.0.0.1",
    )
    await log_audit_event(
        db=db_session,
        user_id=admin_user_id,
        action="DELETE",
        resource_type="project",
        request_ip="127.0.0.1",
    )
    await db_session.commit()

    resp = await client.get(
        "/api/admin/audit-logs?action=EXPORT",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["action"] == "EXPORT"


@pytest.mark.asyncio
async def test_admin_audit_logs_filter_by_resource_type(client: AsyncClient, db_session):
    """按 resource_type 过滤"""
    token, admin_user_id = await _register_admin(client, db_session)

    await log_audit_event(
        db=db_session,
        user_id=admin_user_id,
        action="CREATE",
        resource_type="project",
        resource_id="p-1",
        request_ip="127.0.0.1",
    )
    await log_audit_event(
        db=db_session,
        user_id=admin_user_id,
        action="CREATE",
        resource_type="budget",
        resource_id="b-1",
        request_ip="127.0.0.1",
    )
    await db_session.commit()

    resp = await client.get(
        "/api/admin/audit-logs?resource_type=project",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["resource_type"] == "project"


@pytest.mark.asyncio
async def test_admin_audit_logs_pagination(client: AsyncClient, db_session):
    """分页查询"""
    token, admin_user_id = await _register_admin(client, db_session)

    # 写入 5 条 LOGIN
    for _ in range(5):
        await log_audit_event(
            db=db_session,
            user_id=admin_user_id,
            action="LOGIN",
            resource_type="user",
            request_ip="127.0.0.1",
        )
    await db_session.commit()

    # 取第 2 页，每页 2 条
    resp = await client.get(
        "/api/admin/audit-logs?skip=2&limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["skip"] == 2
    assert data["limit"] == 2
    assert len(data["items"]) <= 2


@pytest.mark.asyncio
async def test_admin_audit_logs_limit_max_200(client: AsyncClient, db_session):
    """limit 超过 200 应被拒绝（422）"""
    token, _ = await _register_admin(client, db_session)

    resp = await client.get(
        "/api/admin/audit-logs?limit=201",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_admin_audit_logs_non_admin_forbidden(client: AsyncClient, db_session):
    """非 admin 用户访问应返回 403"""
    # 注册一个普通 homeowner
    phone = f"139{str(uuid.uuid4().int)[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "普通用户", "password": "test123456"},
    )
    token = resp.json()["access_token"]

    audit_resp = await client.get(
        "/api/admin/audit-logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert audit_resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_audit_logs_unauthenticated(client: AsyncClient):
    """未认证访问应返回 401"""
    resp = await client.get("/api/admin/audit-logs")
    assert resp.status_code == 401


# ═══════════════════════════════════════════
#  失败安全测试
# ═══════════════════════════════════════════


@pytest.mark.asyncio
async def test_log_audit_event_failure_does_not_raise(db_session, monkeypatch):
    """审计日志写入失败时不应抛出异常"""

    # 模拟 db.flush 抛异常
    async def _raise(*args, **kwargs):
        raise RuntimeError("simulated DB error")

    monkeypatch.setattr(db_session, "flush", _raise)

    entry = await log_audit_event(
        db=db_session,
        user_id="u-fail",
        action="LOGIN",
        resource_type="user",
        request_ip="127.0.0.1",
    )

    # 失败安全：返回 None，不抛出
    assert entry is None


@pytest.mark.asyncio
async def test_log_audit_event_with_disabled_user_agent(db_session):
    """user_agent 为 None 时应正常写入"""
    entry = await log_audit_event(
        db=db_session,
        user_id="u-no-ua",
        action="LOGIN",
        resource_type="user",
        request_ip="127.0.0.1",
        user_agent=None,
    )
    await db_session.commit()

    assert entry is not None
    assert entry.user_agent is None

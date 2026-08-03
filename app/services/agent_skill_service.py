"""Agent Skill 资产服务 — scope-owned 可授权共享的 Agent 能力管理

借鉴 YC QM（2026-07-31 开源）的 Skill 设计，提供：
- CRUD：create/get/list/update/delete（软删除）
- 版本化：update 时 version+1，旧版本 archived，parent_version_id 串联
- 回退：rollback 基于历史 version 创建新 version
- 授权共享：share by grant（share_grants 列表）
- admin 门控提升：promote_to_org 仅 admin 可操作
- skill_pack 导入：从 git raw URL fetch JSON（字段白名单解析，失败 422 诚实报错）
- instantiate：动态创建 BaseAgent 子类实例供 harness.run 调用

权限模型（对齐 CLAUDE.md 缓存隔离红线）：
- owner（created_by 或 owner_id 在 personal 作用域）可读写
- 非 owner：share_scope=org 全可见；share_scope=grant 且 share_grants 含 requester_id 可读
- promote_to_org：仅 role=admin 可操作

设计约束：
- 不引入 K8s/容器编排（FC 函数计算红线）
- 诚实降级：git fetch 失败明确 422，不伪造数据
- 版本链仅直接 parent，不递归（防链过长）
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.agent_skill import (
    AgentSkill, SCOPE_PERSONAL, SCOPE_ORG, STATUS_DRAFT, STATUS_ACTIVE,
    STATUS_ARCHIVED, SHARE_NONE, SHARE_GRANT, SHARE_ORG,
)

logger = logging.getLogger(__name__)

# skill_pack 导入允许的字段白名单（防注入任意字段）
_SKILL_PACK_ALLOWED_FIELDS = {
    "name", "description", "agent_name", "system_prompt",
    "provider", "tools", "cost_tier", "acceptance_criteria",
}


def _gen_id() -> str:
    return str(uuid.uuid4())


def _parse_json_field(value: str | None, default: Any) -> Any:
    """安全解析 JSON 字段，失败返回 default。"""
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _dump_json_field(value: Any) -> str:
    """序列化为 JSON 字符串。"""
    return json.dumps(value, ensure_ascii=False)


async def create_skill(
    db: AsyncSession,
    owner_scope: str,
    owner_id: str,
    name: str,
    description: str,
    agent_name: str,
    system_prompt: str,
    created_by: str,
    provider: str = "deepseek",
    tools: list | None = None,
    cost_tier: str = "standard",
    acceptance_criteria: list | None = None,
    skill_pack_source: str | None = None,
) -> AgentSkill:
    """创建一个新 Skill（status=draft）。

    owner_scope=personal 时 owner_id 应为 created_by（用户自己）。
    """
    skill = AgentSkill(
        id=_gen_id(),
        name=name,
        description=description,
        owner_scope=owner_scope,
        owner_id=owner_id,
        agent_name=agent_name,
        system_prompt=system_prompt,
        provider=provider,
        tools=_dump_json_field(tools or []),
        cost_tier=cost_tier,
        acceptance_criteria=_dump_json_field(acceptance_criteria or []),
        version=1,
        status=STATUS_DRAFT,
        share_scope=SHARE_NONE,
        share_grants=_dump_json_field([]),
        created_by=created_by,
        skill_pack_source=skill_pack_source,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill


async def get_skill(
    db: AsyncSession, skill_id: str, requester_id: str,
) -> AgentSkill | None:
    """获取单个 Skill（权限校验：owner / share_grants 含 requester / share_scope=org）。

    未授权返回 None（调用方转 404）。
    """
    stmt = select(AgentSkill).where(
        AgentSkill.id == skill_id,
        AgentSkill.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    skill = result.scalar_one_or_none()
    if skill is None:
        return None
    if not _can_read(skill, requester_id):
        return None
    return skill


def _can_read(skill: AgentSkill, requester_id: str) -> bool:
    """权限校验：requester 是否可读该 Skill。"""
    # owner 可读
    if skill.created_by == requester_id:
        return True
    if skill.owner_scope == SCOPE_PERSONAL and skill.owner_id == requester_id:
        return True
    # org 级全可见
    if skill.share_scope == SHARE_ORG:
        return True
    # grant 授权
    if skill.share_scope == SHARE_GRANT:
        grants = _parse_json_field(skill.share_grants, [])
        if requester_id in grants:
            return True
    return False


async def list_skills(
    db: AsyncSession,
    requester_id: str,
    scope_filter: str | None = None,
    include_archived: bool = False,
) -> list[AgentSkill]:
    """列出 requester 可见的 Skill。

    返回：owner 的 + 被授权的 + org 级的。
    scope_filter 可按 owner_scope 过滤。
    """
    conds = [AgentSkill.deleted_at.is_(None)]
    # 可见性：owner 创建的 / org 级 / grant 含 requester
    grants_contains = AgentSkill.share_grants.like(f'%"{requester_id}"%')
    visibility = or_(
        AgentSkill.created_by == requester_id,
        and_(AgentSkill.share_scope == SHARE_ORG, AgentSkill.owner_scope == SCOPE_ORG),
        and_(AgentSkill.share_scope == SHARE_GRANT, grants_contains),
    )
    conds.append(visibility)
    if scope_filter:
        conds.append(AgentSkill.owner_scope == scope_filter)
    if not include_archived:
        conds.append(AgentSkill.status != STATUS_ARCHIVED)

    stmt = select(AgentSkill).where(*conds).order_by(AgentSkill.updated_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_skill(
    db: AsyncSession,
    skill_id: str,
    requester_id: str,
    **fields,
) -> AgentSkill | None:
    """更新 Skill → version+1，旧版本 archived，新版本 parent_version_id 指向旧。

    仅 owner 可更新。可更新字段：description/system_prompt/provider/tools/
    cost_tier/acceptance_criteria/status(draft→active)。
    name 不可改（版本链锚点）。
    """
    stmt = select(AgentSkill).where(
        AgentSkill.id == skill_id,
        AgentSkill.deleted_at.is_(None),
        AgentSkill.status != STATUS_ARCHIVED,
    )
    result = await db.execute(stmt)
    old = result.scalar_one_or_none()
    if old is None:
        return None
    if old.created_by != requester_id:
        return None  # 非 owner 无权更新

    # 创建新版本（复制旧字段 + 应用更新）
    new_skill = AgentSkill(
        id=_gen_id(),
        name=old.name,
        description=fields.get("description", old.description),
        owner_scope=old.owner_scope,
        owner_id=old.owner_id,
        agent_name=old.agent_name,
        system_prompt=fields.get("system_prompt", old.system_prompt),
        provider=fields.get("provider", old.provider),
        tools=_dump_json_field(
            fields.get("tools", _parse_json_field(old.tools, []))
        ),
        cost_tier=fields.get("cost_tier", old.cost_tier),
        acceptance_criteria=_dump_json_field(
            fields.get("acceptance_criteria", _parse_json_field(old.acceptance_criteria, []))
        ),
        version=old.version + 1,
        status=fields.get("status", old.status),
        parent_version_id=old.id,
        share_scope=old.share_scope,
        share_grants=old.share_grants,
        created_by=requester_id,
        skill_pack_source=old.skill_pack_source,
    )
    # 旧版本 archived
    old.status = STATUS_ARCHIVED
    db.add(new_skill)
    await db.commit()
    await db.refresh(new_skill)
    return new_skill


async def delete_skill(
    db: AsyncSession, skill_id: str, requester_id: str,
) -> bool:
    """软删除 Skill（仅 owner）。"""
    stmt = select(AgentSkill).where(
        AgentSkill.id == skill_id,
        AgentSkill.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    skill = result.scalar_one_or_none()
    if skill is None or skill.created_by != requester_id:
        return False
    skill.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return True


async def share_skill(
    db: AsyncSession, skill_id: str, requester_id: str,
    grant_to: list[str], share_scope: str = SHARE_GRANT,
) -> AgentSkill | None:
    """授权共享 Skill（仅 owner）。share_scope=grant 时 grant_to 必填。"""
    stmt = select(AgentSkill).where(
        AgentSkill.id == skill_id,
        AgentSkill.deleted_at.is_(None),
        AgentSkill.status != STATUS_ARCHIVED,
    )
    result = await db.execute(stmt)
    skill = result.scalar_one_or_none()
    if skill is None or skill.created_by != requester_id:
        return None
    if share_scope == SHARE_GRANT and not grant_to:
        return None
    skill.share_scope = share_scope
    skill.share_grants = _dump_json_field(grant_to) if share_scope == SHARE_GRANT else _dump_json_field([])
    await db.commit()
    await db.refresh(skill)
    return skill


async def promote_to_org(
    db: AsyncSession, skill_id: str, admin_id: str, is_admin: bool,
) -> AgentSkill | None:
    """提升 Skill 到 org 级（仅 admin）。

    is_admin 由调用方传入（从 User.role == 'admin' 判定）。
    """
    if not is_admin:
        return None
    stmt = select(AgentSkill).where(
        AgentSkill.id == skill_id,
        AgentSkill.deleted_at.is_(None),
        AgentSkill.status != STATUS_ARCHIVED,
    )
    result = await db.execute(stmt)
    skill = result.scalar_one_or_none()
    if skill is None:
        return None
    skill.owner_scope = SCOPE_ORG
    skill.owner_id = SCOPE_ORG
    skill.share_scope = SHARE_ORG
    skill.reviewed_by = admin_id
    skill.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(skill)
    return skill


async def rollback_skill(
    db: AsyncSession, skill_id: str, target_version: int, requester_id: str,
) -> AgentSkill | None:
    """回退 Skill 到指定 version（仅 owner）。

    机制：找到该 name+owner 下 version==target_version 的历史记录，
    复制其内容创建新 version（旧 active archived）。
    """
    # 先找到当前 skill 拿 name/owner
    stmt = select(AgentSkill).where(
        AgentSkill.id == skill_id,
        AgentSkill.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    current = result.scalar_one_or_none()
    if current is None or current.created_by != requester_id:
        return None

    # 找历史版本
    hist_stmt = select(AgentSkill).where(
        AgentSkill.name == current.name,
        AgentSkill.owner_scope == current.owner_scope,
        AgentSkill.owner_id == current.owner_id,
        AgentSkill.version == target_version,
        AgentSkill.deleted_at.is_(None),
    )
    hist_result = await db.execute(hist_stmt)
    target = hist_result.scalar_one_or_none()
    if target is None:
        return None

    # 当前 active 版本 archived
    if current.status != STATUS_ARCHIVED:
        current.status = STATUS_ARCHIVED

    # 创建新版本（内容复制自 target）
    new_skill = AgentSkill(
        id=_gen_id(),
        name=target.name,
        description=target.description,
        owner_scope=target.owner_scope,
        owner_id=target.owner_id,
        agent_name=target.agent_name,
        system_prompt=target.system_prompt,
        provider=target.provider,
        tools=target.tools,
        cost_tier=target.cost_tier,
        acceptance_criteria=target.acceptance_criteria,
        version=current.version + 1,
        status=STATUS_ACTIVE,
        parent_version_id=target.id,
        share_scope=target.share_scope,
        share_grants=target.share_grants,
        created_by=requester_id,
        skill_pack_source=target.skill_pack_source,
    )
    db.add(new_skill)
    await db.commit()
    await db.refresh(new_skill)
    return new_skill


async def import_skill_pack(
    db: AsyncSession,
    git_url: str,
    owner_scope: str,
    owner_id: str,
    created_by: str,
) -> AgentSkill | None:
    """从 git raw URL 导入 Skill 包（fetch JSON，字段白名单解析）。

    失败返回 None（调用方转 422 诚实报错，不伪造）。
    """
    settings = get_settings()
    if not settings.agent_skill_enabled:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(git_url)
            if resp.status_code != 200:
                logger.warning("skill_pack_fetch_failed: status=%s url=%s", resp.status_code, git_url)
                return None
            data = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as e:
        logger.warning("skill_pack_parse_failed: %s url=%s", e, git_url)
        return None

    # 字段白名单解析
    allowed: dict[str, Any] = {}
    for k in _SKILL_PACK_ALLOWED_FIELDS:
        if k in data:
            allowed[k] = data[k]
    if "name" not in allowed or "agent_name" not in allowed:
        logger.warning("skill_pack_missing_required_fields: url=%s", git_url)
        return None

    # tools/acceptance_criteria 序列化
    tools_val = allowed.get("tools", [])
    if isinstance(tools_val, list):
        tools_val = _dump_json_field(tools_val)
    criteria_val = allowed.get("acceptance_criteria", [])
    if isinstance(criteria_val, list):
        criteria_val = _dump_json_field(criteria_val)

    skill = AgentSkill(
        id=_gen_id(),
        name=allowed["name"],
        description=allowed.get("description", ""),
        owner_scope=owner_scope,
        owner_id=owner_id,
        agent_name=allowed["agent_name"],
        system_prompt=allowed.get("system_prompt", ""),
        provider=allowed.get("provider", "deepseek"),
        tools=tools_val if isinstance(tools_val, str) else _dump_json_field([]),
        cost_tier=allowed.get("cost_tier", "standard"),
        acceptance_criteria=criteria_val if isinstance(criteria_val, str) else _dump_json_field([]),
        version=1,
        status=STATUS_DRAFT,
        share_scope=SHARE_NONE,
        share_grants=_dump_json_field([]),
        created_by=created_by,
        skill_pack_source=git_url,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill


async def instantiate(
    db: AsyncSession, skill_id: str, requester_id: str,
) -> Any | None:
    """动态创建 BaseAgent 子类实例（供 harness.run 调用）。

    通过 type() 动态创建类，复用 BaseAgent 的 _chat/think/think_with_tools。
    不注册到 harness._agent_registry（harness.run 直接接收实例）。
    """
    skill = await get_skill(db, skill_id, requester_id)
    if skill is None:
        return None
    from app.agents.base import BaseAgent
    tools_list = _parse_json_field(skill.tools, [])
    # 动态创建子类
    cls = type(
        f"SkillAgent_{skill.agent_name}",
        (BaseAgent,),
        {
            "agent_name": skill.agent_name,
            "system_prompt": skill.system_prompt,
            "provider": skill.provider,
            "tools": tools_list,
            "cost_tier": skill.cost_tier,
        },
    )
    return cls()

"""Agent Skill 资产管理 API — scope-owned 可授权共享的 Agent 能力

端点（前缀 /agents/skills）：
  GET    /api/agents/skills                列出当前用户可见的 Skill
  POST   /api/agents/skills                创建 Skill（draft）
  GET    /api/agents/skills/{id}           获取单个 Skill
  PUT    /api/agents/skills/{id}           更新 Skill（version+1，旧版本 archived）
  DELETE /api/agents/skills/{id}           软删除 Skill
  POST   /api/agents/skills/{id}/share     授权共享（grant_to + share_scope）
  POST   /api/agents/skills/{id}/promote   提升到 org 级（仅 admin）
  POST   /api/agents/skills/{id}/rollback  回退到指定 version
  POST   /api/agents/skills/import         从 git URL 导入 Skill 包
  POST   /api/agents/skills/{id}/instantiate 实例化为 BaseAgent 执行测试消息

借鉴 YC QM（2026-07-31 开源）的 Skill 设计。所有操作强制 user_id 隔离。
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.services import agent_skill_service

router = APIRouter(prefix="/agents/skills", tags=["AI Agent Skill 资产"])


# ── 请求/响应 schema ──


class SkillCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    agent_name: str = Field(min_length=1, max_length=50)
    system_prompt: str = Field(default="", max_length=20000)
    provider: str = Field(default="deepseek", max_length=30)
    tools: list = Field(default_factory=list)
    cost_tier: str = Field(default="standard", max_length=20)
    acceptance_criteria: list = Field(default_factory=list)
    owner_scope: str = Field(default="personal", max_length=20)
    owner_id: str | None = Field(default=None, max_length=36)


class SkillUpdateRequest(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    system_prompt: str | None = Field(default=None, max_length=20000)
    provider: str | None = Field(default=None, max_length=30)
    tools: list | None = None
    cost_tier: str | None = Field(default=None, max_length=20)
    acceptance_criteria: list | None = None
    status: str | None = Field(default=None, max_length=20)


class SkillShareRequest(BaseModel):
    grant_to: list[str] = Field(default_factory=list)
    share_scope: str = Field(default="grant", max_length=20)


class SkillRollbackRequest(BaseModel):
    target_version: int = Field(ge=1)


class SkillImportRequest(BaseModel):
    git_url: str = Field(min_length=10, max_length=500)
    owner_scope: str = Field(default="personal", max_length=20)
    owner_id: str | None = Field(default=None, max_length=36)


class SkillInstantiateRequest(BaseModel):
    test_message: str = Field(default="你好", max_length=500)


class SkillItemResponse(BaseModel):
    id: str
    name: str
    description: str
    owner_scope: str
    owner_id: str
    agent_name: str
    system_prompt: str
    provider: str
    tools: list
    cost_tier: str
    acceptance_criteria: list
    version: int
    status: str
    parent_version_id: str | None = None
    share_scope: str
    share_grants: list
    created_by: str
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    skill_pack_source: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SkillListResponse(BaseModel):
    count: int
    items: list[SkillItemResponse]


def _serialize(skill) -> SkillItemResponse:
    import json as _json
    return SkillItemResponse(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        owner_scope=skill.owner_scope,
        owner_id=skill.owner_id,
        agent_name=skill.agent_name,
        system_prompt=skill.system_prompt,
        provider=skill.provider,
        tools=_json.loads(skill.tools) if skill.tools else [],
        cost_tier=skill.cost_tier,
        acceptance_criteria=_json.loads(skill.acceptance_criteria) if skill.acceptance_criteria else [],
        version=skill.version,
        status=skill.status,
        parent_version_id=skill.parent_version_id,
        share_scope=skill.share_scope,
        share_grants=_json.loads(skill.share_grants) if skill.share_grants else [],
        created_by=skill.created_by,
        reviewed_by=skill.reviewed_by,
        reviewed_at=skill.reviewed_at.isoformat() if skill.reviewed_at else None,
        skill_pack_source=skill.skill_pack_source,
        created_at=skill.created_at.isoformat() if skill.created_at else None,
        updated_at=skill.updated_at.isoformat() if skill.updated_at else None,
    )


# ── 端点 ──


@router.get("", response_model=SkillListResponse)
async def list_skills(
    scope: str | None = Query(default=None, description="作用域过滤：personal/project/team/org"),
    include_archived: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户可见的 Skill（owner + 被授权 + org 级）。"""
    skills = await agent_skill_service.list_skills(
        db, current_user.id, scope_filter=scope, include_archived=include_archived,
    )
    items = [_serialize(s) for s in skills]
    return SkillListResponse(count=len(items), items=items)


@router.post("", response_model=SkillItemResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    payload: SkillCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建 Skill（status=draft）。owner_scope=personal 时 owner_id 默认当前用户。"""
    settings = get_settings()
    if not settings.agent_skill_enabled:
        raise HTTPException(status_code=503, detail="Skill 资产化功能未启用")
    owner_id = payload.owner_id or current_user.id
    if payload.owner_scope == "personal" and owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="personal 作用域 owner_id 必须是当前用户")
    try:
        skill = await agent_skill_service.create_skill(
            db,
            owner_scope=payload.owner_scope,
            owner_id=owner_id,
            name=payload.name,
            description=payload.description,
            agent_name=payload.agent_name,
            system_prompt=payload.system_prompt,
            provider=payload.provider,
            tools=payload.tools,
            cost_tier=payload.cost_tier,
            acceptance_criteria=payload.acceptance_criteria,
            created_by=current_user.id,
        )
    except Exception as e:
        # 唯一约束冲突等
        raise HTTPException(status_code=409, detail=f"创建失败：{e}")
    return _serialize(skill)


@router.get("/{skill_id}", response_model=SkillItemResponse)
async def get_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个 Skill（无权访问 → 404）。"""
    skill = await agent_skill_service.get_skill(db, skill_id, current_user.id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill 不存在或无权访问")
    return _serialize(skill)


@router.put("/{skill_id}", response_model=SkillItemResponse)
async def update_skill(
    skill_id: str,
    payload: SkillUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新 Skill（version+1，旧版本 archived）。仅 owner 可更新。"""
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    skill = await agent_skill_service.update_skill(
        db, skill_id, current_user.id, **fields,
    )
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill 不存在或无权更新")
    return _serialize(skill)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """软删除 Skill（仅 owner）。"""
    deleted = await agent_skill_service.delete_skill(db, skill_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Skill 不存在或无权删除")
    return None


@router.post("/{skill_id}/share", response_model=SkillItemResponse)
async def share_skill(
    skill_id: str,
    payload: SkillShareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """授权共享 Skill（仅 owner）。share_scope=grant 时 grant_to 必填。"""
    if payload.share_scope == "grant" and not payload.grant_to:
        raise HTTPException(status_code=422, detail="share_scope=grant 时 grant_to 必填")
    skill = await agent_skill_service.share_skill(
        db, skill_id, current_user.id,
        grant_to=payload.grant_to, share_scope=payload.share_scope,
    )
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill 不存在或无权操作")
    return _serialize(skill)


@router.post("/{skill_id}/promote", response_model=SkillItemResponse)
async def promote_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提升 Skill 到 org 级（仅 admin，403 否则）。"""
    is_admin = current_user.role == "admin"
    if not is_admin:
        raise HTTPException(status_code=403, detail="仅 admin 可提升 Skill 到 org 级")
    skill = await agent_skill_service.promote_to_org(
        db, skill_id, current_user.id, is_admin=True,
    )
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    return _serialize(skill)


@router.post("/{skill_id}/rollback", response_model=SkillItemResponse)
async def rollback_skill(
    skill_id: str,
    payload: SkillRollbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """回退 Skill 到指定 version（仅 owner）。"""
    skill = await agent_skill_service.rollback_skill(
        db, skill_id, payload.target_version, current_user.id,
    )
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill 不存在/无权/目标 version 不存在")
    return _serialize(skill)


@router.post("/import", response_model=SkillItemResponse, status_code=status.HTTP_201_CREATED)
async def import_skill(
    payload: SkillImportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从 git raw URL 导入 Skill 包（字段白名单解析，失败 422 诚实报错）。"""
    settings = get_settings()
    if not settings.agent_skill_enabled:
        raise HTTPException(status_code=503, detail="Skill 资产化功能未启用")
    owner_id = payload.owner_id or current_user.id
    skill = await agent_skill_service.import_skill_pack(
        db, payload.git_url,
        owner_scope=payload.owner_scope,
        owner_id=owner_id,
        created_by=current_user.id,
    )
    if skill is None:
        raise HTTPException(
            status_code=422,
            detail="Skill 包导入失败：URL 不可达或 JSON 格式错误或缺少必填字段(name/agent_name)",
        )
    return _serialize(skill)


@router.post("/{skill_id}/instantiate")
async def instantiate_skill(
    skill_id: str,
    payload: SkillInstantiateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """实例化 Skill 为 BaseAgent 并执行测试消息（mock 模式下返回降级响应）。"""
    agent = await agent_skill_service.instantiate(db, skill_id, current_user.id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Skill 不存在或无权访问")
    try:
        # mock 模式（无 API key）下 think 会走降级，不阻塞
        reply = await agent.think(
            payload.test_message, db=db, user_id=current_user.id,
        )
        return {
            "skill_id": skill_id,
            "agent_name": agent.agent_name,
            "reply": reply or "[mock 模式无 LLM 响应]",
            "status": "ok",
        }
    except Exception as e:
        # LLM 不可用 → 诚实降级，不伪造
        return {
            "skill_id": skill_id,
            "agent_name": agent.agent_name,
            "reply": f"[实例化执行失败：{type(e).__name__}]",
            "status": "degraded",
        }
    finally:
        await agent.close()

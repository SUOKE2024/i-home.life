"""Agent 长期记忆管理 API — 跨会话记忆的手动读写入口

端点（前缀 /agents/memory）：
  GET    /api/agents/memory          列出当前用户长期记忆
  POST   /api/agents/memory          手动保存一条记忆（upsert）
  DELETE /api/agents/memory/{id}     删除一条记忆

所有操作强制 user_id 隔离（PASETO current_user），记忆数据不跨用户可见。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.services import agent_memory_service

router = APIRouter(prefix="/agents/memory", tags=["AI Agent 记忆"])

# 允许的类目（与服务层常量保持一致）
_ALLOWED_CATEGORIES = (
    agent_memory_service.CATEGORY_PREFERENCE,
    agent_memory_service.CATEGORY_LOCATION,
    agent_memory_service.CATEGORY_FACT,
)
# 允许的作用域（与服务层常量保持一致，借鉴 YC QM Scope）
_ALLOWED_SCOPES = agent_memory_service._ALL_SCOPES


class MemoryCreateRequest(BaseModel):
    category: str = Field(default=agent_memory_service.CATEGORY_FACT, max_length=30)
    key: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=200)
    importance: int = Field(default=1, ge=1, le=5)
    # v1.4.x scope 透传（借鉴 YC QM）：personal=仅本人（默认）/ project=项目内共享 / team / org
    scope: str = Field(default=agent_memory_service.SCOPE_PERSONAL, max_length=20)
    project_id: str | None = Field(default=None, max_length=36)


class MemoryItemResponse(BaseModel):
    id: str
    category: str
    key: str
    value: str
    source: str | None = None
    importance: int
    scope: str = agent_memory_service.SCOPE_PERSONAL
    project_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class MemoryListResponse(BaseModel):
    count: int
    items: list[MemoryItemResponse]


@router.get("/org", response_model=MemoryListResponse)
async def list_org_memories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """v1.15.7 组织级共享记忆（信通院记忆分级「跨 Agent 共享」对齐）。

    平台管理员写入（POST scope=org 需 admin）、全平台成员可读。
    team 级共享因项目无 Team 实体暂缓（P2 路线图，诚实标注）。
    """
    rows = await agent_memory_service.get_org_memories(db)
    items = [_serialize(m) for m in rows]
    return MemoryListResponse(count=len(items), items=items)


def _serialize(mem) -> MemoryItemResponse:
    return MemoryItemResponse(
        id=mem.id,
        category=mem.category,
        key=mem.memory_key,
        value=mem.memory_value,
        source=mem.source,
        importance=mem.importance,
        scope=mem.scope,
        project_id=mem.project_id or None,
        created_at=mem.created_at.isoformat() if mem.created_at else None,
        updated_at=mem.updated_at.isoformat() if mem.updated_at else None,
    )


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    scope: str | None = Query(default=None, description="作用域过滤：personal/project/team/org"),
    project_id: str | None = Query(default=None, description="项目ID（scope=project 时按项目过滤）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的长期记忆（按最近更新倒序）。

    v1.4.x：支持 scope/project_id 过滤（借鉴 YC QM Scope）。
    不传 scope 返回全部作用域记忆（兼容旧行为）。
    """
    if scope is not None and scope not in _ALLOWED_SCOPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"scope 必须是 {list(_ALLOWED_SCOPES)} 之一",
        )
    rows = await agent_memory_service.get_user_memories(
        db, current_user.id, scope=scope, project_id=project_id,
    )
    items = [_serialize(m) for m in rows]
    return MemoryListResponse(count=len(items), items=items)


@router.post("", response_model=MemoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_memory(
    payload: MemoryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手动保存一条长期记忆（同 key+scope+project_id 覆盖更新）。

    v1.4.x：scope=project 时 project_id 必填，否则回退 personal 并告警
    （对齐 service 层 agent_memory_service.save_memory 行为）。
    """
    if payload.category not in _ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"category 必须是 {list(_ALLOWED_CATEGORIES)} 之一",
        )
    if payload.scope not in _ALLOWED_SCOPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"scope 必须是 {list(_ALLOWED_SCOPES)} 之一",
        )
    if payload.scope == agent_memory_service.SCOPE_PROJECT and not payload.project_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="scope=project 时 project_id 必填",
        )
    # v1.15.7 组织级共享记忆：scope=org 仅平台管理员可写（全平台可见，防滥用）
    if payload.scope == agent_memory_service.SCOPE_ORG and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="scope=org 组织级共享记忆仅平台管理员可写入",
        )
    mem = await agent_memory_service.save_memory(
        db, current_user.id, payload.category, payload.key,
        payload.value, source="manual", importance=payload.importance,
        scope=payload.scope, project_id=payload.project_id,
    )
    return _serialize(mem)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除一条记忆（仅限当前用户自己的记忆）"""
    deleted = await agent_memory_service.delete_memory(db, current_user.id, memory_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="记忆不存在")
    return None

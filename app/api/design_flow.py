"""设计流程编排 API — 风格/预算选供应商 → VR 效果图 → 可行性分析"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.rbac import verify_project_access
from app.schemas.design_flow import (
    DesignFlowCreate,
    DesignFlowResponse,
    DesignFlowAdjustRequest,
    DesignFlowFeasibilityResponse,
    DesignFlowSuggestResponse,
    SupplierCandidate,
    SupplierSelectRequest,
)
from app.services import design_flow_service

router = APIRouter(prefix="/design-flow", tags=["设计流程编排"])


async def _get_flow_or_404(db: AsyncSession, flow_id: str, user: User):
    flow = await design_flow_service.get_design_flow(db, flow_id)
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设计流程会话不存在")
    await verify_project_access(project_id=flow.project_id, current_user=user, db=db)
    return flow


@router.post("", response_model=DesignFlowResponse, status_code=status.HTTP_201_CREATED)
async def create_design_flow(
    body: DesignFlowCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """创建编排会话（量房户型就绪 → 选风格/预算）。"""
    await verify_project_access(project_id=body.project_id, current_user=user, db=db)
    try:
        flow = await design_flow_service.start_design_flow(
            db,
            project_id=body.project_id,
            floorplan_id=body.floorplan_id,
            style=body.style,
            budget=body.budget,
            supplier_selection_mode=body.supplier_selection_mode,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return DesignFlowResponse.model_validate(flow)


@router.get("/{flow_id}", response_model=DesignFlowResponse)
async def get_design_flow(
    flow_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    flow = await _get_flow_or_404(db, flow_id, user)
    return DesignFlowResponse.model_validate(flow)


@router.post("/{flow_id}/suppliers/match", response_model=list[SupplierCandidate])
async def match_suppliers(
    flow_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """匹配候选供应商（风格 + 价格档位硬过滤）。"""
    flow = await _get_flow_or_404(db, flow_id, user)
    candidates = await design_flow_service.match_suppliers(db, flow.style, flow.price_tier)
    return [SupplierCandidate(**c) for c in candidates]


@router.post("/{flow_id}/suppliers/select", response_model=DesignFlowResponse)
async def select_supplier(
    flow_id: str,
    body: SupplierSelectRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """随机/自选供应商。"""
    flow = await _get_flow_or_404(db, flow_id, user)
    try:
        flow = await design_flow_service.select_supplier(
            db, flow, body.mode, body.supplier_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return DesignFlowResponse.model_validate(flow)


@router.post("/{flow_id}/render", response_model=DesignFlowResponse)
async def render(
    flow_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """触发渲染（每房间效果图 + 全屋漫游）。"""
    flow = await _get_flow_or_404(db, flow_id, user)
    try:
        flow = await design_flow_service.trigger_render(db, flow, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return DesignFlowResponse.model_validate(flow)


@router.post("/{flow_id}/adjust", response_model=DesignFlowResponse)
async def adjust(
    flow_id: str,
    body: DesignFlowAdjustRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """调整（任意环节调整均触发重渲染）。"""
    flow = await _get_flow_or_404(db, flow_id, user)
    changes = body.model_dump(exclude_none=True)
    try:
        flow = await design_flow_service.adjust(db, flow, changes, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return DesignFlowResponse.model_validate(flow)


@router.post("/{flow_id}/confirm", response_model=DesignFlowResponse)
async def confirm(
    flow_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """确认 → 触发可行性分析。"""
    flow = await _get_flow_or_404(db, flow_id, user)
    try:
        flow = await design_flow_service.confirm(db, flow)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return DesignFlowResponse.model_validate(flow)


@router.get("/{flow_id}/feasibility", response_model=DesignFlowFeasibilityResponse)
async def get_feasibility(
    flow_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """查询可行性分析结果。"""
    await _get_flow_or_404(db, flow_id, user)
    feasibility = await design_flow_service.get_feasibility(db, flow_id)
    if not feasibility:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="可行性分析尚未生成")
    return DesignFlowFeasibilityResponse.model_validate(feasibility)


@router.post("/{flow_id}/suggest", response_model=DesignFlowSuggestResponse)
async def suggest(
    flow_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """LLM 智能体调整建议（旁路，只读，不阻塞主流程）。"""
    flow = await _get_flow_or_404(db, flow_id, user)
    result = await design_flow_service.suggest_adjustment(db, flow, user.id)
    return DesignFlowSuggestResponse(**result)

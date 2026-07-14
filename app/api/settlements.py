from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.settlement import (
    AnomalyAttachRequest,
    ReviewRequest,
    SettlementCreate,
    SettlementResponse,
)
from app.auth import get_current_user
from app.services import settlement_service
from app.agents.settlement import SettlementAgent
from app.ws import ws_manager

router = APIRouter(prefix="/settlements", tags=["结算"])


class MilestoneSettlementRequest(BaseModel):
    contract_amount: float
    milestone_code: str
    change_amount: float = 0.0
    deduction_amount: float = 0.0
    paid_amount: float = 0.0


class AnomalyCheckRequest(BaseModel):
    contract_amount: float
    actual_amount: float
    change_orders: list[dict] = []
    unaccepted_items: list[dict] = []
    line_items: list[dict] = []


class ReconciliationRequest(BaseModel):
    contract_amount: float
    change_orders: list[dict] = []
    procurement_actual: float = 0.0
    labor_actual: float = 0.0
    unaccepted_items: list[dict] = []


class AutoSettlementRequest(BaseModel):
    """F14 一键自动结算请求"""
    contract_amount: float
    actual_amount: float
    change_orders: list[dict] = []
    unaccepted_items: list[dict] = []
    line_items: list[dict] = []


@router.get("/project/{project_id}", response_model=SettlementResponse)
async def get_settlement(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settlement = await settlement_service.get_settlement(db, project_id)
    if not settlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="结算单不存在")
    return SettlementResponse.model_validate(settlement)


@router.post("", response_model=SettlementResponse, status_code=status.HTTP_201_CREATED)
async def create_settlement(
    data: SettlementCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await settlement_service.get_settlement(db, data.project_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该项目已有结算单")
    settlement = await settlement_service.create_settlement(db, data.model_dump())
    resp = SettlementResponse.model_validate(settlement)
    await ws_manager.broadcast_to_project(data.project_id, "settlement.created", resp.model_dump())
    return resp


@router.post("/generate-from-budget/{project_id}", response_model=SettlementResponse, status_code=status.HTTP_201_CREATED)
async def generate_from_budget(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settlement = await settlement_service.generate_from_budget(db, project_id)
    if not settlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到预算，请先创建预算")
    resp = SettlementResponse.model_validate(settlement)
    await ws_manager.broadcast_to_project(project_id, "settlement.generated", resp.model_dump())
    return resp


@router.post("/confirm/{project_id}", response_model=SettlementResponse)
async def confirm_settlement(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settlement = await settlement_service.confirm_settlement(db, project_id)
    if not settlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="结算单不存在")
    resp = SettlementResponse.model_validate(settlement)
    # F14：若存在严重异常未复核，返回 409 阻止确认
    if settlement.review_required and settlement.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "存在严重异常，需先人工复核",
                "critical_anomaly_count": settlement.critical_anomaly_count,
                "suggested_deduction": settlement.suggested_deduction,
            },
        )
    await ws_manager.broadcast_to_project(project_id, "settlement.confirmed", resp.model_dump())
    return resp


# ── F14 里程碑结算 ──
@router.post("/milestone")
async def generate_milestone_settlement(
    data: MilestoneSettlementRequest,
    current_user: User = Depends(get_current_user),
):
    agent = SettlementAgent()
    return agent.generate_milestone_settlement(
        data.contract_amount,
        data.milestone_code,
        data.change_amount,
        data.deduction_amount,
        data.paid_amount,
    )


@router.get("/milestones")
async def list_milestones(
    current_user: User = Depends(get_current_user),
):
    agent = SettlementAgent()
    return agent.list_milestones()


# ── 结算异常检测 ──
@router.post("/anomaly-check")
async def check_anomalies(
    data: AnomalyCheckRequest,
    current_user: User = Depends(get_current_user),
):
    agent = SettlementAgent()
    return agent.detect_anomalies(data.model_dump())


# ── F14 异常标记附加到结算单 ──
@router.post("/anomaly-attach/{project_id}", response_model=SettlementResponse)
async def attach_anomalies(
    project_id: str,
    data: AnomalyAttachRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settlement = await settlement_service.attach_anomalies(
        db, project_id, data.anomalies, data.auto_mark_lines
    )
    if not settlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="结算单不存在")
    resp = SettlementResponse.model_validate(settlement)
    await ws_manager.broadcast_to_project(project_id, "settlement.anomaly_attached", resp.model_dump())
    return resp


# ── F14 人工复核 ──
@router.post("/request-review/{project_id}", response_model=SettlementResponse)
async def request_review(
    project_id: str,
    data: ReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settlement = await settlement_service.request_review(
        db, project_id, data.reason, data.reviewer_id or str(current_user.id)
    )
    if not settlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="结算单不存在")
    resp = SettlementResponse.model_validate(settlement)
    await ws_manager.broadcast_to_project(project_id, "settlement.review_requested", resp.model_dump())
    return resp


@router.post("/approve-review/{project_id}", response_model=SettlementResponse)
async def approve_review(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settlement = await settlement_service.approve_review(db, project_id, str(current_user.id))
    if not settlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="结算单不存在")
    resp = SettlementResponse.model_validate(settlement)
    await ws_manager.broadcast_to_project(project_id, "settlement.review_approved", resp.model_dump())
    return resp


# ── 对账单生成 ──
@router.post("/reconciliation")
async def generate_reconciliation(
    data: ReconciliationRequest,
    current_user: User = Depends(get_current_user),
):
    agent = SettlementAgent()
    return agent.generate_reconciliation(data.model_dump())


# ── F14 一键自动结算 ──
@router.post("/auto-settlement")
async def auto_settlement(
    data: AutoSettlementRequest,
    current_user: User = Depends(get_current_user),
):
    agent = SettlementAgent()
    return agent.auto_generate_full_settlement(
        contract_amount=data.contract_amount,
        actual_amount=data.actual_amount,
        change_orders=data.change_orders,
        unaccepted_items=data.unaccepted_items,
        line_items=data.line_items,
    )


# ── F14 对账单导出 ──
@router.get("/export/{project_id}")
async def export_reconciliation(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payload = await settlement_service.export_reconciliation(db, project_id)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="结算单不存在")
    return payload

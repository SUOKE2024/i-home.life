from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import StreamingResponse
import io

from app.database import get_db
from app.models.user import User
from app.schemas.settlement import (
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


# ── 对账单生成 ──
@router.post("/reconciliation")
async def generate_reconciliation(
    data: ReconciliationRequest,
    current_user: User = Depends(get_current_user),
):
    agent = SettlementAgent()
    return agent.generate_reconciliation(data.model_dump())

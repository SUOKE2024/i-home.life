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
from app.rbac import verify_project_access
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


@router.get(
    "/project/{project_id}",
    response_model=SettlementResponse,
    summary="获取项目结算单",
    description="根据项目 ID 获取该项目的结算单，包含结算金额和异常信息。",
    response_description="结算单详情",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "结算单不存在"},
    },
)
async def get_settlement(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    settlement = await settlement_service.get_settlement(db, project_id)
    if not settlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="结算单不存在")
    return SettlementResponse.model_validate(settlement)


@router.post(
    "",
    response_model=SettlementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建结算单",
    description="为项目创建结算单，包含合同金额、变更金额和扣款金额。",
    response_description="创建成功，返回结算单信息",
    responses={
        201: {"description": "结算单创建成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        409: {"description": "该项目已有结算单"},
    },
)
async def create_settlement(
    data: SettlementCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    existing = await settlement_service.get_settlement(db, data.project_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该项目已有结算单")
    settlement = await settlement_service.create_settlement(db, data.model_dump())
    resp = SettlementResponse.model_validate(settlement)
    await ws_manager.broadcast_to_project(data.project_id, "settlement.created", resp.model_dump())
    return resp


@router.post(
    "/generate-from-budget/{project_id}",
    response_model=SettlementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="从预算生成结算单",
    description="根据项目预算自动生成结算单，将预算金额转化为结算明细。",
    response_description="生成成功，返回结算单信息",
    responses={
        201: {"description": "结算单生成成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "未找到预算"},
    },
)
async def generate_from_budget(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    settlement = await settlement_service.generate_from_budget(db, project_id)
    if not settlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到预算，请先创建预算")
    resp = SettlementResponse.model_validate(settlement)
    await ws_manager.broadcast_to_project(project_id, "settlement.generated", resp.model_dump())
    return resp


@router.post(
    "/submit/{project_id}",
    response_model=SettlementResponse,
    summary="提交结算单",
    description="提交结算单，将状态从 draft 变更为 submitted。",
    response_description="提交后的结算单信息",
    responses={
        200: {"description": "提交成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "结算单不存在"},
    },
)
async def submit_settlement(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    settlement = await settlement_service.submit_settlement(db, project_id)
    if not settlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="结算单不存在")
    resp = SettlementResponse.model_validate(settlement)
    await ws_manager.broadcast_to_project(project_id, "settlement.submitted", resp.model_dump())
    return resp


@router.post(
    "/confirm/{project_id}",
    response_model=SettlementResponse,
    summary="确认结算单",
    description="确认项目的结算单，如有严重异常未复核则返回 409 阻止确认。",
    response_description="确认成功，返回结算单信息",
    responses={
        200: {"description": "确认成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "结算单不存在"},
        409: {"description": "存在严重异常需人工复核"},
    },
)
async def confirm_settlement(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
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
@router.post(
    "/milestone",
    summary="里程碑结算",
    description="根据里程碑进度自动计算应付款项，生成里程碑结算报告。",
    responses={
        200: {"description": "结算成功"},
        400: {"description": "请求参数无效"},
    },
)
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


@router.get(
    "/milestones",
    summary="获取里程碑列表",
    description="获取系统预设的施工里程碑节点和付款比例。",
    responses={
        200: {"description": "获取成功"},
    },
)
async def list_milestones(
    current_user: User = Depends(get_current_user),
):
    agent = SettlementAgent()
    return agent.list_milestones()


# ── 结算异常检测 ──
@router.post(
    "/anomaly-check",
    summary="结算异常检测",
    description="AI 检测结算数据中的异常，包括金额偏差、未验收项和变更单异常。",
    responses={
        200: {"description": "检测成功"},
        400: {"description": "请求参数无效"},
    },
)
async def check_anomalies(
    data: AnomalyCheckRequest,
    current_user: User = Depends(get_current_user),
):
    agent = SettlementAgent()
    return agent.detect_anomalies(data.model_dump())


# ── F14 异常标记附加到结算单 ──
@router.post(
    "/anomaly-attach/{project_id}",
    response_model=SettlementResponse,
    summary="附加异常标记",
    description="将检测到的结算异常标记附加到项目结算单上。",
    response_description="更新后的结算单信息",
    responses={
        200: {"description": "标记成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "结算单不存在"},
    },
)
async def attach_anomalies(
    project_id: str,
    data: AnomalyAttachRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    settlement = await settlement_service.attach_anomalies(
        db, project_id, data.anomalies, data.auto_mark_lines
    )
    if not settlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="结算单不存在")
    resp = SettlementResponse.model_validate(settlement)
    await ws_manager.broadcast_to_project(project_id, "settlement.anomaly_attached", resp.model_dump())
    return resp


# ── F14 人工复核 ──
@router.post(
    "/request-review/{project_id}",
    response_model=SettlementResponse,
    summary="请求人工复核",
    description="对存在异常的结算单发起人工复核请求，指定复核人和复核原因。",
    response_description="复核请求已提交",
    responses={
        200: {"description": "复核请求成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "结算单不存在"},
    },
)
async def request_review(
    project_id: str,
    data: ReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    settlement = await settlement_service.request_review(
        db, project_id, data.reason, data.reviewer_id or str(current_user.id)
    )
    if not settlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="结算单不存在")
    resp = SettlementResponse.model_validate(settlement)
    await ws_manager.broadcast_to_project(project_id, "settlement.review_requested", resp.model_dump())
    return resp


@router.post(
    "/approve-review/{project_id}",
    response_model=SettlementResponse,
    summary="批准复核",
    description="复核人批准结算单的复核请求，确认异常已处理。",
    response_description="复核已批准",
    responses={
        200: {"description": "批准成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "结算单不存在"},
    },
)
async def approve_review(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    settlement = await settlement_service.approve_review(db, project_id, str(current_user.id))
    if not settlement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="结算单不存在")
    resp = SettlementResponse.model_validate(settlement)
    await ws_manager.broadcast_to_project(project_id, "settlement.review_approved", resp.model_dump())
    return resp


# ── 对账单生成 ──
@router.post(
    "/reconciliation",
    summary="生成对账单",
    description="AI 根据合同金额、变更单和实际花费生成对账单，对比预算与实际差异。",
    responses={
        200: {"description": "生成成功"},
        400: {"description": "请求参数无效"},
    },
)
async def generate_reconciliation(
    data: ReconciliationRequest,
    current_user: User = Depends(get_current_user),
):
    agent = SettlementAgent()
    return agent.generate_reconciliation(data.model_dump())


# ── F14 一键自动结算 ──
@router.post(
    "/auto-settlement",
    summary="一键自动结算",
    description="AI 自动生成完整的结算报告，包含异常检测、扣款建议和对账单。",
    responses={
        200: {"description": "结算成功"},
        400: {"description": "请求参数无效"},
    },
)
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
@router.get(
    "/export/{project_id}",
    summary="导出对账单",
    description="导出项目的结算对账单数据。",
    responses={
        200: {"description": "导出成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "结算单不存在"},
    },
)
async def export_reconciliation(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    payload = await settlement_service.export_reconciliation(db, project_id)
    if not payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="结算单不存在")
    return payload

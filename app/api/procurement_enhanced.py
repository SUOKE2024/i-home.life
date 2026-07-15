"""F33/F34 增强 API — AI 比价 + 担保支付 + 物流追踪 + 样品索要"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.material import BOMItem
from app.models.procurement import ProcurementOrder
from app.auth import get_current_user
from app.schemas.procurement_enhanced import (
    ComparisonCreateRequest,
    PriceComparisonResponse,
    PriceComparisonDetailResponse,
    PriceComparisonItemResponse,
    AiMatchRequest,
    AiMatchResult,
    EscrowCreateRequest,
    EscrowRefundRequest,
    EscrowPaymentResponse,
    LogisticsCreateRequest,
    LogisticsUpdateRequest,
    LogisticsTrackingResponse,
    SampleCreateRequest,
    SampleUpdateRequest,
    SampleRequestResponse,
)
from app.services import procurement_enhanced_service as svc
from app.ws import ws_manager

router = APIRouter(prefix="/procurement-enhanced", tags=["采购增强"])


# ── F33 比价报告 ──

@router.post(
    "/comparisons",
    response_model=PriceComparisonDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comparison(
    data: ComparisonCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从 BOM 生成比价报告"""
    project = await db.get(Project, data.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    try:
        comparison = await svc.generate_comparison_from_bom(
            db, data.project_id, data.bom_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    detail = await svc.get_comparison(db, comparison.id)
    resp = PriceComparisonDetailResponse.model_validate(detail)
    await ws_manager.broadcast_to_project(
        data.project_id, "comparison.created", resp.model_dump(mode="json")
    )
    return resp


@router.get(
    "/comparisons/project/{project_id}",
    response_model=list[PriceComparisonResponse],
)
async def list_project_comparisons(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await svc.list_project_comparisons(db, project_id)
    return [PriceComparisonResponse.model_validate(c) for c in items]


@router.get(
    "/comparisons/{comparison_id}",
    response_model=PriceComparisonDetailResponse,
)
async def get_comparison(
    comparison_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    comparison = await svc.get_comparison(db, comparison_id)
    if not comparison:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="比价报告不存在")
    return PriceComparisonDetailResponse.model_validate(comparison)


@router.get(
    "/comparisons/{comparison_id}/items",
    response_model=list[PriceComparisonItemResponse],
)
async def list_comparison_items(
    comparison_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await svc.list_comparison_items(db, comparison_id)
    return [PriceComparisonItemResponse.model_validate(i) for i in items]


@router.post("/ai-match", response_model=AiMatchResult)
async def ai_match(
    data: AiMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI 供应商匹配"""
    from sqlalchemy import select

    result = await db.execute(select(BOMItem).where(BOMItem.id == data.bom_item_id))
    bom_item = result.scalar_one_or_none()
    if not bom_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BOM 物料不存在")

    match = await svc.ai_match_suppliers(db, bom_item, location=data.location)
    return AiMatchResult(
        bom_item_id=data.bom_item_id,
        material_name=match["material_name"],
        matched_suppliers=match["matched_suppliers"],
        recommended_supplier_id=match["recommended_supplier_id"],
        reason=match["reason"],
    )


@router.delete("/comparisons/{comparison_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comparison(
    comparison_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ok = await svc.delete_comparison(db, comparison_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="比价报告不存在")
    return None


# ── F34 担保支付 ──

@router.post(
    "/escrow",
    response_model=EscrowPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_escrow(
    data: EscrowCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建担保支付"""
    order = await db.get(ProcurementOrder, data.order_id)
    if order:
        project = await db.get(Project, order.project_id)
        if not project or project.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    try:
        payment = await svc.create_escrow_payment(db, data.order_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    resp = EscrowPaymentResponse.model_validate(payment)
    await ws_manager.broadcast_to_project(
        payment.project_id, "escrow.created", resp.model_dump(mode="json")
    )
    return resp


@router.get("/escrow/{escrow_id}", response_model=EscrowPaymentResponse)
async def get_escrow(
    escrow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payment = await svc.get_escrow(db, escrow_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="担保支付不存在")
    return EscrowPaymentResponse.model_validate(payment)


@router.get(
    "/escrow/order/{order_id}",
    response_model=list[EscrowPaymentResponse],
)
async def list_order_escrow(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按订单查询担保支付记录"""
    items = await svc.list_order_escrow(db, order_id)
    return [EscrowPaymentResponse.model_validate(p) for p in items]


@router.post("/escrow/{escrow_id}/pay", response_model=EscrowPaymentResponse)
async def buyer_pay(
    escrow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """买家付款（资金进入平台担保账户）"""
    payment = await svc.get_escrow(db, escrow_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="担保支付不存在")
    project = await db.get(Project, payment.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    try:
        payment = await svc.buyer_pay(db, escrow_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="担保支付不存在")

    resp = EscrowPaymentResponse.model_validate(payment)
    await ws_manager.broadcast_to_project(
        payment.project_id, "escrow.buyer_paid", resp.model_dump(mode="json")
    )
    return resp


@router.post("/escrow/{escrow_id}/release", response_model=EscrowPaymentResponse)
async def release_to_supplier(
    escrow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """确认收货后释放资金给供应商"""
    existing = await svc.get_escrow(db, escrow_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="担保支付不存在")
    project = await db.get(Project, existing.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    try:
        payment = await svc.release_to_supplier(db, escrow_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="担保支付不存在")

    resp = EscrowPaymentResponse.model_validate(payment)
    await ws_manager.broadcast_to_project(
        payment.project_id, "escrow.released", resp.model_dump(mode="json")
    )
    return resp


@router.post("/escrow/{escrow_id}/refund", response_model=EscrowPaymentResponse)
async def request_refund(
    escrow_id: str,
    data: EscrowRefundRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """申请退款"""
    existing = await svc.get_escrow(db, escrow_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="担保支付不存在")
    project = await db.get(Project, existing.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    try:
        payment = await svc.request_refund(db, escrow_id, data.reason)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="担保支付不存在")

    resp = EscrowPaymentResponse.model_validate(payment)
    await ws_manager.broadcast_to_project(
        payment.project_id, "escrow.refunded", resp.model_dump(mode="json")
    )
    return resp


@router.post("/escrow/{escrow_id}/dispute", response_model=EscrowPaymentResponse)
async def request_dispute(
    escrow_id: str,
    data: EscrowRefundRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发起争议"""
    existing = await svc.get_escrow(db, escrow_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="担保支付不存在")
    project = await db.get(Project, existing.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    try:
        payment = await svc.request_dispute(db, escrow_id, data.reason)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="担保支付不存在")

    resp = EscrowPaymentResponse.model_validate(payment)
    await ws_manager.broadcast_to_project(
        payment.project_id, "escrow.disputed", resp.model_dump(mode="json")
    )
    return resp


@router.post("/escrow/{escrow_id}/resolve", response_model=EscrowPaymentResponse)
async def resolve_dispute(
    escrow_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """解决争议: refunded 或 supplier_received"""
    existing = await svc.get_escrow(db, escrow_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="担保支付不存在")
    project = await db.get(Project, existing.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    resolution = body.get("resolution")
    if resolution not in ("refunded", "supplier_received"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="resolution 必须为 refunded 或 supplier_received",
        )
    try:
        payment = await svc.resolve_dispute(db, escrow_id, resolution)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="担保支付不存在")

    resp = EscrowPaymentResponse.model_validate(payment)
    event = "escrow.resolved_refunded" if resolution == "refunded" else "escrow.resolved_released"
    await ws_manager.broadcast_to_project(
        payment.project_id, event, resp.model_dump(mode="json")
    )
    return resp


# ── F34 物流追踪 ──

@router.post(
    "/logistics",
    response_model=LogisticsTrackingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_logistics(
    data: LogisticsCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建物流单"""
    order = await db.get(ProcurementOrder, data.order_id)
    if order:
        project = await db.get(Project, order.project_id)
        if not project or project.owner_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    try:
        tracking = await svc.create_logistics(
            db, data.order_id, data.carrier, data.ship_from, data.ship_to
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    resp = LogisticsTrackingResponse.model_validate(tracking)
    await ws_manager.broadcast_to_project(
        tracking.project_id, "logistics.created", resp.model_dump(mode="json")
    )
    return resp


@router.get("/logistics/{tracking_id}", response_model=LogisticsTrackingResponse)
async def get_logistics(
    tracking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tracking = await svc.get_logistics(db, tracking_id)
    if not tracking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物流单不存在")
    return LogisticsTrackingResponse.model_validate(tracking)


@router.patch("/logistics/{tracking_id}", response_model=LogisticsTrackingResponse)
async def update_logistics(
    tracking_id: str,
    data: LogisticsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新物流轨迹"""
    existing = await svc.get_logistics(db, tracking_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物流单不存在")
    project = await db.get(Project, existing.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    tracking = await svc.update_tracking(
        db,
        tracking_id,
        status=data.status,
        location=data.location,
        description=data.description,
    )
    if not tracking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物流单不存在")

    resp = LogisticsTrackingResponse.model_validate(tracking)
    await ws_manager.broadcast_to_project(
        tracking.project_id, "logistics.updated", resp.model_dump(mode="json")
    )
    return resp


@router.get(
    "/logistics/order/{order_id}",
    response_model=list[LogisticsTrackingResponse],
)
async def get_order_logistics(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await svc.get_order_logistics(db, order_id)
    return [LogisticsTrackingResponse.model_validate(t) for t in items]


# ── F34 样品索要 ──

@router.post(
    "/samples",
    response_model=SampleRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sample(
    data: SampleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """样品索要"""
    project = await db.get(Project, data.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    sample = await svc.request_sample(
        db,
        project_id=data.project_id,
        supplier_id=data.supplier_id,
        material_id=data.material_id,
        sample_type=data.sample_type,
    )
    resp = SampleRequestResponse.model_validate(sample)
    await ws_manager.broadcast_to_project(
        data.project_id, "sample.created", resp.model_dump(mode="json")
    )
    return resp


@router.get(
    "/samples/project/{project_id}",
    response_model=list[SampleRequestResponse],
)
async def list_project_samples(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await svc.list_project_samples(db, project_id)
    return [SampleRequestResponse.model_validate(s) for s in items]


@router.patch("/samples/{sample_id}", response_model=SampleRequestResponse)
async def update_sample(
    sample_id: str,
    data: SampleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新样品状态"""
    existing = await svc.get_sample(db, sample_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="样品索要不存在")
    project = await db.get(Project, existing.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    sample = await svc.update_sample_status(
        db, sample_id, data.status, notes=data.notes
    )
    if not sample:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="样品索要不存在")

    resp = SampleRequestResponse.model_validate(sample)
    await ws_manager.broadcast_to_project(
        sample.project_id, "sample.updated", resp.model_dump(mode="json")
    )
    return resp

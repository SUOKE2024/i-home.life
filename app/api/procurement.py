from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.schemas.procurement import (
    SupplierCreate,
    SupplierResponse,
    QuotationCreate,
    QuotationResponse,
    OrderCreate,
    OrderUpdate,
    OrderResponse,
)
from app.auth import get_current_user
from app.services import procurement_service, project_service
from app.agents.procurement import ProcurementAgent
from app.ws import ws_manager

router = APIRouter(prefix="/procurement", tags=["采购"])


async def _verify_project_owner(db: AsyncSession, project_id: str, user: User) -> Project:
    """校验当前用户是项目所有者，否则抛 403"""
    project = await project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    return project


class QuotationItem(BaseModel):
    supplier_name: str
    unit_price: float
    quantity: float = 1.0
    delivery_days: int = 7
    rating: float = 4.0


class CompareRequest(BaseModel):
    quotations: list[QuotationItem]


@router.get("/suppliers", response_model=list[SupplierResponse])
async def list_suppliers(
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    suppliers = await procurement_service.get_suppliers(db, category)
    return [SupplierResponse.model_validate(s) for s in suppliers]


@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    data: SupplierCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    supplier = await procurement_service.create_supplier(db, data.model_dump())
    return SupplierResponse.model_validate(supplier)


@router.post("/quotations", response_model=QuotationResponse, status_code=status.HTTP_201_CREATED)
async def create_quotation(
    data: QuotationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_owner(db, data.project_id, current_user)
    quotation = await procurement_service.create_quotation(db, data.model_dump())
    resp = QuotationResponse.model_validate(quotation)
    await ws_manager.broadcast_to_project(data.project_id, "quotation.created", resp.model_dump())
    return resp


@router.get("/quotations/{project_id}", response_model=list[QuotationResponse])
async def get_quotations(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_owner(db, project_id, current_user)
    quotations = await procurement_service.get_quotations(db, project_id)
    return [QuotationResponse.model_validate(q) for q in quotations]


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_owner(db, data.project_id, current_user)
    order = await procurement_service.create_order(db, data.model_dump())
    resp = OrderResponse.model_validate(order)
    await ws_manager.broadcast_to_project(data.project_id, "order.created", resp.model_dump())
    return resp


@router.get("/orders/{project_id}", response_model=list[OrderResponse])
async def get_project_orders(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_owner(db, project_id, current_user)
    orders = await procurement_service.get_project_orders(db, project_id)
    return [OrderResponse.model_validate(o) for o in orders]


@router.get("/orders/detail/{order_id}", response_model=OrderResponse)
async def get_order_detail(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await procurement_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    await _verify_project_owner(db, order.project_id, current_user)
    return OrderResponse.model_validate(order)


@router.patch("/orders/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: str,
    data: OrderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await procurement_service.get_order(db, order_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    await _verify_project_owner(db, existing.project_id, current_user)
    order = await procurement_service.update_order(db, order_id, data.model_dump(exclude_unset=True))
    resp = OrderResponse.model_validate(order)
    await ws_manager.broadcast_to_project(order.project_id, "order.updated", resp.model_dump())
    return resp


@router.patch("/orders/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: str,
    status_val: str = Query(..., alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await procurement_service.get_order(db, order_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    await _verify_project_owner(db, existing.project_id, current_user)
    try:
        order = await procurement_service.update_order_status(db, order_id, status_val)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    resp = OrderResponse.model_validate(order)
    await ws_manager.broadcast_to_project(order.project_id, "order.status_updated", resp.model_dump())
    return resp


@router.delete("/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await procurement_service.get_order(db, order_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    await _verify_project_owner(db, existing.project_id, current_user)
    await procurement_service.delete_order(db, order_id)
    await ws_manager.broadcast_to_project(existing.project_id, "order.deleted", {"id": order_id})


# ── F33 自动比价报告 ──
@router.post("/compare")
async def compare_quotations(
    data: CompareRequest,
    current_user: User = Depends(get_current_user),
):
    agent = ProcurementAgent()
    return agent.generate_comparison_report([q.model_dump() for q in data.quotations])


@router.get("/recommend-suppliers")
async def recommend_suppliers(
    category: str = Query(..., description="物料品类"),
    current_user: User = Depends(get_current_user),
):
    agent = ProcurementAgent()
    return agent.recommend_suppliers(category)

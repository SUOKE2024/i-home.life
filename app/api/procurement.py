from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.procurement import (
    SupplierCreate,
    SupplierResponse,
    QuotationCreate,
    QuotationResponse,
    OrderCreate,
    OrderResponse,
)
from app.auth import get_current_user
from app.services import procurement_service
from app.agents.procurement import ProcurementAgent
from app.ws import ws_manager

router = APIRouter(prefix="/procurement", tags=["采购"])


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
    quotations = await procurement_service.get_quotations(db, project_id)
    return [QuotationResponse.model_validate(q) for q in quotations]


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
    orders = await procurement_service.get_project_orders(db, project_id)
    return [OrderResponse.model_validate(o) for o in orders]


@router.patch("/orders/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: str,
    status_val: str = Query(..., alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await procurement_service.update_order_status(db, order_id, status_val)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    resp = OrderResponse.model_validate(order)
    await ws_manager.broadcast_to_project(order.project_id, "order.status_updated", resp.model_dump())
    return resp


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

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


@router.get(
    "/suppliers",
    response_model=list[SupplierResponse],
    summary="获取供应商列表",
    description="获取系统中的供应商列表，可按物料品类筛选。",
    response_description="供应商列表",
    responses={
        200: {"description": "获取成功"},
    },
)
async def list_suppliers(
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    suppliers = await procurement_service.get_suppliers(db, category)
    return [SupplierResponse.model_validate(s) for s in suppliers]


@router.post(
    "/suppliers",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建供应商",
    description="在系统中添加一个新的供应商信息。",
    response_description="创建成功，返回供应商信息",
    responses={
        201: {"description": "创建成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
    },
)
async def create_supplier(
    data: SupplierCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    supplier = await procurement_service.create_supplier(db, data.model_dump())
    return SupplierResponse.model_validate(supplier)


@router.post(
    "/quotations",
    response_model=QuotationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建报价单",
    description="为项目的采购需求创建一个新的供应商报价单。",
    response_description="创建成功，返回报价单信息",
    responses={
        201: {"description": "创建成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
)
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


@router.get(
    "/quotations/{project_id}",
    response_model=list[QuotationResponse],
    summary="获取项目报价单列表",
    description="获取指定项目的所有供应商报价单。",
    response_description="报价单列表",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
)
async def get_quotations(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_owner(db, project_id, current_user)
    quotations = await procurement_service.get_quotations(db, project_id)
    return [QuotationResponse.model_validate(q) for q in quotations]


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建采购订单",
    description="根据报价单创建一个新的采购订单，将报价转化为正式采购订单。",
    response_description="创建成功，返回订单信息",
    responses={
        201: {"description": "创建成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
)
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


@router.get(
    "/orders/{project_id}",
    response_model=list[OrderResponse],
    summary="获取项目采购订单列表",
    description="获取指定项目的所有采购订单。",
    response_description="订单列表",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "项目不存在"},
    },
)
async def get_project_orders(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_project_owner(db, project_id, current_user)
    orders = await procurement_service.get_project_orders(db, project_id)
    return [OrderResponse.model_validate(o) for o in orders]


@router.get(
    "/orders/detail/{order_id}",
    response_model=OrderResponse,
    summary="获取订单详情",
    description="根据订单 ID 获取采购订单的详细信息。",
    response_description="订单详情",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "订单不存在"},
    },
)
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


@router.patch(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="更新采购订单",
    description="根据订单 ID 更新采购订单的部分信息。",
    response_description="更新成功，返回订单信息",
    responses={
        200: {"description": "更新成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "订单不存在"},
    },
)
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


@router.patch(
    "/orders/{order_id}/status",
    response_model=OrderResponse,
    summary="更新订单状态",
    description="更新采购订单的状态（如：待确认、进行中、已发货、已完成、已取消）。",
    response_description="更新成功，返回订单信息",
    responses={
        200: {"description": "更新成功"},
        400: {"description": "无效的状态值"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "订单不存在"},
    },
)
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


@router.delete(
    "/orders/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除采购订单",
    description="根据订单 ID 删除采购订单。",
    response_description="删除成功，无返回内容",
    responses={
        204: {"description": "删除成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "订单不存在"},
    },
)
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
@router.post(
    "/compare",
    summary="AI 自动比价",
    description="AI 对多个供应商报价进行自动对比分析，生成最高性价比推荐。",
    responses={
        200: {"description": "比价成功"},
        400: {"description": "请求参数无效"},
    },
)
async def compare_quotations(
    data: CompareRequest,
    current_user: User = Depends(get_current_user),
):
    agent = ProcurementAgent()
    return agent.generate_comparison_report([q.model_dump() for q in data.quotations])


@router.get(
    "/recommend-suppliers",
    summary="AI 供应商推荐",
    description="AI 根据物料品类智能推荐合适的供应商。",
    responses={
        200: {"description": "推荐成功"},
        400: {"description": "请求参数无效"},
    },
)
async def recommend_suppliers(
    category: str = Query(..., description="物料品类"),
    current_user: User = Depends(get_current_user),
):
    agent = ProcurementAgent()
    return agent.recommend_suppliers(category)

"""变更管理路由 — F39"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.change_order import (
    ChangeOrderCreate,
    ChangeOrderResponse,
    ChangeOrderReview,
)
from app.auth import get_current_user
from app.rbac import verify_project_access
from app.services import change_order_service
from app.ws import ws_manager

router = APIRouter(prefix="/change-orders", tags=["变更管理"])


@router.get("/project/{project_id}", response_model=list[ChangeOrderResponse])
async def list_change_orders(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    orders = await change_order_service.get_change_orders(db, project_id)
    return [ChangeOrderResponse.model_validate(o) for o in orders]


@router.post("", response_model=ChangeOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_change_order(
    data: ChangeOrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    payload = data.model_dump()
    payload["submitted_by"] = current_user.name
    order = await change_order_service.create_change_order(db, payload)
    resp = ChangeOrderResponse.model_validate(order)
    await ws_manager.broadcast_to_project(data.project_id, "change_order.created", resp.model_dump())
    return resp


@router.get("/{change_id}", response_model=ChangeOrderResponse)
async def get_change_order(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await change_order_service.get_change_order(db, change_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="变更单不存在")
    await verify_project_access(project_id=order.project_id, current_user=current_user, db=db)
    return ChangeOrderResponse.model_validate(order)


@router.post("/{change_id}/review", response_model=ChangeOrderResponse)
async def review_change_order(
    change_id: str,
    data: ChangeOrderReview,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await change_order_service.get_change_order(db, change_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="变更单不存在")
    await verify_project_access(project_id=existing.project_id, current_user=current_user, db=db)
    order = await change_order_service.review_change_order(db, change_id, data.model_dump(), current_user.name)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="变更单不存在")
    resp = ChangeOrderResponse.model_validate(order)
    await ws_manager.broadcast_to_project(order.project_id, "change_order.reviewed", resp.model_dump())
    return resp


@router.post("/{change_id}/approve", response_model=ChangeOrderResponse)
async def approve_change_order(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await change_order_service.get_change_order(db, change_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="变更单不存在")
    await verify_project_access(project_id=existing.project_id, current_user=current_user, db=db)
    order = await change_order_service.approve_change_order(db, change_id, current_user.name)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="变更单不存在")
    resp = ChangeOrderResponse.model_validate(order)
    await ws_manager.broadcast_to_project(order.project_id, "change_order.approved", resp.model_dump())
    return resp


@router.post("/{change_id}/cancel", response_model=ChangeOrderResponse)
async def cancel_change_order(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await change_order_service.get_change_order(db, change_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="变更单不存在")
    await verify_project_access(project_id=existing.project_id, current_user=current_user, db=db)
    order = await change_order_service.cancel_change_order(db, change_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="变更单不存在")
    resp = ChangeOrderResponse.model_validate(order)
    await ws_manager.broadcast_to_project(order.project_id, "change_order.cancelled", resp.model_dump())
    return resp

"""通知 API — 设备推送令牌注册"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.device_token import DeviceToken
from app.auth import get_current_user
from app.schemas.notification import (
    RegisterDeviceRequest,
    DeviceTokenResponse,
)

router = APIRouter(prefix="/notifications", tags=["通知"])


@router.post("/register-device", response_model=DeviceTokenResponse)
async def register_device(
    data: RegisterDeviceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """注册/更新设备推送令牌（每用户每平台仅保留一条活跃记录）"""
    # 查找该用户该平台已有记录
    stmt = select(DeviceToken).where(
        DeviceToken.user_id == current_user.id,
        DeviceToken.platform == data.platform,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.device_token = data.device_token
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        return existing

    token = DeviceToken(
        user_id=current_user.id,
        device_token=data.device_token,
        platform=data.platform,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


@router.get("/devices", response_model=list[DeviceTokenResponse])
async def list_my_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的所有活跃设备"""
    stmt = select(DeviceToken).where(
        DeviceToken.user_id == current_user.id,
        DeviceToken.is_active == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.delete("/devices/{device_id}")
async def unregister_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """注销设备推送令牌（软删除）"""
    stmt = select(DeviceToken).where(
        DeviceToken.id == device_id,
        DeviceToken.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=404, detail="设备不存在")
    token.is_active = False
    await db.commit()
    return {"detail": "设备已注销"}

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
from app.services.notification_service import (
    register_device as _svc_register_device,
    get_user_tokens,
    unregister_device as _svc_unregister_device,
)

router = APIRouter(prefix="/notifications", tags=["通知"])


@router.post("/register-device", response_model=DeviceTokenResponse)
async def register_device(
    data: RegisterDeviceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """注册/更新设备推送令牌（每用户每平台仅保留一条活跃记录）"""
    return await _svc_register_device(db, current_user.id, data.device_token, data.platform)


@router.get("/devices", response_model=list[DeviceTokenResponse])
async def list_my_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的所有活跃设备"""
    return await get_user_tokens(db, current_user.id)


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
    await _svc_unregister_device(db, current_user.id, token.device_token)
    return {"detail": "设备已注销"}

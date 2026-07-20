"""推送通知 Service — 设备令牌注册/注销"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.device_token import DeviceToken


async def register_device(
    db: AsyncSession,
    user_id: str,
    device_token: str,
    platform: str,
) -> DeviceToken:
    """注册或更新设备推送令牌。

    同一用户同一平台只保留一条记录，重复注册时自动更新令牌和激活状态。
    """
    # 查找同用户同平台的现有记录
    result = await db.execute(
        select(DeviceToken)
        .where(
            DeviceToken.user_id == user_id,
            DeviceToken.platform == platform,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # 更新已有记录
        existing.device_token = device_token
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        return existing

    # 新建记录
    token = DeviceToken(
        user_id=user_id,
        device_token=device_token,
        platform=platform,
        is_active=True,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


async def unregister_device(
    db: AsyncSession,
    user_id: str,
    device_token: str,
) -> bool:
    """注销设备令牌（软删除，标记为未激活）"""
    result = await db.execute(
        select(DeviceToken)
        .where(
            DeviceToken.user_id == user_id,
            DeviceToken.device_token == device_token,
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        return False
    token.is_active = False
    await db.commit()
    return True


async def get_user_tokens(
    db: AsyncSession, user_id: str,
) -> list[DeviceToken]:
    """获取用户所有已激活的设备令牌"""
    result = await db.execute(
        select(DeviceToken)
        .where(
            DeviceToken.user_id == user_id,
            DeviceToken.is_active.is_(True),
        )
    )
    return list(result.scalars().all())


async def get_active_tokens(
    db: AsyncSession, user_id: str,
) -> list[str]:
    """获取用户所有已激活的设备令牌值（仅 token 字符串）"""
    tokens = await get_user_tokens(db, user_id)
    return [t.device_token for t in tokens]

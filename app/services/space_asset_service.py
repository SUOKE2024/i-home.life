"""空间资产台账服务层 — Phase 3 存量空间资产化（2026-09-13）

职责：
1. 台账 CRUD（按 owner_id 归属隔离）
2. 改造状态机流转（pending_assessment → assessed → in_renovation → delivered → operating）
3. 智能化就绪度确定性评分（设备/传感器/场景自动化/合规四维）
4. 资产组合汇总（台账看板）

轻资产约束（强制，不可绕过）：
- `platform_role` 恒为 `service_provider`，写入时强制覆盖任何传入值
- `asset_holder` 不得为平台自身（索克家居 / i-home.life / 索克），命中即 ValueError

数据纪律：就绪度评分仅基于已落库真实计数，无数据项计 0 分并标注，不猜测。
"""
from __future__ import annotations

import logging

from sqlalchemy import func as sql_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.space_asset import (
    ASSET_CATEGORIES,
    BUSINESS_FORMATS,
    HOLDER_TYPES,
    PLATFORM_ROLE,
    RENOVATION_STATUSES,
    SpaceAsset,
)

logger = logging.getLogger(__name__)

# 平台主体名（轻资产约束：asset_holder 不得命中）
_PLATFORM_HOLDER_KEYWORDS: tuple[str, ...] = ("索克家居", "i-home.life", "索克生活", "索克（昆明）")

# 改造状态机：允许的流转（不可跳跃至 operating，必须经 delivered）
_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "pending_assessment": ("assessed", "suspended"),
    "assessed": ("in_renovation", "pending_assessment", "suspended"),
    "in_renovation": ("delivered", "assessed", "suspended"),
    "delivered": ("operating", "suspended"),
    "operating": ("suspended",),
    "suspended": ("pending_assessment", "assessed"),
}


def _validate_holder(asset_holder: str) -> None:
    """轻资产约束校验：资产持有方不得为平台自身。

    Raises:
        ValueError: 持有方命中平台主体关键词
    """
    if not asset_holder or not asset_holder.strip():
        raise ValueError("asset_holder 不能为空（资产必须由外部主体持有）")
    for kw in _PLATFORM_HOLDER_KEYWORDS:
        if kw in asset_holder:
            raise ValueError(
                f"asset_holder 不得为平台自身（命中「{kw}」）——"
                "本平台为轻资产改造服务商，不持有房产"
            )


def compute_smart_readiness(
    *,
    matter_device_count: int = 0,
    sensor_count: int = 0,
    scene_automation_count: int = 0,
    accessibility_status: str = "unknown",
    fire_safety_status: str = "unknown",
) -> tuple[float, dict]:
    """智能化就绪度确定性评分（0-100）。

    四维权重：设备接入 30 / 环境感知 25 / 场景自动化 25 / 合规 20。
    无数据项计 0 分并在 breakdown 标注，不猜测、不虚增。

    Returns:
        (score, breakdown_dict)
    """
    device_score = min(30.0, matter_device_count * 3.0)
    sensor_score = min(25.0, sensor_count * 2.5)
    scene_score = min(25.0, scene_automation_count * 5.0)

    compliance_score = 0.0
    if accessibility_status == "pass":
        compliance_score += 10.0
    elif accessibility_status == "warning":
        compliance_score += 5.0
    if fire_safety_status == "pass":
        compliance_score += 10.0
    elif fire_safety_status == "warning":
        compliance_score += 5.0

    total = round(device_score + sensor_score + scene_score + compliance_score, 1)
    breakdown = {
        "device_access": {"score": device_score, "max": 30.0, "count": matter_device_count},
        "environment_sensing": {"score": sensor_score, "max": 25.0, "count": sensor_count},
        "scene_automation": {"score": scene_score, "max": 25.0, "count": scene_automation_count},
        "compliance": {"score": compliance_score, "max": 20.0,
                       "accessibility": accessibility_status, "fire_safety": fire_safety_status},
    }
    return total, breakdown


async def create_asset(db: AsyncSession, data: dict) -> SpaceAsset:
    """创建空间资产台账记录。

    Raises:
        ValueError: 业态/类别/持有方类型非法，或持有方为平台自身
    """
    if data.get("asset_category") and data["asset_category"] not in ASSET_CATEGORIES:
        raise ValueError(f"asset_category 非法，可选: {', '.join(ASSET_CATEGORIES)}")
    if data.get("business_format") and data["business_format"] not in BUSINESS_FORMATS:
        raise ValueError(f"business_format 非法，可选: {', '.join(BUSINESS_FORMATS)}")
    if data.get("holder_type") and data["holder_type"] not in HOLDER_TYPES:
        raise ValueError(f"holder_type 非法，可选: {', '.join(HOLDER_TYPES)}")

    _validate_holder(data["asset_holder"])

    payload = dict(data)
    # 轻资产约束：平台角色强制为服务商，忽略任何传入值
    payload["platform_role"] = PLATFORM_ROLE

    score, _ = compute_smart_readiness(
        matter_device_count=payload.get("matter_device_count", 0) or 0,
        sensor_count=payload.get("sensor_count", 0) or 0,
        scene_automation_count=payload.get("scene_automation_count", 0) or 0,
        accessibility_status=payload.get("accessibility_status", "unknown"),
        fire_safety_status=payload.get("fire_safety_status", "unknown"),
    )
    payload["smart_readiness_score"] = score
    payload["smart_ready"] = score >= 60.0

    asset = SpaceAsset(**payload)
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


async def get_asset(db: AsyncSession, asset_id: str) -> SpaceAsset | None:
    result = await db.execute(select(SpaceAsset).where(SpaceAsset.id == asset_id))
    return result.scalar_one_or_none()


async def list_assets(
    db: AsyncSession,
    *,
    owner_id: str | None = None,
    asset_category: str | None = None,
    renovation_status: str | None = None,
    city: str | None = None,
    limit: int = 50,
) -> list[SpaceAsset]:
    """按条件列出台账（owner_id 传入时做归属隔离）。"""
    stmt = select(SpaceAsset)
    if owner_id:
        stmt = stmt.where(SpaceAsset.owner_id == owner_id)
    if asset_category:
        stmt = stmt.where(SpaceAsset.asset_category == asset_category)
    if renovation_status:
        stmt = stmt.where(SpaceAsset.renovation_status == renovation_status)
    if city:
        stmt = stmt.where(SpaceAsset.city == city)
    stmt = stmt.order_by(SpaceAsset.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_asset(db: AsyncSession, asset_id: str, data: dict) -> SpaceAsset | None:
    """更新台账（重算就绪度；持有方变更须过轻资产校验）。"""
    asset = await get_asset(db, asset_id)
    if not asset:
        return None

    payload = {k: v for k, v in data.items() if v is not None}
    if "asset_holder" in payload:
        _validate_holder(payload["asset_holder"])
    # 平台角色不可被改写
    payload.pop("platform_role", None)
    # 状态流转走专用状态机，此处拒绝直接改状态
    payload.pop("renovation_status", None)

    for key, value in payload.items():
        if hasattr(asset, key):
            setattr(asset, key, value)

    asset.smart_readiness_score, _ = compute_smart_readiness(
        matter_device_count=asset.matter_device_count or 0,
        sensor_count=asset.sensor_count or 0,
        scene_automation_count=asset.scene_automation_count or 0,
        accessibility_status=asset.accessibility_status or "unknown",
        fire_safety_status=asset.fire_safety_status or "unknown",
    )
    asset.smart_ready = asset.smart_readiness_score >= 60.0

    await db.commit()
    await db.refresh(asset)
    return asset


async def transition_renovation_status(
    db: AsyncSession, asset_id: str, new_status: str
) -> tuple[SpaceAsset | None, str | None]:
    """改造状态机流转。

    Returns:
        (asset, error)——asset 为 None 表示不存在；error 非 None 表示流转非法
    """
    if new_status not in RENOVATION_STATUSES:
        return None, f"new_status 非法，可选: {', '.join(RENOVATION_STATUSES)}"

    asset = await get_asset(db, asset_id)
    if not asset:
        return None, None

    allowed = _STATUS_TRANSITIONS.get(asset.renovation_status, ())
    if new_status not in allowed:
        return asset, (
            f"非法流转 {asset.renovation_status} → {new_status}，"
            f"允许: {', '.join(allowed) if allowed else '（无）'}"
        )

    asset.renovation_status = new_status
    await db.commit()
    await db.refresh(asset)
    return asset, None


async def delete_asset(db: AsyncSession, asset_id: str) -> bool:
    asset = await get_asset(db, asset_id)
    if not asset:
        return False
    await db.delete(asset)
    await db.commit()
    return True


async def portfolio_summary(db: AsyncSession, *, owner_id: str | None = None) -> dict:
    """资产组合汇总（台账看板）。

    所有指标基于 space_assets 真实行聚合；无数据返回 0 并标注 total=0，不伪造。
    """
    base = select(SpaceAsset)
    count_stmt = select(sql_func.count(SpaceAsset.id))
    if owner_id:
        base = base.where(SpaceAsset.owner_id == owner_id)
        count_stmt = count_stmt.where(SpaceAsset.owner_id == owner_id)

    total = (await db.execute(count_stmt)).scalar() or 0

    if total == 0:
        return {
            "total_assets": 0,
            "by_category": {},
            "by_status": {},
            "by_city": {},
            "avg_smart_readiness": 0.0,
            "smart_ready_count": 0,
            "total_area_sqm": 0.0,
            "note": "台账暂无资产记录",
        }

    assets = list((await db.execute(base)).scalars().all())

    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_city: dict[str, int] = {}
    total_area = 0.0
    score_sum = 0.0
    ready_count = 0
    for a in assets:
        by_category[a.asset_category] = by_category.get(a.asset_category, 0) + 1
        by_status[a.renovation_status] = by_status.get(a.renovation_status, 0) + 1
        by_city[a.city] = by_city.get(a.city, 0) + 1
        total_area += float(a.building_area_sqm or 0.0)
        score_sum += float(a.smart_readiness_score or 0.0)
        if a.smart_ready:
            ready_count += 1

    return {
        "total_assets": total,
        "by_category": by_category,
        "by_status": by_status,
        "by_city": by_city,
        "avg_smart_readiness": round(score_sum / len(assets), 1) if assets else 0.0,
        "smart_ready_count": ready_count,
        "total_area_sqm": round(total_area, 1),
        "platform_role": PLATFORM_ROLE,
        "note": "指标基于 space_assets 真实聚合；平台为轻资产改造服务商，不持有房产",
    }

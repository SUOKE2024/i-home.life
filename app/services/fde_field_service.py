"""FDE 现场服务记录服务层（v1.17.4）

政策依据：工信厅科函〔2026〕414号 任务四（前线部署工程师扎根用户现场）。
职责：现场服务记录 CRUD（按 `owner_id` 归属隔离）+ 枚举/契约校验。

诚实红线：
- `capability_tags` 只接受 `FDE_CAPABILITY_TAGS` 子集，允许为空
  （未声明维度不硬凑四维）。
- 记录为**现场服务事实**，`resolved` 仅表示现场问题是否闭环，
  **不构成交付验收结论**（验收以质检/节点确认为准）。
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fde_field_service import (
    FDE_CAPABILITY_TAGS,
    FDE_MODES,
    FDE_SERVICE_TYPES,
    FdeFieldVisit,
)

logger = logging.getLogger(__name__)

# 任何写入路径均不可覆盖的字段（owner_id 在 update 时同样不可改写）
_PROTECTED_FIELDS: tuple[str, ...] = ("id", "created_at", "updated_at")


def _validate(payload: dict, *, partial: bool) -> None:
    """字段契约校验（确定性，无 DB 依赖）。

    Raises:
        ValueError: 枚举非法 / 标题为空 / 工时负数 / capability_tags 越界
    """
    if "title" in payload or not partial:
        title = (payload.get("title") or "").strip()
        if not title:
            raise ValueError("title 不能为空（现场服务事由）")

    if payload.get("service_type") is not None and payload["service_type"] not in FDE_SERVICE_TYPES:
        raise ValueError(f"service_type 非法，可选: {', '.join(FDE_SERVICE_TYPES)}")

    if payload.get("mode") is not None and payload["mode"] not in FDE_MODES:
        raise ValueError(f"mode 非法，可选: {', '.join(FDE_MODES)}")

    tags = payload.get("capability_tags")
    if tags is not None:
        if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
            raise ValueError("capability_tags 必须为字符串数组")
        unknown = [t for t in tags if t not in FDE_CAPABILITY_TAGS]
        if unknown:
            raise ValueError(
                f"capability_tags 含未知维度 {unknown}，可选: {', '.join(FDE_CAPABILITY_TAGS)}"
                "（只声明实际具备的维度，不硬凑四维）"
            )
        # 去重保序，避免同一维度重复声明
        payload["capability_tags"] = list(dict.fromkeys(tags))

    duration = payload.get("duration_hours")
    if duration is not None and duration < 0:
        raise ValueError("duration_hours 不得为负（现场服务工时）")


async def create_visit(db: AsyncSession, data: dict) -> FdeFieldVisit:
    """登记一条 FDE 现场服务记录（必须携带 owner_id，由 API 层注入记录人）。"""
    payload = {k: v for k, v in data.items() if k not in _PROTECTED_FIELDS}
    if not payload.get("owner_id"):
        raise ValueError("owner_id 缺失（现场服务记录必须归属到记录人）")
    _validate(payload, partial=False)

    visit = FdeFieldVisit(**payload)
    db.add(visit)
    await db.commit()
    await db.refresh(visit)
    return visit


async def get_visit(db: AsyncSession, visit_id: str) -> FdeFieldVisit | None:
    result = await db.execute(select(FdeFieldVisit).where(FdeFieldVisit.id == visit_id))
    return result.scalar_one_or_none()


async def list_visits(
    db: AsyncSession,
    *,
    owner_id: str | None = None,
    project_id: str | None = None,
    space_asset_id: str | None = None,
    service_type: str | None = None,
    mode: str | None = None,
    resolved: bool | None = None,
    limit: int = 50,
) -> list[FdeFieldVisit]:
    """按条件列出（owner_id 传入时做归属隔离）。"""
    stmt = select(FdeFieldVisit)
    if owner_id:
        stmt = stmt.where(FdeFieldVisit.owner_id == owner_id)
    if project_id:
        stmt = stmt.where(FdeFieldVisit.project_id == project_id)
    if space_asset_id:
        stmt = stmt.where(FdeFieldVisit.space_asset_id == space_asset_id)
    if service_type:
        stmt = stmt.where(FdeFieldVisit.service_type == service_type)
    if mode:
        stmt = stmt.where(FdeFieldVisit.mode == mode)
    if resolved is not None:
        stmt = stmt.where(FdeFieldVisit.resolved.is_(resolved))
    stmt = stmt.order_by(FdeFieldVisit.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_visit(db: AsyncSession, visit_id: str, data: dict) -> FdeFieldVisit | None:
    """更新现场服务记录（owner_id / id / 时间戳不可改写）。"""
    visit = await get_visit(db, visit_id)
    if not visit:
        return None

    payload = {
        k: v for k, v in data.items()
        if k not in _PROTECTED_FIELDS and k != "owner_id"
    }
    _validate(payload, partial=True)

    for key, value in payload.items():
        if hasattr(visit, key):
            setattr(visit, key, value)

    await db.commit()
    await db.refresh(visit)
    return visit


async def delete_visit(db: AsyncSession, visit_id: str) -> bool:
    visit = await get_visit(db, visit_id)
    if not visit:
        return False
    await db.delete(visit)
    await db.commit()
    return True

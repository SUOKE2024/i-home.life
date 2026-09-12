"""施工进度 3DGS 数字存档服务层（评估报告 2026-09-12 P3）

施工节点现场 3DGS 快照上传/查询，形成施工时间线（竣工验收比对 + 业主远程查看）。
复用 P0 的 .spz/.ply 资产托管（FileAttachment）+ validate_splat_file 校验。
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.construction_snapshot import ConstructionSnapshot

# 施工阶段值域（与 ConstructionTask.phase 对齐，供校验与前端下拉）
STAGES = (
    "preparation", "demolition", "water_electricity", "electrical", "waterproof",
    "masonry", "mep", "carpentry", "painting", "installation", "completion", "inspection",
)


async def create_snapshot(
    db: AsyncSession,
    project_id: str,
    splat_url: str,
    stage: str,
    task_id: str | None = None,
    room_name: str | None = None,
    thumbnail_url: str | None = None,
    notes: str | None = None,
) -> ConstructionSnapshot:
    """登记施工节点 3DGS 快照。"""
    snapshot = ConstructionSnapshot(
        project_id=project_id,
        task_id=task_id,
        stage=stage,
        room_name=room_name,
        splat_url=splat_url,
        thumbnail_url=thumbnail_url,
        notes=notes,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def list_snapshots(
    db: AsyncSession,
    project_id: str,
    stage_filter: str | None = None,
) -> list[ConstructionSnapshot]:
    """按项目列施工快照（按拍摄时间倒序，构成施工时间线）。"""
    stmt = (
        select(ConstructionSnapshot)
        .where(ConstructionSnapshot.project_id == project_id)
        .order_by(ConstructionSnapshot.captured_at.desc())
    )
    if stage_filter:
        stmt = stmt.where(ConstructionSnapshot.stage == stage_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_snapshot(db: AsyncSession, snapshot_id: str) -> ConstructionSnapshot | None:
    """查询单条施工快照。"""
    result = await db.execute(
        select(ConstructionSnapshot).where(ConstructionSnapshot.id == snapshot_id)
    )
    return result.scalar_one_or_none()

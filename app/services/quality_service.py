"""F38 质量管理服务层 — 质量问题 + 整改单 + 质量评估"""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quality import QualityIssue, RectificationOrder, QualityAssessment


# ── 质量问题 ──

async def create_issue(db: AsyncSession, data: dict) -> QualityIssue:
    issue = QualityIssue(**data)
    db.add(issue)
    await db.commit()
    await db.refresh(issue)
    return issue


async def get_issue(db: AsyncSession, issue_id: str) -> QualityIssue | None:
    result = await db.execute(select(QualityIssue).where(QualityIssue.id == issue_id))
    return result.scalar_one_or_none()


async def list_issues(
    db: AsyncSession,
    project_id: str,
    phase: str | None = None,
    status_filter: str | None = None,
    severity: str | None = None,
) -> list[QualityIssue]:
    stmt = (
        select(QualityIssue)
        .where(QualityIssue.project_id == project_id)
        .order_by(QualityIssue.created_at.desc())
    )
    if phase:
        stmt = stmt.where(QualityIssue.phase == phase)
    if status_filter:
        stmt = stmt.where(QualityIssue.status == status_filter)
    if severity:
        stmt = stmt.where(QualityIssue.severity == severity)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# 质量问题状态机: open → in_progress → resolved → verified / reopened
ISSUE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "open": {"in_progress", "resolved", "closed"},
    "in_progress": {"resolved", "closed"},
    "resolved": {"verified", "reopened"},
    "verified": {"closed", "reopened"},
    "reopened": {"in_progress", "resolved", "closed"},
    "closed": {"reopened"},
}

# 整改单状态机: pending → in_progress → completed → verified
ORDER_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"in_progress", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": {"verified"},
    "verified": set(),  # 终态
    "cancelled": set(),  # 终态
}


def _validate_transition(current: str, target: str, transitions: dict[str, set[str]]) -> bool:
    """校验状态流转是否合法"""
    allowed = transitions.get(current, set())
    return target in allowed


async def update_issue_status(
    db: AsyncSession,
    issue_id: str,
    new_status: str,
    resolution: str | None = None,
    resolver: str | None = None,
    verifier: str | None = None,
) -> QualityIssue | None:
    result = await db.execute(select(QualityIssue).where(QualityIssue.id == issue_id))
    issue = result.scalar_one_or_none()
    if not issue:
        return None
    # 校验状态机
    if not _validate_transition(issue.status, new_status, ISSUE_STATUS_TRANSITIONS):
        raise ValueError(f"非法状态流转: {issue.status} → {new_status} (允许: {ISSUE_STATUS_TRANSITIONS.get(issue.status, set())})")
    issue.status = new_status
    if resolution:
        issue.resolution = resolution
    if new_status == "resolved":
        issue.resolved_at = datetime.now(timezone.utc)
        issue.resolved_by = resolver
    elif new_status == "verified":
        issue.verified_at = datetime.now(timezone.utc)
        issue.verified_by = verifier
    await db.commit()
    await db.refresh(issue)
    return issue


# ── 整改单 ──

async def generate_order_no() -> str:
    """生成整改单号：RO-YYYYMMDD-XXXX"""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:8].upper()
    return f"RO-{today}-{short_uuid}"


async def create_rectification_order(db: AsyncSession, data: dict, created_by: str | None = None) -> RectificationOrder:
    # issue_ids 列表 → JSON 字符串
    issue_ids = data.pop("issue_ids", None)
    if isinstance(issue_ids, list):
        data["issue_ids"] = json.dumps(issue_ids, ensure_ascii=False)
    data["order_no"] = await generate_order_no()
    if created_by:
        data["created_by"] = created_by
    order = RectificationOrder(**data)
    db.add(order)
    await db.commit()
    await db.refresh(order)
    # 同步关联的 issue 状态为 in_progress
    if issue_ids:
        for issue_id in issue_ids:
            await update_issue_status(db, issue_id, "in_progress")
    return order


async def get_order(db: AsyncSession, order_id: str) -> RectificationOrder | None:
    result = await db.execute(select(RectificationOrder).where(RectificationOrder.id == order_id))
    return result.scalar_one_or_none()


async def list_orders(
    db: AsyncSession,
    project_id: str,
    status_filter: str | None = None,
) -> list[RectificationOrder]:
    stmt = (
        select(RectificationOrder)
        .where(RectificationOrder.project_id == project_id)
        .order_by(RectificationOrder.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(RectificationOrder.status == status_filter)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_order_status(
    db: AsyncSession,
    order_id: str,
    new_status: str,
    verifier: str | None = None,
) -> RectificationOrder | None:
    result = await db.execute(select(RectificationOrder).where(RectificationOrder.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        return None
    # 校验状态机
    if not _validate_transition(order.status, new_status, ORDER_STATUS_TRANSITIONS):
        raise ValueError(f"非法状态流转: {order.status} → {new_status} (允许: {ORDER_STATUS_TRANSITIONS.get(order.status, set())})")
    order.status = new_status
    if new_status == "completed":
        order.completed_at = datetime.now(timezone.utc)
        # 整改完成时，关联 issue 转为 resolved
        if order.issue_ids:
            try:
                issue_ids = json.loads(order.issue_ids)
                for issue_id in issue_ids:
                    await update_issue_status(db, issue_id, "resolved", resolver=verifier)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"整改单 {order_id} 关联 issue 同步失败: {e}")
    elif new_status == "verified":
        order.verified_at = datetime.now(timezone.utc)
        # 验收通过时，关联 issue 转为 verified
        if order.issue_ids:
            try:
                issue_ids = json.loads(order.issue_ids)
                for issue_id in issue_ids:
                    await update_issue_status(db, issue_id, "verified", verifier=verifier)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"整改单 {order_id} 关联 issue 同步失败: {e}")
    await db.commit()
    await db.refresh(order)
    return order


# ── 质量评估 ──

async def create_assessment(db: AsyncSession, data: dict) -> QualityAssessment:
    if data.get("assessed_at") is None:
        data["assessed_at"] = datetime.now(timezone.utc)
    assessment = QualityAssessment(**data)
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)
    return assessment


async def list_assessments(db: AsyncSession, project_id: str) -> list[QualityAssessment]:
    result = await db.execute(
        select(QualityAssessment)
        .where(QualityAssessment.project_id == project_id)
        .order_by(QualityAssessment.created_at.desc())
    )
    return list(result.scalars().all())

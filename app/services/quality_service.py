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
        raise ValueError(
            f"非法状态流转: {issue.status} → {new_status} "
            f"(允许: {ISSUE_STATUS_TRANSITIONS.get(issue.status, set())})"
        )
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
        raise ValueError(
            f"非法状态流转: {order.status} → {new_status} "
            f"(允许: {ORDER_STATUS_TRANSITIONS.get(order.status, set())})"
        )
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


# ── 验收报告生成（v1.1.31 FP-5 / S4：验收清单贯通）──

def _issue_to_check_status(issue_status: str) -> str:
    """QualityIssue.status → 验收项状态映射

    open/in_progress → fail（未通过），resolved → warning（已整改待复验），
    verified/closed → pass（已验收）。
    """
    return {
        "open": "fail",
        "in_progress": "fail",
        "resolved": "warning",
        "verified": "pass",
        "closed": "pass",
    }.get(issue_status, "warning")


async def generate_acceptance_report(
    db: AsyncSession,
    project_id: str,
    phase: str | None = None,
) -> dict:
    """生成验收报告：比对标准验收清单与项目实际质量问题

    v1.1.31 FP-5（S4）：原 quality_service 与 ConstructionAgent 的
    QUALITY_CHECKLISTS 割裂，现统一引用 ``app.standards.acceptance_checklists``。

    逻辑：
    1. 从标准库加载该阶段验收清单（每项含 item/standard/method/regulation）
    2. 查询项目该阶段的 QualityIssue
    3. 按 category/item 名称模糊匹配，将 issue 关联到 checklist 项
    4. 未匹配到 issue 的 checklist 项标记为 "pending"（待检）
    5. 计算合格率与验收结论

    受 ``settings.acceptance_checklist_enabled`` 控制：
    - True：完整比对（标准清单 + 实际 issue）
    - False：仅汇总实际 issue（回退，不比对标准清单）

    Args:
        db: 异步数据库会话
        project_id: 项目 ID
        phase: 阶段码（mep/waterproof/masonry/carpentry/painting/installation/completion）；
                None 表示全阶段汇总

    Returns:
        验收报告 dict（含 checklist_items / issues / pass_rate / verdict）
    """
    from app.config import get_settings
    from app.standards.acceptance_checklists import all_phases, get_checklist

    settings = get_settings()

    # 查询项目实际质量问题
    stmt = select(QualityIssue).where(QualityIssue.project_id == project_id)
    if phase:
        stmt = stmt.where(QualityIssue.phase == phase)
    result = await db.execute(stmt)
    issues = list(result.scalars().all())

    # 关闭 flag 或无标准清单时：仅汇总 issue
    if not settings.acceptance_checklist_enabled:
        return _summarize_issues_only(project_id, phase, issues)

    # 加载标准验收清单
    phases_to_check = [phase] if phase else all_phases()
    checklist_items: list[dict] = []
    for ph in phases_to_check:
        for item in get_checklist(ph):
            checklist_items.append({**item, "phase": ph})

    # 按 category + item 名称匹配 issue（同 phase 前提下）
    results: list[dict] = []
    passed = 0
    failed = 0
    pending = 0
    for ci in checklist_items:
        matched_issues: list[QualityIssue] = []
        cat = ci.get("category", "")
        for iss in issues:
            if iss.phase != ci["phase"]:
                continue
            # category 精确/包含匹配，或 issue.category 包含 checklist item 名
            if (cat and cat in iss.category) or (ci["item"] in iss.category) or (iss.category in ci["item"]):
                matched_issues.append(iss)

        if not matched_issues:
            # 无对应 issue：待检（不算合格也不算不合格）
            status = "pending"
            pending += 1
        else:
            # 取最严重的 issue 状态
            severities = [i.status for i in matched_issues]
            if any(s in ("open", "in_progress") for s in severities):
                status = "fail"
                failed += 1
            elif any(s == "resolved" for s in severities):
                status = "warning"
                passed += 1  # 已整改视为条件合格
            else:
                status = "pass"
                passed += 1

        results.append({
            "phase": ci["phase"],
            "item": ci["item"],
            "standard": ci["standard"],
            "method": ci.get("method", ""),
            "regulation": ci.get("regulation", ""),
            "category": ci.get("category", ""),
            "status": status,
            "matched_issue_count": len(matched_issues),
            "matched_issues": [
                {
                    "id": i.id, "category": i.category, "severity": i.severity,
                    "issue_status": i.status, "description": i.description,
                    "location": i.location or "",
                } for i in matched_issues[:3]
            ],
        })

    total_checked = passed + failed
    pass_rate = round(passed / max(total_checked, 1) * 100, 1)
    # 验收结论：有待检项不影响结论，仅看已检项
    if failed == 0 and total_checked > 0:
        verdict = "pass" if pending == 0 else "conditional_pass"
        verdict_text = "合格" if pending == 0 else "有条件合格（含待检项）"
    elif pass_rate >= 85:
        verdict = "conditional_pass"
        verdict_text = "有条件合格（需整改）"
    else:
        verdict = "fail"
        verdict_text = "不合格（需返工）"

    return {
        "source": "standard_checklist",
        "project_id": project_id,
        "phase": phase or "all",
        "total_checklist_items": len(checklist_items),
        "passed": passed,
        "failed": failed,
        "pending": pending,
        "pass_rate": pass_rate,
        "verdict": verdict,
        "verdict_text": verdict_text,
        "checklist_items": results,
        "issues_summary": {
            "total_issues": len(issues),
            "by_status": _count_by(issues, lambda i: i.status),
            "by_severity": _count_by(issues, lambda i: i.severity),
        },
    }


def _count_by(items: list, key_fn) -> dict[str, int]:
    """按 key_fn 分组计数"""
    counts: dict[str, int] = {}
    for it in items:
        k = key_fn(it)
        counts[k] = counts.get(k, 0) + 1
    return counts


def _summarize_issues_only(project_id: str, phase: str | None, issues: list[QualityIssue]) -> dict:
    """acceptance_checklist_enabled=False 时的回退：仅汇总 issue，不比对标准清单"""
    passed = sum(1 for i in issues if i.status in ("verified", "closed"))
    failed = sum(1 for i in issues if i.status in ("open", "in_progress"))
    warning = sum(1 for i in issues if i.status == "resolved")
    total = len(issues)
    pass_rate = round(passed / max(total, 1) * 100, 1)
    if failed == 0 and total > 0:
        verdict = "pass"
        verdict_text = "合格"
    elif pass_rate >= 85:
        verdict = "conditional_pass"
        verdict_text = "有条件合格（需整改）"
    else:
        verdict = "fail"
        verdict_text = "不合格（需返工）"
    return {
        "source": "issues_only_fallback",
        "project_id": project_id,
        "phase": phase or "all",
        "total_issues": total,
        "passed": passed,
        "failed": failed,
        "warning": warning,
        "pass_rate": pass_rate,
        "verdict": verdict,
        "verdict_text": verdict_text,
        "issues": [
            {
                "id": i.id, "phase": i.phase, "category": i.category,
                "severity": i.severity, "status": i.status,
                "description": i.description, "standard": i.standard or "",
                "location": i.location or "",
            } for i in issues
        ],
    }

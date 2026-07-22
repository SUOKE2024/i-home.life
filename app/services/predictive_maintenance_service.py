"""A6 施工预测性维护 — 风险分析服务"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.predictive_maintenance import RiskPrediction
from app.models.construction import ConstructionTask, Inspection
from app.models.budget import Budget, BudgetLine
from app.models.material import Material, BOMItem

logger = logging.getLogger("ihome")


async def analyze_project_risks(project_id: str, db: AsyncSession) -> dict:
    """分析项目风险，返回新创建的风险列表"""

    now = datetime.now(timezone.utc)
    risks_created: list[RiskPrediction] = []

    # 1. 延期检测：任务 end_date < today 但 status != completed
    delay_tasks_result = await db.execute(
        select(ConstructionTask).where(
            ConstructionTask.project_id == project_id,
            ConstructionTask.end_date.isnot(None),
            ConstructionTask.end_date < now,
            ConstructionTask.status != "completed",
        )
    )
    delay_tasks = delay_tasks_result.scalars().all()
    if delay_tasks:
        affected_ids = [t.id for t in delay_tasks]
        delay_days = max(
            (now - t.end_date).days
            for t in delay_tasks
            if t.end_date
        )
        risk_score = min(100, 30 + delay_days * 5)
        probability = min(1.0, delay_days / 30.0)
        impact_level = "critical" if delay_days > 14 else ("high" if delay_days > 7 else "medium")

        risk = RiskPrediction(
            project_id=project_id,
            risk_type="schedule_delay",
            risk_score=risk_score,
            probability=probability,
            impact_level=impact_level,
            trigger_factors=[
                f"任务 [{t.name}] 截止日期 {t.end_date.isoformat() if t.end_date else 'N/A'}，"
                f"已延期 {(now - t.end_date).days if t.end_date else 0} 天"
                for t in delay_tasks
            ],
            affected_tasks=affected_ids,
            mitigation_actions=[
                "重新评估剩余任务工期，压缩非关键路径任务",
                "增加施工人力或采取两班倒加速追赶进度",
                "与业主沟通调整交付日期预期",
                "优先保证关键路径任务的资源投入",
            ],
            status="active",
            predicted_at=now,
        )
        db.add(risk)
        risks_created.append(risk)

    # 2. 成本超支：预算已用 > 预算 80%
    budget_result = await db.execute(
        select(Budget).where(Budget.project_id == project_id)
    )
    budget = budget_result.scalar_one_or_none()
    if budget and budget.total_estimated > 0:
        actual_ratio = budget.total_actual / budget.total_estimated
        if actual_ratio > 0.8:
            risk_score = min(100, 50 + (actual_ratio - 0.8) * 250)
            probability = min(1.0, actual_ratio)
            impact_level = "critical" if actual_ratio > 1.0 else ("high" if actual_ratio > 0.95 else "medium")

            risk = RiskPrediction(
                project_id=project_id,
                risk_type="cost_overrun",
                risk_score=risk_score,
                probability=probability,
                impact_level=impact_level,
                trigger_factors=[
                    f"预算预估: ¥{budget.total_estimated:.2f}，实际已用: ¥{budget.total_actual:.2f}，"
                    f"使用率: {actual_ratio * 100:.1f}%"
                ],
                affected_tasks=[],
                mitigation_actions=[
                    "审查所有待执行采购订单，寻求更优报价",
                    "与供应商重新谈判材料价格或付款条件",
                    "评估后续工序中可优化的材料损耗率",
                    "考虑使用替代材料降低采购成本",
                ],
                status="active",
                predicted_at=now,
            )
            db.add(risk)
            risks_created.append(risk)

    # 3. 材料短缺：检查 BOMItem allocated 字段（如有）vs 需求量
    bom_result = await db.execute(
        select(BOMItem).where(BOMItem.project_id == project_id)
    )
    bom_items = bom_result.scalars().all()
    material_shortages = []
    for bom in bom_items:
        if bom.allocated is not None and bom.allocated < bom.quantity:
            shortage = bom.quantity - bom.allocated
            material_shortages.append(
                f"物料 [{bom.material_name or bom.id}] 需求 {bom.quantity}，已分配 {bom.allocated}，缺口 {shortage}"
            )
    if material_shortages:
        risk_score = min(100, len(material_shortages) * 20)
        probability = min(1.0, len(material_shortages) / 10.0)
        impact_level = "high" if len(material_shortages) > 5 else "medium"

        risk = RiskPrediction(
            project_id=project_id,
            risk_type="material_shortage",
            risk_score=risk_score,
            probability=probability,
            impact_level=impact_level,
            trigger_factors=material_shortages,
            affected_tasks=[],
            mitigation_actions=[
                "联系当前供应商确认能否加急补货",
                "启动备用供应商询价，缩短采购周期",
                "评估替代材料的可行性，减少对单一材料的依赖",
                "调整施工顺序，先执行不受材料影响的工序",
            ],
            status="active",
            predicted_at=now,
        )
        db.add(risk)
        risks_created.append(risk)

    # 4. 质量风险：近期 Inspection 不合格率 > 20%
    inspection_result = await db.execute(
        select(Inspection).where(
            Inspection.task_id.in_(
                select(ConstructionTask.id).where(ConstructionTask.project_id == project_id)
            ),
            Inspection.inspected_at.isnot(None),
        ).order_by(Inspection.inspected_at.desc()).limit(20)
    )
    recent_inspections = inspection_result.scalars().all()
    if recent_inspections:
        failed = sum(1 for i in recent_inspections if i.status == "failed")
        fail_rate = failed / len(recent_inspections)
        if fail_rate > 0.2:
            risk_score = min(100, fail_rate * 100)
            probability = fail_rate
            impact_level = "critical" if fail_rate > 0.5 else ("high" if fail_rate > 0.35 else "medium")

            risk = RiskPrediction(
                project_id=project_id,
                risk_type="quality_risk",
                risk_score=risk_score,
                probability=probability,
                impact_level=impact_level,
                trigger_factors=[
                    f"近期 {len(recent_inspections)} 次质检中 {failed} 次不合格，"
                    f"不合格率: {fail_rate * 100:.1f}%"
                ],
                affected_tasks=[i.task_id for i in recent_inspections if i.status == "failed"],
                mitigation_actions=[
                    "对不合格项所在工序进行全面复盘和重新检查",
                    "暂停同类型施工任务，排查是否存在系统性问题",
                    "更换施工班组或加强施工规范培训",
                    "增加质检频率，每道工序完工后立即检查",
                ],
                status="active",
                predicted_at=now,
            )
            db.add(risk)
            risks_created.append(risk)

    # 5. 劳动力：施工任务 assigned_to 为空
    labor_tasks_result = await db.execute(
        select(ConstructionTask).where(
            ConstructionTask.project_id == project_id,
            ConstructionTask.assigned_to.is_(None),
            ConstructionTask.status.in_(["pending", "in_progress"]),
        )
    )
    unassigned_tasks = labor_tasks_result.scalars().all()
    if unassigned_tasks:
        risk_score = min(100, len(unassigned_tasks) * 15)
        probability = min(1.0, len(unassigned_tasks) / 15.0)
        impact_level = "high" if len(unassigned_tasks) > 8 else ("medium" if len(unassigned_tasks) > 3 else "low")

        risk = RiskPrediction(
            project_id=project_id,
            risk_type="labor_shortage",
            risk_score=risk_score,
            probability=probability,
            impact_level=impact_level,
            trigger_factors=[
                f"任务 [{t.name}] 状态 {t.status}，但未指派施工负责人"
                for t in unassigned_tasks
            ],
            affected_tasks=[t.id for t in unassigned_tasks],
            mitigation_actions=[
                "立即为未指派任务分配施工负责人",
                "联系施工队长确认可用人力情况",
                "考虑从已完成队列转调人力到高优先级任务",
                "评估是否可以通过临时工或外包解决人力缺口",
            ],
            status="active",
            predicted_at=now,
        )
        db.add(risk)
        risks_created.append(risk)

    await db.flush()
    logger.info(f"项目 {project_id} 风险分析完成，创建 {len(risks_created)} 个新风险")

    return {
        "project_id": project_id,
        "risks_created": len(risks_created),
        "risks": risks_created,
    }


async def get_active_risks(project_id: str, db: AsyncSession) -> list[RiskPrediction]:
    """获取项目活跃风险"""
    result = await db.execute(
        select(RiskPrediction)
        .where(
            RiskPrediction.project_id == project_id,
            RiskPrediction.status == "active",
        )
        .order_by(RiskPrediction.risk_score.desc())
    )
    return list(result.scalars().all())


async def get_all_risks(project_id: str, db: AsyncSession) -> list[RiskPrediction]:
    """获取项目所有风险"""
    result = await db.execute(
        select(RiskPrediction)
        .where(RiskPrediction.project_id == project_id)
        .order_by(RiskPrediction.predicted_at.desc())
    )
    return list(result.scalars().all())


async def get_risk(risk_id: str, db: AsyncSession) -> RiskPrediction | None:
    """获取单个风险"""
    return await db.get(RiskPrediction, risk_id)


async def mitigate_risk(risk_id: str, db: AsyncSession, note: str | None = None) -> RiskPrediction | None:
    """标记风险已缓解"""
    risk = await db.get(RiskPrediction, risk_id)
    if not risk:
        return None
    risk.status = "mitigated"
    if note:
        current_mitigation = risk.mitigation_actions or []
        current_mitigation.append(f"[{datetime.now(timezone.utc).isoformat()}] 缓解备注: {note}")
        risk.mitigation_actions = current_mitigation
    await db.flush()
    return risk


async def resolve_risk(risk_id: str, db: AsyncSession, note: str | None = None) -> RiskPrediction | None:
    """解除风险"""
    risk = await db.get(RiskPrediction, risk_id)
    if not risk:
        return None
    risk.status = "resolved"
    risk.resolved_at = datetime.now(timezone.utc)
    if note:
        current_mitigation = risk.mitigation_actions or []
        current_mitigation.append(f"[{datetime.now(timezone.utc).isoformat()}] 解决备注: {note}")
        risk.mitigation_actions = current_mitigation
    await db.flush()
    return risk


async def get_dashboard(project_id: str, db: AsyncSession, project_name: str | None = None) -> dict:
    """获取施工健康度仪表盘"""
    all_risks = await get_all_risks(project_id, db)

    total = len(all_risks)
    active_count = sum(1 for r in all_risks if r.status == "active")
    mitigated_count = sum(1 for r in all_risks if r.status == "mitigated")
    resolved_count = sum(1 for r in all_risks if r.status == "resolved")

    # 健康度评分: 基于活跃风险的 risk_score 加权计算
    if active_count > 0:
        avg_active_score = sum(r.risk_score for r in all_risks if r.status == "active") / active_count
        health_score = max(0, 100 - avg_active_score)
    else:
        health_score = 100.0

    # 按 risk_type 分组统计
    risk_breakdown = {}
    for risk_type in ["schedule_delay", "cost_overrun", "material_shortage", "quality_risk", "labor_shortage", "weather_impact"]:
        type_risks = [r for r in all_risks if r.risk_type == risk_type and r.status == "active"]
        if type_risks:
            risk_breakdown[risk_type] = {
                "active": len(type_risks),
                "avg_score": sum(r.risk_score for r in type_risks) / len(type_risks),
            }

    # 生成摘要
    if health_score >= 80:
        summary = f"项目 [{project_name or project_id}] 施工健康度良好 ({health_score:.0f}/100)，当前 {active_count} 个活跃风险需关注。"
    elif health_score >= 50:
        summary = f"项目 [{project_name or project_id}] 施工健康度一般 ({health_score:.0f}/100)，{active_count} 个活跃风险建议及时处理。"
    else:
        summary = f"项目 [{project_name or project_id}] 施工健康度较差 ({health_score:.0f}/100)，{active_count} 个活跃风险需要紧急处理！"

    return {
        "project_id": project_id,
        "project_name": project_name,
        "total_risks": total,
        "active_count": active_count,
        "mitigated_count": mitigated_count,
        "resolved_count": resolved_count,
        "health_score": round(health_score, 1),
        "risk_breakdown": risk_breakdown,
        "active_risks": [r for r in all_risks if r.status == "active"],
        "summary": summary,
    }

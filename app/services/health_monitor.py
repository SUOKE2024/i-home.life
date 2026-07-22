"""施工健康 OS — 主动干预式进度监控与智能预警

借鉴索克生活"Health OS 主动干预"范式：不再等用户查询进度，而是
通过定时巡检 + 规则引擎 + 多通道推送，主动发现施工延期/质检异常
并向相关方推送预警卡片。

核心能力：
1. **定时巡检**：周期性检查所有活跃项目的里程碑完成率 vs 计划完成率
2. **规则引擎**：定义 5 级预警规则（正常/关注/警告/严重/紧急）
3. **主动推送**：通过 push_sender 向业主/施工方/监理发送预警卡片
4. **趋势分析**：基于历史里程碑数据预测潜在延期风险
5. **施工健康评分**：0-100 分综合评估项目健康度

受 settings.health_os_enabled feature flag 控制。
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """预警级别"""
    NORMAL = "normal"       # 正常 — 无需处理
    ATTENTION = "attention"  # 关注 — 偏差 < 10%
    WARNING = "warning"      # 警告 — 偏差 10-20%
    SEVERE = "severe"        # 严重 — 偏差 20-30%
    CRITICAL = "critical"    # 紧急 — 偏差 > 30% 或里程碑超期


class HealthStatus(str, Enum):
    """施工健康状态"""
    HEALTHY = "healthy"         # 健康 (≥80分)
    ATTENTION = "attention"     # 需关注 (60-79分)
    AT_RISK = "at_risk"         # 有风险 (40-59分)
    CRITICAL = "critical"       # 严重 ( <40分)


@dataclass
class HealthCheckResult:
    """单项目健康检查结果"""
    project_id: str
    project_name: str = ""
    health_score: float = 100.0
    status: HealthStatus = HealthStatus.HEALTHY
    total_milestones: int = 0
    completed_milestones: int = 0
    delayed_milestones: int = 0
    planned_progress: float = 0.0
    actual_progress: float = 0.0
    deviation: float = 0.0  # 实际-计划偏差（百分点）
    alerts: list[dict[str, Any]] = field(default_factory=list)
    checked_at: str = ""


# ════════════════════════════════════════════════════════════════
# 规则引擎
# ════════════════════════════════════════════════════════════════


class HealthRuleEngine:
    """施工健康规则引擎 — 5 级预警判定

    规则优先级（从高到低）：
    1. CRITICAL: 里程碑已超 planned_date 且未完成，或进度偏差 > 30%
    2. SEVERE:   进度偏差 20-30%
    3. WARNING:  进度偏差 10-20%
    4. ATTENTION: 进度偏差 < 10%，或仅 1 个里程碑延期
    5. NORMAL:   无问题
    """

    @staticmethod
    def evaluate(
        planned_progress: float,
        actual_progress: float,
        delayed_count: int,
        overdue_count: int,  # 超期未完成的里程碑数
    ) -> tuple[AlertLevel, str]:
        """评估项目预警级别。

        Returns:
            (AlertLevel, reason_string)
        """
        deviation = actual_progress - planned_progress

        if overdue_count >= 2:
            return AlertLevel.CRITICAL, f"{overdue_count} 个里程碑已超期未完成"
        if overdue_count == 1:
            return AlertLevel.SEVERE, "1 个里程碑已超期未完成"
        if deviation < -30:
            return AlertLevel.CRITICAL, f"进度严重滞后 {abs(deviation):.0f}%"
        if deviation < -20:
            return AlertLevel.SEVERE, f"进度滞后 {abs(deviation):.0f}%"
        if deviation < -10:
            return AlertLevel.WARNING, f"进度略滞后 {abs(deviation):.0f}%"
        if deviation < -5 or delayed_count > 0:
            return AlertLevel.ATTENTION, f"进度轻微偏差 {abs(deviation):.0f}%"
        return AlertLevel.NORMAL, "进度正常"

    @staticmethod
    def compute_health_score(
        planned_progress: float,
        actual_progress: float,
        delayed_count: int,
        overdue_count: int,
        total_milestones: int,
    ) -> float:
        """计算施工健康评分（0-100）。

        基准 100 分，各项扣分：
        - 进度偏差每 1% 扣 1 分（最多扣 40 分）
        - 每个延期里程碑扣 5 分
        - 每个超期里程碑扣 15 分
        - 最低 0 分
        """
        if total_milestones == 0:
            return 100.0

        score = 100.0
        deviation = max(0, planned_progress - actual_progress)
        score -= min(40, deviation)  # 进度偏差扣分，上限 40

        score -= min(30, delayed_count * 5)  # 延期扣分
        score -= min(45, overdue_count * 15)  # 超期扣分

        return max(0.0, round(score, 1))

    @staticmethod
    def score_to_status(score: float) -> HealthStatus:
        """评分 → 健康状态"""
        if score >= 80:
            return HealthStatus.HEALTHY
        if score >= 60:
            return HealthStatus.ATTENTION
        if score >= 40:
            return HealthStatus.AT_RISK
        return HealthStatus.CRITICAL


# ════════════════════════════════════════════════════════════════
# 主动巡检器
# ════════════════════════════════════════════════════════════════


class HealthMonitor:
    """施工健康主动巡检器

    Usage::

        monitor = HealthMonitor(db_session_factory)
        await monitor.start(interval_seconds=3600)  # 每小时巡检一次
        # ... 应用运行中 ...
        await monitor.stop()
    """

    def __init__(self, db_session_factory=None):
        self._db_factory = db_session_factory
        self._running = False
        self._task: asyncio.Task | None = None
        self._interval: int = 3600  # 默认每小时巡检
        self._last_results: dict[str, HealthCheckResult] = {}
        self._rule_engine = HealthRuleEngine()

    async def start(self, interval_seconds: int = 3600):
        """启动定时巡检（后台任务）。

        Args:
            interval_seconds: 巡检间隔（秒），默认 3600（1小时）
        """
        if not settings.health_os_enabled:
            logger.info("health_monitor: health_os_enabled=False，不启动巡检")
            return

        self._interval = interval_seconds
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "health_monitor_started: interval=%ds feature_flag=%s",
            interval_seconds, settings.health_os_enabled,
        )

    async def stop(self):
        """停止巡检"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("health_monitor_stopped")

    async def _run_loop(self):
        """巡检主循环"""
        while self._running:
            try:
                await self.run_check()
            except Exception as e:
                logger.error("health_monitor_loop_error: %s", e)
            await asyncio.sleep(self._interval)

    async def run_check(self) -> list[HealthCheckResult]:
        """执行一次全量巡检。

        检查所有活跃项目的里程碑进度，对异常项目生成预警并推送。
        """
        if not settings.health_os_enabled:
            return []

        if not self._db_factory:
            logger.warning("health_monitor: db_session_factory 未配置，跳过巡检")
            return []

        start = time.perf_counter()
        results: list[HealthCheckResult] = []

        try:
            from sqlalchemy import select
            from app.models.project import Project
            from app.models.progress_alert import ProgressAlert, MilestoneTracker

            async with self._db_factory() as db:
                # 查询所有活跃项目
                proj_result = await db.execute(
                    select(Project).where(Project.status.in_(["active", "in_progress"]))
                )
                projects = proj_result.scalars().all()

                for project in projects:
                    try:
                        result = await self._check_project(db, project)
                        results.append(result)
                        self._last_results[project.id] = result

                        # 主动推送预警
                        if result.status != HealthStatus.HEALTHY:
                            await self._trigger_alerts(db, project, result)
                    except Exception as e:
                        logger.error(
                            "health_check_project_error: project=%s error=%s",
                            project.id, e,
                        )

        except Exception as e:
            logger.error("health_monitor_check_error: %s", e)

        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "health_monitor_check_done: projects=%d unhealthy=%d elapsed_ms=%d",
            len(results),
            sum(1 for r in results if r.status != HealthStatus.HEALTHY),
            elapsed,
        )
        return results

    async def _check_project(self, db, project) -> HealthCheckResult:
        """检查单个项目的健康状态"""
        from sqlalchemy import select
        from app.models.progress_alert import MilestoneTracker

        result = HealthCheckResult(
            project_id=project.id,
            project_name=getattr(project, "name", project.id),
            checked_at=datetime.now(timezone.utc).isoformat(),
        )

        # 加载所有里程碑
        ms_result = await db.execute(
            select(MilestoneTracker).where(
                MilestoneTracker.project_id == project.id
            ).order_by(MilestoneTracker.planned_percent)
        )
        milestones = ms_result.scalars().all()

        result.total_milestones = len(milestones)
        if not milestones:
            return result

        # 统计数据
        now = datetime.now(timezone.utc)
        overdue_count = 0
        delayed_count = 0
        total_planned = 0.0
        total_actual = 0.0

        for m in milestones:
            total_planned += m.planned_percent
            if m.status == "completed":
                result.completed_milestones += 1
                total_actual += m.actual_percent
            elif m.status == "delayed":
                delayed_count += 1
            if m.planned_date and m.planned_date < now and m.status not in ("completed",):
                overdue_count += 1

        result.delayed_milestones = delayed_count
        result.planned_progress = total_planned
        result.actual_progress = total_actual
        result.deviation = total_actual - total_planned

        # 规则引擎判定
        level, reason = self._rule_engine.evaluate(
            planned_progress=total_planned,
            actual_progress=total_actual,
            delayed_count=delayed_count,
            overdue_count=overdue_count,
        )

        result.health_score = self._rule_engine.compute_health_score(
            planned_progress=total_planned,
            actual_progress=total_actual,
            delayed_count=delayed_count,
            overdue_count=overdue_count,
            total_milestones=len(milestones),
        )
        result.status = self._rule_engine.score_to_status(result.health_score)

        if level != AlertLevel.NORMAL:
            result.alerts.append({
                "level": level.value,
                "reason": reason,
                "project_id": project.id,
                "health_score": result.health_score,
                "planned": total_planned,
                "actual": total_actual,
                "delayed": delayed_count,
                "overdue": overdue_count,
            })

        return result

    async def _trigger_alerts(self, db, project, result: HealthCheckResult):
        """触发主动预警：创建 ProgressAlert + 推送通知"""
        from app.models.progress_alert import ProgressAlert

        for alert_info in result.alerts:
            severity_map = {
                AlertLevel.ATTENTION: "low",
                AlertLevel.WARNING: "medium",
                AlertLevel.SEVERE: "high",
                AlertLevel.CRITICAL: "critical",
            }
            severity = severity_map.get(
                AlertLevel(alert_info["level"]), "medium"
            )

            # 检查是否已有同类活跃预警（去重）
            from sqlalchemy import select
            existing = await db.execute(
                select(ProgressAlert).where(
                    ProgressAlert.project_id == project.id,
                    ProgressAlert.alert_type == "health_check",
                    ProgressAlert.status == "active",
                )
            )
            if existing.scalar_one_or_none():
                continue

            alert = ProgressAlert(
                project_id=project.id,
                alert_type="health_check",
                severity=severity,
                phase="overall",
                message=f"施工健康预警: {alert_info['reason']}（评分 {result.health_score}）",
                delay_days=max(0, alert_info.get("overdue", 0)),
                progress_percent=result.actual_progress,
                suggestion=(
                    f"当前进度 {result.actual_progress:.0f}%，计划 {result.planned_progress:.0f}%，"
                    f"{alert_info['delayed']} 个里程碑延期。"
                    f"建议与施工方沟通赶工计划或调整里程碑时间节点。"
                ),
            )
            db.add(alert)
            logger.info(
                "health_alert_created: project=%s level=%s score=%.1f",
                project.id, alert_info["level"], result.health_score,
            )

            # 推送通知（非阻塞）
            try:
                from app.services.push_sender import send_project_push
                await send_project_push(
                    db=db,
                    project_id=project.id,
                    title="施工健康预警",
                    body=f"{project.name or '项目'} 施工进度异常: {alert_info['reason']}",
                    alert_type=alert_info["level"],
                )
            except Exception as e:
                logger.debug("health_push_failed: project=%s error=%s", project.id, e)

        await db.commit()

    def get_latest_result(self, project_id: str) -> HealthCheckResult | None:
        """获取项目最近一次巡检结果（内存缓存）"""
        return self._last_results.get(project_id)

    def get_all_results(self) -> dict[str, HealthCheckResult]:
        """获取所有项目最近巡检结果"""
        return dict(self._last_results)


# 模块级单例
health_monitor = HealthMonitor()

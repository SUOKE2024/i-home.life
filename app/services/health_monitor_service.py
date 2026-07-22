"""A2 智能家居健康监测系统服务层 — CRUD + 阈值检测 + 健康报告"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.health_monitor import HealthMonitor, AirQualityRecord


# ── 阈值常量 ──

THRESHOLDS: dict[str, Any] = {
    "sleep_quality": {
        "sleep_score_warning": 60,    # 睡眠分数 < 60 触发预警
        "sleep_score_critical": 40,   # 睡眠分数 < 40 触发严重预警
    },
    "pm25": {
        "warning": 75.0,              # PM2.5 > 75 μg/m³ 触发预警（中国标准）
        "critical": 150.0,            # PM2.5 > 150 μg/m³ 触发严重预警
    },
    "formaldehyde": {
        "warning": 0.08,              # 甲醛 > 0.08 mg/m³ 触发预警（GB/T 18883-2022）
        "critical": 0.10,             # 甲醛 > 0.10 mg/m³ 触发严重预警
    },
    "fall_detection": {
        "warning": True,              # 检测到跌倒直接触发预警
    },
    "heart_rate": {
        "bpm_low_warning": 50,         # 心率 < 50 bpm 触发预警
        "bpm_high_warning": 100,       # 心率 > 100 bpm 触发预警
        "bpm_low_critical": 40,
        "bpm_high_critical": 120,
    },
    "spo2": {
        "spo2_warning": 95,            # 血氧 < 95% 触发预警
        "spo2_critical": 90,           # 血氧 < 90% 触发严重预警
    },
    "co2": {
        "warning": 1000.0,             # CO2 > 1000 ppm 触发预警
        "critical": 2000.0,            # CO2 > 2000 ppm 触发严重预警
    },
    "tvoc": {
        "warning": 500.0,              # TVOC > 500 ppb 触发预警
        "critical": 1000.0,
    },
}


# ── 健康监测记录 CRUD ──


async def create_health_record(db: AsyncSession, data: dict) -> HealthMonitor:
    """创建健康监测记录"""
    record = HealthMonitor(**data)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_health_record(db: AsyncSession, record_id: str) -> HealthMonitor | None:
    """获取单条健康监测记录"""
    result = await db.execute(
        select(HealthMonitor).where(HealthMonitor.id == record_id)
    )
    return result.scalar_one_or_none()


async def list_health_records_by_project(
    db: AsyncSession,
    project_id: str,
    monitor_type: str | None = None,
    limit: int = 50,
) -> list[HealthMonitor]:
    """按项目查询健康监测记录，支持按类型筛选"""
    stmt = select(HealthMonitor).where(HealthMonitor.project_id == project_id)
    if monitor_type:
        stmt = stmt.where(HealthMonitor.monitor_type == monitor_type)
    stmt = stmt.order_by(HealthMonitor.recorded_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_alert_records_by_project(
    db: AsyncSession,
    project_id: str,
    limit: int = 20,
) -> list[HealthMonitor]:
    """按项目查询预警记录（warning + critical）"""
    stmt = (
        select(HealthMonitor)
        .where(
            HealthMonitor.project_id == project_id,
            HealthMonitor.alert_level.in_(["warning", "critical"]),
        )
        .order_by(HealthMonitor.recorded_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── 空气质量记录 CRUD ──


async def create_air_quality_record(db: AsyncSession, data: dict) -> AirQualityRecord:
    """创建空气质量记录"""
    record = AirQualityRecord(**data)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def list_air_quality_records_by_project(
    db: AsyncSession,
    project_id: str,
    room_name: str | None = None,
    limit: int = 50,
) -> list[AirQualityRecord]:
    """按项目查询空气质量记录，支持按房间筛选"""
    stmt = select(AirQualityRecord).where(AirQualityRecord.project_id == project_id)
    if room_name:
        stmt = stmt.where(AirQualityRecord.room_name == room_name)
    stmt = stmt.order_by(AirQualityRecord.recorded_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_latest_air_quality(db: AsyncSession, project_id: str) -> AirQualityRecord | None:
    """获取项目最新空气质量记录"""
    result = await db.execute(
        select(AirQualityRecord)
        .where(AirQualityRecord.project_id == project_id)
        .order_by(AirQualityRecord.recorded_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ── 阈值检测 ──


def check_thresholds(
    monitor_type: str,
    value: dict[str, Any],
) -> tuple[str, str | None]:
    """阈值检测：返回 (alert_level, alert_message)

    - 睡眠 < 60 分预警
    - PM2.5 > 75 预警
    - 甲醛 > 0.08 预警
    - 跌倒检测
    - 心率异常
    - 血氧异常
    """
    alert_level = "normal"
    alert_message = None

    if monitor_type == "sleep_quality":
        score = value.get("sleep_score")
        if score is not None:
            thresholds = THRESHOLDS.get("sleep_quality", {})
            if score < thresholds.get("sleep_score_critical", 40):
                alert_level = "critical"
                alert_message = f"睡眠质量严重偏低，睡眠分数: {score}"
            elif score < thresholds.get("sleep_score_warning", 60):
                alert_level = "warning"
                alert_message = f"睡眠质量偏低，建议关注。睡眠分数: {score}"

    elif monitor_type == "fall_detection":
        if value.get("fall_detected"):
            alert_level = "critical"
            alert_message = "检测到跌倒事件，请立即关注！"

    elif monitor_type == "heart_rate":
        bpm = value.get("bpm")
        if bpm is not None:
            thresholds = THRESHOLDS.get("heart_rate", {})
            if bpm < thresholds.get("bpm_low_critical", 40):
                alert_level = "critical"
                alert_message = f"心率严重偏低: {bpm} bpm"
            elif bpm > thresholds.get("bpm_high_critical", 120):
                alert_level = "critical"
                alert_message = f"心率严重偏高: {bpm} bpm"
            elif bpm < thresholds.get("bpm_low_warning", 50):
                alert_level = "warning"
                alert_message = f"心率偏低: {bpm} bpm"
            elif bpm > thresholds.get("bpm_high_warning", 100):
                alert_level = "warning"
                alert_message = f"心率偏高: {bpm} bpm"

    elif monitor_type == "spo2":
        spo2 = value.get("spo2")
        if spo2 is not None:
            thresholds = THRESHOLDS.get("spo2", {})
            if spo2 < thresholds.get("spo2_critical", 90):
                alert_level = "critical"
                alert_message = f"血氧饱和度严重偏低: {spo2}%"
            elif spo2 < thresholds.get("spo2_warning", 95):
                alert_level = "warning"
                alert_message = f"血氧饱和度偏低: {spo2}%"

    elif monitor_type == "air_quality":
        pm25 = value.get("pm25")
        formaldehyde = value.get("formaldehyde")
        co2 = value.get("co2")
        tvoc = value.get("tvoc")
        messages = []

        if pm25 is not None:
            if pm25 > THRESHOLDS.get("pm25", {}).get("critical", 150):
                alert_level = "critical"
                messages.append(f"PM2.5 严重超标: {pm25} μg/m³")
            elif pm25 > THRESHOLDS.get("pm25", {}).get("warning", 75):
                alert_level = max(alert_level, "warning") if alert_level != "critical" else "critical"
                messages.append(f"PM2.5 超标: {pm25} μg/m³")

        if formaldehyde is not None:
            if formaldehyde > THRESHOLDS.get("formaldehyde", {}).get("critical", 0.10):
                alert_level = "critical"
                messages.append(f"甲醛严重超标: {formaldehyde} mg/m³")
            elif formaldehyde > THRESHOLDS.get("formaldehyde", {}).get("warning", 0.08):
                alert_level = max(alert_level, "warning") if alert_level != "critical" else "critical"
                messages.append(f"甲醛浓度超标: {formaldehyde} mg/m³")

        if co2 is not None and co2 > THRESHOLDS.get("co2", {}).get("critical", 2000):
            alert_level = max(alert_level, "warning") if alert_level != "critical" else "critical"
            messages.append(f"CO2 浓度偏高: {co2} ppm")
        elif co2 is not None and co2 > THRESHOLDS.get("co2", {}).get("warning", 1000):
            alert_level = max(alert_level, "warning") if alert_level != "critical" else "critical"
            messages.append(f"CO2 浓度偏高: {co2} ppm")

        if tvoc is not None and tvoc > THRESHOLDS.get("tvoc", {}).get("critical", 1000):
            alert_level = max(alert_level, "warning") if alert_level != "critical" else "critical"
            messages.append(f"TVOC 浓度偏高: {tvoc} ppb")

        if messages:
            alert_message = "; ".join(messages)

    if alert_level == "normal":
        return "normal", None
    else:
        # 修正：确保比较逻辑中 warning 不会被覆盖为 normal
        return alert_level if alert_level in ("warning", "critical") else "warning", alert_message


def check_air_quality_thresholds(record: AirQualityRecord) -> tuple[str, str | None]:
    """对空气质量记录进行阈值检测"""
    alert_level = "normal"
    messages = []

    if record.pm25 > THRESHOLDS.get("pm25", {}).get("critical", 150):
        alert_level = "critical"
        messages.append(f"PM2.5 严重超标: {record.pm25} μg/m³")
    elif record.pm25 > THRESHOLDS.get("pm25", {}).get("warning", 75):
        alert_level = "warning"
        messages.append(f"PM2.5 超标: {record.pm25} μg/m³")

    if record.formaldehyde > THRESHOLDS.get("formaldehyde", {}).get("critical", 0.10):
        alert_level = "critical"
        messages.append(f"甲醛严重超标: {record.formaldehyde} mg/m³")
    elif record.formaldehyde > THRESHOLDS.get("formaldehyde", {}).get("warning", 0.08):
        alert_level = "warning" if alert_level != "critical" else "critical"
        messages.append(f"甲醛浓度超标: {record.formaldehyde} mg/m³")

    if record.co2 > THRESHOLDS.get("co2", {}).get("critical", 2000):
        alert_level = "warning" if alert_level != "critical" else "critical"
        messages.append(f"CO2 浓度偏高: {record.co2} ppm")
    elif record.co2 > THRESHOLDS.get("co2", {}).get("warning", 1000):
        alert_level = "warning" if alert_level != "critical" else "critical"
        messages.append(f"CO2 浓度偏高: {record.co2} ppm")

    if record.tvoc > THRESHOLDS.get("tvoc", {}).get("critical", 1000):
        alert_level = "warning" if alert_level != "critical" else "critical"
        messages.append(f"TVOC 浓度偏高: {record.tvoc} ppb")
    elif record.tvoc > THRESHOLDS.get("tvoc", {}).get("warning", 500):
        alert_level = "warning" if alert_level != "critical" else "critical"
        messages.append(f"TVOC 浓度偏高: {record.tvoc} ppb")

    if not messages:
        return "normal", None

    alert_message = "; ".join(messages)
    return alert_level, alert_message


# ── 综合健康报告 ──


async def generate_health_report(db: AsyncSession, project_id: str) -> dict:
    """生成综合健康报告"""
    now = datetime.now(timezone.utc)

    # 统计总记录数
    total_result = await db.execute(
        select(sql_func.count(HealthMonitor.id)).where(HealthMonitor.project_id == project_id)
    )
    total_records = total_result.scalar() or 0

    # 统计预警记录数
    alert_result = await db.execute(
        select(sql_func.count(HealthMonitor.id)).where(
            HealthMonitor.project_id == project_id,
            HealthMonitor.alert_level.in_(["warning", "critical"]),
        )
    )
    alert_records = alert_result.scalar() or 0

    # 计算睡眠平均分
    sleep_result = await db.execute(
        select(sql_func.avg(
            HealthMonitor.value["sleep_score"].as_float()
        )).where(
            HealthMonitor.project_id == project_id,
            HealthMonitor.monitor_type == "sleep_quality",
        )
    )
    sleep_avg = sleep_result.scalar()
    sleep_avg_score = round(float(sleep_avg), 1) if sleep_avg is not None else None

    # 最新空气质量
    latest_aq = await get_latest_air_quality(db, project_id)

    # 最近预警记录
    alert_records_list = await list_alert_records_by_project(db, project_id, limit=10)
    recent_alerts = [
        {
            "monitor_type": r.monitor_type,
            "alert_level": r.alert_level,
            "alert_message": r.alert_message,
            "value": r.value,
            "recorded_at": r.recorded_at,
        }
        for r in alert_records_list
    ]

    # 生成建议
    recommendations: list[str] = []
    if sleep_avg_score is not None and sleep_avg_score < 60:
        recommendations.append("睡眠质量低于 60 分，建议调整作息时间，睡前减少屏幕使用")
    if latest_aq and latest_aq.pm25 > 75:
        recommendations.append("PM2.5 超标，建议开启空气净化器并减少开窗")
    if latest_aq and latest_aq.formaldehyde > 0.08:
        recommendations.append("甲醛浓度超标，建议加强通风并使用活性炭吸附")
    if latest_aq and latest_aq.co2 > 1000:
        recommendations.append("CO2 浓度偏高，建议开窗通风改善室内空气质量")
    if alert_records > 0:
        recommendations.append(f"近期待 {alert_records} 条预警记录，请关注健康状态")
    if not recommendations:
        recommendations.append("当前各项健康指标良好，请继续保持")

    # 生成摘要
    parts = [f"共 {total_records} 条健康监测记录"]
    if alert_records > 0:
        parts.append(f"{alert_records} 条预警")
    if sleep_avg_score is not None:
        desc = "良好" if sleep_avg_score >= 80 else ("一般" if sleep_avg_score >= 60 else "偏低")
        parts.append(f"睡眠平均分 {sleep_avg_score}（{desc}）")
    if latest_aq:
        parts.append(f"室内空气质量 {latest_aq.aqi_level}，AQI {latest_aq.aqi_index}")
    summary = "；".join(parts) + "。"

    return {
        "project_id": project_id,
        "generated_at": now,
        "summary": summary,
        "total_records": total_records,
        "alert_records": alert_records,
        "sleep_avg_score": sleep_avg_score,
        "latest_air_quality": latest_aq,
        "recent_alerts": recent_alerts,
        "recommendations": recommendations,
    }

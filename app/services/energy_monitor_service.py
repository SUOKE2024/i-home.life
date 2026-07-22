"""A1 智能家居能耗监测系统服务层 — 能耗记录 + 报告生成 + 节能建议"""

from datetime import datetime, timedelta

from sqlalchemy import select, func as sql_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.energy_monitor import EnergyMonitor, EnergySavingTip
from app.models.smart_home import SmartHomeScheme, SmartDevice

# ── 常量 ──

ENERGY_PRICE_PER_KWH = 0.6  # 元/度，基准电价
CARBON_FACTOR = 0.581       # kgCO2/kWh，中国电网碳排放因子

# 设备待机功率参考值（W）
STANDBY_POWER_REFERENCE: dict[str, float] = {
    "tv": 5.0,
    "ac": 3.0,
    "light": 0.5,
    "computer": 4.0,
    "router": 6.0,
    "speaker": 3.0,
    "curtain": 1.5,
    "socket": 1.0,
    "camera": 2.0,
    "thermostat": 1.0,
    "air_purifier": 2.0,
    "robot_vacuum": 3.0,
}

# 设备类型到中文描述映射
DEVICE_TYPE_LABELS: dict[str, str] = {
    "light": "照明",
    "ac": "空调",
    "tv": "电视",
    "computer": "电脑",
    "router": "路由器",
    "speaker": "音箱",
    "curtain": "电动窗帘",
    "switch": "智能开关",
    "socket": "智能插座",
    "camera": "摄像头",
    "lock": "智能门锁",
    "sensor": "传感器",
    "thermostat": "温控器",
    "air_purifier": "空气净化器",
    "robot_vacuum": "扫地机器人",
}


# ── CRUD ──


async def create_record(db: AsyncSession, data: dict) -> EnergyMonitor:
    """创建能耗监测记录"""
    total = float(data.get("total_consumption_kwh", 0))
    # 自动计算费用和碳排放
    if "estimated_cost" not in data or not data.get("estimated_cost"):
        data["estimated_cost"] = round(total * ENERGY_PRICE_PER_KWH, 2)
    if "carbon_footprint_kg" not in data or not data.get("carbon_footprint_kg"):
        data["carbon_footprint_kg"] = round(total * CARBON_FACTOR, 4)

    record = EnergyMonitor(**data)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_records_by_scheme(db: AsyncSession, scheme_id: str) -> list[EnergyMonitor]:
    """获取方案的全部能耗记录"""
    result = await db.execute(
        select(EnergyMonitor)
        .where(EnergyMonitor.scheme_id == scheme_id)
        .order_by(EnergyMonitor.recorded_at.desc())
    )
    return list(result.scalars().all())


async def get_records_by_project(db: AsyncSession, project_id: str) -> list[EnergyMonitor]:
    """获取项目的全部能耗记录"""
    result = await db.execute(
        select(EnergyMonitor)
        .where(EnergyMonitor.project_id == project_id)
        .order_by(EnergyMonitor.recorded_at.desc())
    )
    return list(result.scalars().all())


# ── 报告生成 ──


async def generate_energy_report(db: AsyncSession, scheme_id: str) -> dict:
    """生成能耗汇总报告：趋势数据 + 设备排行 + 节能建议"""
    # 获取最近 30 条记录用于趋势分析
    result = await db.execute(
        select(EnergyMonitor)
        .where(EnergyMonitor.scheme_id == scheme_id)
        .order_by(EnergyMonitor.recorded_at.desc())
        .limit(30)
    )
    records = list(result.scalars().all())

    if not records:
        return {
            "scheme_id": scheme_id,
            "period": "monthly",
            "total_consumption_kwh": 0.0,
            "estimated_cost": 0.0,
            "carbon_footprint_kg": 0.0,
            "peak_power_w": 0.0,
            "avg_power_w": 0.0,
            "standby_consumption_kwh": 0.0,
            "standby_ratio": 0.0,
            "trend": [],
            "device_ranking": [],
            "tips": [],
        }

    latest = records[0]

    # 趋势数据（时间升序）
    trend = [
        {
            "recorded_at": r.recorded_at.isoformat(),
            "total_consumption_kwh": r.total_consumption_kwh,
            "estimated_cost": r.estimated_cost,
        }
        for r in reversed(records)
    ]

    # 设备排行（汇总所有记录的 device_breakdown）
    device_totals: dict[str, float] = {}
    for r in records:
        breakdown = r.device_breakdown or {}
        for dev_name, kwh in breakdown.items():
            device_totals[dev_name] = device_totals.get(dev_name, 0) + float(kwh)

    grand_total = sum(device_totals.values()) or 1.0
    device_ranking = [
        {
            "device_name": dev,
            "consumption_kwh": round(kwh, 2),
            "percentage": round(kwh / grand_total * 100, 1),
        }
        for dev, kwh in sorted(device_totals.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    # 待机能耗占比
    total_consumption = latest.total_consumption_kwh or 0.0
    standby = latest.standby_consumption_kwh or 0.0
    standby_ratio = round(standby / total_consumption * 100, 1) if total_consumption > 0 else 0.0

    # 节能建议
    tips = await get_tips(db, scheme_id)

    return {
        "scheme_id": scheme_id,
        "period": "monthly",
        "total_consumption_kwh": latest.total_consumption_kwh,
        "estimated_cost": latest.estimated_cost,
        "carbon_footprint_kg": latest.carbon_footprint_kg,
        "peak_power_w": latest.peak_power_w,
        "avg_power_w": latest.avg_power_w,
        "standby_consumption_kwh": standby,
        "standby_ratio": standby_ratio,
        "trend": trend,
        "device_ranking": device_ranking,
        "tips": [await _tip_to_dict(db, t) for t in tips],
    }


# ── 节能建议 ──


async def generate_tips(db: AsyncSession, scheme_id: str) -> list[EnergySavingTip]:
    """基于能耗模式自动生成节能建议

    规则：
    1. 待机能耗 > 15% → standby_reduction
    2. 峰值功率 > 日均 × 3 → schedule_optimization
    3. 空调/暖气能耗 > 40% → bill_optimization
    4. 老旧高功耗设备 → device_replacement
    """
    result = await db.execute(
        select(EnergyMonitor)
        .where(EnergyMonitor.scheme_id == scheme_id)
        .order_by(EnergyMonitor.recorded_at.desc())
        .limit(5)
    )
    records = list(result.scalars().all())

    if not records:
        return []

    latest = records[0]
    tips: list[EnergySavingTip] = []

    # 1. 待机能耗检查
    total = latest.total_consumption_kwh or 0.0
    standby = latest.standby_consumption_kwh or 0.0
    if total > 0 and (standby / total) > 0.15:
        standby_pct = round(standby / total * 100, 0)
        tip = EnergySavingTip(
            scheme_id=scheme_id,
            tip_type="standby_reduction",
            suggestion=f"待机能耗占比 {standby_pct:.0f}%，超过 15% 阈值。建议：1) 为电视/路由器/音箱安装智能插座定时断电；2) 开启设备的节能模式；3) 不使用时完全关闭而非待机。预计每月可节省 {round(standby * 0.6 * ENERGY_PRICE_PER_KWH, 2)} 元。",
            priority="high",
        )
        db.add(tip)
        tips.append(tip)

    # 2. 峰值功率检查
    avg_power = latest.avg_power_w or 0.0
    peak_power = latest.peak_power_w or 0.0
    if avg_power > 0 and (peak_power / avg_power) > 3:
        tip = EnergySavingTip(
            scheme_id=scheme_id,
            tip_type="schedule_optimization",
            suggestion=f"峰值功率 {peak_power:.0f}W 远高于平均功率 {avg_power:.0f}W（比值 {peak_power / avg_power:.1f}x），存在功率尖峰。建议：1) 错峰使用大功率电器（空调、热水器）；2) 利用智能场景设置定时启动，避免同时开启多台大功率设备；3) 考虑安装智能负载管理设备。",
            priority="medium",
        )
        db.add(tip)
        tips.append(tip)

    # 3. 高功耗设备检查
    device_breakdown = latest.device_breakdown or {}
    if device_breakdown:
        total_devices = sum(v for v in device_breakdown.values())
        if total_devices > 0:
            for dev, kwh in device_breakdown.items():
                pct = kwh / total_devices
                if dev in ("ac", "thermostat", "air_purifier") and pct > 0.4:
                    tip = EnergySavingTip(
                        scheme_id=scheme_id,
                        tip_type="bill_optimization",
                        device_type=dev,
                        device_name=DEVICE_TYPE_LABELS.get(dev, dev),
                        current_consumption=round(kwh, 2),
                        potential_saving_pct=15.0,
                        suggestion=f"{DEVICE_TYPE_LABELS.get(dev, dev)} 能耗占比 {pct * 100:.0f}%，建议：1) 夏季空调温度设定在 26°C 以上（每升高 1°C 可节电 6-8%）；2) 定期清洗滤网；3) 配合智能窗帘和自然通风减少使用时长。预计可降低该类能耗 15-20%。",
                        priority="high",
                    )
                    db.add(tip)
                    tips.append(tip)

    # 4. 设备平衡检查：如果有设备能耗很低但待机偏高
    if latest.standby_consumption_kwh > 2.0:
        tip = EnergySavingTip(
            scheme_id=scheme_id,
            tip_type="device_replacement",
            suggestion=f"系统检测到待机能耗较高（{standby:.2f} kWh），可能存在老旧高功耗待机设备。建议：1) 排查路由器、机顶盒等 24 小时在线设备；2) 更换为一级能效新品；3) 老式变压器适配器建议更换为开关电源。预计月省 {round(standby * 0.5, 2)} kg CO2 碳排放。",
            priority="medium",
        )
        db.add(tip)
        tips.append(tip)

    if tips:
        await db.commit()
        for t in tips:
            await db.refresh(t)

    return tips


async def get_tips(db: AsyncSession, scheme_id: str) -> list[EnergySavingTip]:
    """获取方案的全部节能建议"""
    result = await db.execute(
        select(EnergySavingTip)
        .where(EnergySavingTip.scheme_id == scheme_id)
        .order_by(EnergySavingTip.created_at.desc())
    )
    return list(result.scalars().all())


async def apply_tip(db: AsyncSession, tip_id: str) -> EnergySavingTip | None:
    """标记建议为已采纳"""
    result = await db.execute(
        select(EnergySavingTip).where(EnergySavingTip.id == tip_id)
    )
    tip = result.scalar_one_or_none()
    if not tip:
        return None
    tip.status = "applied"
    await db.commit()
    await db.refresh(tip)
    return tip


async def _tip_to_dict(db: AsyncSession, tip: EnergySavingTip) -> dict:
    """将 EnergySavingTip ORM 对象转为字典"""
    return {
        "id": tip.id,
        "scheme_id": tip.scheme_id,
        "tip_type": tip.tip_type,
        "device_type": tip.device_type,
        "device_name": tip.device_name,
        "current_consumption": tip.current_consumption,
        "potential_saving_pct": tip.potential_saving_pct,
        "suggestion": tip.suggestion,
        "priority": tip.priority,
        "status": tip.status,
        "created_at": tip.created_at.isoformat() if tip.created_at else None,
    }

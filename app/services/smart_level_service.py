"""F46 全屋智能 L1-L5 智能等级预适配 — 对齐智能家电国标

2026-05-01 起两项智能家电国标实施：L1-L5 五级智能等级 + 九大场景量化评价体系，
**L3 起才算"真智能"**；2028 互联互通强制国标执行是确定性窗口。

本模块为"预适配"层：把 GB 五级智能等级映射为可量化评价函数，聚合既有
数据（SmartHomeScheme / SmartDevice / SceneAutomation / EcosystemIntegration）
评定项目当前智能等级，为 2028 强制国标预留能力。不伪装真实设备联动能力——
缺数据如实计为 L0 并给 gap 说明。
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.smart_home import SmartDevice, SmartHomeScheme
from app.models.scene_automation import SceneAutomation

# ── 五级智能等级（对齐 GB 智能家电国标，L3 起真智能） ──
# L1 基础单品智能：单设备远程控制
# L2 场景联动：场景/定时/两两联动
# L3 全屋智能：多房间 + 跨设备自动化 + 语音（真智能起点）
# L4 主动智能：传感器触发主动服务 + 习惯学习
# L5 自主智能：跨生态自主编排 + AI 决策
LEVELS: list[dict] = [
    {
        "level": "L1",
        "name": "基础单品智能",
        "requirement": "≥1 台设备可远程控制（App/语音）",
        "is_true_smart": False,
    },
    {
        "level": "L2",
        "name": "场景联动",
        "requirement": "≥1 个场景联动（定时/触发），≥2 台设备",
        "is_true_smart": False,
    },
    {
        "level": "L3",
        "name": "全屋智能",
        "requirement": "≥2 类房间 + ≥2 个场景 + 语音控制（真智能起点）",
        "is_true_smart": True,
    },
    {
        "level": "L4",
        "name": "主动智能",
        "requirement": "≥1 个传感器主动触发场景 + 习惯学习",
        "is_true_smart": True,
    },
    {
        "level": "L5",
        "name": "自主智能",
        "requirement": "≥2 个已连接生态 + 跨生态自主编排 + AI 决策",
        "is_true_smart": True,
    },
]

# 九大场景（国标量化维度，用于评估覆盖度）
NINE_SCENARIOS = [
    "回家", "离家", "晚安", "起床", "观影", "用餐", "会客", "安防", "节能",
]


def evaluate_smart_level(snapshot: dict) -> dict:
    """按量化快照评定五级智能等级（L0 表示未达标，诚实标注）。

    Args:
        snapshot: {
            device_count: int,          # 智能设备总数
            room_types: int,            # 覆盖房间类型数
            scene_count: int,           # 场景联动总数
            triggered_scene_count: int, # 设备/传感器主动触发场景数（L4 关键）
            voice_count: int,           # 支持语音控制的设备数
            connected_ecosystems: int,  # 已连接生态数（auth_status=connected）
        }

    Returns:
        {
            "level": "L0".."L5",
            "name": str,
            "is_true_smart": bool,
            "achieved": [..],  # 已达成等级
            "gap": str,        # 未达标 gap 说明
        }
    """
    device_count = int(snapshot.get("device_count", 0))
    room_types = int(snapshot.get("room_types", 0))
    scene_count = int(snapshot.get("scene_count", 0))
    triggered = int(snapshot.get("triggered_scene_count", 0))
    voice = int(snapshot.get("voice_count", 0))
    ecosystems = int(snapshot.get("connected_ecosystems", 0))

    achieved: list[str] = []
    if device_count >= 1:
        achieved.append("L1")
    if scene_count >= 1 and device_count >= 2:
        achieved.append("L2")
    if room_types >= 2 and scene_count >= 2 and voice >= 1:
        achieved.append("L3")
    if triggered >= 1 and scene_count >= 2:
        achieved.append("L4")
    if ecosystems >= 2 and triggered >= 1 and scene_count >= 3:
        achieved.append("L5")

    level = achieved[-1] if achieved else "L0"
    level_info = next((lv for lv in LEVELS if lv["level"] == level), {
        "level": "L0", "name": "未达标", "requirement": "尚无智能设备/场景",
        "is_true_smart": False,
    })

    gap = _build_gap(level, room_types, scene_count, triggered, voice, ecosystems)
    return {
        "level": level,
        "name": level_info["name"],
        "is_true_smart": level_info["is_true_smart"],
        "achieved": achieved,
        "gap": gap,
    }


def _build_gap(
    level: str,
    room_types: int,
    scene_count: int,
    triggered: int,
    voice: int,
    ecosystems: int,
) -> str:
    """给出达到下一等级还缺什么（诚实 gap 说明）。"""
    if level == "L0":
        return "当前无智能设备，需先接入 ≥1 台可远程控制设备"
    if level == "L1":
        return "需新增 ≥1 个场景联动（≥2 台设备）以达 L2"
    if level == "L2":
        return "需补: " + "、".join(_missing_l2(room_types, scene_count, voice)) + " 以达 L3（真智能）"
    if level == "L3":
        return "需补: " + "、".join(_missing_l3(triggered, scene_count)) + " 以达 L4 主动智能"
    if level == "L4":
        return "需补: " + "、".join(_missing_l4(ecosystems, scene_count)) + " 以达 L5 自主智能"
    return "已达最高等级 L5"


def _missing_l2(room_types: int, scene_count: int, voice: int) -> list[str]:
    """L2→L3 缺口清单。"""
    missing = []
    if room_types < 2:
        missing.append(f"覆盖房间类型（现 {room_types}/2）")
    if scene_count < 2:
        missing.append(f"场景数量（现 {scene_count}/2）")
    if voice < 1:
        missing.append("语音控制设备")
    if not missing:
        missing.append("满足 L3 组合条件")
    return missing


def _missing_l3(triggered: int, scene_count: int) -> list[str]:
    """L3→L4 缺口清单。"""
    missing = []
    if triggered < 1:
        missing.append("传感器主动触发场景")
    if scene_count < 2:
        missing.append(f"场景数量（现 {scene_count}/2）")
    if not missing:
        missing.append("满足 L4 组合条件")
    return missing


def _missing_l4(ecosystems: int, scene_count: int) -> list[str]:
    """L4→L5 缺口清单。"""
    missing = []
    if ecosystems < 2:
        missing.append(f"已连接生态 ≥2（现 {ecosystems}）")
    if scene_count < 3:
        missing.append(f"场景数量（现 {scene_count}/3）")
    if not missing:
        missing.append("满足 L5 组合条件")
    return missing


async def build_snapshot(db: AsyncSession, project_id: str) -> dict:
    """聚合项目智能能力快照（诚实：按实际落库数据统计）。

    数据源：
    - SmartHomeScheme.room_type / SmartDevice（设备与房间覆盖）
    - SceneAutomation（场景数量与触发类型）
    - EcosystemIntegration（已连接生态数，auth_status=connected）
    """
    # 设备总数
    device_count = await _scalar(db, select(func.count(SmartDevice.id)).join(
        SmartHomeScheme, SmartDevice.scheme_id == SmartHomeScheme.id
    ).where(SmartHomeScheme.project_id == project_id))

    # 覆盖房间类型数（去重）
    room_types = await _scalar(db, select(func.count(func.distinct(
        SmartHomeScheme.room_type
    ))).where(SmartHomeScheme.project_id == project_id, SmartHomeScheme.deleted_at.is_(None)))

    # 场景总数（启用中的）
    scene_count = await _scalar(db, select(func.count(SceneAutomation.id)).where(
        SceneAutomation.project_id == project_id, SceneAutomation.enabled.is_(True)
    ))

    # 设备/传感器主动触发场景数（scene_type=triggered 且触发条件为设备）
    triggered_scene_count = await _scalar(db, select(func.count(SceneAutomation.id)).where(
        SceneAutomation.project_id == project_id,
        SceneAutomation.enabled.is_(True),
        SceneAutomation.scene_type == "triggered",
    ))

    # 语音控制设备数
    voice_count = await _scalar(db, select(func.count(SmartDevice.id)).join(
        SmartHomeScheme, SmartDevice.scheme_id == SmartHomeScheme.id
    ).where(
        SmartHomeScheme.project_id == project_id,
        SmartDevice.control_mode == "voice",
    ))

    # 已连接生态数
    from app.models.scene_automation import EcosystemIntegration
    connected_ecosystems = await _scalar(db, select(func.count(EcosystemIntegration.id)).where(
        EcosystemIntegration.project_id == project_id,
        EcosystemIntegration.auth_status == "connected",
    ))

    return {
        "device_count": device_count,
        "room_types": room_types,
        "scene_count": scene_count,
        "triggered_scene_count": triggered_scene_count,
        "voice_count": voice_count,
        "connected_ecosystems": connected_ecosystems,
    }


async def _scalar(db: AsyncSession, stmt) -> int:
    result = await db.execute(stmt)
    val = result.scalar()
    return int(val or 0)


def list_levels() -> list[dict]:
    """返回五级智能等级定义（对齐国标）。"""
    return [
        {
            "level": lv["level"],
            "name": lv["name"],
            "requirement": lv["requirement"],
            "is_true_smart": lv["is_true_smart"],
        }
        for lv in LEVELS
    ]

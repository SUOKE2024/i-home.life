"""F42 局部焕新服务层 — 模板生成 + CRUD

市场行情参考（2026 存量焕新）：
- kitchen_refresh 厨卫焕新 舒适档 5-7 天、1.5-4 万
- wall_refresh 墙面刷新 舒适档 3-5 天、0.5-1.5 万
- full_renovation 全屋 舒适档 60-90 天、12-20 万
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partial_renovation import PartialRenovationPlan

# 预算档位
BUDGET_LEVELS: tuple[str, ...] = ("economic", "comfort", "quality")

# scope_type → 焕新模板
SCOPE_TEMPLATES: dict[str, dict] = {
    "kitchen_refresh": {
        "name": "厨房焕新",
        "duration_days": 7,
        "budget_range": {
            "economic": (1.0, 2.5),
            "comfort": (1.5, 4.0),
            "quality": (3.0, 6.0),
        },
        "tasks": [
            {"phase": "拆旧", "name": "旧橱柜/台面拆除清运", "duration_days": 1,
             "detail": "保护性拆除，燃气/水电点位确认", "needs_owner_confirm": True},
            {"phase": "水电", "name": "水电点位改造", "duration_days": 1,
             "detail": "按新橱柜尺寸调整给排水与插座", "needs_owner_confirm": True},
            {"phase": "施工", "name": "墙地面找平与防水", "duration_days": 2,
             "detail": "湿区防水重做，闭水试验 24h", "needs_owner_confirm": False},
            {"phase": "安装", "name": "橱柜/台面/烟机安装", "duration_days": 2,
             "detail": "柜体安装、台面开孔、燃气灶具调试", "needs_owner_confirm": False},
            {"phase": "收尾", "name": "保洁与验收", "duration_days": 1,
             "detail": "成品保护拆除、深度保洁、业主验收", "needs_owner_confirm": True},
        ],
        "interference": {
            "noise_windows": "工作日 9:00-12:00 / 14:00-18:00（拆旧期避开休息时段）",
            "dust_control": "拆除区域薄膜封闭 + 湿法作业降尘",
            "living_zone": "厨房区域独立施工，不影响其他空间正常使用",
            "material_inventory": "材料堆放于厨房指定区域，每日清场",
            "relocation": "无需搬离，电器与餐具集中收纳并覆盖保护",
        },
    },
    "bathroom_refresh": {
        "name": "卫浴焕新",
        "duration_days": 10,
        "budget_range": {
            "economic": (1.5, 3.0),
            "comfort": (2.0, 5.0),
            "quality": (4.0, 8.0),
        },
        "tasks": [
            {"phase": "拆旧", "name": "旧洁具/瓷砖拆除清运", "duration_days": 2,
             "detail": "保护性拆除，下水口临时封堵防堵", "needs_owner_confirm": True},
            {"phase": "水电", "name": "给排水与电路改造", "duration_days": 1,
             "detail": "马桶移位/花洒点位按新布局调整", "needs_owner_confirm": True},
            {"phase": "防水", "name": "墙地面防水施工", "duration_days": 2,
             "detail": "淋浴区防水上翻 1800mm，闭水试验 24h", "needs_owner_confirm": False},
            {"phase": "铺贴", "name": "墙地砖铺贴", "duration_days": 3,
             "detail": "瓷砖铺贴 + 美缝", "needs_owner_confirm": False},
            {"phase": "安装", "name": "洁具/五金安装", "duration_days": 1,
             "detail": "马桶/淋浴/浴室柜安装调试", "needs_owner_confirm": False},
            {"phase": "收尾", "name": "保洁与验收", "duration_days": 1,
             "detail": "深度保洁、打胶收口、业主验收", "needs_owner_confirm": True},
        ],
        "interference": {
            "noise_windows": "工作日 9:00-12:00 / 14:00-18:00",
            "dust_control": "卫生间门洞封闭 + 排风降尘",
            "living_zone": "卫生间封闭施工，其他空间正常使用",
            "material_inventory": "材料存放于卫生间内，门口铺设保护垫",
            "relocation": "提供临时如厕方案（移动马桶）建议",
        },
    },
    "wall_refresh": {
        "name": "墙面刷新",
        "duration_days": 5,
        "budget_range": {
            "economic": (0.3, 1.0),
            "comfort": (0.5, 1.5),
            "quality": (1.0, 2.5),
        },
        "tasks": [
            {"phase": "准备", "name": "家具搬移与成品保护", "duration_days": 1,
             "detail": "家具集中收纳覆盖，地面铺设保护膜", "needs_owner_confirm": True},
            {"phase": "基层", "name": "旧墙皮铲除与修补", "duration_days": 1,
             "detail": "空鼓/开裂处铲除修补，阴阳角找直", "needs_owner_confirm": False},
            {"phase": "涂刷", "name": "底漆与面漆涂刷", "duration_days": 2,
             "detail": "一底两面，每遍间隔 ≥ 4h", "needs_owner_confirm": False},
            {"phase": "收尾", "name": "家具复位与验收", "duration_days": 1,
             "detail": "撕除保护、家具复位、业主验收", "needs_owner_confirm": True},
        ],
        "interference": {
            "noise_windows": "工作日 9:00-18:00（涂刷期几乎无噪音）",
            "dust_control": "打磨阶段湿法作业 + 门窗封闭防尘",
            "living_zone": "按房间分区施工，可逐间完成逐间恢复",
            "material_inventory": "涂料/工具存放于施工房间内",
            "relocation": "无需搬离，家具原位覆盖保护",
        },
    },
    "single_room": {
        "name": "单空间改造",
        "duration_days": 15,
        "budget_range": {
            "economic": (2.0, 4.0),
            "comfort": (3.0, 7.0),
            "quality": (6.0, 12.0),
        },
        "tasks": [
            {"phase": "设计", "name": "空间方案确认", "duration_days": 2,
             "detail": "布局/风格/主材定版", "needs_owner_confirm": True},
            {"phase": "拆旧", "name": "原空间拆除清运", "duration_days": 2,
             "detail": "隔墙/吊顶/地面拆除，复核结构安全", "needs_owner_confirm": True},
            {"phase": "水电", "name": "水电改造", "duration_days": 2,
             "detail": "按新布局布置强弱电与给排水", "needs_owner_confirm": True},
            {"phase": "施工", "name": "泥木施工", "duration_days": 5,
             "detail": "砌筑/吊顶/墙地面找平与铺贴", "needs_owner_confirm": False},
            {"phase": "涂装", "name": "油漆涂装", "duration_days": 2,
             "detail": "墙面顶面涂刷，一底两面", "needs_owner_confirm": False},
            {"phase": "收尾", "name": "保洁与验收", "duration_days": 2,
             "detail": "深度保洁、家具进场、业主验收", "needs_owner_confirm": True},
        ],
        "interference": {
            "noise_windows": "工作日 9:00-12:00 / 14:00-18:00",
            "dust_control": "施工区与生活区硬隔离，双层防尘膜",
            "living_zone": "仅施工单空间，生活区保持正常",
            "material_inventory": "材料按批次进场，当日清场",
            "relocation": "施工房间内物品集中收纳至其他空间",
        },
    },
    "full_renovation": {
        "name": "全屋焕新",
        "duration_days": 90,
        "budget_range": {
            "economic": (8.0, 15.0),
            "comfort": (12.0, 20.0),
            "quality": (18.0, 35.0),
        },
        "tasks": [
            {"phase": "设计", "name": "全屋方案设计与定版", "duration_days": 10,
             "detail": "整体布局/风格/主材/软装联动定版", "needs_owner_confirm": True},
            {"phase": "拆旧", "name": "全屋拆除清运", "duration_days": 7,
             "detail": "分区分期拆除，保留结构安全", "needs_owner_confirm": True},
            {"phase": "水电", "name": "全屋水电改造", "duration_days": 15,
             "detail": "强弱电/给排水整体改造", "needs_owner_confirm": True},
            {"phase": "泥木", "name": "泥木工程", "duration_days": 25,
             "detail": "砌筑/吊顶/找平/铺贴", "needs_owner_confirm": False},
            {"phase": "涂装", "name": "油漆工程", "duration_days": 15,
             "detail": "墙面顶面涂刷，一底两面", "needs_owner_confirm": False},
            {"phase": "安装", "name": "主材与定制安装", "duration_days": 12,
             "detail": "门/柜/洁具/灯具/开关面板安装", "needs_owner_confirm": False},
            {"phase": "收尾", "name": "开荒保洁与验收", "duration_days": 6,
             "detail": "分项验收 + 全屋开荒保洁 + 交付", "needs_owner_confirm": True},
        ],
        "interference": {
            "noise_windows": "工作日 8:30-12:00 / 14:00-19:00（分区域错峰）",
            "dust_control": "分区分期封闭施工，全程新风降尘",
            "living_zone": "建议施工期间迁出，保留部分区域存放家具",
            "material_inventory": "设置独立材料仓库，按施工计划分批进场",
            "relocation": "提前安排临时住所与家具仓储",
        },
    },
}


def list_templates() -> list[dict]:
    """返回可用 scope_type 模板摘要（不含任务明细等私有结构）"""
    return [
        {
            "scope_type": scope_type,
            "name": template["name"],
            "duration_days": template["duration_days"],
            "budget_range": template["budget_range"],
            "task_count": len(template["tasks"]),
        }
        for scope_type, template in SCOPE_TEMPLATES.items()
    ]


async def generate_plan_from_template(
    db: AsyncSession,
    project_id: str,
    name: str,
    scope_type: str,
    budget_level: str = "comfort",
) -> PartialRenovationPlan:
    """按模板生成并持久化局部焕新计划

    Args:
        db: 数据库会话
        project_id: 项目 ID
        name: 计划名称
        scope_type: kitchen_refresh / bathroom_refresh / wall_refresh / single_room / full_renovation
        budget_level: economic / comfort / quality

    Raises:
        ValueError: scope_type 或 budget_level 非法
    """
    template = SCOPE_TEMPLATES.get(scope_type)
    if template is None:
        raise ValueError(
            f"未知 scope_type: {scope_type}，可选: {', '.join(SCOPE_TEMPLATES.keys())}"
        )
    if budget_level not in BUDGET_LEVELS:
        raise ValueError(f"未知 budget_level: {budget_level}，可选: {', '.join(BUDGET_LEVELS)}")

    budget_lower, budget_upper = template["budget_range"][budget_level]

    plan = PartialRenovationPlan(
        project_id=project_id,
        name=name,
        scope_type=scope_type,
        budget_level=budget_level,
        duration_days=template["duration_days"],
        budget_lower=budget_lower,
        budget_upper=budget_upper,
        tasks=template["tasks"],
        interference_plan=template["interference"],
        status="draft",
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def get_plan(db: AsyncSession, plan_id: str) -> PartialRenovationPlan | None:
    result = await db.execute(
        select(PartialRenovationPlan).where(PartialRenovationPlan.id == plan_id)
    )
    return result.scalar_one_or_none()


async def list_plans(db: AsyncSession, project_id: str) -> list[PartialRenovationPlan]:
    result = await db.execute(
        select(PartialRenovationPlan)
        .where(PartialRenovationPlan.project_id == project_id)
        .order_by(PartialRenovationPlan.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_plan(db: AsyncSession, plan_id: str) -> bool:
    plan = await get_plan(db, plan_id)
    if not plan:
        return False
    await db.delete(plan)
    await db.commit()
    return True

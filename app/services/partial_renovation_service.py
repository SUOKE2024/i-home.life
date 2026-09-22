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


# ── F49 局改快装产品化：标准化套餐（一口价 + 干法施工 + 0 搬家） ──
#
# 局改独立赛道 30%+ 增速（京东/索菲亚/金牌全线下场）。产品化核心：
# - 一口价 fixed_price：标准化透明报价，无隐形增项
# - 干法施工 dry_construction：免湿作业/免停水，48h 内可交付
# - 0 搬家 zero_relocation：业主无需搬离，原位保护施工
QUICK_INSTALL_PACKAGES: dict[str, dict] = {
    "PKG-48H-KITCHEN": {
        "name": "48h 厨房快装",
        "scope_type": "kitchen_refresh",
        "duration_hours": 48,
        "duration_days": 2,
        "fixed_price": 19800.0,
        "dry_construction": True,
        "zero_relocation": True,
        "inclusions": [
            "旧橱柜/台面保护性拆除清运",
            "干法橱柜定制（环保板材，免湿作业）",
            "台面石英石/岩板安装",
            "烟机/灶具/水槽/龙头安装调试",
            "水电点位原位或微调",
            "成品保护 + 唯一污染区隔离",
        ],
        "excludes": ["旧电器更换", "燃气改造申报", "非厨房区域施工"],
        "warranty": "整包 2 年质保，防水 5 年",
    },
    "PKG-48H-BATHROOM": {
        "name": "48h 卫浴快装",
        "scope_type": "bathroom_refresh",
        "duration_hours": 48,
        "duration_days": 2,
        "fixed_price": 21800.0,
        "dry_construction": True,
        "zero_relocation": True,
        "inclusions": [
            "旧洁具/瓷砖保护性拆除清运",
            "干法墙板 + 快装防水（免剔凿）",
            "马桶/淋浴/浴室柜/五金安装调试",
            "下水口临时封堵与最终疏通",
            "成品保护 + 卫生间封闭施工",
        ],
        "excludes": ["结构改造", "排水主管移位", "全屋施工"],
        "warranty": "整包 2 年质保，防水 5 年",
    },
    "PKG-7D-WALL": {
        "name": "7 天墙面焕新",
        "scope_type": "wall_refresh",
        "duration_hours": 168,
        "duration_days": 7,
        "fixed_price": 6800.0,
        "dry_construction": True,
        "zero_relocation": True,
        "inclusions": [
            "家具集中收纳与地面保护",
            "旧墙皮铲除/空鼓修补（干法基层）",
            "一底两面环保涂料涂刷",
            "阴阳角找直 + 灯带/踢脚线收口",
            "逐间施工逐间恢复，7 天交付",
        ],
        "excludes": ["墙纸/软包类", "外墙", "全屋拆改"],
        "warranty": "涂料 3 年质保，返修免费",
    },
    # ── 适老改造套餐（政策：商务部等八部门《促进智能家居消费行动方案》第四条
    #    「发展适老化智能家居」+ 推广家庭服务机器人/健康监测/智能照护，
    #    推行产品尺寸/操作便利/方言识别/安全性能适老化设计）──
    #
    # 与 F41 适老改造方案（GB 50763-2012 无障碍尺寸 + HC-006 逃生通道）配套：
    # 方案出条目清单，套餐出可售一口价，两者经 space_assets.retrofit_package_code 关联。
    # 定价为平台标准一口价（与 F49 同口径），区域差异化定价由业务侧维护。
    "PKG-ELDERLY-BATH": {
        "name": "适老卫浴改造（48h）",
        "scope_type": "bathroom_refresh",
        "duration_hours": 48,
        "duration_days": 2,
        "fixed_price": 16800.0,
        "dry_construction": True,
        "zero_relocation": True,
        "inclusions": [
            "旧洁具/瓷砖保护性拆除清运",
            "干法墙板 + 快装防水（免剔凿）",
            "坐便器旁/淋浴区/浴缸出口不锈钢扶手（φ35mm，高 700mm）",
            "湿区防滑处理（摩擦系数 ≥ 0.5）+ 无门槛化（高差 ≤ 15mm）",
            "门洞净宽校核 ≥ 800mm（轮椅通行）",
            "夜间感应照明（低照度、防眩光）",
            "成品保护 + 卫生间封闭施工",
        ],
        "excludes": ["结构改造", "排水主管移位", "全屋施工", "护理床等重度失能辅具"],
        "warranty": "整包 2 年质保，防水 5 年，扶手五金 5 年",
        "elderly_theme": True,
        "target_occupant": ["elderly_living", "semi_selfcare", "nursing", "family"],
        "accessibility_standard": "GB 50763-2012",
        "subsidy_category": "fall_prevention",
        "elderly_design": {
            "尺寸适配": "门洞净宽 ≥ 800mm、扶手高度 700mm、地面高差 ≤ 15mm（GB 50763-2012）",
            "操作便利": "保留机械式冲水/阀门作为断电可用冗余，避免纯感应式操作",
            "安全性能": "防滑地面 + 防烫伤限温 + 夜间感应照明，降低湿区跌倒与烫伤风险",
        },
    },
    "PKG-ELDERLY-ROOM": {
        "name": "适老卧室改造（72h）",
        "scope_type": "single_room",
        "duration_hours": 72,
        "duration_days": 3,
        "fixed_price": 12800.0,
        "dry_construction": True,
        "zero_relocation": True,
        "inclusions": [
            "家具移位与地面保护",
            "床头扶手 + 走廊双侧连续扶手（φ35mm，高 700mm）",
            "无门槛化处理（高差 ≤ 15mm，消除绊倒点）",
            "紧急呼叫按钮（床头 + 卫生间联动）",
            "夜间感应地脚照明（低照度、不刺眼）",
            "护理床/移位机通行与回转空间校核",
            "成品保护 + 逐间施工逐间恢复",
        ],
        "excludes": ["结构改造", "护理床/移位机设备本体", "全屋施工"],
        "warranty": "整包 2 年质保，扶手五金 5 年",
        "elderly_theme": True,
        "target_occupant": ["elderly_living", "semi_selfcare", "nursing", "family"],
        "accessibility_standard": "GB 50763-2012",
        "subsidy_category": "health_emergency",
        "elderly_design": {
            "尺寸适配": "扶手高度 700mm、通道净宽满足助行器/轮椅回转、无门槛化",
            "操作便利": "紧急呼叫采用大按键实体按钮，支持拉绳/按键双方式，无需学习成本",
            "安全性能": "起夜路径全程感应照明 + 一键紧急呼叫，缩短跌倒后响应时间",
        },
    },
    "PKG-ELDERLY-FULL": {
        "name": "全屋适老智能化改造（7 天）",
        "scope_type": "full_renovation",
        "duration_hours": 168,
        "duration_days": 7,
        "fixed_price": 39800.0,
        "dry_construction": True,
        "zero_relocation": True,
        "inclusions": [
            "全屋无障碍动线改造（门洞/走廊/高差，GB 50763-2012）",
            "入户门与逃生通道畅通性整改（HC-006：净宽 + 禁止封闭）",
            "卫生间/走廊/卧室扶手系统 + 地面防滑处理",
            "跌倒报警器 + 紧急呼叫按钮（全屋多点）",
            "燃气泄漏报警 + 夜间感应照明",
            "适老智能家居配置（智能开关/语音控制/环境联动）",
            "无障碍动线复测报告（含逃生通道专项检查）",
        ],
        "excludes": ["结构改造", "电梯加装", "护理机器人等设备本体"],
        "warranty": "整包 2 年质保，防水 5 年，扶手五金 5 年",
        "elderly_theme": True,
        "target_occupant": ["elderly_living", "semi_selfcare", "nursing", "family"],
        "accessibility_standard": "GB 50763-2012",
        "subsidy_category": "fall_prevention",
        "elderly_design": {
            "尺寸适配": "全屋门洞 ≥ 800mm、走廊 ≥ 900mm、高差 ≤ 15mm（GB 50763-2012）",
            "操作便利": "实体大按键 + 语音控制双通道，保留断电可用的机械操作路径",
            "方言识别": "语音交互支持方言识别（需所选智能家居网关/音箱能力支持，选型时逐项确认）",
            "安全性能": "跌倒报警 + 一键呼叫 + 燃气泄漏报警 + 夜间照明，覆盖三大高频风险场景",
        },
    },
}

# 公众视图基础字段（套餐目录/详情统一输出）
_PUBLIC_PACKAGE_FIELDS: tuple[str, ...] = (
    "name", "scope_type", "duration_hours", "duration_days", "fixed_price",
    "dry_construction", "zero_relocation", "inclusions", "excludes", "warranty",
)

# 适老套餐附加字段（非适老套餐不输出，避免误标）
_ELDERLY_PACKAGE_FIELDS: tuple[str, ...] = (
    "elderly_theme", "target_occupant", "accessibility_standard",
    "subsidy_category", "elderly_design",
)


def _public_package_view(package_code: str) -> dict:
    """构造套餐对外的公开视图（基础字段 + 存在时附加适老元数据）"""
    pkg = QUICK_INSTALL_PACKAGES[package_code]
    view = {"package_code": package_code}
    view.update({field: pkg[field] for field in _PUBLIC_PACKAGE_FIELDS})
    view.update({field: pkg[field] for field in _ELDERLY_PACKAGE_FIELDS if field in pkg})
    return view


def list_quick_install_packages() -> list[dict]:
    """返回标准快装套餐目录（不含任务/干扰方案等私有结构）"""
    return [_public_package_view(code) for code in QUICK_INSTALL_PACKAGES]


def get_quick_install_package(package_code: str) -> dict | None:
    """按编码取单个快装套餐"""
    if package_code not in QUICK_INSTALL_PACKAGES:
        return None
    return _public_package_view(package_code)


def get_package_subsidy_line(package_code: str) -> dict:
    """把套餐折算为补贴预检清单行（一口价 × 1，品类取套餐声明的补贴场景）

    Raises:
        ValueError: package_code 非法
    """
    pkg = QUICK_INSTALL_PACKAGES.get(package_code)
    if pkg is None:
        raise ValueError(
            f"未知快装套餐: {package_code}，可选: {', '.join(QUICK_INSTALL_PACKAGES.keys())}"
        )
    return {
        "name": pkg["name"],
        "category": pkg.get("subsidy_category", "other"),
        "unit_price": pkg["fixed_price"],
        "quantity": 1,
    }


async def instantiate_quick_install_package(
    db: AsyncSession,
    project_id: str,
    package_code: str,
    name: str | None = None,
) -> PartialRenovationPlan:
    """把标准快装套餐实例化为具体项目计划（一口价/干法/0 搬家落库）

    Args:
        db: 数据库会话
        project_id: 项目 ID
        package_code: PKG-48H-KITCHEN / PKG-48H-BATHROOM / PKG-7D-WALL
        name: 计划名称（缺省用套餐名）

    Raises:
        ValueError: package_code 非法
    """
    pkg = QUICK_INSTALL_PACKAGES.get(package_code)
    if pkg is None:
        raise ValueError(
            f"未知快装套餐: {package_code}，可选: {', '.join(QUICK_INSTALL_PACKAGES.keys())}"
        )

    plan = PartialRenovationPlan(
        project_id=project_id,
        name=name or pkg["name"],
        scope_type=pkg["scope_type"],
        budget_level="comfort",
        duration_days=pkg["duration_days"],
        budget_lower=pkg["fixed_price"],
        budget_upper=pkg["fixed_price"],
        package_code=package_code,
        fixed_price=pkg["fixed_price"],
        dry_construction=pkg["dry_construction"],
        zero_relocation=pkg["zero_relocation"],
        tasks=[
            {"phase": "快装", "name": pkg["name"], "duration_days": pkg["duration_days"],
             "detail": "标准化套餐干法施工，免湿作业/免停水，业主无需搬离",
             "needs_owner_confirm": False},
        ],
        interference_plan={
            "noise_windows": "工作日 9:00-18:00（干法施工噪音低）",
            "dust_control": "施工区封闭 + 湿法除尘，0 搬家属地保护",
            "living_zone": "仅施工单一空间，其余空间正常使用",
            "material_inventory": "材料按套餐标准清单当日进场",
            "relocation": "0 搬家：业主原位正常居住，家具原位覆盖保护",
        },
        status="draft",
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan

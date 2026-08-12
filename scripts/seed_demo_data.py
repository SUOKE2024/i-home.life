"""演示项目种子数据 — 为业主演示账号（张先生 13800138000）注入 3 个模拟项目

目的：让「一键演示登录」后的首页/各页面有真实可看的数据（不是假数据，
而是写入真实业务表、由现有 API 原样读出的种子数据）。数据均来自业务表，
符合项目「诚实降级 / 禁止硬编码假数据」约定——演示数据本身就是种子数据。

3 个模拟项目覆盖不同生命周期阶段（全景展示 + 全链路模块验证）：
  ① 云栖雅苑 · 智能整装（126㎡·昆明西山）施工中 —— 全链路完整
     （预算/施工7任务/里程碑5/预警3/质检/采购2/结算/智能家居3方案）
  ② 滇池湖畔 · 现代简约（88㎡·昆明西山）采购阶段 —— 预算/施工4任务/
     里程碑/预警/质检1/采购2/智能家居2方案（无结算，阶段合理）
  ③ 翠湖名邸 · 原木奶油风（110㎡·昆明五华）设计阶段 —— 户型/预算草案/
     智能家居规划1方案（无施工/采购/结算，阶段合理）

覆盖链路（对齐 webapp 各页面数据源）：
  项目 → 户型(逐房间状态) → 预算(明细) → 施工任务(阶段) →
  里程碑 → 进度预警 → 质检(问题+评估) → 采购(订单+明细) →
  结算(明细) → 智能家居(方案+设备)

用法：
  python scripts/seed_demo_data.py               # 注入 3 个演示项目（幂等：已存在则跳过）
  python scripts/seed_demo_data.py --clear       # 清理本脚本创建的演示项目
  python scripts/seed_demo_data.py --clear-all-projects   # 清空全库所有用户的项目（破坏性）

日志说明：本脚本为一次性 CLI 工具，日志仅经 basicConfig 输出到 stderr/stdout
（无 FileHandler/RotatingFileHandler，不写日志文件）；运行结束进程即退出，
部署脚本（deploy-remote.sh seed）以管道 `2>&1 | tail -2` 截断输出，不会造成
磁盘空间累积。
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import async_session, init_db
from app.models.budget import Budget, BudgetLine
from app.models.construction import ConstructionTask
from app.models.floorplan import FloorPlan
from app.models.procurement import OrderLine, ProcurementOrder, Quotation, Supplier
from app.models.progress_alert import MilestoneTracker, ProgressAlert
from app.models.project import Floor, Project, Room
from app.models.quality import QualityAssessment, QualityIssue, RectificationOrder
from app.models.settlement import Settlement, SettlementLine
from app.models.smart_home import SmartDevice, SmartHomeScheme
from app.models.user import User

logger = logging.getLogger("seed_demo_data")

DEMO_PHONE = "13800138000"       # 业主演示账号（scripts/seed.py 体验账户）
DEMO_PASSWORD_HINT = "123456"
DEMO_PROJECT_NAME = "云栖雅苑 · 智能整装"   # 主演示项目（全链路最完整）

_UTC = timezone.utc
_BJ = timezone(timedelta(hours=8), name="Asia/Shanghai")

# 演示收货地址（昆明）
_DEMO_ADDR1 = "云南省昆明市西山区广福路云栖雅苑 3 栋 1201"
_DEMO_ADDR2 = "云南省昆明市西山区滇池路湖畔小区 8 栋 502"
_DEMO_ADDR3 = "云南省昆明市五华区翠湖南路名邸 2 栋 1101"

# ═══════════════════════════════════════════
# 3 个模拟项目配置
# ═══════════════════════════════════════════
# budget_lines: (类别/名称/数量/单价/实际花费)
# construction_tasks: (名称/阶段/状态/前置任务名)
# milestones: (code/名称/计划百分比/状态/支付比例/是否完成)
# alerts: (类型/严重度/消息/状态/建议)
# quality_issues: (阶段/类别/描述/严重度/状态/位置/标准)
# procurement_orders: (供应商名/状态/配送状态/预计送达偏移天/备注/明细[(物料名,数量,单价)])
# smart_home_schemes: (房间/类型/协议/品牌/状态/备注/设备[(类型,名称,品牌,价格)])

DEMO_PROJECTS = [
    # ── ① 云栖雅苑 · 智能整装（施工中，全链路完整）──
    {
        "name": DEMO_PROJECT_NAME,
        "description": "完整家装全链路演示项目（施工中），覆盖预算/施工/质检/采购/结算/智能家居全模块",
        "address": _DEMO_ADDR1,
        "total_area": 126.0,
        "status": "in_progress",
        "phase": "construction",
        "project_type": "full_renovation",
        "house_type": "平层",
        "latitude": 24.9057,
        "longitude": 102.8345,
        "created_days_ago": 60,
        "plan_name": "126㎡ 现代简约 · 智能整装",
        "rooms": [
            ("客厅", "living_room", 35.0), ("主卧", "bedroom", 20.0),
            ("次卧", "bedroom", 15.0), ("书房", "study", 10.0),
            ("厨房", "kitchen", 10.0), ("卫生间", "bathroom", 6.0),
        ],
        "room_status": {
            "客厅": "in_progress", "主卧": "completed", "次卧": "in_progress",
            "书房": "not_started", "厨房": "completed", "卫生间": "in_progress",
        },
        "budget_status": "approved",
        "budget_created_days_ago": 50,
        # budget_lines: (类别/名称/数量/单位/单价/实际花费)——单位显式声明，符合真实装修计价
        "budget_lines": [
            ("地面", "750×1500 大板砖", 82.0, "㎡", 198.0, 16236.0),
            # 净味乳胶漆 18L/桶 覆盖约 90㎡，126㎡ 三居墙面约 320㎡ → 4 桶
            ("墙面", "净味乳胶漆（全屋）", 4.0, "桶", 680.0, 0.0),
            ("顶面", "石膏板吊顶", 46.0, "㎡", 95.0, 4370.0),
            ("厨卫", "石英石台面 + 台下盆", 1.0, "项", 9860.0, 9860.0),
            # 126㎡ 单卫生间 → 智能马桶 + 恒温花洒 1 套
            ("厨卫", "智能马桶 + 恒温花洒", 1.0, "套", 5660.0, 5660.0),
            ("水电", "强弱电改造（含材料）", 126.0, "㎡", 168.0, 21168.0),
            ("定制", "定制衣柜（主卧+次卧）", 24.0, "㎡", 1280.0, 0.0),
            ("软装", "LED 无主灯全屋套餐", 1.0, "套", 2680.0, 0.0),
            ("家电", "中央空调一拖四", 1.0, "套", 12800.0, 0.0),
        ],
        "construction_tasks": [
            ("开工准备与成品保护", "preparation", "completed", None),
            ("水电改造与防水", "waterproof", "completed", "开工准备与成品保护"),
            ("泥瓦铺贴", "masonry", "in_progress", "水电改造与防水"),
            ("木工吊顶与定制", "carpentry", "in_progress", "泥瓦铺贴"),
            ("油漆涂刷", "painting", "pending", "木工吊顶与定制"),
            ("主材安装", "installation", "pending", "油漆涂刷"),
            ("竣工验收", "inspection", "pending", "主材安装"),
        ],
        "milestones": [
            ("delivery", "交房开工", 30.0, "completed", 0.30, True),
            ("mep", "水电验收", 50.0, "completed", 0.20, True),
            ("masonry", "泥瓦验收", 75.0, "in_progress", 0.25, False),
            ("completion", "竣工结算", 100.0, "pending", 0.20, False),
            ("warranty", "质保期满", 100.0, "pending", 0.05, False),
        ],
        "alerts": [
            ("delay", "high", "客厅地砖进场较计划延迟 3 天，泥瓦铺贴进度略滞后",
             "active", "建议联系东鹏瓷砖旗舰店确认补货时间，必要时先安排墙面工序"),
            ("risk", "medium", "定制衣柜下单 15 天仍未排产，存在影响木工阶段收尾的风险",
             "active", "建议通过 AI 管家催单或联系索菲亚衣柜客服跟进排产"),
            ("milestone", "low", "水电验收里程碑已按计划完成", "resolved", None),
        ],
        "quality_issues": [
            ("masonry", "平整度", "客厅阳台墙砖平整度偏差 3mm，超出验收标准（≤2mm）",
             "medium", "open", "客厅阳台", "GB 50210-2018 饰面砖允许偏差 ≤2mm"),
            ("waterproof", "防水", "主卫防水层上翻高度不足（实测 250mm，标准 300mm）",
             "high", "resolved", "主卫", "GB 50327-2001 淋浴区防水上翻 ≥1800mm"),
        ],
        "quality_assessment": {
            "phase": "masonry", "total_items": 36, "passed": 33, "failed": 3,
            "score": 92.0, "verdict": "pass", "assessor": "王监理",
            "summary": "泥瓦阶段整体合格，3 项轻微问题已开出整改单",
            "issues_summary": "墙砖平整度偏差 1 项（整改中）",
        },
        "procurement_orders": [
            ("东鹏瓷砖旗舰店", "delivered", "delivered", -2,
             "客厅 + 厨卫墙地砖（第一批）", [("750×1500 大板砖", 82.0, 198.0), ("400×800 瓷片", 120.0, 88.0)]),
            ("索菲亚衣柜", "confirmed", "shipping", 5,
             "定制衣柜（主卧 + 次卧）", [("定制衣柜", 24.0, 1280.0)]),
        ],
        "settlement": {
            "milestone": "completion", "status": "in_progress",
            "lines": [
                ("预付款", "开工预付 30%", 0.30, "paid"),
                ("进度款", "水电阶段 20%", 0.20, "paid"),
                ("进度款", "泥瓦阶段 25%", 0.25, "pending"),
                ("尾款", "竣工验收 25%", 0.25, "pending"),
            ],
        },
        "smart_home_schemes": [
            ("客厅", "living_room", "matter", "huawei", "installing", "华为全屋智能 · 中控屏方案",
             [("light", "客厅磁吸轨道灯", "华为", 1299.0),
              ("switch", "智能场景开关面板", "华为", 299.0),
              ("sensor", "人体存在传感器", "华为", 199.0)]),
            ("主卧", "bedroom", "zigbee", "xiaomi", "planned", "小米智能灯 + 窗帘方案",
             [("light", "卧室吸顶灯（调光调色）", "小米", 499.0),
              ("curtain", "电动窗帘电机", "杜亚", 599.0)]),
            ("厨房", "kitchen", "wifi", "xiaomi", "planned", "燃气/漏水安防方案",
             [("sensor", "烟雾报警器", "小米", 129.0),
              ("sensor", "燃气报警器", "小米", 199.0),
              ("socket", "智能插座（防漏电）", "小米", 59.0)]),
        ],
    },
    # ── ② 滇池湖畔 · 现代简约（采购阶段）──
    {
        "name": "滇池湖畔 · 现代简约",
        "description": "现代简约风格装修，当前处于采购阶段（预算已确认，主材陆续进场）",
        "address": _DEMO_ADDR2,
        "total_area": 88.0,
        "status": "active",
        "phase": "procurement",
        "project_type": "full_renovation",
        "house_type": "平层",
        "latitude": 24.9682,
        "longitude": 102.6723,
        "created_days_ago": 45,
        "plan_name": "88㎡ 现代简约 · 两居",
        "rooms": [
            ("客厅", "living_room", 26.0), ("主卧", "bedroom", 15.0),
            ("次卧", "bedroom", 12.0), ("书房", "study", 8.0),
            ("厨房", "kitchen", 8.0), ("卫生间", "bathroom", 5.0),
        ],
        "room_status": {
            "客厅": "in_progress", "主卧": "completed", "次卧": "completed",
            "书房": "not_started", "厨房": "completed", "卫生间": "not_started",
        },
        "budget_status": "approved",
        "budget_created_days_ago": 35,
        "budget_lines": [
            ("地面", "强化复合地板", 60.0, "㎡", 158.0, 9480.0),
            ("墙面", "净味乳胶漆", 4.0, "桶", 680.0, 2720.0),
            ("顶面", "石膏板吊顶", 35.0, "㎡", 95.0, 0.0),
            ("厨卫", "石英石台面", 6.0, "m", 680.0, 4080.0),
            ("厨卫", "恒温花洒", 1.0, "套", 1680.0, 1680.0),
            ("水电", "强弱电改造（含材料）", 88.0, "㎡", 168.0, 8000.0),
            ("定制", "定制衣柜（主卧+次卧）", 16.0, "㎡", 1280.0, 0.0),
            ("家电", "燃气热水器", 1.0, "台", 3280.0, 0.0),
        ],
        "construction_tasks": [
            ("开工准备与成品保护", "preparation", "completed", None),
            ("拆除工程", "demolition", "completed", "开工准备与成品保护"),
            ("水电改造", "water_electricity", "in_progress", "拆除工程"),
            ("防水工程", "waterproof", "pending", "水电改造"),
        ],
        "milestones": [
            ("delivery", "交房开工", 30.0, "completed", 0.30, True),
            ("mep", "水电验收", 50.0, "in_progress", 0.20, False),
            ("masonry", "泥瓦验收", 75.0, "pending", 0.25, False),
            ("completion", "竣工结算", 100.0, "pending", 0.20, False),
            ("warranty", "质保期满", 100.0, "pending", 0.05, False),
        ],
        "alerts": [
            ("delay", "low", "水电改造管线铺设较计划延迟 2 天",
             "active", "建议协调水电班组加班推进，优先保障防水工期"),
        ],
        "quality_issues": [
            ("water_electricity", "电路", "次卧墙面线盒安装不平整，面板存在歪斜",
             "low", "open", "次卧", "GB 50303-2015 电气安装工程质量验收规范"),
        ],
        "quality_assessment": None,
        "procurement_orders": [
            ("圣象地板", "delivered", "delivered", -3,
             "强化复合地板（全屋）", [("强化复合地板", 60.0, 158.0)]),
            ("立邦涂料", "confirmed", "shipping", 3,
             "净味乳胶漆（墙面）", [("净味乳胶漆", 4.0, 680.0)]),
        ],
        "settlement": None,
        "smart_home_schemes": [
            ("客厅", "living_room", "zigbee", "xiaomi", "planned", "小米全屋智能 · 基础套餐",
             [("switch", "智能开关面板", "小米", 199.0),
              ("light", "客厅吸顶灯", "小米", 399.0),
              ("sensor", "人体传感器", "小米", 99.0)]),
            ("主卧", "bedroom", "zigbee", "xiaomi", "planned", "卧室智能灯 + 窗帘",
             [("light", "卧室吸顶灯（调光调色）", "小米", 499.0),
              ("curtain", "电动窗帘电机", "杜亚", 599.0)]),
        ],
    },
    # ── ③ 翠湖名邸 · 原木奶油风（设计阶段）──
    {
        "name": "翠湖名邸 · 原木奶油风",
        "description": "原木奶油风格装修，当前处于设计阶段（户型已确认，预算为初步估算）",
        "address": _DEMO_ADDR3,
        "total_area": 110.0,
        "status": "draft",
        "phase": "design",
        "project_type": "full_renovation",
        "house_type": "平层",
        "latitude": 25.0435,
        "longitude": 102.7083,
        "created_days_ago": 15,
        "plan_name": "110㎡ 原木奶油 · 三居",
        "rooms": [
            ("客厅", "living_room", 35.0), ("主卧", "bedroom", 18.0),
            ("次卧", "bedroom", 14.0), ("书房", "study", 9.0),
            ("厨房", "kitchen", 10.0), ("卫生间", "bathroom", 6.0),
        ],
        "room_status": {
            "客厅": "not_started", "主卧": "not_started", "次卧": "not_started",
            "书房": "not_started", "厨房": "not_started", "卫生间": "not_started",
        },
        "budget_status": "draft",
        "budget_created_days_ago": 8,
        "budget_lines": [
            ("地面", "实木多层地板", 65.0, "㎡", 328.0, 0.0),
            ("墙面", "无纺布墙布", 200.0, "㎡", 168.0, 0.0),
            ("顶面", "石膏板吊顶", 40.0, "㎡", 95.0, 0.0),
            ("厨卫", "台下盆洗手盆", 2.0, "个", 580.0, 0.0),
            ("定制", "定制衣柜（全屋）", 20.0, "㎡", 1280.0, 0.0),
            ("软装", "LED 无主灯全屋套餐", 1.0, "套", 2680.0, 0.0),
        ],
        "construction_tasks": [],
        "milestones": [
            ("delivery", "交房开工", 30.0, "pending", 0.30, False),
            ("mep", "水电验收", 50.0, "pending", 0.20, False),
            ("masonry", "泥瓦验收", 75.0, "pending", 0.25, False),
            ("completion", "竣工结算", 100.0, "pending", 0.20, False),
            ("warranty", "质保期满", 100.0, "pending", 0.05, False),
        ],
        "alerts": [],
        "quality_issues": [],
        "quality_assessment": None,
        "procurement_orders": [],
        "settlement": None,
        "smart_home_schemes": [
            ("客厅", "living_room", "matter", "huawei", "planned", "华为全屋智能 · 中控屏方案（设计预埋）",
             [("light", "客厅磁吸轨道灯", "华为", 1299.0),
              ("switch", "智能场景开关面板", "华为", 299.0),
              ("sensor", "人体存在传感器", "华为", 199.0)]),
        ],
    },
]

# 兼容引用（测试/脚本沿用）：主演示项目（云栖雅苑）配置
BUDGET_LINES = DEMO_PROJECTS[0]["budget_lines"]
CONSTRUCTION_TASKS = DEMO_PROJECTS[0]["construction_tasks"]
MILESTONES = DEMO_PROJECTS[0]["milestones"]
ALERTS = DEMO_PROJECTS[0]["alerts"]
QUALITY_ISSUES = DEMO_PROJECTS[0]["quality_issues"]
PROCUREMENT_ORDERS = DEMO_PROJECTS[0]["procurement_orders"]
SMART_HOME_SCHEMES = DEMO_PROJECTS[0]["smart_home_schemes"]


def _configure_logging() -> None:
    """CLI 运行时启用标准日志（含时间戳，便于排查注入时序）。

    幂等：已配置过 handler 则不重复添加（避免测试/重复调用时重复输出）。
    """
    if not logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    logger.setLevel(logging.INFO)


def _now() -> datetime:
    return datetime.now(_UTC)


def _days_ago(days: float) -> datetime:
    return _now() - timedelta(days=days)


# ═══════════════════════════════════════════
# 基础数据查找
# ═══════════════════════════════════════════

async def _material_id(db, material_name: str) -> str:
    from app.models.material import Material
    result = await db.execute(select(Material).where(Material.name == material_name))
    material = result.scalar_one_or_none()
    if not material:
        raise RuntimeError(f"物料不存在（请先执行 scripts/seed.py）：{material_name}")
    return str(material.id)


async def _supplier_id(db, supplier_name: str) -> str:
    result = await db.execute(select(Supplier).where(Supplier.name == supplier_name))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise RuntimeError(f"供应商不存在（请先执行 scripts/seed.py）：{supplier_name}")
    return str(supplier.id)


# ═══════════════════════════════════════════
# 分域注入（每域接受项目 spec）
# ═══════════════════════════════════════════

async def _seed_project_and_plan(db, owner: User, spec: dict) -> Project:
    """模拟项目 + 户型（楼层/房间/户型方案）。"""
    days = spec["created_days_ago"]
    project = Project(
        name=spec["name"],
        description=spec["description"],
        address=spec["address"],
        total_area=spec["total_area"],
        status=spec["status"],
        phase=spec["phase"],
        project_type=spec.get("project_type", "full_renovation"),
        house_type=spec.get("house_type"),
        latitude=spec.get("latitude"),
        longitude=spec.get("longitude"),
        contact_name=owner.name,
        contact_phone=DEMO_PHONE,
        owner_id=owner.id,
        source="manual",
        created_at=_days_ago(days),
    )
    db.add(project)
    await db.flush()
    logger.info("project_created id=%s name=%s owner_id=%s status=%s phase=%s",
                project.id, project.name, owner.id, project.status, project.phase)

    floor = Floor(project_id=project.id, name="1 层", floor_number=1,
                  area=spec["total_area"], created_at=_days_ago(days - 2))
    db.add(floor)
    await db.flush()
    for name, rtype, area in spec["rooms"]:
        db.add(Room(floor_id=floor.id, name=name, room_type=rtype, area=area,
                    width=area * 0.8, length=area / (area * 0.8) if area else 1.0, height=2.8))
    await db.flush()

    plan_data = {
        "name": spec["plan_name"],
        "total_area": spec["total_area"],
        "wall_height": 2.8,
        "rooms": [
            {"name": n, "room_type": t, "area": a, "width": a * 0.8, "length": a / (a * 0.8)}
            for n, t, a in spec["rooms"]
        ],
    }
    plan = FloorPlan(
        project_id=project.id,
        name=spec["plan_name"],
        data=json.dumps(plan_data, ensure_ascii=False),
        wall_height=2.8,
        total_area=spec["total_area"],
        room_count=len(spec["rooms"]),
        room_status=json.dumps(spec["room_status"], ensure_ascii=False),
        is_active=True,
        created_at=_days_ago(days - 5),
    )
    db.add(plan)
    await db.flush()
    logger.info("floor_plan_created id=%s floor_id=%s rooms=%d total_area=%s",
                plan.id, floor.id, plan.room_count, plan.total_area)
    return project


async def _seed_budget(db, project_id: str, spec: dict) -> tuple[float, float]:
    """预算 + 明细。返回 (预估总额, 实际花费)。

    明细格式: (类别/名称/数量/单位/单价/实际花费)，单位显式声明（㎡/桶/套/台/个/m/项），
    避免按数量自动推断单位导致「乳胶漆按 ㎡ 计价」类错误。
    """
    lines = spec["budget_lines"]
    logger.info("budget_seed_start project_id=%s lines=%d", project_id, len(lines))
    total_estimated = round(sum(q * p for _, _, q, _, p, _ in lines), 2)
    total_actual = round(sum(a for _, _, _, _, _, a in lines), 2)
    budget = Budget(
        project_id=project_id, total_estimated=total_estimated,
        total_actual=total_actual, status=spec["budget_status"],
        created_at=_days_ago(spec["budget_created_days_ago"]),
    )
    db.add(budget)
    await db.flush()
    for cat, name, qty, unit, price, actual in lines:
        amount = round(qty * price, 2)
        db.add(BudgetLine(
            budget_id=budget.id, category=cat, name=name,
            estimated_amount=amount, actual_amount=actual,
            unit=unit, quantity=qty, unit_price=price,
            note="演示数据", created_at=_days_ago(spec["budget_created_days_ago"]),
        ))
        logger.info(
            "budget_line_created project_id=%s category=%s name=%s qty=%s unit=%s "
            "unit_price=%s amount=%s actual=%s",
            project_id, cat, name, qty, unit, price, amount, actual,
        )
    await db.flush()
    logger.info("budget_seed_done project_id=%s budget_id=%s total_estimated=%s total_actual=%s",
                project_id, budget.id, total_estimated, total_actual)
    return total_estimated, total_actual


async def _seed_construction(db, project_id: str, spec: dict) -> dict[str, str]:
    """施工任务（带前置依赖）。返回 任务名 → id 映射。"""
    tasks = spec["construction_tasks"]
    if not tasks:
        return {}
    logger.info("construction_seed_start project_id=%s tasks=%d", project_id, len(tasks))
    task_ids: dict[str, str] = {}
    for name, phase, status, predecessor in tasks:
        task = ConstructionTask(
            project_id=project_id, name=name, phase=phase, status=status,
            priority={"completed": 3, "in_progress": 5, "pending": 1}.get(status, 1),
            predecessor_id=task_ids.get(predecessor) if predecessor else None,
            description=f"演示数据：{name}",
            created_at=_days_ago(45),
        )
        if status == "completed":
            task.start_date = _days_ago(45)
            task.end_date = _days_ago(30)
            task.actual_duration_days = 15
        elif status == "in_progress":
            task.start_date = _days_ago(20)
        db.add(task)
        await db.flush()
        task_ids[name] = task.id
        logger.info("construction_task_created project_id=%s task_id=%s name=%s phase=%s status=%s predecessor=%s",
                    project_id, task.id, name, phase, status, predecessor)
    await db.flush()
    return task_ids


async def _seed_milestones_and_alerts(db, project_id: str, spec: dict) -> None:
    """里程碑 + 进度预警。"""
    milestones, alerts = spec["milestones"], spec["alerts"]
    logger.info("milestone_seed_start project_id=%s milestones=%d alerts=%d",
                project_id, len(milestones), len(alerts))
    for idx, (code, name, percent, status, ratio, done) in enumerate(milestones):
        milestone = MilestoneTracker(
            project_id=project_id, milestone_code=code, name=name,
            planned_date=_days_ago(40 - idx * 15),
            actual_date=_days_ago(30 - idx * 2) if done else None,
            planned_percent=percent, actual_percent=100.0 if done else 60.0,
            status=status, payment_ratio=ratio, note="演示数据",
        )
        db.add(milestone)
        logger.info("milestone_created project_id=%s code=%s name=%s status=%s ratio=%s",
                    project_id, code, name, status, ratio)
    for alert_type, severity, message, status, suggestion in alerts:
        alert = ProgressAlert(
            project_id=project_id,
            task_id=None,   # 预警不绑定具体任务（配置保持简单，避免任务名耦合）
            phase="masonry" if alert_type in ("delay", "risk") else "mep",
            alert_type=alert_type, severity=severity, message=message,
            delay_days=3 if alert_type == "delay" else 0,
            progress_percent=75.0, suggestion=suggestion, status=status,
            resolved_at=_days_ago(2) if status == "resolved" else None,
            resolved_by="AI 管家" if status == "resolved" else None,
            created_at=_days_ago(8),
        )
        db.add(alert)
        logger.info("progress_alert_created project_id=%s alert_type=%s severity=%s status=%s",
                    project_id, alert_type, severity, status)
    await db.flush()


async def _seed_quality(db, project_id: str, spec: dict) -> None:
    """质检问题 + 质量评估。"""
    issues = spec["quality_issues"]
    if not issues:
        return
    logger.info("quality_seed_start project_id=%s issues=%d", project_id, len(issues))
    for phase, category, desc, severity, status, location, standard in issues:
        issue = QualityIssue(
            project_id=project_id,
            task_id=None,
            phase=phase, category=category, description=desc, severity=severity,
            status=status, detected_by="ai", standard=standard, location=location,
            resolution="已整改复验合格" if status == "resolved" else None,
            resolved_at=_days_ago(2) if status == "resolved" else None,
            resolved_by="郑水电" if status == "resolved" else None,
        )
        db.add(issue)
        logger.info("quality_issue_created project_id=%s phase=%s category=%s severity=%s status=%s location=%s",
                    project_id, phase, category, severity, status, location)
    qa = spec.get("quality_assessment")
    if qa:
        qa_obj = QualityAssessment(project_id=project_id, **qa)
        db.add(qa_obj)
        logger.info("quality_assessment_created project_id=%s phase=%s score=%s verdict=%s",
                    project_id, qa["phase"], qa["score"], qa["verdict"])
    await db.flush()


async def _seed_procurement(db, project_id: str, spec: dict) -> None:
    """采购订单 + 明细。"""
    orders = spec["procurement_orders"]
    if not orders:
        return
    logger.info("procurement_seed_start project_id=%s orders=%d", project_id, len(orders))
    for supplier_name, status, delivery_status, deliver_offset, note, lines in orders:
        supplier_id = await _supplier_id(db, supplier_name)
        order = ProcurementOrder(
            project_id=project_id, supplier_id=supplier_id,
            total_amount=round(sum(qty * price for _, qty, price in lines), 2),
            status=status, delivery_status=delivery_status,
            expected_delivery=_now() + timedelta(days=deliver_offset),
            estimated_delivery_date=_now() + timedelta(days=deliver_offset),
            actual_delivery_date=_days_ago(1) if delivery_status == "delivered" else None,
            delivery_address=spec["address"],
            delivery_notes=note, tracking_number=f"SF{abs(deliver_offset)}0{hash(note) % 10000:04d}",
            carrier="顺丰速运", assembly_required=True, assembly_difficulty="medium",
            material_delivered_at=_days_ago(1) if delivery_status == "delivered" else None,
            created_at=_days_ago(12),
        )
        db.add(order)
        await db.flush()
        logger.info(
            "procurement_order_created project_id=%s order_id=%s supplier=%s status=%s "
            "delivery_status=%s lines=%d",
            project_id, order.id, supplier_name, status, delivery_status, len(lines),
        )
        for mat_name, qty, price in lines:
            material_id = await _material_id(db, mat_name)
            db.add(OrderLine(
                order_id=order.id, material_id=material_id,
                quantity=qty, unit_price=price, total_price=round(qty * price, 2),
                delivered_quantity=qty if delivery_status == "delivered" else 0.0,
                note="演示数据",
            ))
            logger.info("order_line_created order_id=%s material=%s qty=%s unit_price=%s",
                        order.id, mat_name, qty, price)
    await db.flush()


async def _seed_settlement(db, project_id: str, spec: dict,
                           total_estimated: float, total_actual: float) -> None:
    """结算 + 明细（按里程碑比例生成）。"""
    settlement_cfg = spec.get("settlement")
    if not settlement_cfg:
        return
    logger.info("settlement_seed_start project_id=%s total_estimated=%s total_actual=%s",
                project_id, total_estimated, total_actual)
    settlement = Settlement(
        project_id=project_id, milestone=settlement_cfg["milestone"],
        contract_amount=total_estimated, actual_amount=total_actual,
        payable_amount=round(total_estimated - total_actual, 2),
        status=settlement_cfg["status"], created_at=_days_ago(20),
    )
    db.add(settlement)
    await db.flush()
    for cat, name, ratio, status in settlement_cfg["lines"]:
        db.add(SettlementLine(
            settlement_id=settlement.id, category=cat, name=name,
            contract_amount=round(total_estimated * ratio, 2), change_amount=0.0,
            actual_amount=0.0, status=status, note="演示数据",
        ))
    await db.flush()
    logger.info("settlement_seed_done project_id=%s settlement_id=%s contract=%s actual=%s payable=%s lines=%d",
                project_id, settlement.id, settlement.contract_amount,
                settlement.actual_amount, settlement.payable_amount,
                len(settlement_cfg["lines"]))


async def _seed_smart_home(db, project_id: str, spec: dict) -> None:
    """智能家居方案 + 设备。"""
    schemes = spec["smart_home_schemes"]
    if not schemes:
        return
    logger.info("smart_home_seed_start project_id=%s schemes=%d", project_id, len(schemes))
    for room_name, room_type, protocol, hub_brand, status, notes, devices in schemes:
        scheme = SmartHomeScheme(
            project_id=project_id, room_name=room_name, room_type=room_type,
            protocol=protocol, hub_brand=hub_brand, device_count=len(devices),
            total_price=round(sum(d[3] for d in devices), 2),
            status=status, notes=notes, created_at=_days_ago(25),
        )
        db.add(scheme)
        await db.flush()
        logger.info("smart_home_scheme_created project_id=%s scheme_id=%s room=%s status=%s devices=%d",
                    project_id, scheme.id, room_name, status, len(devices))
        for dev_type, dev_name, brand, price in devices:
            db.add(SmartDevice(
                scheme_id=scheme.id, device_type=dev_type, device_name=dev_name,
                brand=brand, room_name=room_name, protocol=protocol,
                control_mode="automation", price=price, status="installed",
                wiring_required=dev_type in ("light", "switch", "socket"),
                wiring_spec={"零火线": dev_type in ("light", "switch", "socket")},
                features={"调光": dev_type == "light"},
            ))
            logger.info("smart_device_created scheme_id=%s device=%s type=%s price=%s",
                        scheme.id, dev_name, dev_type, price)
    await db.flush()


async def _seed_one_project(db, owner: User, spec: dict) -> None:
    """注入单个模拟项目（全链路分域）。"""
    project = await _seed_project_and_plan(db, owner, spec)
    total_estimated, total_actual = await _seed_budget(db, project.id, spec)
    await _seed_construction(db, project.id, spec)
    await _seed_milestones_and_alerts(db, project.id, spec)
    await _seed_quality(db, project.id, spec)
    await _seed_procurement(db, project.id, spec)
    await _seed_settlement(db, project.id, spec, total_estimated, total_actual)
    await _seed_smart_home(db, project.id, spec)
    logger.info("project_seed_done id=%s name=%s total_estimated=%s total_actual=%s",
                project.id, spec["name"], total_estimated, total_actual)
    print(f"  ✅ 项目「{spec['name']}」（{spec['total_area']:g}㎡ · {spec['phase']}）")


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

async def seed_demo_project() -> bool:
    """注入全部演示项目（幂等：已存在同名项目则跳过）。返回是否新注入。"""
    logger.info("seed_demo_start phone=%s projects=%d", DEMO_PHONE, len(DEMO_PROJECTS))
    await init_db()
    logger.info("init_db_done")
    async with async_session() as db:
        owner_result = await db.execute(select(User).where(User.phone == DEMO_PHONE))
        owner = owner_result.scalar_one_or_none()
        if not owner:
            logger.warning("demo_owner_not_found phone=%s — 请先执行 scripts/seed.py", DEMO_PHONE)
            print(f"❌ 业主演示账号不存在（{DEMO_PHONE}），请先执行 scripts/seed.py")
            return False
        logger.info("demo_owner_found user_id=%s name=%s role=%s", owner.id, owner.name, owner.role)

        injected = False
        for spec in DEMO_PROJECTS:
            exist_result = await db.execute(
                select(Project).where(Project.owner_id == owner.id, Project.name == spec["name"])
            )
            existing = exist_result.scalar_one_or_none()
            if existing:
                logger.info("seed_skip_idempotent project_id=%s name=%s — 已存在", existing.id, spec["name"])
                print(f"  ℹ️  项目「{spec['name']}」已存在，跳过注入")
                continue
            await _seed_one_project(db, owner, spec)
            injected = True

        await db.commit()
        logger.info("seed_demo_commit_done projects=%d", len(DEMO_PROJECTS))
        print(f"✅ 演示项目种子完成（{DEMO_PROJECTS[0]['name']} 等 {len(DEMO_PROJECTS)} 个项目，业主 {owner.name} {DEMO_PHONE}）")
        return injected


async def _delete_project_related(db, project_id: str) -> int:
    """删除项目的全部关联业务数据（含子表，供清理复用）。返回删除行数。

    按外键依赖自底向上删除，避免 FK 违规（曾因先删 construction_tasks 而
    quality_issues.task_id 仍引用导致失败）：
      ① 无 project_id 的中间子表（经父表 id 间接关联：budget_lines / order_lines /
         settlement_lines / smart_devices / rooms）
      ② 引用 construction_tasks 的项目级表（quality_issues / progress_alerts /
         procurement_orders，必须早于 ConstructionTask 删除）
      ③ ConstructionTask（ORM cascade 连带删除 ConstructionLog / Inspection）
      ④ 其余项目级父表（milestone_trackers / floor_plans / budgets /
         quality_assessments / rectification_orders / quotations / settlements /
         smart_home_schemes）
      ⑤ 空间层级 Floor（Room 已在 ① 删除）
    """
    deleted = 0

    async def _delete_rows(model, where) -> None:
        nonlocal deleted
        rows = (await db.execute(select(model).where(where))).scalars().all()
        for row in rows:
            await db.delete(row)
            deleted += 1

    # 父表 id 子查询（供中间子表按 FK 关联定位）
    budget_ids = select(Budget.id).where(Budget.project_id == project_id)
    order_ids = select(ProcurementOrder.id).where(ProcurementOrder.project_id == project_id)
    settlement_ids = select(Settlement.id).where(Settlement.project_id == project_id)
    scheme_ids = select(SmartHomeScheme.id).where(SmartHomeScheme.project_id == project_id)
    floor_ids = select(Floor.id).where(Floor.project_id == project_id)

    # ① 中间子表（无 project_id，经父表 id 间接关联）
    await _delete_rows(BudgetLine, BudgetLine.budget_id.in_(budget_ids))
    await _delete_rows(OrderLine, OrderLine.order_id.in_(order_ids))
    await _delete_rows(SettlementLine, SettlementLine.settlement_id.in_(settlement_ids))
    await _delete_rows(SmartDevice, SmartDevice.scheme_id.in_(scheme_ids))
    await _delete_rows(Room, Room.floor_id.in_(floor_ids))

    # ② 引用 construction_tasks / inspections 的项目级表
    await _delete_rows(QualityIssue, QualityIssue.project_id == project_id)
    await _delete_rows(ProgressAlert, ProgressAlert.project_id == project_id)
    await _delete_rows(ProcurementOrder, ProcurementOrder.project_id == project_id)

    # ③ ConstructionTask（ORM cascade 连带删除 ConstructionLog / Inspection）
    await _delete_rows(ConstructionTask, ConstructionTask.project_id == project_id)

    # ④ 其余项目级父表
    await _delete_rows(MilestoneTracker, MilestoneTracker.project_id == project_id)
    await _delete_rows(FloorPlan, FloorPlan.project_id == project_id)
    await _delete_rows(Budget, Budget.project_id == project_id)
    await _delete_rows(QualityAssessment, QualityAssessment.project_id == project_id)
    await _delete_rows(RectificationOrder, RectificationOrder.project_id == project_id)
    await _delete_rows(Quotation, Quotation.project_id == project_id)
    await _delete_rows(Settlement, Settlement.project_id == project_id)
    await _delete_rows(SmartHomeScheme, SmartHomeScheme.project_id == project_id)

    # ⑤ 空间层级（Room 已在 ① 删除）
    await _delete_rows(Floor, Floor.project_id == project_id)
    return deleted


async def clear_demo_project() -> bool:
    """清理本脚本创建的演示项目（含全部关联数据）。返回是否删除了项目。"""
    logger.info("seed_demo_clear_start phone=%s projects=%d", DEMO_PHONE, len(DEMO_PROJECTS))
    await init_db()
    async with async_session() as db:
        owner_result = await db.execute(select(User).where(User.phone == DEMO_PHONE))
        owner = owner_result.scalar_one_or_none()
        if not owner:
            logger.warning("demo_owner_not_found phone=%s — 无需清理", DEMO_PHONE)
            print(f"ℹ️  业主演示账号不存在（{DEMO_PHONE}），无需清理")
            return False

        names = [spec["name"] for spec in DEMO_PROJECTS]
        result = await db.execute(
            select(Project).where(Project.owner_id == owner.id, Project.name.in_(names))
        )
        projects = result.scalars().all()
        if not projects:
            logger.info("seed_clear_skip project_names=%s — 演示项目不存在", names)
            print("ℹ️  演示项目不存在，无需清理")
            return False

        total_deleted = 0
        for project in projects:
            total_deleted += await _delete_project_related(db, project.id)
            await db.delete(project)
        await db.commit()
        logger.info("seed_demo_clear_done projects=%d related_rows_deleted=%d", len(projects), total_deleted)
        print(f"🗑️  已清理 {len(projects)} 个演示项目")
        return True


async def clear_all_projects() -> int:
    """清空全库所有用户的项目（含全部关联数据）。返回删除的项目数（破坏性操作）。"""
    logger.warning("clear_all_projects_start — 清空全库所有用户的项目")
    await init_db()
    async with async_session() as db:
        result = await db.execute(select(Project))
        projects = result.scalars().all()
        total_deleted = 0
        for project in projects:
            total_deleted += await _delete_project_related(db, project.id)
            await db.delete(project)
        await db.commit()
        logger.info("clear_all_projects_done projects=%d related_rows_deleted=%d",
                    len(projects), total_deleted)
        print(f"🗑️  已清空项目库：{len(projects)} 个项目（含关联数据 {total_deleted} 行）")
        return len(projects)


if __name__ == "__main__":
    _configure_logging()
    parser = argparse.ArgumentParser(description="演示项目种子数据注入/清理")
    parser.add_argument("--clear", action="store_true", help="清理演示项目")
    parser.add_argument("--clear-all-projects", action="store_true",
                        help="清空全库所有用户的项目（破坏性操作）")
    args = parser.parse_args()
    if args.clear_all_projects:
        asyncio.run(clear_all_projects())
    elif args.clear:
        asyncio.run(clear_demo_project())
    else:
        asyncio.run(seed_demo_project())

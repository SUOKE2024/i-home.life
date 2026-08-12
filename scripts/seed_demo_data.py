"""演示项目种子数据 — 为业主演示账号（张先生 13800138000）注入完整演示项目

目的：让「一键演示登录」后的首页/各页面有真实可看的数据（不是假数据，
而是写入真实业务表、由现有 API 原样读出的演示数据）。数据均来自业务表，
符合项目「诚实降级 / 禁止硬编码假数据」约定——演示数据本身就是种子数据。

覆盖链路（对齐 webapp 各页面数据源）：
  项目 → 户型(逐房间状态) → 预算(明细) → 施工任务(7 阶段) →
  里程碑 → 进度预警 → 质检(问题+评估) → 采购(订单+明细) →
  结算(明细) → 智能家居(方案+设备)

用法：
  python scripts/seed_demo_data.py            # 注入（幂等：已存在则跳过）
  python scripts/seed_demo_data.py --clear    # 清理本脚本创建的演示项目
"""

import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import async_session, init_db
from app.models.budget import Budget, BudgetLine
from app.models.construction import ConstructionTask
from app.models.floorplan import FloorPlan
from app.models.procurement import OrderLine, ProcurementOrder, Supplier
from app.models.progress_alert import MilestoneTracker, ProgressAlert
from app.models.project import Floor, Project, Room
from app.models.quality import QualityAssessment, QualityIssue
from app.models.settlement import Settlement, SettlementLine
from app.models.smart_home import SmartDevice, SmartHomeScheme
from app.models.user import User

DEMO_PHONE = "13800138000"       # 业主演示账号（scripts/seed.py 体验账户）
DEMO_PASSWORD_HINT = "123456"
DEMO_PROJECT_NAME = "云栖雅苑 · 智能整装"

_UTC = timezone.utc
_BJ = timezone(timedelta(hours=8), name="Asia/Shanghai")


def _now() -> datetime:
    return datetime.now(_UTC)


def _days_ago(days: float) -> datetime:
    return _now() - timedelta(days=days)


# 预算明细（类别/名称/数量/单价/实际花费）
BUDGET_LINES = [
    ("地面", "750×1500 大板砖", 82.0, 198.0, 16236.0),
    ("墙面", "净味乳胶漆（全屋）", 320.0, 680.0, 0.0),
    ("顶面", "石膏板吊顶", 46.0, 95.0, 4370.0),
    ("厨卫", "石英石台面 + 台下盆", 1.0, 9860.0, 9860.0),
    ("厨卫", "智能马桶 + 恒温花洒", 2.0, 5660.0, 5660.0),
    ("水电", "强弱电改造（含材料）", 126.0, 168.0, 21168.0),
    ("定制", "定制衣柜（主卧+次卧）", 24.0, 1280.0, 0.0),
    ("软装", "LED 无主灯全屋套餐", 1.0, 2680.0, 0.0),
    ("家电", "中央空调一拖四", 1.0, 12800.0, 0.0),
]

# 施工任务（名称/阶段/状态/前置任务名/延期天数 0 表示无预警）
CONSTRUCTION_TASKS = [
    ("开工准备与成品保护", "preparation", "completed", None, 0),
    ("水电改造与防水", "waterproof", "completed", "开工准备与成品保护", 0),
    ("泥瓦铺贴", "masonry", "in_progress", "水电改造与防水", 0),
    ("木工吊顶与定制", "carpentry", "in_progress", "泥瓦铺贴", 0),
    ("油漆涂刷", "painting", "pending", "木工吊顶与定制", 0),
    ("主材安装", "installation", "pending", "油漆涂刷", 0),
    ("竣工验收", "inspection", "pending", "主材安装", 0),
]

# 里程碑（code/名称/计划百分比/状态/支付比例/是否完成）
MILESTONES = [
    ("delivery", "交房开工", 30.0, "completed", 0.30, True),
    ("mep", "水电验收", 50.0, "completed", 0.20, True),
    ("masonry", "泥瓦验收", 75.0, "in_progress", 0.25, False),
    ("completion", "竣工结算", 100.0, "pending", 0.20, False),
    ("warranty", "质保期满", 100.0, "pending", 0.05, False),
]

# 进度预警（类型/严重度/消息/状态/建议）
ALERTS = [
    ("delay", "high", "客厅地砖进场较计划延迟 3 天，泥瓦铺贴进度略滞后",
     "active", "建议联系东鹏瓷砖旗舰店确认补货时间，必要时先安排墙面工序"),
    ("risk", "medium", "定制衣柜下单 15 天仍未排产，存在影响木工阶段收尾的风险",
     "active", "建议通过 AI 管家催单或联系索菲亚衣柜客服跟进排产"),
    ("milestone", "low", "水电验收里程碑已按计划完成", "resolved", None),
]

# 质检问题（阶段/类别/描述/严重度/状态/位置）
QUALITY_ISSUES = [
    ("masonry", "平整度", "客厅阳台墙砖平整度偏差 3mm，超出验收标准（≤2mm）",
     "medium", "open", "客厅阳台", "GB 50210-2018 饰面砖允许偏差 ≤2mm"),
    ("waterproof", "防水", "主卫防水层上翻高度不足（实测 250mm，标准 300mm）",
     "high", "resolved", "主卫", "GB 50327-2001 淋浴区防水上翻 ≥1800mm"),
]

# 采购订单（供应商名/状态/配送状态/预计送达偏移天/备注/明细[(物料名, 数量, 单价)]）
PROCUREMENT_ORDERS = [
    ("东鹏瓷砖旗舰店", "delivered", "delivered", -2,
     "客厅 + 厨卫墙地砖（第一批）", [("750×1500 大板砖", 82.0, 198.0), ("400×800 瓷片", 120.0, 88.0)]),
    ("索菲亚衣柜", "confirmed", "shipping", 5,
     "定制衣柜（主卧 + 次卧）", [("定制衣柜", 24.0, 1280.0)]),
]

# 智能家居方案（房间/类型/协议/品牌/状态/备注/设备[(类型, 名称, 品牌, 价格)])
SMART_HOME_SCHEMES = [
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
]


async def _material_id(db, material_name: str) -> str:
    from app.models.material import Material
    result = await db.execute(select(Material).where(Material.name == material_name))
    material = result.scalar_one_or_none()
    if not material:
        raise RuntimeError(f"物料不存在（请先执行 scripts/seed.py）：{material_name}")
    return material.id


async def _supplier_id(db, supplier_name: str) -> str:
    result = await db.execute(select(Supplier).where(Supplier.name == supplier_name))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise RuntimeError(f"供应商不存在（请先执行 scripts/seed.py）：{supplier_name}")
    return supplier.id


async def _seed_project_and_plan(db, owner: User) -> Project:
    """演示项目 + 户型（楼层/房间/户型方案）。"""
    project = Project(
        name=DEMO_PROJECT_NAME,
        description="演示数据：完整家装全链路示例项目（一键演示登录可用）",
        address="云南省昆明市西山区广福路云栖雅苑 3 栋 1201",
        total_area=126.0,
        status="in_progress",
        phase="construction",
        project_type="full_renovation",
        house_type="平层",
        latitude=24.9057,
        longitude=102.8345,
        contact_name="张先生",
        contact_phone=DEMO_PHONE,
        owner_id=owner.id,
        source="manual",
        created_at=_days_ago(60),
    )
    db.add(project)
    await db.flush()

    floor = Floor(project_id=project.id, name="1 层", floor_number=1, area=126.0, created_at=_days_ago(58))
    db.add(floor)
    await db.flush()
    room_defs = [
        ("客厅", "living_room", 35.0), ("主卧", "bedroom", 20.0),
        ("次卧", "bedroom", 15.0), ("书房", "study", 10.0),
        ("厨房", "kitchen", 10.0), ("卫生间", "bathroom", 6.0),
    ]
    for name, rtype, area in room_defs:
        db.add(Room(floor_id=floor.id, name=name, room_type=rtype, area=area, width=area * 0.8,
                    length=area / (area * 0.8) if area else 1.0, height=2.8))
    await db.flush()

    plan_data = {
        "name": DEMO_PROJECT_NAME,
        "total_area": 126.0,
        "wall_height": 2.8,
        "rooms": [
            {"name": n, "room_type": t, "area": a, "width": a * 0.8, "length": a / (a * 0.8)}
            for n, t, a in room_defs
        ],
    }
    db.add(FloorPlan(
        project_id=project.id,
        name="126㎡ 现代简约 · 智能整装",
        data=json.dumps(plan_data, ensure_ascii=False),
        wall_height=2.8,
        total_area=126.0,
        room_count=6,
        room_status=json.dumps({
            "客厅": "in_progress", "主卧": "completed", "次卧": "in_progress",
            "书房": "not_started", "厨房": "completed", "卫生间": "in_progress",
        }, ensure_ascii=False),
        is_active=True,
        created_at=_days_ago(55),
    ))
    await db.flush()
    return project


async def _seed_budget(db, project_id: str) -> tuple[float, float]:
    """预算 + 明细。返回 (预估总额, 实际花费)。"""
    total_estimated = round(sum(q * p for _, _, q, p, _ in BUDGET_LINES), 2)
    total_actual = round(sum(a for _, _, _, _, a in BUDGET_LINES), 2)
    budget = Budget(
        project_id=project_id, total_estimated=total_estimated,
        total_actual=total_actual, status="approved", created_at=_days_ago(50),
    )
    db.add(budget)
    await db.flush()
    for cat, name, qty, price, actual in BUDGET_LINES:
        db.add(BudgetLine(
            budget_id=budget.id, category=cat, name=name,
            estimated_amount=round(qty * price, 2), actual_amount=actual,
            unit="㎡" if qty > 1 else "项", quantity=qty, unit_price=price,
            note="演示数据", created_at=_days_ago(50),
        ))
    await db.flush()
    return total_estimated, total_actual


async def _seed_construction(db, project_id: str) -> dict[str, str]:
    """施工任务（带前置依赖）。返回 任务名 → id 映射。"""
    task_ids: dict[str, str] = {}
    for name, phase, status, predecessor, _delay in CONSTRUCTION_TASKS:
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
    await db.flush()
    return task_ids


async def _seed_milestones_and_alerts(db, project_id: str, task_ids: dict[str, str]) -> None:
    """里程碑 + 进度预警。"""
    for idx, (code, name, percent, status, ratio, done) in enumerate(MILESTONES):
        db.add(MilestoneTracker(
            project_id=project_id, milestone_code=code, name=name,
            planned_date=_days_ago(40 - idx * 15),
            actual_date=_days_ago(30 - idx * 2) if done else None,
            planned_percent=percent, actual_percent=100.0 if done else 60.0,
            status=status, payment_ratio=ratio, note="演示数据",
        ))
    for alert_type, severity, message, status, suggestion in ALERTS:
        db.add(ProgressAlert(
            project_id=project_id,
            task_id=task_ids.get("泥瓦铺贴") if alert_type == "delay" else None,
            phase="masonry" if alert_type in ("delay", "risk") else "mep",
            alert_type=alert_type, severity=severity, message=message,
            delay_days=3 if alert_type == "delay" else 0,
            progress_percent=75.0, suggestion=suggestion, status=status,
            resolved_at=_days_ago(2) if status == "resolved" else None,
            resolved_by="AI 管家" if status == "resolved" else None,
            created_at=_days_ago(8),
        ))
    await db.flush()


async def _seed_quality(db, project_id: str, task_ids: dict[str, str]) -> None:
    """质检问题 + 质量评估。"""
    for phase, category, desc, severity, status, location, standard in QUALITY_ISSUES:
        db.add(QualityIssue(
            project_id=project_id,
            task_id=task_ids.get("水电改造与防水") if phase == "waterproof" else task_ids.get("泥瓦铺贴"),
            phase=phase, category=category, description=desc, severity=severity,
            status=status, detected_by="ai", standard=standard, location=location,
            resolution="已整改复验合格" if status == "resolved" else None,
            resolved_at=_days_ago(2) if status == "resolved" else None,
            resolved_by="郑水电" if status == "resolved" else None,
        ))
    db.add(QualityAssessment(
        project_id=project_id, phase="masonry", total_items=36, passed=33, failed=3,
        score=92.0, verdict="pass", assessor="王监理",
        summary="泥瓦阶段整体合格，3 项轻微问题已开出整改单",
        issues_summary="墙砖平整度偏差 1 项（整改中）",
        assessed_at=_days_ago(3),
    ))
    await db.flush()


async def _seed_procurement(db, project_id: str) -> None:
    """采购订单 + 明细。"""
    for supplier_name, status, delivery_status, deliver_offset, note, lines in PROCUREMENT_ORDERS:
        order = ProcurementOrder(
            project_id=project_id, supplier_id=await _supplier_id(db, supplier_name),
            total_amount=round(sum(qty * price for _, qty, price in lines), 2),
            status=status, delivery_status=delivery_status,
            expected_delivery=_now() + timedelta(days=deliver_offset),
            estimated_delivery_date=_now() + timedelta(days=deliver_offset),
            actual_delivery_date=_days_ago(1) if delivery_status == "delivered" else None,
            delivery_address="云南省昆明市西山区广福路云栖雅苑 3 栋 1201",
            delivery_notes=note, tracking_number=f"SF{abs(deliver_offset)}0{hash(note) % 10000:04d}",
            carrier="顺丰速运", assembly_required=True, assembly_difficulty="medium",
            material_delivered_at=_days_ago(1) if delivery_status == "delivered" else None,
            created_at=_days_ago(12),
        )
        db.add(order)
        await db.flush()
        for mat_name, qty, price in lines:
            db.add(OrderLine(
                order_id=order.id, material_id=await _material_id(db, mat_name),
                quantity=qty, unit_price=price, total_price=round(qty * price, 2),
                delivered_quantity=qty if delivery_status == "delivered" else 0.0,
                note="演示数据",
            ))
    await db.flush()


async def _seed_settlement(db, project_id: str, total_estimated: float, total_actual: float) -> None:
    """结算 + 明细。"""
    settlement = Settlement(
        project_id=project_id, milestone="completion",
        contract_amount=total_estimated, actual_amount=total_actual,
        payable_amount=round(total_estimated - total_actual, 2),
        status="in_progress", created_at=_days_ago(20),
    )
    db.add(settlement)
    await db.flush()
    settlement_lines = [
        ("预付款", "开工预付 30%", round(total_estimated * 0.30, 2), 0.0, "paid"),
        ("进度款", "水电阶段 20%", round(total_estimated * 0.20, 2), 0.0, "paid"),
        ("进度款", "泥瓦阶段 25%", round(total_estimated * 0.25, 2), total_actual, "pending"),
        ("尾款", "竣工验收 25%", round(total_estimated * 0.25, 2), 0.0, "pending"),
    ]
    for cat, name, contract, actual, status in settlement_lines:
        db.add(SettlementLine(
            settlement_id=settlement.id, category=cat, name=name,
            contract_amount=contract, change_amount=0.0, actual_amount=actual,
            status=status, note="演示数据",
        ))
    await db.flush()


async def _seed_smart_home(db, project_id: str) -> None:
    """智能家居方案 + 设备。"""
    for room_name, room_type, protocol, hub_brand, status, notes, devices in SMART_HOME_SCHEMES:
        scheme = SmartHomeScheme(
            project_id=project_id, room_name=room_name, room_type=room_type,
            protocol=protocol, hub_brand=hub_brand, device_count=len(devices),
            total_price=round(sum(d[3] for d in devices), 2),
            status=status, notes=notes, created_at=_days_ago(25),
        )
        db.add(scheme)
        await db.flush()
        for dev_type, dev_name, brand, price in devices:
            db.add(SmartDevice(
                scheme_id=scheme.id, device_type=dev_type, device_name=dev_name,
                brand=brand, room_name=room_name, protocol=protocol,
                control_mode="automation", price=price, status="installed",
                wiring_required=dev_type in ("light", "switch", "socket"),
                wiring_spec={"零火线": dev_type in ("light", "switch", "socket")},
                features={"调光": dev_type == "light"},
            ))
    await db.flush()


async def seed_demo_project() -> bool:
    """注入演示项目。已存在同名项目时跳过（幂等）。返回是否新注入。"""
    await init_db()
    async with async_session() as db:
        # 幂等：业主名下已存在演示项目则跳过
        owner_result = await db.execute(select(User).where(User.phone == DEMO_PHONE))
        owner = owner_result.scalar_one_or_none()
        if not owner:
            print(f"❌ 业主演示账号不存在（{DEMO_PHONE}），请先执行 scripts/seed.py")
            return False

        exist_result = await db.execute(
            select(Project).where(Project.owner_id == owner.id, Project.name == DEMO_PROJECT_NAME)
        )
        if exist_result.scalar_one_or_none():
            print(f"ℹ️  演示项目「{DEMO_PROJECT_NAME}」已存在，跳过注入")
            return False

        project = await _seed_project_and_plan(db, owner)
        total_estimated, total_actual = await _seed_budget(db, project.id)
        task_ids = await _seed_construction(db, project.id)
        await _seed_milestones_and_alerts(db, project.id, task_ids)
        await _seed_quality(db, project.id, task_ids)
        await _seed_procurement(db, project.id)
        await _seed_settlement(db, project.id, total_estimated, total_actual)
        await _seed_smart_home(db, project.id)

        await db.commit()
        print(f"✅ 已注入演示项目「{DEMO_PROJECT_NAME}」（业主 {owner.name} {DEMO_PHONE}）")
        print(f"   预算 ¥{total_estimated:,.2f}（实际 ¥{total_actual:,.2f}） · "
              f"施工 7 任务 · 里程碑 5 · 预警 3 · 质检问题 2 · 采购订单 2 · 结算 1 · 智能家居方案 3")
        return True


async def clear_demo_project() -> bool:
    """清理演示项目（含全部级联关联数据）。返回是否删除了项目。"""
    await init_db()
    async with async_session() as db:
        owner_result = await db.execute(select(User).where(User.phone == DEMO_PHONE))
        owner = owner_result.scalar_one_or_none()
        if not owner:
            print(f"ℹ️  业主演示账号不存在（{DEMO_PHONE}），无需清理")
            return False
        result = await db.execute(
            select(Project).where(Project.owner_id == owner.id, Project.name == DEMO_PROJECT_NAME)
        )
        project = result.scalar_one_or_none()
        if not project:
            print(f"ℹ️  演示项目「{DEMO_PROJECT_NAME}」不存在，无需清理")
            return False
        # 关联子表通过外键/级联关系手动清理（SQLite 生产环境关闭外键时依赖显式删除）
        project_id = project.id
        from app.models.budget import Budget
        from app.models.procurement import ProcurementOrder
        from app.models.quality import QualityIssue, QualityAssessment
        from app.models.settlement import Settlement

        for model, col in [
            (ProgressAlert, "project_id"), (MilestoneTracker, "project_id"),
            (FloorPlan, "project_id"), (Budget, "project_id"),
            (ConstructionTask, "project_id"), (QualityIssue, "project_id"),
            (QualityAssessment, "project_id"), (ProcurementOrder, "project_id"),
            (Settlement, "project_id"), (SmartHomeScheme, "project_id"),
        ]:
            for row in (await db.execute(select(model).where(getattr(model, col) == project_id))).scalars().all():
                await db.delete(row)
        # 项目级联删除楼层/房间
        await db.delete(project)
        await db.commit()
        print(f"🗑️  已清理演示项目「{DEMO_PROJECT_NAME}」")
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="演示项目种子数据注入/清理")
    parser.add_argument("--clear", action="store_true", help="清理演示项目")
    args = parser.parse_args()
    asyncio.run(clear_demo_project() if args.clear else seed_demo_project())

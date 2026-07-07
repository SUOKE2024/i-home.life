"""F18 厨卫水电服务层 — 给排水点位 + 厨房回路 + 等电位校验 + 燃气规划 + CRUD"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.kitchen_bath_mep import KitchenBathMEPPlan, MEPPoint


# ── 给排水点位规划 ──

# 设备 → 给排水点位规格映射
_DEVICE_WATER_SPEC = {
    "热水器": {"inlets": ["冷水进水", "热水出水"], "drains": [], "spec": "1/2\"", "needs_gas": True},
    "洗碗机": {"inlets": ["冷水进水"], "drains": ["排水"], "spec": "3/4\"", "needs_gas": False},
    "净水器": {"inlets": ["冷水进水"], "drains": ["浓水排水"], "spec": "1/2\"", "needs_gas": False},
    "智能马桶": {"inlets": ["冷水进水"], "drains": [], "spec": "1/2\"", "needs_gas": False, "note": "独立角阀"},
    "洗衣机": {"inlets": ["冷水进水"], "drains": ["排水(地漏)"], "spec": "1/2\"", "needs_gas": False},
}


def generate_water_inlets(room_type: str, devices: list[str]) -> dict:
    """给排水点位规划 (热水器/洗碗机/净水器/智能马桶/洗衣机)

    Args:
        room_type: 厨房 kitchen / 卫生间 bathroom / 洗衣房 laundry / 阳台 balcony
        devices: 设备清单
    """
    water_inlets: list[dict] = []
    drains: list[dict] = []
    gas_points: list[dict] = []

    for idx, dev in enumerate(devices):
        spec = _DEVICE_WATER_SPEC.get(dev)
        if not spec:
            continue
        # 给水点位
        for inlet in spec["inlets"]:
            water_inlets.append({
                "device": dev,
                "type": inlet,
                "spec": spec["spec"],
                "position": {"x": 300 + idx * 150, "y": 0, "z": 450},
                "note": spec.get("note"),
            })
        # 排水点位
        for drain in spec["drains"]:
            drains.append({
                "device": dev,
                "type": drain,
                "position": {"x": 300 + idx * 150, "y": 0, "z": 0},
            })
        # 燃气接口 (仅燃气热水器)
        if spec.get("needs_gas"):
            gas_points.append({
                "device": dev,
                "type": "燃气接口",
                "position": {"x": 300 + idx * 150, "y": 0, "z": 1800},
            })

    return {
        "room_type": room_type,
        "water_inlets": water_inlets,
        "drains": drains,
        "gas_points": gas_points,
        "total_inlets": len(water_inlets),
        "total_drains": len(drains),
    }


# ── 厨房专用回路设计 ──

# 大功率电器 (≥2000W) 独立回路
_HIGH_POWER_APPLIANCES = {
    "烤箱": {"power": 2500, "wire": "4mm²", "breaker": "16A"},
    "微波炉": {"power": 2000, "wire": "4mm²", "breaker": "16A"},
    "洗碗机": {"power": 2200, "wire": "4mm²", "breaker": "16A"},
    "热水器": {"power": 3000, "wire": "4mm²", "breaker": "20A"},
    "电磁炉": {"power": 3000, "wire": "4mm²", "breaker": "20A"},
}
# 单独回路的小功率电器
_DEDICATED_APPLIANCES = {
    "小厨宝": {"power": 1500, "wire": "2.5mm²", "breaker": "10A"},
    "垃圾处理器": {"power": 800, "wire": "2.5mm²", "breaker": "10A"},
}


def design_kitchen_circuits(devices: list[str]) -> dict:
    """厨房专用回路设计

    - 大功率电器 (≥2000W) 独立回路: 烤箱/微波炉/洗碗机/热水器
    - 小厨宝/垃圾处理器 单独回路
    - 照明回路 1.5mm²
    - 普通插座 2.5mm²
    - 大功率插座 4mm²
    """
    circuits: list[dict] = []
    circuit_no = 1

    # 大功率电器独立回路
    high_power_used = []
    for dev in devices:
        spec = _HIGH_POWER_APPLIANCES.get(dev)
        if spec:
            circuits.append({
                "circuit_no": f"K{circuit_no}",
                "type": "大功率专用回路",
                "device": dev,
                "power_w": spec["power"],
                "wire": spec["wire"],
                "breaker": spec["breaker"],
                "voltage": "220V",
            })
            circuit_no += 1
            high_power_used.append(dev)

    # 小厨宝/垃圾处理器单独回路
    dedicated_used = []
    for dev in devices:
        spec = _DEDICATED_APPLIANCES.get(dev)
        if spec:
            circuits.append({
                "circuit_no": f"K{circuit_no}",
                "type": "专用回路",
                "device": dev,
                "power_w": spec["power"],
                "wire": spec["wire"],
                "breaker": spec["breaker"],
                "voltage": "220V",
            })
            circuit_no += 1
            dedicated_used.append(dev)

    # 照明回路 (1.5mm²)
    circuits.append({
        "circuit_no": f"K{circuit_no}",
        "type": "照明回路",
        "device": "厨房照明",
        "power_w": 200,
        "wire": "1.5mm²",
        "breaker": "10A",
        "voltage": "220V",
    })
    circuit_no += 1

    # 普通插座回路 (2.5mm²)
    circuits.append({
        "circuit_no": f"K{circuit_no}",
        "type": "普通插座回路",
        "device": "厨房普通插座",
        "power_w": 1500,
        "wire": "2.5mm²",
        "breaker": "16A",
        "voltage": "220V",
    })

    total_power = sum(c["power_w"] for c in circuits)
    return {
        "circuits": circuits,
        "total_circuits": len(circuits),
        "total_power_w": total_power,
        "main_breaker_recommended": "40A" if total_power > 6000 else "32A",
    }


# ── 卫生间等电位连接校验 ──

def validate_bathroom_equipotential(plan: KitchenBathMEPPlan) -> dict:
    """卫生间等电位连接校验 (GB 50096 强制要求)

    卫生间金属管道/金属构件必须做等电位连接
    """
    checks = []
    all_pass = True

    # 1. 是否设置等电位连接
    passed = plan.equipotential_bonding
    checks.append({
        "item": "等电位连接设置",
        "value": "已设置" if passed else "未设置",
        "passed": passed,
        "standard": "GB 50096 卫生间必须做等电位连接",
    })
    if not passed:
        all_pass = False

    # 2. 房型校验 (仅卫生间强制)
    is_bathroom = plan.room_type == "bathroom"
    if is_bathroom and not passed:
        checks.append({
            "item": "卫生间强制要求",
            "value": plan.room_type,
            "passed": False,
            "standard": "卫生间 (GB 50096) 必须做局部等电位连接 (LEB)",
        })
        all_pass = False
    else:
        checks.append({
            "item": "卫生间强制要求",
            "value": plan.room_type,
            "passed": True,
            "standard": "仅卫生间强制要求等电位,其他房间推荐",
        })

    # 3. 等电位端子箱
    checks.append({
        "item": "等电位端子箱 (LEB)",
        "value": "应在卫生间内墙设置",
        "passed": passed,
        "standard": "距地 0.3m,连接金属管道/金属构件/钢筋网",
    })

    return {
        "compliant": all_pass,
        "room_type": plan.room_type,
        "equipotential_bonding": plan.equipotential_bonding,
        "checks": checks,
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c.get("passed")),
    }


# ── 燃气管道预留 ──

def plan_gas_pipe(plan: KitchenBathMEPPlan) -> dict:
    """燃气管道预留 (灶台 + 热水器,预留接口位置,距灶台 ≥ 500mm)

    Args:
        plan: 厨卫水电方案
    """
    # 仅厨房 / 含燃气热水器的房间需要燃气规划
    if plan.room_type != "kitchen" and plan.water_heater_type != "gas":
        return {
            "needed": False,
            "reason": "非厨房房间且无燃气热水器,无需燃气管道规划",
            "outlets": [],
        }

    outlets: list[dict] = []
    # 灶台接口
    outlets.append({
        "device": "燃气灶",
        "position": {"x": 600, "y": 600, "z": 850},
        "pipe_spec": "4分管",
        "valve": "燃气专用球阀",
        "note": "距灶台中心 ≥ 500mm,预留接口",
    })
    # 燃气热水器接口
    if plan.water_heater_type == "gas":
        outlets.append({
            "device": "燃气热水器",
            "position": {"x": 300, "y": 0, "z": 1800},
            "pipe_spec": "4分管",
            "valve": "燃气专用球阀",
            "note": "热水器进气接口,距地 1.8m",
        })

    # 管道路径
    pipe_path = [
        {"point": "燃气表", "position": {"x": 0, "y": 0, "z": 1500}},
        {"point": "分支三通", "position": {"x": 300, "y": 0, "z": 1500}},
        {"point": "灶台接口", "position": {"x": 600, "y": 600, "z": 850}},
        {"point": "热水器接口", "position": {"x": 300, "y": 0, "z": 1800}},
    ]

    return {
        "needed": True,
        "outlets": outlets,
        "pipe_path": pipe_path,
        "pipe_material": "不锈钢波纹管",
        "notes": "燃气管道须由燃气公司施工,严禁私自改动;预留接口距灶台 ≥ 500mm",
    }


# ── 厨卫水电方案 CRUD ──

async def create_plan(db: AsyncSession, data: dict) -> KitchenBathMEPPlan:
    plan = KitchenBathMEPPlan(**data)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def get_plan(db: AsyncSession, plan_id: str) -> KitchenBathMEPPlan | None:
    result = await db.execute(
        select(KitchenBathMEPPlan)
        .where(KitchenBathMEPPlan.id == plan_id)
        .options(selectinload(KitchenBathMEPPlan.points))
    )
    return result.scalar_one_or_none()


async def list_plans(db: AsyncSession, project_id: str) -> list[KitchenBathMEPPlan]:
    result = await db.execute(
        select(KitchenBathMEPPlan)
        .where(KitchenBathMEPPlan.project_id == project_id)
        .order_by(KitchenBathMEPPlan.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_plan(db: AsyncSession, plan_id: str) -> bool:
    plan = await get_plan(db, plan_id)
    if not plan:
        return False
    await db.delete(plan)
    await db.commit()
    return True


# ── 水电点位 CRUD ──

async def add_point(db: AsyncSession, data: dict) -> MEPPoint:
    point = MEPPoint(**data)
    db.add(point)
    await db.commit()
    await db.refresh(point)
    return point


async def list_points(db: AsyncSession, plan_id: str) -> list[MEPPoint]:
    result = await db.execute(
        select(MEPPoint)
        .where(MEPPoint.plan_id == plan_id)
        .order_by(MEPPoint.created_at)
    )
    return list(result.scalars().all())


async def delete_point(db: AsyncSession, point_id: str) -> bool:
    result = await db.execute(select(MEPPoint).where(MEPPoint.id == point_id))
    point = result.scalar_one_or_none()
    if not point:
        return False
    await db.delete(point)
    await db.commit()
    return True

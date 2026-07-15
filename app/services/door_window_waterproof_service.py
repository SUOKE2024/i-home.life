"""F23 门窗/防水工程服务层 — 门窗推荐 + 防水面积 + 规范校验 + 材料用量 + CRUD"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.door_window_waterproof import DoorWindowSpec, WaterproofPlan


# ── 门窗推荐 ──

def recommend_door_window(spec_type: str, room_type: str | None = None, opening_direction: str | None = None) -> dict:
    """门窗推荐

    - 入户门: 钢质防盗门,≥90mm 厚,C 级锁
    - 室内门: 实木复合门,35-40mm 厚
    - 卫生间门: 防潮 PVC 或铝合金门
    - 厨房门: 推拉门/折叠门 (节省空间)
    - 窗户: 断桥铝合金 + 双层中空玻璃 (节能)
    """
    if spec_type == "entry_door":
        return {
            "spec_type": spec_type,
            "recommended_material": "steel",
            "material_name": "钢质防盗门",
            "thickness_mm": 90,
            "opening_direction": opening_direction or "inward",
            "glass_type": None,
            "has_lock": True,
            "lock_grade": "C 级 (最高防盗等级)",
            "has_screen": False,
            "notes": "入户门应选甲级防盗门,门体厚度 ≥ 90mm,配 C 级锁芯",
        }
    elif spec_type == "interior_door":
        # 卫生间门特殊处理
        if room_type in ("bathroom", "卫生间"):
            return {
                "spec_type": spec_type,
                "recommended_material": "aluminum",
                "material_name": "铝合金门 (防潮)",
                "thickness_mm": 40,
                "opening_direction": opening_direction or "inward",
                "glass_type": "laminated",
                "has_lock": True,
                "has_screen": False,
                "notes": "卫生间门需防潮,推荐铝合金或 PVC 材质,带磨砂玻璃",
            }
        return {
            "spec_type": spec_type,
            "recommended_material": "wood_composite",
            "material_name": "实木复合门",
            "thickness_mm": 38,
            "opening_direction": opening_direction or "inward",
            "glass_type": None,
            "has_lock": True,
            "has_screen": False,
            "notes": "室内门选实木复合门,厚度 35-40mm,静音合页",
        }
    elif spec_type in ("sliding_door", "french_window"):
        # 厨房推拉门 / 折叠门
        if room_type in ("kitchen", "厨房"):
            return {
                "spec_type": spec_type,
                "recommended_material": "aluminum",
                "material_name": "铝合金推拉门 (节省空间)",
                "thickness_mm": 70,
                "opening_direction": "sliding",
                "glass_type": "double",
                "has_lock": True,
                "has_screen": True,
                "notes": "厨房推荐推拉门/折叠门,节省空间,配双层中空玻璃",
            }
        # 阳台法式门
        return {
            "spec_type": spec_type,
            "recommended_material": "aluminum",
            "material_name": "断桥铝合金推拉门",
            "thickness_mm": 90,
            "opening_direction": "sliding",
            "glass_type": "double",
            "has_lock": True,
            "has_screen": True,
            "notes": "阳台推拉门选断桥铝合金,双层中空玻璃,节能隔音",
        }
    elif spec_type == "window":
        return {
            "spec_type": spec_type,
            "recommended_material": "aluminum",
            "material_name": "断桥铝合金窗",
            "thickness_mm": 70,
            "opening_direction": opening_direction or "inward",
            "glass_type": "double",
            "has_lock": True,
            "has_screen": True,
            "notes": "窗户推荐断桥铝合金 + 双层中空玻璃,节能隔音;高层推荐内开内倒",
        }
    else:
        return {
            "spec_type": spec_type,
            "recommended_material": "wood_composite",
            "material_name": "实木复合门",
            "thickness_mm": 38,
            "opening_direction": opening_direction or "inward",
            "glass_type": None,
            "has_lock": False,
            "has_screen": False,
            "notes": "默认推荐实木复合门",
        }


# ── 防水面积计算 ──

def compute_waterproof_area(
    room_type: str,
    room_width: float,
    room_length: float,
    wall_height_mm: int = 1800,
) -> dict:
    """防水面积计算

    - 卫生间: 地面全防水 + 墙面 1.8m (淋浴区) + 0.3m (其他)
    - 厨房: 地面 + 墙面 0.3m (水槽周边)
    - 阳台: 地面 + 墙面 0.3m

    Args:
        room_type: 房间类型
        room_width: 房间宽 (m)
        room_length: 房间长 (m)
        wall_height_mm: 防水高度 (mm)
    """
    floor_area = room_width * room_length
    # 周长 (假设矩形房间)
    perimeter = 2 * (room_width + room_length)

    if room_type in ("bathroom", "卫生间"):
        # 卫生间: 地面全防水 + 墙面 1.8m (淋浴区) + 0.3m (其他)
        # 淋浴区按一面墙 0.9m 宽计算
        shower_wall_width = 0.9
        shower_area = shower_wall_width * (wall_height_mm / 1000)
        # 其他墙面 0.3m 高
        other_wall_height = 0.3
        other_wall_area = (perimeter - shower_wall_width) * other_wall_height
        wall_area = shower_area + other_wall_area
        standard_height_mm = 1800
        description = "卫生间: 地面全防水 + 淋浴区墙面 1.8m + 其他墙面 0.3m"
    elif room_type in ("kitchen", "厨房"):
        # 厨房: 地面 + 墙面 0.3m (水槽周边)
        wall_area = perimeter * 0.3
        standard_height_mm = 300
        description = "厨房: 地面 + 墙面 0.3m (水槽周边)"
    elif room_type in ("balcony", "阳台", "terrace", "露台", "laundry", "洗衣房"):
        # 阳台/露台/洗衣房: 地面 + 墙面 0.3m
        wall_area = perimeter * 0.3
        standard_height_mm = 300
        description = f"{room_type}: 地面 + 墙面 0.3m"
    else:
        wall_area = perimeter * 0.3
        standard_height_mm = 300
        description = "默认: 地面 + 墙面 0.3m"

    total_area = floor_area + wall_area
    return {
        "room_type": room_type,
        "floor_area_m2": round(floor_area, 2),
        "wall_area_m2": round(wall_area, 2),
        "total_area_m2": round(total_area, 2),
        "wall_height_mm": wall_height_mm,
        "standard_height_mm": standard_height_mm,
        "description": description,
    }


# ── 防水规范校验 ──

def validate_waterproof_spec(plan: WaterproofPlan) -> dict:
    """防水规范校验

    - 卫生间防水高度 ≥ 1800mm (GB 50209)
    - 涂膜厚度 ≥ 1.5mm
    - 闭水试验 ≥ 24 小时
    """
    checks = []
    all_pass = True

    # 1. 卫生间防水高度 ≥ 1800mm
    if plan.room_type in ("bathroom", "卫生间"):
        passed = plan.wall_height_mm >= 1800
        checks.append({
            "item": "卫生间防水高度 ≥ 1800mm",
            "value": plan.wall_height_mm,
            "unit": "mm",
            "passed": passed,
            "standard": "GB 50209 卫生间墙面防水高度 ≥ 1800mm (淋浴区)",
        })
        if not passed:
            all_pass = False
    else:
        # 非卫生间 ≥ 300mm
        passed = plan.wall_height_mm >= 300
        checks.append({
            "item": f"{plan.room_type}防水高度 ≥ 300mm",
            "value": plan.wall_height_mm,
            "unit": "mm",
            "passed": passed,
            "standard": "非卫生间房间墙面防水高度 ≥ 300mm",
        })
        if not passed:
            all_pass = False

    # 2. 涂膜厚度 ≥ 1.5mm
    passed = plan.thickness_mm >= 1.5
    checks.append({
        "item": "涂膜厚度 ≥ 1.5mm",
        "value": plan.thickness_mm,
        "unit": "mm",
        "passed": passed,
        "standard": "GB 50209 防水涂膜厚度 ≥ 1.5mm",
    })
    if not passed:
        all_pass = False

    # 3. 闭水试验 ≥ 24 小时
    passed = plan.closure_test_hours >= 24
    checks.append({
        "item": "闭水试验 ≥ 24 小时",
        "value": plan.closure_test_hours,
        "unit": "h",
        "passed": passed,
        "standard": "GB 50209 闭水试验 ≥ 24h,蓄水高度 ≥ 20mm",
    })
    if not passed:
        all_pass = False

    # 4. 涂刷遍数 ≥ 2
    passed = plan.coating_layers >= 2
    checks.append({
        "item": "涂刷遍数 ≥ 2 遍",
        "value": plan.coating_layers,
        "unit": "遍",
        "passed": passed,
        "standard": "防水涂料至少涂刷 2 遍,十字交叉法施工",
    })
    if not passed:
        all_pass = False

    return {
        "compliant": all_pass,
        "room_type": plan.room_type,
        "checks": checks,
        "total_checks": len(checks),
        "passed_checks": sum(1 for c in checks if c.get("passed")),
    }


# ── 防水材料用量 ──

def compute_material_quantity(area: float, thickness_mm: float, layers: int = 2) -> dict:
    """防水材料用量计算

    Args:
        area: 防水面积 (m²)
        thickness_mm: 涂膜厚度 (mm)
        layers: 涂刷遍数
    """
    # 每平米每毫米厚度用量约 1.2 kg (含损耗)
    usage_per_m2_per_mm = 1.2
    # 总用量
    total_kg = area * thickness_mm * usage_per_m2_per_mm
    # 损耗 5%
    waste = total_kg * 0.05
    final_total = total_kg + waste

    return {
        "area_m2": round(area, 2),
        "thickness_mm": thickness_mm,
        "layers": layers,
        "usage_per_m2_kg": round(usage_per_m2_per_mm * thickness_mm, 2),
        "total_kg": round(total_kg, 2),
        "waste_kg": round(waste, 2),
        "final_total_kg": round(final_total, 2),
    }


# ── 门窗选型 CRUD ──

async def create_door_window(db: AsyncSession, data: dict) -> DoorWindowSpec:
    spec = DoorWindowSpec(**data)
    db.add(spec)
    await db.commit()
    await db.refresh(spec)
    return spec


async def get_door_window(db: AsyncSession, spec_id: str) -> DoorWindowSpec | None:
    result = await db.execute(select(DoorWindowSpec).where(DoorWindowSpec.id == spec_id))
    return result.scalar_one_or_none()


async def list_door_windows(db: AsyncSession, project_id: str) -> list[DoorWindowSpec]:
    result = await db.execute(
        select(DoorWindowSpec)
        .where(DoorWindowSpec.project_id == project_id)
        .order_by(DoorWindowSpec.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_door_window(db: AsyncSession, spec_id: str) -> bool:
    spec = await get_door_window(db, spec_id)
    if not spec:
        return False
    await db.delete(spec)
    await db.commit()
    return True


# ── 防水方案 CRUD ──

async def create_waterproof(db: AsyncSession, data: dict) -> WaterproofPlan:
    plan = WaterproofPlan(**data)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def get_waterproof(db: AsyncSession, plan_id: str) -> WaterproofPlan | None:
    result = await db.execute(select(WaterproofPlan).where(WaterproofPlan.id == plan_id))
    return result.scalar_one_or_none()


async def list_waterproofs(db: AsyncSession, project_id: str) -> list[WaterproofPlan]:
    result = await db.execute(
        select(WaterproofPlan)
        .where(WaterproofPlan.project_id == project_id)
        .order_by(WaterproofPlan.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_waterproof(db: AsyncSession, plan_id: str) -> bool:
    plan = await get_waterproof(db, plan_id)
    if not plan:
        return False
    await db.delete(plan)
    await db.commit()
    return True

"""F27 定制家具设计器服务层 — 参数化设计 + 板材计算 + BOM + 价格估算 + 规格校验"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.custom_furniture import CustomFurnitureDesign, FurnitureModule, FurnitureBOM


# ── 板材单价 (元/㎡) ──
PANEL_UNIT_PRICE = {
    "颗粒板": 180.0,
    "多层板": 280.0,
    "欧松板": 220.0,
    "实木": 580.0,
}

# ── 标准板材规格 2440×1220mm ≈ 2.98 ㎡/张 ──
PANEL_SHEET_AREA_M2 = 2.98
# 板材利用率 (考虑损耗)
PANEL_UTILIZATION = 0.85

# ── 五金单价 (元) ──
HARDWARE_UNIT_PRICE = {
    "slide": 88.0,        # 抽屉滑轨 副
    "hinge": 25.0,        # 铰链 个
    "handle": 38.0,       # 拉手 个
    "hanging_rod": 68.0,  # 衣通 根
    "screw_kit": 30.0,    # 螺丝包 套
    "connector": 12.0,    # 三合一 个
}

# 门板单价 元/㎡
DOOR_UNIT_PRICE_M2 = 380.0
# 加工费 元/单
PROCESS_FEE = 500.0


# ── 设计 CRUD ──


async def create_design(db: AsyncSession, data: dict) -> CustomFurnitureDesign:
    design = CustomFurnitureDesign(**data)
    db.add(design)
    await db.commit()
    await db.refresh(design)
    return design


async def get_design(db: AsyncSession, design_id: str) -> CustomFurnitureDesign | None:
    result = await db.execute(
        select(CustomFurnitureDesign)
        .where(CustomFurnitureDesign.id == design_id)
        .options(selectinload(CustomFurnitureDesign.modules), selectinload(CustomFurnitureDesign.boms))
    )
    return result.scalar_one_or_none()


async def list_designs_by_project(db: AsyncSession, project_id: str) -> list[CustomFurnitureDesign]:
    result = await db.execute(
        select(CustomFurnitureDesign)
        .where(CustomFurnitureDesign.project_id == project_id)
        .order_by(CustomFurnitureDesign.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_design(db: AsyncSession, design_id: str) -> bool:
    design = await get_design(db, design_id)
    if not design:
        return False
    await db.delete(design)
    await db.commit()
    return True


# ── 模块 CRUD ──


async def add_module(db: AsyncSession, design_id: str, data: dict) -> FurnitureModule:
    module = FurnitureModule(design_id=design_id, **data)
    db.add(module)
    await db.commit()
    await db.refresh(module)
    return module


async def list_modules(db: AsyncSession, design_id: str) -> list[FurnitureModule]:
    result = await db.execute(
        select(FurnitureModule)
        .where(FurnitureModule.design_id == design_id)
        .order_by(FurnitureModule.position_index)
    )
    return list(result.scalars().all())


async def delete_module(db: AsyncSession, module_id: str) -> tuple[bool, str | None]:
    """删除模块，返回 (是否成功, design_id)"""
    result = await db.execute(select(FurnitureModule).where(FurnitureModule.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        return False, None
    design_id = module.design_id
    await db.delete(module)
    await db.commit()
    return True, design_id


# ── BOM 查询 ──


async def list_boms(db: AsyncSession, design_id: str) -> list[FurnitureBOM]:
    result = await db.execute(
        select(FurnitureBOM)
        .where(FurnitureBOM.design_id == design_id)
        .order_by(FurnitureBOM.item_type, FurnitureBOM.created_at)
    )
    return list(result.scalars().all())


async def _clear_boms(db: AsyncSession, design_id: str) -> None:
    result = await db.execute(select(FurnitureBOM).where(FurnitureBOM.design_id == design_id))
    for bom in result.scalars().all():
        await db.delete(bom)


# ── 参数化设计:根据 furniture_type 自动生成模块 ──


def parametric_design(design: CustomFurnitureDesign) -> list[dict]:
    """根据家具类型自动生成模块列表

    返回模块字典列表,字段与 FurnitureModule 对齐(不含 design_id)。
    """
    ftype = design.furniture_type
    W = float(design.total_width or 0)
    H = float(design.total_height or 0)
    D = float(design.total_depth or 0)
    material = design.panel_material
    color = design.color or ""

    modules: list[dict] = []
    pos = 0

    def add(mtype: str, w: float, h: float, d: float, qty: int = 1, **extra) -> None:
        nonlocal pos
        modules.append({
            "module_type": mtype,
            "position_index": pos,
            "width": w,
            "height": h,
            "depth": d,
            "quantity": qty,
            "material": material,
            "color": color,
            "hardware_specs": extra.get("hardware_specs"),
            "price": 0.0,
        })
        pos += 1

    if ftype == "wardrobe":
        # 衣柜: 顶板 + 底板 + 2 侧板 + 背板 + 层板(每 400mm 一层) + 挂衣杆 + 抽屉
        add("top", W, design.panel_thickness, D)
        add("bottom", W, design.panel_thickness, D)
        add("side", design.panel_thickness, H, D, qty=2)
        add("back", W, H, 9.0)
        # 层板数 = 总宽 / 400,至少 2
        shelf_count = max(2, int(W / 400))
        # 每个分区下的层板
        add("shelf", W, design.panel_thickness, D - 30, qty=shelf_count)
        # 挂衣杆
        add("hanging_rod", W - 20, 25, 25, hardware_specs={"type": "衣通", "brand": design.hardware_brand})
        # 抽屉 (按宽度估算)
        drawer_count = max(1, int(W / 600))
        add("drawer", W / drawer_count - 10, 200, D - 30, qty=drawer_count,
            hardware_specs={"slide": "450mm 缓冲", "brand": design.hardware_brand})
        # 门板
        door_count = max(2, int(W / 500))
        add("door", W / door_count, H, design.panel_thickness, qty=door_count)
    elif ftype == "cabinet":
        # 橱柜: 顶板 + 底板 + 2 侧板 + 背板 + 层板 + 门板
        add("top", W, design.panel_thickness, D)
        add("bottom", W, design.panel_thickness, D)
        add("side", design.panel_thickness, H, D, qty=2)
        add("back", W, H, 9.0)
        add("shelf", W, design.panel_thickness, D - 30, qty=max(1, int(H / 350)))
        door_count = max(2, int(W / 500))
        add("door", W / door_count, H, design.panel_thickness, qty=door_count)
    elif ftype == "bookshelf":
        # 书柜: 顶板 + 底板 + 2 侧板 + 背板 + 层板 (按高度 350mm 一层)
        add("top", W, design.panel_thickness, D)
        add("bottom", W, design.panel_thickness, D)
        add("side", design.panel_thickness, H, D, qty=2)
        add("back", W, H, 9.0)
        shelf_count = max(2, int(H / 350))
        add("shelf", W, design.panel_thickness, D - 20, qty=shelf_count)
    elif ftype == "shoe_cabinet":
        # 鞋柜: 顶板 + 底板 + 2 侧板 + 背板 + 层板 (按高度 200mm 一层)
        add("top", W, design.panel_thickness, D)
        add("bottom", W, design.panel_thickness, D)
        add("side", design.panel_thickness, H, D, qty=2)
        add("back", W, H, 9.0)
        shelf_count = max(2, int(H / 200))
        add("shelf", W, design.panel_thickness, D - 20, qty=shelf_count)
        door_count = max(1, int(W / 500))
        add("door", W / door_count, H, design.panel_thickness, qty=door_count)
    elif ftype == "tv_cabinet":
        # 电视柜: 顶板 + 底板 + 2 侧板 + 背板 + 门板
        add("top", W, design.panel_thickness, D)
        add("bottom", W, design.panel_thickness, D)
        add("side", design.panel_thickness, H, D, qty=2)
        add("back", W, H, 9.0)
        door_count = max(2, int(W / 500))
        add("door", W / door_count, H, design.panel_thickness, qty=door_count)
    elif ftype == "bed":
        # 床: 床头板 + 床侧板×2 + 床尾板 + 床板
        add("back", W, 1000.0, design.panel_thickness)  # 床头板
        add("side", design.panel_thickness, H, D, qty=2)
        add("bottom", W, design.panel_thickness, 200.0)  # 床尾板
        add("shelf", W, 18.0, D)  # 床板
    elif ftype == "door":
        # 门: 门板 + 框
        add("door", W, H, design.panel_thickness)
        add("side", 60.0, H, design.panel_thickness, qty=2)  # 门框竖
        add("top", W, 60.0, design.panel_thickness)
        add("bottom", W, 60.0, design.panel_thickness)
    else:
        # 默认: 顶+底+侧×2+背
        add("top", W, design.panel_thickness, D)
        add("bottom", W, design.panel_thickness, D)
        add("side", design.panel_thickness, H, D, qty=2)
        add("back", W, H, 9.0)

    return modules


async def apply_parametric_design(db: AsyncSession, design: CustomFurnitureDesign) -> list[FurnitureModule]:
    """执行参数化设计,写入数据库并返回模块列表"""
    # 先清空已有模块
    existing = await list_modules(db, design.id)
    for m in existing:
        await db.delete(m)
    await db.flush()

    module_dicts = parametric_design(design)
    created: list[FurnitureModule] = []
    for md in module_dicts:
        module = FurnitureModule(design_id=design.id, **md)
        db.add(module)
        created.append(module)

    design.status = "designed"
    await db.commit()
    for m in created:
        await db.refresh(m)
    return created


# ── 板材计算 ──


def _is_panel_module(module_type: str) -> bool:
    """判断是否为板材类模块(需要计算展开面积)"""
    return module_type in {"top", "bottom", "side", "back", "shelf"}


def _is_door_module(module_type: str) -> bool:
    return module_type == "door"


def compute_panels(design: CustomFurnitureDesign) -> dict:
    """板材计算

    返回:
      - total_panel_area_m2: 总展开面积(㎡)
      - panel_sheets: 板材用量(张)
      - hardware_list: 五金件清单
    """
    total_area_m2 = 0.0
    hardware_list: list[dict] = []

    for module in design.modules:
        qty = int(module.quantity or 1)
        if _is_panel_module(module.module_type):
            # 单块面积 (mm² → m²)
            area = (float(module.width or 0) * float(module.height or 0)) / 1e6
            total_area_m2 += area * qty
        elif module.module_type == "hanging_rod":
            hardware_list.append({
                "name": "衣通",
                "spec": f"{module.width:.0f}mm",
                "quantity": qty,
                "unit_price": HARDWARE_UNIT_PRICE["hanging_rod"],
                "total_price": HARDWARE_UNIT_PRICE["hanging_rod"] * qty,
            })
        elif module.module_type == "drawer":
            qty_i = qty
            hardware_list.append({
                "name": "抽屉滑轨",
                "spec": "450mm 缓冲",
                "quantity": qty_i * 2,  # 每抽屉 2 副滑轨
                "unit_price": HARDWARE_UNIT_PRICE["slide"],
                "total_price": HARDWARE_UNIT_PRICE["slide"] * qty_i * 2,
            })
            hardware_list.append({
                "name": "拉手",
                "spec": "锌合金",
                "quantity": qty_i,
                "unit_price": HARDWARE_UNIT_PRICE["handle"],
                "total_price": HARDWARE_UNIT_PRICE["handle"] * qty_i,
            })

    # 门板产生铰链
    door_modules = [m for m in design.modules if _is_door_module(m.module_type)]
    hinge_count = 0
    for m in door_modules:
        qty = int(m.quantity or 1)
        # 每扇门按高度估算铰链数: ≤1000mm 2个,≤1500mm 3个,>1500mm 4个
        h = float(m.height or 0)
        per_door = 2 if h <= 1000 else (3 if h <= 1500 else 4)
        hinge_count += per_door * qty
    if hinge_count > 0:
        hardware_list.append({
            "name": "铰链",
            "spec": "全阻尼",
            "quantity": hinge_count,
            "unit_price": HARDWARE_UNIT_PRICE["hinge"],
            "total_price": HARDWARE_UNIT_PRICE["hinge"] * hinge_count,
        })

    # 板材用量(张) = 面积 / (单张面积 × 利用率)
    effective_per_sheet = PANEL_SHEET_AREA_M2 * PANEL_UTILIZATION
    panel_sheets = round(total_area_m2 / effective_per_sheet, 2) if effective_per_sheet > 0 else 0.0

    return {
        "total_panel_area_m2": round(total_area_m2, 3),
        "panel_sheets": panel_sheets,
        "hardware_list": hardware_list,
    }


# ── 价格估算 ──


def estimate_price(design: CustomFurnitureDesign) -> dict:
    """价格估算

    总价 = 板材面积 × 单价 + 五金数量 × 单价 + 门板面积 × 单价 + 加工费
    """
    panel_result = compute_panels(design)
    panel_area = panel_result["total_panel_area_m2"]

    # 板材费用
    panel_unit = PANEL_UNIT_PRICE.get(design.panel_material, PANEL_UNIT_PRICE["颗粒板"])
    panel_cost = panel_area * panel_unit

    # 五金费用
    hardware_cost = sum(h["total_price"] for h in panel_result["hardware_list"])

    # 门板费用 (按门板面积计算)
    door_area_m2 = 0.0
    for m in design.modules:
        if _is_door_module(m.module_type):
            qty = int(m.quantity or 1)
            door_area_m2 += (float(m.width or 0) * float(m.height or 0)) / 1e6 * qty
    door_cost = door_area_m2 * DOOR_UNIT_PRICE_M2

    # 加工费
    process_cost = PROCESS_FEE if design.modules else 0.0

    total = panel_cost + hardware_cost + door_cost + process_cost

    return {
        "panel_cost": round(panel_cost, 2),
        "hardware_cost": round(hardware_cost, 2),
        "door_cost": round(door_cost, 2),
        "process_cost": round(process_cost, 2),
        "total_price": round(total, 2),
    }


# ── BOM 生成 ──


async def generate_bom(db: AsyncSession, design: CustomFurnitureDesign) -> list[FurnitureBOM]:
    """生成拆单 BOM: 板材 + 五金 + 配件 + 门板"""
    # 清空已有 BOM
    await _clear_boms(db, design.id)
    await db.flush()

    panel_result = compute_panels(design)
    supplier = f"{design.hardware_brand} 体系供应商"

    boms: list[FurnitureBOM] = []

    # 1. 板材汇总
    if panel_result["total_panel_area_m2"] > 0:
        unit_price = PANEL_UNIT_PRICE.get(design.panel_material, PANEL_UNIT_PRICE["颗粒板"])
        qty = panel_result["panel_sheets"]
        total = qty * unit_price
        boms.append(FurnitureBOM(
            design_id=design.id,
            item_name=f"{design.panel_material} 板材",
            item_type="panel",
            spec=f"{design.panel_thickness:.0f}mm 厚,共 {panel_result['total_panel_area_m2']:.2f}㎡",
            material=design.panel_material,
            quantity=qty,
            unit="张",
            unit_price=unit_price,
            total_price=round(total, 2),
            supplier=supplier,
            notes=f"利用率 {PANEL_UTILIZATION*100:.0f}%",
        ))

    # 2. 五金清单
    for hw in panel_result["hardware_list"]:
        boms.append(FurnitureBOM(
            design_id=design.id,
            item_name=hw["name"],
            item_type="hardware",
            spec=hw["spec"],
            material=design.hardware_brand,
            quantity=hw["quantity"],
            unit="个" if hw["name"] in ("铰链", "拉手") else ("副" if hw["name"] == "抽屉滑轨" else "根"),
            unit_price=hw["unit_price"],
            total_price=round(hw["total_price"], 2),
            supplier=design.hardware_brand,
        ))

    # 3. 配件: 三合一连接件 + 螺丝包
    panel_modules = [m for m in design.modules if _is_panel_module(m.module_type)]
    connector_count = sum(int(m.quantity or 1) * 4 for m in panel_modules)  # 每板 4 个三合一
    if connector_count > 0:
        unit_price = HARDWARE_UNIT_PRICE["connector"]
        boms.append(FurnitureBOM(
            design_id=design.id,
            item_name="三合一连接件",
            item_type="accessory",
            spec="偏心轮+螺杆+预埋件",
            material="碳钢",
            quantity=connector_count,
            unit="个",
            unit_price=unit_price,
            total_price=round(unit_price * connector_count, 2),
            supplier=design.hardware_brand,
        ))
    # 螺丝包 (按模块数)
    if design.modules:
        screw_qty = max(1, len(design.modules) // 2)
        unit_price = HARDWARE_UNIT_PRICE["screw_kit"]
        boms.append(FurnitureBOM(
            design_id=design.id,
            item_name="螺丝包",
            item_type="accessory",
            spec="M4×30 组合装",
            material="碳钢",
            quantity=screw_qty,
            unit="套",
            unit_price=unit_price,
            total_price=round(unit_price * screw_qty, 2),
            supplier=design.hardware_brand,
        ))

    # 4. 门板
    door_modules = [m for m in design.modules if _is_door_module(m.module_type)]
    if door_modules:
        door_area_m2 = 0.0
        door_count = 0
        for m in door_modules:
            qty = int(m.quantity or 1)
            door_area_m2 += (float(m.width or 0) * float(m.height or 0)) / 1e6 * qty
            door_count += qty
        unit_price = DOOR_UNIT_PRICE_M2
        total = door_area_m2 * unit_price
        boms.append(FurnitureBOM(
            design_id=design.id,
            item_name="定制门板",
            item_type="door",
            spec=f"共 {door_count} 扇,{door_area_m2:.2f}㎡",
            material=design.panel_material,
            quantity=door_count,
            unit="扇",
            unit_price=unit_price,
            total_price=round(total, 2),
            supplier=supplier,
            notes="含封边、打孔",
        ))

    for b in boms:
        db.add(b)

    # 同步更新设计总价
    price = estimate_price(design)
    design.total_price = price["total_price"]
    design.status = "quoted"

    await db.commit()
    for b in boms:
        await db.refresh(b)
    return boms


# ── 规格校验 ──


def validate_furniture_spec(design: CustomFurnitureDesign) -> dict:
    """规格校验

    规则:
      - 衣柜深度 ≥ 550mm
      - 鞋柜深度 ≥ 300mm
      - 书柜层板跨度 ≤ 800mm
      - 抽屉宽度 ≤ 1000mm
      - 门板宽度 ≤ 600mm (单开门)
    """
    issues: list[dict] = []

    if design.furniture_type == "wardrobe":
        if design.total_depth < 550:
            issues.append({
                "field": "total_depth",
                "message": f"衣柜深度应 ≥ 550mm (挂衣区),当前 {design.total_depth:.0f}mm",
                "severity": "high",
            })

    if design.furniture_type == "shoe_cabinet":
        if design.total_depth < 300:
            issues.append({
                "field": "total_depth",
                "message": f"鞋柜深度应 ≥ 300mm,当前 {design.total_depth:.0f}mm",
                "severity": "medium",
            })

    # 书柜层板跨度
    if design.furniture_type == "bookshelf":
        for m in design.modules:
            if m.module_type == "shelf" and float(m.width or 0) > 800:
                issues.append({
                    "field": "shelf_width",
                    "message": f"书柜层板跨度 {m.width:.0f}mm 超过 800mm,易变形,建议增加中隔板",
                    "severity": "medium",
                })

    # 抽屉宽度
    for m in design.modules:
        if m.module_type == "drawer" and float(m.width or 0) > 1000:
            issues.append({
                "field": "drawer_width",
                "message": f"抽屉宽度 {m.width:.0f}mm 超过 1000mm,滑轨负荷过大",
                "severity": "high",
            })

    # 门板宽度
    for m in design.modules:
        if m.module_type == "door" and float(m.width or 0) > 600:
            issues.append({
                "field": "door_width",
                "message": f"单开门宽度 {m.width:.0f}mm 超过 600mm,建议改为对开门",
                "severity": "medium",
            })

    return {
        "valid": len(issues) == 0,
        "issues": issues,
    }

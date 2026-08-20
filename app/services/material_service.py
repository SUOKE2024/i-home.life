import json
import time
from types import SimpleNamespace
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.eco_material import MaterialEcoCert
from app.models.floorplan import FloorPlan
from app.models.material import MaterialCategory, Material, BOMItem
from app.models.project import Floor, Room
from app.models.budget import Budget


# 标准损耗系数
WASTE_FACTOR = {
    "flooring": 1.05,   # 地面 5% 损耗
    "wall": 1.08,       # 墙面 8% 损耗
    "ceiling": 1.05,    # 顶面 5% 损耗
}

# F44 AI 选材强制提示环保等级（对标 HC-003 环保等级硬约束）：
# 材料无环保认证数据时诚实标注 unverified，不伪装认证等级。
ECO_NOTICE_UNVERIFIED = "该材料未登记环保等级（HC-003 合规要求建议选用 ENF/E0 认证材料）"

# 墙地比（墙面面积 / 地面面积）经验值
WALL_TO_FLOOR_RATIO = 2.8

# 涂料每桶覆盖面积（18L 桶，1底2面 ≈ 90 m²）
PAINT_COVERAGE_PER_BUCKET = 90.0

# 各房间类型默认物料品类映射
ROOM_CATEGORY_MAP: dict[str, list[str]] = {
    "bedroom": ["flooring", "wall", "ceiling", "doors_windows", "custom_furniture"],
    "living": ["flooring", "wall", "ceiling", "doors_windows"],
    "kitchen": ["flooring", "wall", "ceiling", "kitchen_bath", "custom_furniture"],
    "bathroom": ["flooring", "wall", "ceiling", "kitchen_bath", "doors_windows"],
    "balcony": ["flooring", "wall", "ceiling"],
    "dining": ["flooring", "wall", "ceiling"],
    "study": ["flooring", "wall", "ceiling", "custom_furniture"],
}


# ── 简单 TTL 内存缓存（v1.1.12 性能优化） ──
# 适用于高频读、低频写的目录数据（物料分类、家具目录）
_CACHE_TTL = 60  # 秒
_cache_store: dict[str, tuple[float, Any]] = {}


def _cache_get(key: str) -> Any | None:
    """命中返回缓存值，未命中或过期返回 None"""
    entry = _cache_store.get(key)
    if entry is None:
        return None
    exp_at, value = entry
    if time.monotonic() >= exp_at:
        _cache_store.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Any, ttl: int = _CACHE_TTL) -> None:
    _cache_store[key] = (time.monotonic() + ttl, value)


def invalidate_material_cache() -> None:
    """清除物料/分类缓存（写操作后调用）"""
    _cache_store.pop("categories", None)
    # 清除所有 materials: 前缀的缓存
    keys_to_remove = [k for k in _cache_store if k.startswith("materials:")]
    for k in keys_to_remove:
        _cache_store.pop(k, None)


# ── F44 环保等级强制提示辅助 ──


async def _load_eco_certs(db: AsyncSession, material_ids: list[str]) -> dict[str, MaterialEcoCert]:
    """批量加载材料环保认证（MaterialEcoCert）：material_id -> cert（无认证的材料不含在内）"""
    if not material_ids:
        return {}
    result = await db.execute(
        select(MaterialEcoCert).where(MaterialEcoCert.material_id.in_(material_ids))
    )
    return {cert.material_id: cert for cert in result.scalars().all()}


def _eco_notice(grade: str, cert: MaterialEcoCert | None) -> str:
    """环保等级提示文案：有认证如实标注，无认证诚实提示 HC-003 合规要求"""
    if cert:
        return f"环保等级 {grade}（认证：{cert.certification}，来源：{cert.source}）"
    return ECO_NOTICE_UNVERIFIED


async def get_categories(db: AsyncSession) -> list[MaterialCategory]:
    cached = _cache_get("categories")
    if cached is not None:
        return cached
    result = await db.execute(
        select(MaterialCategory).order_by(MaterialCategory.code)
    )
    categories = list(result.scalars().all())
    _cache_set("categories", categories)
    return categories


async def get_category_by_id(db: AsyncSession, category_id: str) -> MaterialCategory | None:
    result = await db.execute(
        select(MaterialCategory).where(MaterialCategory.id == category_id)
    )
    return result.scalar_one_or_none()


async def create_category(db: AsyncSession, data: dict) -> MaterialCategory:
    category = MaterialCategory(**data)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    invalidate_material_cache()
    return category


async def get_materials(
    db: AsyncSession, category_id: str | None = None, skip: int = 0, limit: int = 50
) -> list[Material]:
    stmt = (
        select(Material)
        .where(Material.is_active.is_(True))
        .options(selectinload(Material.category))
        .offset(skip)
        .limit(limit)
        .order_by(Material.created_at.desc())
    )
    if category_id:
        stmt = stmt.where(Material.category_id == category_id)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_material_by_id(db: AsyncSession, material_id: str) -> Material | None:
    result = await db.execute(
        select(Material)
        .where(Material.id == material_id)
        .options(selectinload(Material.category))
    )
    return result.scalar_one_or_none()


async def create_material(db: AsyncSession, data: dict) -> Material:
    material = Material(**data)
    db.add(material)
    await db.commit()
    await db.refresh(material)
    invalidate_material_cache()
    return await get_material_by_id(db, material.id)


async def get_current_bom_version(db: AsyncSession, project_id: str) -> int:
    """当前 BOM 工作集版本号（F7 版本管理；无 BOM 时默认 1）"""
    result = await db.execute(
        select(func.max(BOMItem.version)).where(BOMItem.project_id == project_id)
    )
    max_version = result.scalar()
    return int(max_version) if max_version else 1


async def add_bom_item(db: AsyncSession, data: dict) -> BOMItem:
    total = data["quantity"] * data["unit_price"]
    # F7: 新 BOM 项加入当前工作集版本
    version = await get_current_bom_version(db, data["project_id"])
    bom_item = BOMItem(**data, total_price=total, version=version)
    db.add(bom_item)
    await db.commit()
    await db.refresh(bom_item)
    return bom_item


async def get_project_bom(db: AsyncSession, project_id: str) -> list[BOMItem]:
    # F7: 仅返回当前工作集版本（最新版本），历史快照不参与日常 BOM 视图
    current_version = await get_current_bom_version(db, project_id)
    result = await db.execute(
        select(BOMItem)
        .where(BOMItem.project_id == project_id, BOMItem.version == current_version)
        .options(selectinload(BOMItem.material).selectinload(Material.category))
        .order_by(BOMItem.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_bom_item(db: AsyncSession, bom_id: str) -> bool:
    result = await db.execute(select(BOMItem).where(BOMItem.id == bom_id))
    item = result.scalar_one_or_none()
    if not item:
        return False
    await db.delete(item)
    await db.commit()
    return True


async def get_bom_summary(db: AsyncSession, project_id: str) -> dict | None:
    """BOM 汇总（按品类聚合） — F6/F7 配套"""
    bom_items = await get_project_bom(db, project_id)
    if not bom_items:
        return None

    cat_map: dict[str, dict] = {}
    total_price = 0.0
    for item in bom_items:
        cat = item.material.category if item.material and item.material.category else None
        code = cat.code if cat else "unknown"
        name = cat.name if cat else "未分类"
        if code not in cat_map:
            cat_map[code] = {
                "category_code": code,
                "category_name": name,
                "item_count": 0,
                "total_price": 0.0,
            }
        cat_map[code]["item_count"] += 1
        cat_map[code]["total_price"] = round(cat_map[code]["total_price"] + item.total_price, 2)
        total_price = round(total_price + item.total_price, 2)

    return {
        "project_id": project_id,
        "total_items": len(bom_items),
        "total_price": total_price,
        "categories": list(cat_map.values()),
    }


# ── F7 BOM 版本管理与差异标注 ──


async def snapshot_bom_version(db: AsyncSession, project_id: str) -> dict:
    """F7 手动打版本快照：将当前工作集（最新版本）复制为 version+1

    快照后旧版本不可变，新版本作为工作集承接后续 BOM 编辑，
    支持跨版本差异对比（新增/删除/价格变化）。
    """
    current_version = await get_current_bom_version(db, project_id)
    result = await db.execute(
        select(BOMItem).where(
            BOMItem.project_id == project_id,
            BOMItem.version == current_version,
        )
    )
    items = list(result.scalars().all())
    if not items:
        raise ValueError("PROJECT_HAS_NO_BOM")

    new_version = current_version + 1
    for item in items:
        db.add(BOMItem(
            project_id=item.project_id,
            material_id=item.material_id,
            room_id=item.room_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=item.total_price,
            note=item.note,
            status=item.status,
            version=new_version,
            quantity_source=item.quantity_source or "empirical",
            fallback_note=item.fallback_note,
        ))
    await db.commit()

    # 全链路编排：BOM 版本定稿 → 自动采购建议（受 lifecycle_orchestration_enabled flag 控制）
    from app.services.lifecycle_events import emit_bom_generated
    await emit_bom_generated(project_id, bom_version=new_version)

    return {
        "project_id": project_id,
        "snapshot_version": current_version,
        "new_version": new_version,
        "copied_items": len(items),
    }


async def get_bom_versions(db: AsyncSession, project_id: str) -> dict:
    """F7 BOM 版本列表（含各版本条目数与总价）"""
    result = await db.execute(
        select(
            BOMItem.version,
            func.count(BOMItem.id),
            func.sum(BOMItem.total_price),
            func.min(BOMItem.created_at),
        )
        .where(BOMItem.project_id == project_id)
        .group_by(BOMItem.version)
        .order_by(BOMItem.version.asc())
    )
    versions = []
    for version, cnt, price, created_at in result.all():
        versions.append({
            "version": int(version),
            "item_count": int(cnt),
            "total_price": round(float(price or 0.0), 2),
            "created_at": created_at.isoformat() if created_at else None,
        })
    return {
        "project_id": project_id,
        "versions": versions,
        "current_version": versions[-1]["version"] if versions else None,
    }


async def diff_bom_versions(
    db: AsyncSession,
    project_id: str,
    from_version: int,
    to_version: int,
) -> dict:
    """F7 BOM 版本差异对比：新增 / 删除 / 数量与价格变化标注

    以 material_id 为键对比两个版本的 BOM 项：
    - added：仅在 to_version 出现
    - removed：仅在 from_version 出现
    - changed：两版本均有但数量或单价变化（change_type 标注）
    - unchanged：完全一致
    """
    result = await db.execute(
        select(BOMItem)
        .where(
            BOMItem.project_id == project_id,
            BOMItem.version.in_([from_version, to_version]),
        )
        .options(selectinload(BOMItem.material).selectinload(Material.category))
    )
    items = list(result.scalars().all())
    from_items = {i.material_id: i for i in items if i.version == from_version}
    to_items = {i.material_id: i for i in items if i.version == to_version}

    def _entry(item: BOMItem) -> dict:
        mat = item.material
        return {
            "material_id": item.material_id,
            "material_name": mat.name if mat else None,
            "material_sku": mat.sku if mat else None,
            "category": mat.category.name if mat and mat.category else None,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "total_price": item.total_price,
        }

    added: list[dict] = []
    removed: list[dict] = []
    changed: list[dict] = []
    unchanged: list[dict] = []

    for mid in sorted(set(from_items) | set(to_items)):
        old = from_items.get(mid)
        new = to_items.get(mid)
        if old is None:
            added.append(_entry(new))
        elif new is None:
            removed.append(_entry(old))
        else:
            qty_delta = round(new.quantity - old.quantity, 2)
            price_delta = round(new.unit_price - old.unit_price, 2)
            if abs(qty_delta) <= 1e-6 and abs(price_delta) <= 1e-6:
                unchanged.append(_entry(new))
                continue
            if abs(price_delta) > 1e-6 and abs(qty_delta) <= 1e-6:
                change_type = "price"
            elif abs(qty_delta) > 1e-6 and abs(price_delta) <= 1e-6:
                change_type = "quantity"
            else:
                change_type = "quantity_and_price"
            changed.append({
                **_entry(old),
                "from_quantity": old.quantity,
                "from_unit_price": old.unit_price,
                "to_quantity": new.quantity,
                "to_unit_price": new.unit_price,
                "quantity_delta": qty_delta,
                "price_delta": price_delta,
                "change_type": change_type,
            })

    return {
        "project_id": project_id,
        "from_version": from_version,
        "to_version": to_version,
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": len(unchanged),
            "total": len(added) + len(removed) + len(changed) + len(unchanged),
        },
    }


def _calc_material_quantity(category_code: str, material: Material, room: Any) -> float:
    """根据品类、物料和房间计算用量（room 可为 Room 或 SimpleNamespace 兜底对象）"""
    area = room.area or 10.0

    if category_code == "flooring":
        return round(area * WASTE_FACTOR["flooring"], 2)
    if category_code == "ceiling":
        return round(area * WASTE_FACTOR["ceiling"], 2)
    if category_code == "wall":
        wall_area = area * WALL_TO_FLOOR_RATIO
        # 涂料按桶计
        if material.unit and "桶" in material.unit:
            buckets = wall_area / PAINT_COVERAGE_PER_BUCKET
            # 整桶向上取整
            return float(int(buckets) + (1 if buckets % 1 > 0 else 0))
        return round(wall_area * WASTE_FACTOR["wall"], 2)
    if category_code == "doors_windows":
        # 卧室/卫生间按 1 扇门
        if room.room_type in ("bedroom", "bathroom"):
            return 1.0
        return 0.0
    if category_code == "kitchen_bath":
        # 卫生间默认 1 套卫浴（马桶/花洒/洗手盆各 1）
        # 厨房默认 1 个水槽 + 1 m 台面
        if room.room_type == "bathroom":
            return 1.0
        if room.room_type == "kitchen":
            # 台面按 m 计，其他按个/套计
            if material.unit == "m":
                return 3.0
            return 1.0
        return 0.0
    if category_code == "custom_furniture":
        # 卧室：衣柜按投影面积 = 房间面积 × 0.6
        # 厨房：橱柜按 m 计，默认 3m
        # 书房：书柜按 m² 计，默认房间面积 × 0.3
        if room.room_type == "bedroom":
            return round(area * 0.6, 2)
        if room.room_type == "kitchen":
            return 3.0
        if room.room_type == "study":
            return round(area * 0.3, 2)
        return 0.0
    return 1.0


def _guess_room_type(name: str) -> str:
    """房间名 → ROOM_CATEGORY_MAP key 粗略推断（无房间明细时的经验法兜底用）"""
    if any(k in name for k in ("卧室", "主卧", "次卧", "儿童房", "客房")):
        return "bedroom"
    if "厨" in name:
        return "kitchen"
    if any(k in name for k in ("卫生", "浴室", "洗手间", "厕所")):
        return "bathroom"
    if "阳台" in name:
        return "balcony"
    if "餐" in name:
        return "dining"
    if any(k in name for k in ("书", "工作", "书房")):
        return "study"
    return "living"


async def generate_bom_for_project(db: AsyncSession, project_id: str) -> list[BOMItem]:  # noqa: C901
    """F6 BOM 自动生成

    数据源优先级（F6 几何算量接入）：
    1. 项目有 active floorplan 且几何算量成功 → 墙体/地面/涂料/吊顶用量
       取自 quantity_takeoff_service 的派生量（quantity_source=geometric_takeoff）
    2. 几何算量失败/无 floorplan → 回退面积×标准用量经验法
       （quantity_source=empirical，fallback_note 标注）

    若项目已有 BOM 项则抛出 ValueError("PROJECT_ALREADY_HAS_BOM")。
    若无房间且无户型占位则返回空列表。
    （2026-08-20 生产验证观察项：有 FloorPlan 占位但无 Room 行时，此前直接 404
    无兜底；现按户型面积×标准用量经验法生成，quantity_source=empirical + fallback_note。）
    """
    existing = await get_project_bom(db, project_id)
    if existing:
        raise ValueError("PROJECT_ALREADY_HAS_BOM")

    # 取项目下所有房间
    room_result = await db.execute(
        select(Room).join(Floor, Floor.id == Room.floor_id).where(Floor.project_id == project_id)
    )
    rooms = list(room_result.scalars().all())
    # 无 Room 行时的经验法兜底标志（有户型占位则合成房间规格）
    no_rooms_fallback = False
    if not rooms:
        fp_result = await db.execute(
            select(FloorPlan)
            .where(FloorPlan.project_id == project_id)
            .order_by(FloorPlan.is_active.desc(), FloorPlan.created_at.desc())
        )
        floorplan = fp_result.scalars().first()
        if not floorplan or (not floorplan.room_count and not floorplan.total_area):
            return []
        no_rooms_fallback = True
        plan_area = floorplan.total_area or 0.0
        per_room = round(plan_area / max(floorplan.room_count, 1), 2) if plan_area > 0 else 0.0
        try:
            status_map = json.loads(floorplan.room_status or "{}") or {}
        except Exception:  # noqa: BLE001
            status_map = {}
        room_specs = [(name, _guess_room_type(name), per_room) for name in status_map]
        if not room_specs:
            room_specs = [("客厅", "living", per_room if per_room > 0 else plan_area)]
    else:
        room_specs = [(r.name or r.room_type, r.room_type, r.area or 0.0) for r in rooms]

    # 取所有启用物料，按品类 code 取首条作为默认物料
    mat_result = await db.execute(
        select(Material)
        .where(Material.is_active.is_(True))
        .options(selectinload(Material.category))
        .order_by(Material.created_at.asc())
    )
    all_materials = list(mat_result.scalars().all())
    materials_by_category: dict[str, Material] = {}
    for m in all_materials:
        code = m.category.code if m.category else None
        if code and code not in materials_by_category:
            materials_by_category[code] = m

    # ── F6 几何算量优先：从 active floorplan 派生墙体/地面/涂料/吊顶用量 ──
    geometric = None
    try:
        from app.services.quantity_takeoff_service import forward_takeoff_for_project
        geometric = await forward_takeoff_for_project(db, project_id)
    except Exception:
        geometric = None

    geometric_quantities: dict[str, float] = {}
    if geometric is not None:
        s = geometric.summary
        if s.get("total_floor_area_m2"):
            geometric_quantities["flooring"] = round(s["total_floor_area_m2"], 2)
        if s.get("total_ceiling_area_m2"):
            geometric_quantities["ceiling"] = round(s["total_ceiling_area_m2"], 2)
        wall_mat = materials_by_category.get("wall")
        if wall_mat and wall_mat.unit and "桶" in wall_mat.unit:
            # 涂料按桶：几何算量的底漆+面漆桶数（18L/桶）
            buckets = sum(
                (p.get("primer_count") or 0) + (p.get("finish_count") or 0)
                for p in geometric.paints
            )
            if buckets > 0:
                geometric_quantities["wall"] = float(buckets)
        elif s.get("total_paint_area_m2"):
            geometric_quantities["wall"] = round(s["total_paint_area_m2"], 2)

    fallback_note = None
    if geometric is None:
        fallback_note = "无可用户型几何数据，采用面积×标准用量经验估算"
    if no_rooms_fallback:
        # 户型占位兜底优先：即使 forward_takeoff 返回空摘要（无房间几何），
        # 也应标注「户型占位经验估算」而非仅 generic 提示
        fallback_note = "项目仅有户型占位无房间明细，按户型面积×标准用量经验估算"

    # 聚合：material_id -> (quantity, rooms, source)
    aggregated: dict[str, dict] = {}
    for rname, rtype, r_area in room_specs:
        cats = ROOM_CATEGORY_MAP.get(rtype, ["flooring", "wall", "ceiling"])
        for code in cats:
            if code in geometric_quantities:
                continue  # 该品类已由几何算量填充（项目级汇总量）
            mat = materials_by_category.get(code)
            if not mat:
                continue
            room_like = SimpleNamespace(area=r_area, room_type=rtype)
            qty = _calc_material_quantity(code, mat, room_like)
            if qty <= 0:
                continue
            if mat.id not in aggregated:
                aggregated[mat.id] = {"quantity": 0.0, "rooms": [], "source": "empirical"}
            aggregated[mat.id]["quantity"] = round(aggregated[mat.id]["quantity"] + qty, 2)
            aggregated[mat.id]["rooms"].append(rname)

    for code, qty in geometric_quantities.items():
        mat = materials_by_category.get(code)
        if not mat or qty <= 0:
            continue
        if mat.id not in aggregated:
            aggregated[mat.id] = {"quantity": 0.0, "rooms": [], "source": "geometric_takeoff"}
        aggregated[mat.id]["quantity"] = round(qty, 2)
        aggregated[mat.id]["rooms"].append("几何算量（floorplan）")

    # F44 AI 选材强制提示环保等级：创建 BOM 项时按 MaterialEcoCert 认证数据
    # 拼接环保提示（无认证 → unverified 诚实标注，不伪装认证等级）
    certs = await _load_eco_certs(db, list(aggregated.keys()))

    # 创建 BOM 项（F7: 写入当前工作集版本）
    current_version = await get_current_bom_version(db, project_id)
    new_items: list[BOMItem] = []
    for mat_id, info in aggregated.items():
        mat = next(m for m in all_materials if m.id == mat_id)
        total = round(info["quantity"] * mat.unit_price, 2)
        source = info.get("source", "empirical")
        cert = certs.get(mat_id)
        grade = cert.eco_grade if cert else "unverified"
        eco_notice = _eco_notice(grade, cert)
        if source == "geometric_takeoff":
            note = "自动生成（来源：户型几何算量 floorplan）"
        else:
            note = f"自动生成（覆盖房间：{', '.join(info['rooms'])}）"
        note = f"{note}；{eco_notice}"
        item = BOMItem(
            project_id=project_id,
            material_id=mat_id,
            quantity=info["quantity"],
            unit_price=mat.unit_price,
            total_price=total,
            note=note,
            status="auto_generated",
            version=current_version,
            quantity_source=source,
            fallback_note=fallback_note if source == "empirical" else None,
        )
        db.add(item)
        new_items.append(item)

    await db.commit()

    # 重新查询以加载关联（仅当前工作集版本）
    result = await db.execute(
        select(BOMItem)
        .where(BOMItem.project_id == project_id, BOMItem.version == current_version)
        .options(selectinload(BOMItem.material).selectinload(Material.category))
        .order_by(BOMItem.created_at.asc())
    )
    items = list(result.scalars().all())

    # 补充 eco_grade/eco_notice 字段（动态属性，认证数据与创建时一致）
    for item in items:
        cert = certs.get(item.material_id)
        grade = cert.eco_grade if cert else "unverified"
        item.eco_grade = grade
        item.eco_notice = _eco_notice(grade, cert)
    return items


async def search_materials(
    db: AsyncSession, keyword: str, skip: int = 0, limit: int = 50
) -> list[Material]:
    """按名称/SKU/品牌模糊搜索物料"""
    pattern = f"%{keyword}%"
    stmt = (
        select(Material)
        .where(
            Material.is_active.is_(True),
            (Material.name.ilike(pattern))
            | (Material.sku.ilike(pattern))
            | (Material.brand.ilike(pattern)),
        )
        .options(selectinload(Material.category))
        .offset(skip)
        .limit(limit)
        .order_by(Material.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── 房间类型 → 物料品类映射 ──
ROOM_TO_CATEGORY_MAP: dict[str, list[str]] = {
    "living": ["flooring", "wall", "ceiling", "doors_windows"],
    "bedroom": ["flooring", "wall", "ceiling", "doors_windows", "custom_furniture"],
    "kitchen": ["flooring", "wall", "ceiling", "kitchen_bath", "custom_furniture"],
    "bathroom": ["flooring", "wall", "ceiling", "kitchen_bath", "doors_windows"],
    "dining": ["flooring", "wall", "ceiling"],
    "study": ["flooring", "wall", "ceiling", "custom_furniture"],
    "balcony": ["flooring", "wall", "ceiling"],
}

# ── 风格 → 关键词映射 ──
STYLE_KEYWORD_MAP: dict[str, list[str]] = {
    "modern": ["现代", "简约", "极简", "现代简约"],
    "nordic": ["北欧", "斯堪的纳维亚"],
    "chinese": ["新中式", "中式", "东方"],
    "american": ["美式", "美式经典", "美式乡村"],
    "french": ["法式", "法式浪漫"],
    "industrial": ["工业", "工业风", "loft"],
    "japanese": ["日式", "和风", "侘寂"],
    "luxury": ["轻奢", "奢华", "高端"],
}


def _calc_match_score(
    material: Material,
    target_categories: list[str],
    style: str | None,
    budget_level: str | None,
) -> int:
    """计算物料匹配分数 (0-100)"""
    score = 0

    # 品类匹配 (0-50 分)
    cat_code = material.category.code if material.category else ""
    if cat_code in target_categories:
        score += 50

    # 风格匹配 (0-25 分)
    if style:
        keywords = STYLE_KEYWORD_MAP.get(style, [])
        text = (material.name or "") + " " + (material.description or "")
        for kw in keywords:
            if kw in text:
                score += 25
                break
        else:
            # 部分匹配给一半分数
            for kw in keywords:
                for sub_kw in kw:
                    if sub_kw in text:
                        score += 10
                        break

    # 品牌加分 (0-10 分)
    if material.brand:
        score += 5
        if material.brand in ("立邦", "多乐士", "三棵树", "马可波罗", "东鹏", "诺贝尔", "科勒", "TOTO", "方太", "老板", "欧派", "索菲亚"):
            score += 5

    # 规格/描述丰富度 (0-5 分)
    if material.spec and len(material.spec) > 20:
        score += 5

    # 价格合理性 (0-10 分) — 根据预算等级调整
    if budget_level:
        if budget_level == "economy" and material.unit_price <= 150:
            score += 10
        elif budget_level == "standard" and 50 <= material.unit_price <= 500:
            score += 10
        elif budget_level == "premium" and material.unit_price >= 300:
            score += 10
    else:
        score += 5  # 无预算偏好的基础分

    return min(score, 100)


def _derive_budget_level(budget: "Budget | None") -> str:
    """根据预算推断等级"""
    if not budget or not budget.total_estimated:
        return "standard"
    total = budget.total_estimated
    if total < 80000:
        return "economy"
    elif total > 200000:
        return "premium"
    return "standard"


def _estimate_environmental_grade(material: Material) -> str:
    """从物料名称/规格推断环保等级"""
    text = (material.name or "") + " " + (material.spec or "") + " " + (material.description or "")
    if "E0" in text:
        return "E0"
    if "E1" in text:
        return "E1"
    if "F4" in text or "F☆☆☆☆" in text:
        return "F4"
    if "零甲醛" in text or "无醛" in text or "ENF" in text:
        return "ENF"
    if "A+" in text or "A+级" in text:
        return "A+"
    if material.category and material.category.code in ("flooring", "custom_furniture"):
        return "E1"  # 板材类默认 E1
    return "A"


async def recommend_materials(  # noqa: C901
    db: AsyncSession,
    project_id: str,
    room_type: str | None = None,
    style: str | None = None,
    budget_level: str | None = None,  # "economy" / "standard" / "premium"
) -> dict:
    """AI 物料推荐引擎

    基于项目预算、房间类型和风格偏好，从数据库中筛选并推荐物料。
    每个品类返回 top 5 推荐，含匹配分数和推荐理由。
    """
    from app.models.budget import Budget
    from app.models.procurement import Quotation

    # 1. 获取项目预算并推断预算等级
    budget_result = await db.execute(
        select(Budget).where(Budget.project_id == project_id)
    )
    budget = budget_result.scalar_one_or_none()

    if not budget_level:
        budget_level = _derive_budget_level(budget)

    total_budget = budget.total_estimated if budget else 0.0
    if total_budget <= 0:
        total_budget = 100000.0  # 默认 10 万

    # 2. 确定目标品类
    if room_type:
        target_categories = ROOM_TO_CATEGORY_MAP.get(
            room_type, ["flooring", "wall", "ceiling"]
        )
    else:
        target_categories = None  # 不限制品类

    # 3. 查询所有活跃物料
    all_materials = await get_materials(db, limit=1000)

    # 如果指定了品类，过滤
    if target_categories:
        all_materials = [
            m for m in all_materials
            if m.category and m.category.code in target_categories
        ]

    if not all_materials:
        return {
            "project_id": project_id,
            "budget_level": budget_level,
            "total_budget": round(total_budget, 2),
            "recommendations": [],
            "total_estimated_cost": 0.0,
            "budget_utilization_percent": 0.0,
            "alternative_suggestions": ["当前数据库中暂无匹配物料，请先添加物料数据"],
        }

    # 4. 为每个物料计算匹配分数
    scored_materials: list[tuple[Material, int]] = []
    for m in all_materials:
        score = _calc_match_score(m, target_categories or [], style, budget_level)
        scored_materials.append((m, score))

    # 5. 按品类分组，每个品类取 top 5
    grouped: dict[str, list[tuple[Material, int]]] = {}
    for m, score in scored_materials:
        cat_code = m.category.code if m.category else "unknown"
        if cat_code not in grouped:
            grouped[cat_code] = []
        grouped[cat_code].append((m, score))

    # 按预算等级排序
    for cat_code in grouped:
        if budget_level == "economy":
            # 低价优先，同价格按分数降序
            grouped[cat_code].sort(key=lambda x: (x[0].unit_price, -x[1]))
        elif budget_level == "premium":
            # 高价优先，同价格按分数降序
            grouped[cat_code].sort(key=lambda x: (-x[0].unit_price, -x[1]))
        else:
            # 标准：按分数降序
            grouped[cat_code].sort(key=lambda x: -x[1])

        # 只保留 top 5
        grouped[cat_code] = grouped[cat_code][:5]

    # 6. 生成推荐结果
    recommendations: list[dict] = []
    total_material_cost = 0.0

    # 为每个物料的 supplier 做批量查询
    supplier_cache: dict[str, str] = {}  # material_id -> supplier_name

    for cat_code, items in grouped.items():
        for m, score in items:
            # 查询供应商信息 (若有报价)
            if m.id not in supplier_cache:
                q_result = await db.execute(
                    select(Quotation)
                    .where(Quotation.material_id == m.id)
                    .options(selectinload(Quotation.supplier))
                    .order_by(Quotation.unit_price.asc())
                    .limit(1)
                )
                quotation = q_result.scalar_one_or_none()
                if quotation and quotation.supplier:
                    supplier_cache[m.id] = quotation.supplier.name
                else:
                    supplier_cache[m.id] = m.brand or "未指定"

            # 估算用量（默认 50㎡面积用量）
            estimated_qty = 50.0
            cat_code_val = m.category.code if m.category else ""
            if cat_code_val in WASTE_FACTOR:
                estimated_qty = round(50.0 * WASTE_FACTOR[cat_code_val], 2)
            if cat_code_val == "wall" and m.unit and "桶" in m.unit:
                wall_area = 50.0 * WALL_TO_FLOOR_RATIO
                buckets = wall_area / PAINT_COVERAGE_PER_BUCKET
                estimated_qty = float(int(buckets) + (1 if buckets % 1 > 0 else 0))

            estimated_cost = round(estimated_qty * m.unit_price, 2)
            total_material_cost += estimated_cost

            # 生成推荐理由
            reasons: list[str] = []
            if cat_code_val in (target_categories or []):
                reasons.append("匹配目标房间类型")
            if style:
                style_kws = STYLE_KEYWORD_MAP.get(style, [])
                text = (m.name or "") + " " + (m.description or "")
                matched_kw = next((kw for kw in style_kws if kw in text), None)
                if matched_kw:
                    reasons.append(f"风格匹配「{matched_kw}」")
            if m.brand:
                reasons.append(f"品牌「{m.brand}」")
            if budget_level == "economy" and m.unit_price <= 100:
                reasons.append("经济实惠")
            elif budget_level == "premium" and m.unit_price >= 300:
                reasons.append("高端品质")
            if not reasons:
                reasons.append("综合评分较高")

            recommendations.append({
                "material_id": m.id,
                "name": m.name,
                "category": m.category.name if m.category else "未分类",
                "category_code": cat_code_val,
                "unit_price": m.unit_price,
                "unit": m.unit,
                "estimated_quantity": estimated_qty,
                "estimated_cost": estimated_cost,
                "environmental_grade": _estimate_environmental_grade(m),
                "supplier": supplier_cache.get(m.id, "未指定"),
                "brand": m.brand,
                "match_score": score,
                "reason": "，".join(reasons),
            })

    # 按匹配分数降序排列所有推荐
    recommendations.sort(key=lambda x: x["match_score"], reverse=True)

    # F44 AI 选材强制提示环保等级：以 MaterialEcoCert 认证数据为准补充
    # eco_grade/eco_notice；无环保认证数据 → eco_grade=unverified 诚实标注，不伪装。
    certs = await _load_eco_certs(db, [r["material_id"] for r in recommendations])
    for rec in recommendations:
        cert = certs.get(rec["material_id"])
        grade = cert.eco_grade if cert else "unverified"
        rec["eco_grade"] = grade
        rec["eco_notice"] = _eco_notice(grade, cert)

    # 7. 计算预算利用率
    budget_utilization = round((total_material_cost / total_budget) * 100, 1) if total_budget > 0 else 0.0

    # 8. 生成替代建议
    alternative_suggestions: list[str] = []
    if budget_utilization > 90:
        alternative_suggestions.append(
            f"推荐物料总费用 {total_material_cost:.0f} 元接近预算 {total_budget:.0f} 元（{budget_utilization}%），"
            f"建议将预算等级从 {budget_level} 调整为标准，或优先选择低价替代品"
        )
    elif budget_utilization < 30 and budget_level == "premium":
        alternative_suggestions.append(
            f"当前预算利用率仅 {budget_utilization}%，建议考虑更高品质物料"
        )
    if budget_level == "economy":
        alternative_suggestions.append("您选择了经济型预算，推荐关注性价比高的物料")
    elif budget_level == "premium":
        alternative_suggestions.append("您选择了高端预算，推荐关注环保等级高、品牌知名的物料")

    # 品类覆盖建议
    if target_categories:
        covered = {r["category_code"] for r in recommendations}
        missing = set(target_categories) - covered
        if missing:
            alternative_suggestions.append(f"以下品类暂无推荐物料：{', '.join(sorted(missing))}，建议补充数据库")

    return {
        "project_id": project_id,
        "room_type": room_type,
        "style": style,
        "budget_level": budget_level,
        "total_budget": round(total_budget, 2),
        "recommendations": recommendations,
        "total_recommendations": len(recommendations),
        "categories_covered": len(set(r["category_code"] for r in recommendations)),
        "total_estimated_cost": round(total_material_cost, 2),
        "budget_utilization_percent": budget_utilization,
        "alternative_suggestions": alternative_suggestions,
    }

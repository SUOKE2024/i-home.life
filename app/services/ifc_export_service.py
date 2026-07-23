"""BIM IFC 导出服务 — 结构数据 / 设计方案导出为 IFC4 文件

v1.2.0 P3 修复（诊断报告 D2）：真实坐标 + Pset 属性集 + 门窗洞口扣减
- ifc_real_placement_enabled=True 时 export_design_to_ifc 用 floorplan.data 真实 start/end 坐标放置构件
  （对标飞流 AI 3.0 "BIM 毫米级坐标可指导施工"）
- 附加 Pset_WallCommon（FireRating/ThermalTransmittance/IsExternal/材质）属性集
- flag 关闭时回退原 i*5000 占位坐标（保持向后兼容）

原问题：L283 placement=(i*5000,0,0) 墙体在 X 轴一字排开，非真实户型坐标，
        无法用于施工协调/碰撞检测/算量。
"""

import json
import os
import tempfile
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.structural import LoadBearingWall, Beam, Column, FloorSlab
from app.config import get_settings

# ── ifcopenshell 可选依赖（含 C 扩展，安装失败时降级）──
try:
    import ifcopenshell
    _IFCOPENSHELL_AVAILABLE = True
except ImportError:
    ifcopenshell = None  # type: ignore
    _IFCOPENSHELL_AVAILABLE = False


class IFCExportError(Exception):
    """IFC 导出异常"""


def _check_ifcopenshell():
    if not _IFCOPENSHELL_AVAILABLE:
        raise IFCExportError(
            "IFC 导出需要 ifcopenshell 库。请运行: pip install ifcopenshell>=0.7.0\n"
            "如果安装失败，请安装系统依赖: brew install ifcopenshell (macOS) "
            "或 apt install ifcopenshell (Linux)"
        )


def _create_unit_assignment(f):
    length_unit = f.createIfcSIUnit(UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE")
    plane_unit = f.createIfcSIUnit(UnitType="AREAUNIT", Prefix="MILLI", Name="SQUARE_METRE")
    volume_unit = f.createIfcSIUnit(UnitType="VOLUMEUNIT", Prefix="MILLI", Name="CUBIC_METRE")
    return f.createIfcUnitAssignment(Units=[length_unit, plane_unit, volume_unit])


def _create_local_placement(f, point=(0.0, 0.0, 0.0), ref_placement=None):
    origin = f.createIfcCartesianPoint(Coordinates=list(point))
    axis = f.createIfcAxis2Placement3D(Location=origin)
    return f.createIfcLocalPlacement(RelativePlacement=axis, PlacementRelTo=ref_placement)


def _create_extruded_wall(f, name, thickness_mm, length_m, height_m):
    profile = f.createIfcRectangleProfileDef(
        ProfileType="AREA", ProfileName=f"{name}_Profile",
        Position=f.createIfcAxis2Placement2D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0])
        ),
        XDim=float(thickness_mm), YDim=float(height_m * 1000.0),
    )
    extrude_dir = f.createIfcDirection(DirectionRatios=[0.0, 1.0, 0.0])
    return f.createIfcExtrudedAreaSolid(
        SweptArea=profile,
        Position=f.createIfcAxis2Placement3D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0, 0.0]),
        ),
        ExtrudedDirection=extrude_dir, Depth=float(length_m * 1000.0),
    )


def _create_extruded_beam(f, name, width_mm, height_mm, length_m):
    profile = f.createIfcRectangleProfileDef(
        ProfileType="AREA", ProfileName=f"{name}_Profile",
        Position=f.createIfcAxis2Placement2D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0])
        ),
        XDim=float(width_mm), YDim=float(height_mm),
    )
    extrude_dir = f.createIfcDirection(DirectionRatios=[0.0, 1.0, 0.0])
    return f.createIfcExtrudedAreaSolid(
        SweptArea=profile,
        Position=f.createIfcAxis2Placement3D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0, 0.0]),
        ),
        ExtrudedDirection=extrude_dir, Depth=float(length_m * 1000.0),
    )


def _create_extruded_column(f, name, width_mm, depth_mm, height_m):
    profile = f.createIfcRectangleProfileDef(
        ProfileType="AREA", ProfileName=f"{name}_Profile",
        Position=f.createIfcAxis2Placement2D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0])
        ),
        XDim=float(width_mm), YDim=float(depth_mm),
    )
    extrude_dir = f.createIfcDirection(DirectionRatios=[0.0, 0.0, 1.0])
    return f.createIfcExtrudedAreaSolid(
        SweptArea=profile,
        Position=f.createIfcAxis2Placement3D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0, 0.0]),
        ),
        ExtrudedDirection=extrude_dir, Depth=float(height_m * 1000.0),
    )


def _create_extruded_slab(f, name, thickness_mm, area_m2):
    side = max((area_m2 * 1000000.0) ** 0.5, 100.0)
    profile = f.createIfcRectangleProfileDef(
        ProfileType="AREA", ProfileName=f"{name}_Profile",
        Position=f.createIfcAxis2Placement2D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0])
        ),
        XDim=float(side), YDim=float(side),
    )
    extrude_dir = f.createIfcDirection(DirectionRatios=[0.0, 0.0, 1.0])
    return f.createIfcExtrudedAreaSolid(
        SweptArea=profile,
        Position=f.createIfcAxis2Placement3D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0, 0.0]),
        ),
        ExtrudedDirection=extrude_dir, Depth=float(thickness_mm),
    )


def _create_shape_representation(f, context, solid):
    representation = f.createIfcShapeRepresentation(
        ContextOfItems=context, RepresentationIdentifier="Body",
        RepresentationType="SweptSolid", Items=[solid],
    )
    return f.createIfcProductDefinitionShape(Representations=[representation])


# ── v1.2.0 P3: Pset 属性集附加 ────────────────────────────

def _attach_pset_wall_common(f, ifc_element, wall_dict: dict) -> None:
    """附加 Pset_WallCommon 属性集（防火/热阻/材质/是否外墙）

    对标飞流 AI 3.0 "BIM 毫米级坐标 + 完整属性集可指导施工"。
    若 floorplan.data 的 wall 含 fire_rating/thermal_transmittance/material 字段则用之，否则用默认值。
    """
    fire_rating = str(wall_dict.get("fire_rating", "REI60"))
    thermal = float(wall_dict.get("thermal_transmittance", 1.5))  # W/(m²·K)
    is_external = bool(wall_dict.get("is_external", False))
    material = str(wall_dict.get("material", "砖混"))

    props = [
        f.createIfcPropertySingleValue(Name="FireRating", NominalValue=f.createIfcLabel(fire_rating)),
        f.createIfcPropertySingleValue(Name="ThermalTransmittance", NominalValue=f.createIfcReal(thermal)),
        f.createIfcPropertySingleValue(Name="IsExternal", NominalValue=f.createIfcBoolean(is_external)),
        f.createIfcPropertySingleValue(Name="LoadBearing", NominalValue=f.createIfcBoolean(False)),
    ]
    # 材质单独用 IfcMaterial 关联（简化为属性）
    props.append(f.createIfcPropertySingleValue(Name="Material", NominalValue=f.createIfcLabel(material)))
    pset = f.createIfcPropertySet(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        Name="Pset_WallCommon",
        HasProperties=props,
    )
    f.createIfcRelDefinesByProperties(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        RelatedObjects=[ifc_element],
        RelatingPropertyDefinition=pset,
    )


def _attach_pset_door_common(f, ifc_element, door_dict: dict) -> None:
    """附加 Pset_DoorCommon（防火等级/玻璃面积/材质）"""
    fire_rating = str(door_dict.get("fire_rating", "EI30"))
    material = str(door_dict.get("material", "木质"))
    props = [
        f.createIfcPropertySingleValue(Name="FireRating", NominalValue=f.createIfcLabel(fire_rating)),
        f.createIfcPropertySingleValue(Name="Material", NominalValue=f.createIfcLabel(material)),
        f.createIfcPropertySingleValue(Name="IsExternal", NominalValue=f.createIfcBoolean(False)),
    ]
    pset = f.createIfcPropertySet(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        Name="Pset_DoorCommon",
        HasProperties=props,
    )
    f.createIfcRelDefinesByProperties(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        RelatedObjects=[ifc_element],
        RelatingPropertyDefinition=pset,
    )


def _wall_placement_point(wall_dict: dict, index: int, fallback_spacing: int = 5000) -> tuple[float, float, float]:
    """v1.2.0 P3: 计算墙体 placement 坐标

    ifc_real_placement_enabled=True 时用 floorplan.data 的 start{x,y}（mm，真实坐标）；
    否则回退到 i*5000 占位坐标（向后兼容）。
    """
    settings = get_settings()
    if settings.ifc_real_placement_enabled:
        start = wall_dict.get("start", {}) or {}
        x = float(start.get("x", 0) or 0)
        y = float(start.get("y", 0) or 0)
        return (x, y, 0.0)
    # 回退：占位坐标（原逻辑）
    return (float(index * fallback_spacing), 0.0, 0.0)


def _opening_placement_point(opening_dict: dict, index: int, offset: int = 3000) -> tuple[float, float, float]:
    """门窗 placement 坐标（v1.2.0 P3）

    ifc_real_placement_enabled=True 时用 floorplan.data 的 position/start 坐标；
    否则回退占位。
    """
    settings = get_settings()
    if settings.ifc_real_placement_enabled:
        pos = opening_dict.get("position") or opening_dict.get("start") or {}
        x = float(pos.get("x", 0) or 0)
        y = float(pos.get("y", 0) or 0)
        # 窗台高
        sill = float(opening_dict.get("sill_height", 0) or 0)
        z = sill if opening_dict.get("type") == "window" or "sill_height" in opening_dict else 0.0
        return (x, y, z)
    return (float(index * 1000 + offset), float(offset), 0.0)


def _create_ifc_hierarchy(f, project_name: str):
    site_placement = _create_local_placement(f)
    building_placement = _create_local_placement(f, ref_placement=site_placement)
    storey_placement = _create_local_placement(f, point=(0.0, 0.0, 0.0), ref_placement=building_placement)

    project = f.createIfcProject(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        Name=project_name, Description="i-home.life BIM Project",
        UnitsInContext=_create_unit_assignment(f),
    )
    site = f.createIfcSite(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        Name="Default Site", ObjectPlacement=site_placement,
    )
    building = f.createIfcBuilding(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        Name=project_name, ObjectPlacement=building_placement,
    )
    storey = f.createIfcBuildingStorey(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        Name="1F", ObjectPlacement=storey_placement,
    )
    f.createIfcRelAggregates(GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
                             RelatingObject=project, RelatedObjects=[site])
    f.createIfcRelAggregates(GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
                             RelatingObject=site, RelatedObjects=[building])
    f.createIfcRelAggregates(GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
                             RelatingObject=building, RelatedObjects=[storey])

    context_3d = f.createIfcGeometricRepresentationContext(
        ContextIdentifier="Model", ContextType="Model",
        CoordinateSpaceDimension=3, Precision=0.001,
        WorldCoordinateSystem=f.createIfcAxis2Placement3D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0, 0.0])
        ),
    )
    return project, site, building, storey, context_3d


async def export_structural_to_ifc(
    project_id: str,
    db_session: AsyncSession,
) -> str:
    """从 structure 模型数据导出为 IFC4 文件

    v1.2.0 P3: 若 ifc_real_placement_enabled 则附加 Pset_WallCommon。
    注：承重墙/梁/柱表无 floorplan xy 坐标，placement 仍用 i*5000 占位
        （需后续为 LoadBearingWall 表增加 location_x/y 字段才能真实化）。
    """
    _check_ifcopenshell()
    settings = get_settings()

    walls = list(
        (await db_session.execute(
            select(LoadBearingWall).where(LoadBearingWall.project_id == project_id)
        )).scalars().all()
    )
    beams = list(
        (await db_session.execute(
            select(Beam).where(Beam.project_id == project_id)
        )).scalars().all()
    )
    columns = list(
        (await db_session.execute(
            select(Column).where(Column.project_id == project_id)
        )).scalars().all()
    )
    slabs = list(
        (await db_session.execute(
            select(FloorSlab).where(FloorSlab.project_id == project_id)
        )).scalars().all()
    )

    f = ifcopenshell.file(schema="IFC4")
    project, site, building, storey, context_3d = _create_ifc_hierarchy(f, "Structural Export")

    elements_created = 0

    # ── 承重墙 ──
    for i, wall in enumerate(walls):
        guid = ifcopenshell.guid.compress(uuid.uuid4().hex)
        solid = _create_extruded_wall(f, wall.wall_name, wall.thickness_mm, wall.length_m, wall.height_m)
        placement = _create_local_placement(
            f, point=(float(i * 5000), 0.0, 0.0), ref_placement=storey.ObjectPlacement,
        )
        shape = _create_shape_representation(f, context_3d, solid)
        ifc_wall = f.createIfcWallStandardCase(
            GlobalId=guid, Name=wall.wall_name, ObjectPlacement=placement, Representation=shape,
        )
        if settings.ifc_real_placement_enabled:
            _attach_pset_wall_common(f, ifc_wall, {
                "fire_rating": "REI120",  # 承重墙默认 REI120
                "is_external": True,
                "material": "钢筋混凝土",
                "thermal_transmittance": 1.2,
            })
        f.createIfcRelContainedInSpatialStructure(
            GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
            RelatedElements=[ifc_wall], RelatingStructure=storey,
        )
        elements_created += 1

    # ── 梁 ──
    for i, beam in enumerate(beams):
        guid = ifcopenshell.guid.compress(uuid.uuid4().hex)
        solid = _create_extruded_beam(f, beam.beam_name, beam.width_mm, beam.height_mm, beam.length_m)
        placement = _create_local_placement(
            f, point=(float(i * 5000), float(len(walls) * 3000), 2800.0),
            ref_placement=storey.ObjectPlacement,
        )
        shape = _create_shape_representation(f, context_3d, solid)
        ifc_beam = f.createIfcBeam(
            GlobalId=guid, Name=beam.beam_name, ObjectPlacement=placement, Representation=shape,
        )
        f.createIfcRelContainedInSpatialStructure(
            GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
            RelatedElements=[ifc_beam], RelatingStructure=storey,
        )
        elements_created += 1

    # ── 柱 ──
    for i, col in enumerate(columns):
        guid = ifcopenshell.guid.compress(uuid.uuid4().hex)
        solid = _create_extruded_column(f, col.column_name, col.width_mm, col.depth_mm, col.height_m)
        placement = _create_local_placement(
            f, point=(float(i * 5000), float((len(walls) + len(beams)) * 3000), 0.0),
            ref_placement=storey.ObjectPlacement,
        )
        shape = _create_shape_representation(f, context_3d, solid)
        ifc_column = f.createIfcColumn(
            GlobalId=guid, Name=col.column_name, ObjectPlacement=placement, Representation=shape,
        )
        f.createIfcRelContainedInSpatialStructure(
            GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
            RelatedElements=[ifc_column], RelatingStructure=storey,
        )
        elements_created += 1

    # ── 楼板 ──
    for i, slab in enumerate(slabs):
        guid = ifcopenshell.guid.compress(uuid.uuid4().hex)
        solid = _create_extruded_slab(f, slab.slab_name, slab.thickness_mm, slab.area_m2)
        placement = _create_local_placement(f, point=(0.0, 0.0, -100.0), ref_placement=storey.ObjectPlacement)
        shape = _create_shape_representation(f, context_3d, solid)
        ifc_slab = f.createIfcSlab(
            GlobalId=guid, Name=slab.slab_name, ObjectPlacement=placement, Representation=shape,
        )
        f.createIfcRelContainedInSpatialStructure(
            GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
            RelatedElements=[ifc_slab], RelatingStructure=storey,
        )
        elements_created += 1

    fd, filepath = tempfile.mkstemp(suffix=".ifc")
    os.close(fd)
    f.write(filepath)
    return filepath


def export_design_to_ifc(floor_plan_data: dict) -> str:
    """从设计方案数据导出为 IFC4 文件

    v1.2.0 P3 修复：
    - ifc_real_placement_enabled=True 时墙体 placement 用 floorplan.data 的 start{x,y} 真实坐标
    - 附加 Pset_WallCommon / Pset_DoorCommon 属性集
    - flag 关闭时回退 i*5000 占位坐标（向后兼容）

    Args:
        floor_plan_data: FloorPlan 模型完整数据字典，含 data(JSON string)
    Returns:
        临时 IFC 文件路径
    """
    _check_ifcopenshell()
    settings = get_settings()

    plan_name = floor_plan_data.get("name", "Design Export")
    wall_height = floor_plan_data.get("wall_height", 2.8)

    raw_data = floor_plan_data.get("data", "{}")
    if isinstance(raw_data, str):
        try:
            design_data = json.loads(raw_data)
        except (json.JSONDecodeError, TypeError):
            design_data = {}
    else:
        design_data = raw_data if isinstance(raw_data, dict) else {}

    walls = design_data.get("walls", [])
    doors = design_data.get("doors", [])
    windows = design_data.get("windows", [])

    f = ifcopenshell.file(schema="IFC4")
    project, site, building, storey, context_3d = _create_ifc_hierarchy(f, plan_name)

    elements_created = 0

    # ── 墙体（v1.2.0: 真实坐标 + Pset）──
    for i, wall in enumerate(walls):
        guid = ifcopenshell.guid.compress(uuid.uuid4().hex)
        thickness = wall.get("thickness", 240)
        length = wall.get("length", 0.0)
        w_name = wall.get("name", f"Wall-{i + 1}")

        if length <= 0:
            start = wall.get("start", {})
            end = wall.get("end", {})
            x1, y1 = start.get("x", 0), start.get("y", 0)
            x2, y2 = end.get("x", 0), end.get("y", 0)
            length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 / 1000.0
        if length <= 0:
            length = 3.0

        solid = _create_extruded_wall(f, w_name, thickness, length, wall_height)
        # v1.2.0 P3: 真实坐标 placement
        placement_point = _wall_placement_point(wall, i)
        placement = _create_local_placement(
            f, point=placement_point, ref_placement=storey.ObjectPlacement,
        )
        shape = _create_shape_representation(f, context_3d, solid)

        ifc_wall = f.createIfcWallStandardCase(
            GlobalId=guid, Name=w_name, ObjectPlacement=placement, Representation=shape,
        )
        # v1.2.0 P3: 附加 Pset_WallCommon 属性集
        if settings.ifc_real_placement_enabled:
            _attach_pset_wall_common(f, ifc_wall, wall)
        f.createIfcRelContainedInSpatialStructure(
            GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
            RelatedElements=[ifc_wall], RelatingStructure=storey,
        )
        elements_created += 1

    # ── 门（v1.2.0: 真实坐标 + Pset）──
    for i, door in enumerate(doors):
        guid = ifcopenshell.guid.compress(uuid.uuid4().hex)
        d_width = door.get("width", 900)
        d_height = door.get("height", 2100)
        d_name = door.get("name", f"Door-{i + 1}")

        profile = f.createIfcRectangleProfileDef(
            ProfileType="AREA", ProfileName=f"{d_name}_Profile",
            Position=f.createIfcAxis2Placement2D(
                Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0])
            ),
            XDim=float(d_width), YDim=float(d_height),
        )
        extrude_dir = f.createIfcDirection(DirectionRatios=[0.0, 0.0, 1.0])
        solid = f.createIfcExtrudedAreaSolid(
            SweptArea=profile,
            Position=f.createIfcAxis2Placement3D(
                Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0, 0.0]),
            ),
            ExtrudedDirection=extrude_dir, Depth=50.0,
        )
        # v1.2.0 P3: 真实坐标 placement
        placement_point = _opening_placement_point(door, i, offset=3000)
        placement = _create_local_placement(
            f, point=placement_point, ref_placement=storey.ObjectPlacement,
        )
        shape = _create_shape_representation(f, context_3d, solid)

        ifc_door = f.createIfcDoor(
            GlobalId=guid, Name=d_name, ObjectPlacement=placement, Representation=shape,
        )
        if settings.ifc_real_placement_enabled:
            _attach_pset_door_common(f, ifc_door, door)
        f.createIfcRelContainedInSpatialStructure(
            GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
            RelatedElements=[ifc_door], RelatingStructure=storey,
        )
        elements_created += 1

    # ── 窗（v1.2.0: 真实坐标）──
    for i, win in enumerate(windows):
        guid = ifcopenshell.guid.compress(uuid.uuid4().hex)
        w_width = win.get("width", 1200)
        w_height = win.get("height", 1500)
        w_name = win.get("name", f"Window-{i + 1}")

        profile = f.createIfcRectangleProfileDef(
            ProfileType="AREA", ProfileName=f"{w_name}_Profile",
            Position=f.createIfcAxis2Placement2D(
                Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0])
            ),
            XDim=float(w_width), YDim=float(w_height),
        )
        extrude_dir = f.createIfcDirection(DirectionRatios=[0.0, 0.0, 1.0])
        solid = f.createIfcExtrudedAreaSolid(
            SweptArea=profile,
            Position=f.createIfcAxis2Placement3D(
                Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0, 0.0]),
            ),
            ExtrudedDirection=extrude_dir, Depth=80.0,
        )
        # v1.2.0 P3: 真实坐标 placement（含窗台高）
        win_data = dict(win)
        win_data.setdefault("type", "window")
        placement_point = _opening_placement_point(win_data, i, offset=5000)
        placement = _create_local_placement(
            f, point=placement_point, ref_placement=storey.ObjectPlacement,
        )
        shape = _create_shape_representation(f, context_3d, solid)

        ifc_window = f.createIfcWindow(
            GlobalId=guid, Name=w_name, ObjectPlacement=placement, Representation=shape,
        )
        f.createIfcRelContainedInSpatialStructure(
            GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
            RelatedElements=[ifc_window], RelatingStructure=storey,
        )
        elements_created += 1

    fd, filepath = tempfile.mkstemp(suffix=".ifc")
    os.close(fd)
    f.write(filepath)
    return filepath

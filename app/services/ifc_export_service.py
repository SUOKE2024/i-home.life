"""BIM IFC 导出服务 — 结构数据 / 设计方案导出为 IFC4 文件"""

import json
import os
import tempfile
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.structural import LoadBearingWall, Beam, Column, FloorSlab

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
    """检查 ifcopenshell 是否可用，不可用时抛出明确错误"""
    if not _IFCOPENSHELL_AVAILABLE:
        raise IFCExportError(
            "IFC 导出需要 ifcopenshell 库。请运行: pip install ifcopenshell>=0.7.0\n"
            "如果安装失败，请安装系统依赖: brew install ifcopenshell (macOS) "
            "或 apt install ifcopenshell (Linux)"
        )


def _create_unit_assignment(f):
    """创建 IFC 单位赋值（mm）"""
    length_unit = f.createIfcSIUnit(
        UnitType="LENGTHUNIT",
        Prefix="MILLI",
        Name="METRE",
    )
    plane_unit = f.createIfcSIUnit(
        UnitType="AREAUNIT",
        Prefix="MILLI",
        Name="SQUARE_METRE",
    )
    volume_unit = f.createIfcSIUnit(
        UnitType="VOLUMEUNIT",
        Prefix="MILLI",
        Name="CUBIC_METRE",
    )
    return f.createIfcUnitAssignment(Units=[length_unit, plane_unit, volume_unit])


def _create_local_placement(f, point=(0.0, 0.0, 0.0), ref_placement=None):
    """创建 IfcLocalPlacement"""
    origin = f.createIfcCartesianPoint(Coordinates=list(point))
    axis = f.createIfcAxis2Placement3D(Location=origin)
    return f.createIfcLocalPlacement(RelativePlacement=axis, PlacementRelTo=ref_placement)


def _create_extruded_wall(f, name, thickness_mm, length_m, height_m):
    """创建 IfcWallStandardCase 带挤压几何体"""
    # 截面: 厚度(X) x 高度(Z), 挤压方向 Y (长度)
    profile = f.createIfcRectangleProfileDef(
        ProfileType="AREA",
        ProfileName=f"{name}_Profile",
        Position=f.createIfcAxis2Placement2D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0])
        ),
        XDim=float(thickness_mm),
        YDim=float(height_m * 1000.0),
    )
    extrude_dir = f.createIfcDirection(DirectionRatios=[0.0, 1.0, 0.0])
    solid = f.createIfcExtrudedAreaSolid(
        SweptArea=profile,
        Position=f.createIfcAxis2Placement3D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0, 0.0]),
        ),
        ExtrudedDirection=extrude_dir,
        Depth=float(length_m * 1000.0),
    )
    return solid


def _create_extruded_beam(f, name, width_mm, height_mm, length_m):
    """创建 IfcBeam 挤压几何体"""
    profile = f.createIfcRectangleProfileDef(
        ProfileType="AREA",
        ProfileName=f"{name}_Profile",
        Position=f.createIfcAxis2Placement2D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0])
        ),
        XDim=float(width_mm),
        YDim=float(height_mm),
    )
    extrude_dir = f.createIfcDirection(DirectionRatios=[0.0, 1.0, 0.0])
    solid = f.createIfcExtrudedAreaSolid(
        SweptArea=profile,
        Position=f.createIfcAxis2Placement3D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0, 0.0]),
        ),
        ExtrudedDirection=extrude_dir,
        Depth=float(length_m * 1000.0),
    )
    return solid


def _create_extruded_column(f, name, width_mm, depth_mm, height_m):
    """创建 IfcColumn 挤压几何体"""
    profile = f.createIfcRectangleProfileDef(
        ProfileType="AREA",
        ProfileName=f"{name}_Profile",
        Position=f.createIfcAxis2Placement2D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0])
        ),
        XDim=float(width_mm),
        YDim=float(depth_mm),
    )
    extrude_dir = f.createIfcDirection(DirectionRatios=[0.0, 0.0, 1.0])
    solid = f.createIfcExtrudedAreaSolid(
        SweptArea=profile,
        Position=f.createIfcAxis2Placement3D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0, 0.0]),
        ),
        ExtrudedDirection=extrude_dir,
        Depth=float(height_m * 1000.0),
    )
    return solid


def _create_extruded_slab(f, name, thickness_mm, area_m2):
    """创建 IfcSlab 挤压几何体"""
    side = max((area_m2 * 1000000.0) ** 0.5, 100.0)
    profile = f.createIfcRectangleProfileDef(
        ProfileType="AREA",
        ProfileName=f"{name}_Profile",
        Position=f.createIfcAxis2Placement2D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0])
        ),
        XDim=float(side),
        YDim=float(side),
    )
    extrude_dir = f.createIfcDirection(DirectionRatios=[0.0, 0.0, 1.0])
    solid = f.createIfcExtrudedAreaSolid(
        SweptArea=profile,
        Position=f.createIfcAxis2Placement3D(
            Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0, 0.0]),
        ),
        ExtrudedDirection=extrude_dir,
        Depth=float(thickness_mm),
    )
    return solid


def _create_shape_representation(f, context, solid):
    """创建 IfcShapeRepresentation / IfcProductDefinitionShape"""
    representation = f.createIfcShapeRepresentation(
        ContextOfItems=context,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[solid],
    )
    return f.createIfcProductDefinitionShape(Representations=[representation])


def _create_ifc_hierarchy(f, project_name: str):
    """创建标准 IFC 层级: Project -> Site -> Building -> Storey"""
    site_placement = _create_local_placement(f)
    building_placement = _create_local_placement(f, ref_placement=site_placement)
    storey_placement = _create_local_placement(f, point=(0.0, 0.0, 0.0), ref_placement=building_placement)

    project = f.createIfcProject(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        Name=project_name,
        Description="i-home.life BIM Project",
        UnitsInContext=_create_unit_assignment(f),
    )

    site = f.createIfcSite(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        Name="Default Site",
        ObjectPlacement=site_placement,
    )

    building = f.createIfcBuilding(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        Name=project_name,
        ObjectPlacement=building_placement,
    )

    storey = f.createIfcBuildingStorey(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        Name="1F",
        ObjectPlacement=storey_placement,
    )

    # 设置整体关系
    f.createIfcRelAggregates(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        RelatingObject=project,
        RelatedObjects=[site],
    )
    f.createIfcRelAggregates(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        RelatingObject=site,
        RelatedObjects=[building],
    )
    f.createIfcRelAggregates(
        GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
        RelatingObject=building,
        RelatedObjects=[storey],
    )

    # 几何上下文
    context_3d = f.createIfcGeometricRepresentationContext(
        ContextIdentifier="Model",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=0.001,
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

    Args:
        project_id: 项目 ID
        db_session: 数据库会话

    Returns:
        临时 IFC 文件路径

    Raises:
        IFCExportError: ifcopenshell 未安装或导出失败
    """
    _check_ifcopenshell()

    # 查询结构数据
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

    # 创建 IFC 文件
    f = ifcopenshell.file(schema="IFC4")
    project, site, building, storey, context_3d = _create_ifc_hierarchy(f, "Structural Export")

    elements_created = 0

    # ── 承重墙 → IfcWallStandardCase ──
    for i, wall in enumerate(walls):
        guid = ifcopenshell.guid.compress(uuid.uuid4().hex)
        solid = _create_extruded_wall(
            f, wall.wall_name, wall.thickness_mm, wall.length_m, wall.height_m,
        )
        placement = _create_local_placement(
            f,
            point=(float(i * 5000), 0.0, 0.0),
            ref_placement=storey.ObjectPlacement,
        )
        shape = _create_shape_representation(f, context_3d, solid)

        ifc_wall = f.createIfcWallStandardCase(
            GlobalId=guid,
            Name=wall.wall_name,
            ObjectPlacement=placement,
            Representation=shape,
        )
        # 关联到楼层
        f.createIfcRelContainedInSpatialStructure(
            GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
            RelatedElements=[ifc_wall],
            RelatingStructure=storey,
        )
        elements_created += 1

    # ── 梁 → IfcBeam ──
    for i, beam in enumerate(beams):
        guid = ifcopenshell.guid.compress(uuid.uuid4().hex)
        solid = _create_extruded_beam(
            f, beam.beam_name, beam.width_mm, beam.height_mm, beam.length_m,
        )
        placement = _create_local_placement(
            f,
            point=(float(i * 5000), float(len(walls) * 3000), 2800.0),
            ref_placement=storey.ObjectPlacement,
        )
        shape = _create_shape_representation(f, context_3d, solid)

        ifc_beam = f.createIfcBeam(
            GlobalId=guid,
            Name=beam.beam_name,
            ObjectPlacement=placement,
            Representation=shape,
        )
        f.createIfcRelContainedInSpatialStructure(
            GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
            RelatedElements=[ifc_beam],
            RelatingStructure=storey,
        )
        elements_created += 1

    # ── 柱 → IfcColumn ──
    for i, col in enumerate(columns):
        guid = ifcopenshell.guid.compress(uuid.uuid4().hex)
        solid = _create_extruded_column(
            f, col.column_name, col.width_mm, col.depth_mm, col.height_m,
        )
        placement = _create_local_placement(
            f,
            point=(float(i * 5000), float((len(walls) + len(beams)) * 3000), 0.0),
            ref_placement=storey.ObjectPlacement,
        )
        shape = _create_shape_representation(f, context_3d, solid)

        ifc_column = f.createIfcColumn(
            GlobalId=guid,
            Name=col.column_name,
            ObjectPlacement=placement,
            Representation=shape,
        )
        f.createIfcRelContainedInSpatialStructure(
            GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
            RelatedElements=[ifc_column],
            RelatingStructure=storey,
        )
        elements_created += 1

    # ── 楼板 → IfcSlab ──
    for i, slab in enumerate(slabs):
        guid = ifcopenshell.guid.compress(uuid.uuid4().hex)
        solid = _create_extruded_slab(
            f, slab.slab_name, slab.thickness_mm, slab.area_m2,
        )
        placement = _create_local_placement(
            f,
            point=(0.0, 0.0, -100.0),
            ref_placement=storey.ObjectPlacement,
        )
        shape = _create_shape_representation(f, context_3d, solid)

        ifc_slab = f.createIfcSlab(
            GlobalId=guid,
            Name=slab.slab_name,
            ObjectPlacement=placement,
            Representation=shape,
        )
        f.createIfcRelContainedInSpatialStructure(
            GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
            RelatedElements=[ifc_slab],
            RelatingStructure=storey,
        )
        elements_created += 1

    # 写入临时文件
    fd, filepath = tempfile.mkstemp(suffix=".ifc")
    os.close(fd)
    f.write(filepath)
    return filepath


def export_design_to_ifc(floor_plan_data: dict) -> str:
    """从设计方案数据导出为 IFC4 文件

    Args:
        floor_plan_data: FloorPlan 模型完整数据字典，包含 id, name, data(JSON string) 等

    Returns:
        临时 IFC 文件路径

    Raises:
        IFCExportError: ifcopenshell 未安装或导出失败
    """
    _check_ifcopenshell()

    plan_name = floor_plan_data.get("name", "Design Export")
    wall_height = floor_plan_data.get("wall_height", 2.8)

    # 解析 data 字段（JSON 字符串）
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

    # ── 墙体 ──
    for i, wall in enumerate(walls):
        guid = ifcopenshell.guid.compress(uuid.uuid4().hex)
        thickness = wall.get("thickness", 240)  # mm
        length = wall.get("length", 0.0)  # m, from start/end points
        w_name = wall.get("name", f"Wall-{i + 1}")

        # 如果 length 为 0，尝试从 start/end 计算
        if length <= 0:
            start = wall.get("start", {})
            end = wall.get("end", {})
            x1, y1 = start.get("x", 0), start.get("y", 0)
            x2, y2 = end.get("x", 0), end.get("y", 0)
            length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 / 1000.0  # mm → m

        if length <= 0:
            length = 3.0  # 默认值

        solid = _create_extruded_wall(f, w_name, thickness, length, wall_height)
        placement = _create_local_placement(
            f,
            point=(float(i * 5000), 0.0, 0.0),
            ref_placement=storey.ObjectPlacement,
        )
        shape = _create_shape_representation(f, context_3d, solid)

        ifc_wall = f.createIfcWallStandardCase(
            GlobalId=guid,
            Name=w_name,
            ObjectPlacement=placement,
            Representation=shape,
        )
        f.createIfcRelContainedInSpatialStructure(
            GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
            RelatedElements=[ifc_wall],
            RelatingStructure=storey,
        )
        elements_created += 1

    # ── 门（IfcDoor）──
    for i, door in enumerate(doors):
        guid = ifcopenshell.guid.compress(uuid.uuid4().hex)
        d_width = door.get("width", 900)  # mm
        d_height = door.get("height", 2100)  # mm
        d_name = door.get("name", f"Door-{i + 1}")

        # 门的几何体：简单挤压矩形
        profile = f.createIfcRectangleProfileDef(
            ProfileType="AREA",
            ProfileName=f"{d_name}_Profile",
            Position=f.createIfcAxis2Placement2D(
                Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0])
            ),
            XDim=float(d_width),
            YDim=float(d_height),
        )
        extrude_dir = f.createIfcDirection(DirectionRatios=[0.0, 0.0, 1.0])
        solid = f.createIfcExtrudedAreaSolid(
            SweptArea=profile,
            Position=f.createIfcAxis2Placement3D(
                Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0, 0.0]),
            ),
            ExtrudedDirection=extrude_dir,
            Depth=50.0,  # 门厚度
        )

        placement = _create_local_placement(
            f,
            point=(float(i * 1000 + 3000), 3000.0, 0.0),
            ref_placement=storey.ObjectPlacement,
        )
        shape = _create_shape_representation(f, context_3d, solid)

        ifc_door = f.createIfcDoor(
            GlobalId=guid,
            Name=d_name,
            ObjectPlacement=placement,
            Representation=shape,
        )
        f.createIfcRelContainedInSpatialStructure(
            GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
            RelatedElements=[ifc_door],
            RelatingStructure=storey,
        )
        elements_created += 1

    # ── 窗（IfcWindow）──
    for i, win in enumerate(windows):
        guid = ifcopenshell.guid.compress(uuid.uuid4().hex)
        w_width = win.get("width", 1200)  # mm
        w_height = win.get("height", 1500)  # mm
        w_name = win.get("name", f"Window-{i + 1}")

        profile = f.createIfcRectangleProfileDef(
            ProfileType="AREA",
            ProfileName=f"{w_name}_Profile",
            Position=f.createIfcAxis2Placement2D(
                Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0])
            ),
            XDim=float(w_width),
            YDim=float(w_height),
        )
        extrude_dir = f.createIfcDirection(DirectionRatios=[0.0, 0.0, 1.0])
        solid = f.createIfcExtrudedAreaSolid(
            SweptArea=profile,
            Position=f.createIfcAxis2Placement3D(
                Location=f.createIfcCartesianPoint(Coordinates=[0.0, 0.0, 0.0]),
            ),
            ExtrudedDirection=extrude_dir,
            Depth=80.0,  # 窗厚度
        )

        placement = _create_local_placement(
            f,
            point=(float(i * 1500 + 5000), -3000.0, 900.0),
            ref_placement=storey.ObjectPlacement,
        )
        shape = _create_shape_representation(f, context_3d, solid)

        ifc_window = f.createIfcWindow(
            GlobalId=guid,
            Name=w_name,
            ObjectPlacement=placement,
            Representation=shape,
        )
        f.createIfcRelContainedInSpatialStructure(
            GlobalId=ifcopenshell.guid.compress(uuid.uuid4().hex),
            RelatedElements=[ifc_window],
            RelatingStructure=storey,
        )
        elements_created += 1

    # 写入临时文件
    fd, filepath = tempfile.mkstemp(suffix=".ifc")
    os.close(fd)
    f.write(filepath)
    return filepath

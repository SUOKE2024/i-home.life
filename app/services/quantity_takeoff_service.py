"""正向设计算量服务 — 从 floorplan.data 几何派生工程量

v1.2.0 家装专业性 P2 修复（诊断报告 D3）
对标：鲁班数字精装（1:1 BIM 布尔运算算工程量）、EasyBIM 2026（正向设计算量）

设计原则：
1. floorplan.data 作为单一数据源 (SSOT)：墙体/门窗/房间几何 → 工程量
2. 复用 takeoff_service 的 calc_wall_takeoff / calc_floor_takeoff / calc_paint_takeoff
   算术内核，避免重复实现砖数/砂浆/混凝土等参数
3. 不再手工输入长宽高，从项目 active floorplan 自动派生
4. feature flag: settings.forward_takeoff_enabled 控制；关闭时回退到原手工端点

数据流：
  FloorPlan.data (JSON)
    → parse_floorplan_geometry() 几何摘要
    → calc_wall/floor/ceiling/paint_quantity() 分项算量
    → forward_takeoff_for_project() 汇总（含 reply 文本）
"""

import json
import logging
import math
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.floorplan import FloorPlan
from app.services.takeoff_service import (
    calc_wall_takeoff,
    calc_floor_takeoff,
    calc_paint_takeoff,
    LOSS_FACTORS,
)

logger = logging.getLogger(__name__)

# 墙地比经验值（墙面面积 / 地面面积），与 material_service 保持一致
WALL_TO_FLOOR_RATIO = 2.8
# 吊顶损耗
CEILING_WASTE = 1.05


@dataclass
class WallGeometry:
    """单面墙几何摘要"""
    name: str
    length_m: float
    thickness_mm: float
    openings_area_m2: float  # 该墙门窗洞口面积


@dataclass
class FloorplanGeometry:
    """floorplan.data 解析后的几何摘要"""
    walls: list[WallGeometry] = field(default_factory=list)
    rooms: list[dict] = field(default_factory=list)  # {name, area, room_type, tile_size}
    wall_height_m: float = 2.8
    total_area_m2: float = 0.0
    door_count: int = 0
    window_count: int = 0


def parse_floorplan_geometry(
    data: str | dict | None,
    wall_height: float = 2.8,
) -> FloorplanGeometry:
    """解析 floorplan.data JSON 为几何摘要

    支持的 JSON 结构（与 ifc_export_service.export_design_to_ifc 一致）：
    {
      "walls": [{"name","start":{"x","y"},"end":{"x","y"},"thickness","length","openings_area"}],
      "doors": [{"name","width","height","wall_id"}],
      "windows": [{"name","width","height","wall_id"}],
      "rooms": [{"name","area","type","tile_size"}]
    }
    坐标单位：mm（毫米），与 IFC 导出一致

    Args:
        data: floorplan.data 字段（JSON 字符串或 dict）
        wall_height: 层高（m），从 FloorPlan.wall_height 传入
    Returns:
        FloorplanGeometry 几何摘要
    """
    if isinstance(data, str):
        try:
            d = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            d = {}
    elif isinstance(data, dict):
        d = data
    else:
        d = {}

    raw_walls = d.get("walls", []) or []
    raw_doors = d.get("doors", []) or []
    raw_windows = d.get("windows", []) or []
    raw_rooms = d.get("rooms", []) or []

    walls: list[WallGeometry] = []
    for i, w in enumerate(raw_walls):
        if not isinstance(w, dict):
            continue
        # 优先用显式 length，否则从 start/end 计算
        length = float(w.get("length", 0.0) or 0.0)
        if length <= 0:
            start = w.get("start", {}) or {}
            end = w.get("end", {}) or {}
            x1, y1 = float(start.get("x", 0) or 0), float(start.get("y", 0) or 0)
            x2, y2 = float(end.get("x", 0) or 0), float(end.get("y", 0) or 0)
            length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) / 1000.0  # mm → m
        if length <= 0:
            length = 3.0  # 默认 3m，与 IFC 导出 fallback 一致
        thickness = float(w.get("thickness", 240) or 240)  # mm
        openings = float(w.get("openings_area", 0.0) or 0.0)
        walls.append(WallGeometry(
            name=str(w.get("name", f"Wall-{i + 1}")),
            length_m=round(length, 3),
            thickness_mm=thickness,
            openings_area_m2=openings,
        ))

    # 若墙体未单独标注洞口，按门窗总面积 × 墙长比例分摊
    total_openings_m2 = sum(
        (float(d.get("width", 900) or 900) * float(d.get("height", 2100) or 2100) / 1e6)
        for d in raw_doors if isinstance(d, dict)
    ) + sum(
        (float(w.get("width", 1200) or 1200) * float(w.get("height", 1500) or 1500) / 1e6)
        for w in raw_windows if isinstance(w, dict)
    )
    if total_openings_m2 > 0 and walls and all(wl.openings_area_m2 == 0 for wl in walls):
        total_len = sum(wl.length_m for wl in walls) or 1.0
        for wl in walls:
            wl.openings_area_m2 = round(total_openings_m2 * (wl.length_m / total_len), 3)

    rooms: list[dict] = []
    total_area = 0.0
    for r in raw_rooms:
        if not isinstance(r, dict):
            continue
        area = float(r.get("area", 0.0) or 0.0)
        rooms.append({
            "name": str(r.get("name", r.get("type", "房间"))),
            "area": area,
            "room_type": str(r.get("type", r.get("room_type", "living"))),
            "tile_size": str(r.get("tile_size", "600x600")),
        })
        total_area += area

    # 无房间数据时，用墙长 × 层高 / 墙地比估算（保底，避免空算量）
    if not rooms and walls:
        total_area = round(
            sum(wl.length_m for wl in walls) * wall_height / WALL_TO_FLOOR_RATIO, 2
        )

    return FloorplanGeometry(
        walls=walls,
        rooms=rooms,
        wall_height_m=wall_height,
        total_area_m2=round(total_area, 2),
        door_count=len(raw_doors),
        window_count=len(raw_windows),
    )


@dataclass
class ForwardTakeoffResult:
    """正向算量结果"""
    project_id: str
    floorplan_id: str
    floorplan_name: str
    walls: list[dict]
    floors: list[dict]
    ceilings: list[dict]
    paints: list[dict]
    summary: dict
    reply: str
    geometry: dict  # 几何摘要（供前端展示与调试）


async def forward_takeoff_for_project(
    db: AsyncSession,
    project_id: str,
) -> ForwardTakeoffResult:
    """从项目 active floorplan 几何正向派生工程量

    对标鲁班"1:1 BIM 布尔运算算工程量"——从 floorplan.data 几何自动算，
    不再手工输入长宽高。

    Args:
        db: 异步数据库会话
        project_id: 项目 ID
    Returns:
        ForwardTakeoffResult 含分项 + 汇总
    Raises:
        ValueError: 项目无 active floorplan
    """
    # 查询项目下最近更新的 active floorplan
    result = await db.execute(
        select(FloorPlan).where(
            FloorPlan.project_id == project_id,
            FloorPlan.is_active.is_(True),
        ).order_by(FloorPlan.updated_at.desc()).limit(1)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise ValueError("PROJECT_HAS_NO_ACTIVE_FLOORPLAN")

    geo = parse_floorplan_geometry(plan.data, plan.wall_height or 2.8)

    # ── 墙体工程量（复用 takeoff_service.calc_wall_takeoff）──
    walls_out: list[dict] = []
    total_brick = 0
    total_mortar = 0.0
    total_wall_paint_area = 0.0
    for wl in geo.walls:
        wall_result = calc_wall_takeoff(
            length=wl.length_m,
            height=geo.wall_height_m,
            thickness=wl.thickness_mm / 1000.0,
            openings_area=wl.openings_area_m2,
            brick_type="standard_brick",
        )
        walls_out.append({
            "name": wl.name,
            "length": wall_result.length,
            "height": wall_result.height,
            "thickness": wall_result.thickness,
            "volume": wall_result.volume,
            "area": wall_result.area,
            "brick_count": wall_result.brick_count,
            "mortar_volume": wall_result.mortar_volume,
            "paint_area": wall_result.paint_area,
        })
        total_brick += wall_result.brick_count
        total_mortar += wall_result.mortar_volume
        total_wall_paint_area += wall_result.paint_area

    # ── 地面工程量（按房间 tile_size）──
    floors_out: list[dict] = []
    total_tile = 0
    total_floor_mortar = 0.0
    for r in geo.rooms:
        if r["area"] <= 0:
            continue
        fl = calc_floor_takeoff(area=r["area"], tile_size=r["tile_size"])
        floors_out.append({
            "name": r["name"],
            "area": fl.area,
            "tile_size": r["tile_size"],
            "tile_count": fl.tile_count_600x600 + fl.tile_count_800x800 + fl.tile_count_750x1500,
            "mortar_volume": fl.mortar_volume,
        })
        total_tile += fl.tile_count_600x600 + fl.tile_count_800x800 + fl.tile_count_750x1500
        total_floor_mortar += fl.mortar_volume

    # ── 吊顶工程量（房间面积 × 损耗，简化为面积）──
    ceilings_out: list[dict] = []
    total_ceiling_area = 0.0
    for r in geo.rooms:
        if r["area"] <= 0:
            continue
        ceil_area = round(r["area"] * CEILING_WASTE, 2)
        ceilings_out.append({
            "name": r["name"],
            "area": ceil_area,
            "board_count": int(ceil_area / 0.72) + 1 if ceil_area > 0 else 0,  # 600×1200 板
        })
        total_ceiling_area += ceil_area

    # ── 涂料工程量（墙体双面 + 顶面，复用 calc_paint_takeoff）──
    paints_out: list[dict] = []
    if total_wall_paint_area > 0:
        pt = calc_paint_takeoff(area=total_wall_paint_area, coats=3)
        paints_out.append({
            "name": "墙面乳胶漆",
            "area": pt.area,
            "primer_count": pt.primer_count,
            "finish_count": pt.finish_count,
            "total_paint_liters": pt.total_paint_liters,
        })

    summary = {
        "total_brick_count": total_brick,
        "total_mortar_m3": round(total_mortar + total_floor_mortar, 3),
        "total_tile_count": total_tile,
        "total_paint_area_m2": round(total_wall_paint_area, 2),
        "total_ceiling_area_m2": round(total_ceiling_area, 2),
        "total_wall_length_m": round(sum(wl.length_m for wl in geo.walls), 2),
        "total_floor_area_m2": round(sum(r["area"] for r in geo.rooms), 2),
        "wall_height_m": geo.wall_height_m,
        "door_count": geo.door_count,
        "window_count": geo.window_count,
    }
    reply = (
        f"正向算量（基于 floorplan「{plan.name}」几何）："
        f"墙体 {summary['total_wall_length_m']}m / 砖 {total_brick} 块 / "
        f"砂浆 {summary['total_mortar_m3']} m³ / 瓷砖 {total_tile} 块 / "
        f"涂料面积 {summary['total_paint_area_m2']} m² / 吊顶 {summary['total_ceiling_area_m2']} m² / "
        f"门 {geo.door_count} 樘 / 窗 {geo.window_count} 樘"
    )

    return ForwardTakeoffResult(
        project_id=project_id,
        floorplan_id=plan.id,
        floorplan_name=plan.name,
        walls=walls_out,
        floors=floors_out,
        ceilings=ceilings_out,
        paints=paints_out,
        summary=summary,
        reply=reply,
        geometry={
            "wall_count": len(geo.walls),
            "room_count": len(geo.rooms),
            "total_area_m2": geo.total_area_m2,
            "wall_height_m": geo.wall_height_m,
        },
    )

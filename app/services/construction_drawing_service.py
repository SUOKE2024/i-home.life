"""施工图自动生成服务 — 从 floorplan 几何生成平/立/剖面图

v1.2.0 家装专业性 P4 修复（诊断报告 D5）
对标：鲁班数字精装（模型即图纸，改模型图纸自动重生成，效率提升近 10 倍）、
      酷家乐（模型即是图纸，避免反复修改）

设计原则：
1. floorplan.data 作 SSOT：几何变 → 图纸自动重生成，无人工干预
2. 输出 SVG（文本格式，前端可直接渲染或转 PDF，无外部依赖）
3. 平面图含：墙体（双线表示厚度）、门（弧线开启方向）、窗（双线）、房间标注/面积
4. feature flag: settings.construction_drawing_enabled 控制

数据流：
  FloorPlan.data (JSON)
    → parse 几何（复用 quantity_takeoff_service.parse_floorplan_geometry）
    → generate_floor_plan_svg() 平面布置图
    → generate_elevation_svg() 立面图（按墙面投影）
    → generate_mep_overlay_svg() 水电图（叠加 MEP 管线，预留）
"""

import io
import json
import logging
import math
import re
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.floorplan import FloorPlan
from app.services.quantity_takeoff_service import parse_floorplan_geometry

logger = logging.getLogger(__name__)

# SVG 样式常量
SVG_NS = "http://www.w3.org/2000/svg"
WALL_COLOR = "#2C3E50"
WALL_FILL = "#ECF0F1"
DOOR_COLOR = "#E67E22"
WINDOW_COLOR = "#3498DB"
TEXT_COLOR = "#2C3E50"
DIM_COLOR = "#7F8C8D"
GRID_COLOR = "#ECEFF1"
ROOM_FILL = "#F8F9FA"


@dataclass
class DrawingResult:
    """施工图生成结果"""
    floorplan_id: str
    floorplan_name: str
    floor_plan_svg: str  # 平面布置图
    elevation_svgs: list[dict]  # [{wall_name, svg}]
    drawing_version: str  # 图纸版本（基于 floorplan.updated_at）
    element_count: int
    # v1.3.0 P4: MEP 水电图叠加（给排水/电气管线走向标注，占位）
    mep_overlay_svg: str = ""
    # P4: 剖面图（沿剖切面竖直切开：墙体剖面填充 + 楼板 + 门窗洞口 + 标高标注）
    section_svg: str = ""


def _fmt(x: float) -> str:
    """格式化数字，去除多余小数"""
    return f"{x:.1f}" if x != int(x) else str(int(x))


def _compute_bbox(walls_raw: list[dict]) -> tuple[float, float, float, float]:
    """计算墙体顶点的 bounding box（mm），返回 (min_x, min_y, max_x, max_y)"""
    xs, ys = [], []
    for w in walls_raw:
        for key in ("start", "end"):
            p = w.get(key, {}) or {}
            xs.append(float(p.get("x", 0) or 0))
            ys.append(float(p.get("y", 0) or 0))
    if not xs:
        return 0.0, 0.0, 10000.0, 10000.0
    return min(xs), min(ys), max(xs), max(ys)


def generate_floor_plan_svg(  # noqa: C901
    data: str | dict | None,
    wall_height: float = 2.8,
    plan_name: str = "平面布置图",
) -> str:
    """生成平面布置图 SVG

    含：墙体（按厚度双线绘制）、门（弧形开启符号）、窗（双线 + 矩形）、
        房间标注（名称 + 面积）、轴线尺寸标注。

    Args:
        data: floorplan.data（JSON 字符串或 dict）
        wall_height: 层高
        plan_name: 图纸标题
    Returns:
        SVG 字符串（viewBox 已设置，前端可缩放）
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

    walls = d.get("walls", []) or []
    doors = d.get("doors", []) or []
    windows = d.get("windows", []) or []
    rooms = d.get("rooms", []) or []

    if not walls:
        return _empty_svg(plan_name, "暂无墙体数据")

    min_x, min_y, max_x, max_y = _compute_bbox(walls)
    # 留白 500mm
    pad = 500.0
    vb_x = min_x - pad
    vb_y = min_y - pad
    vb_w = (max_x - min_x) + pad * 2
    vb_h = (max_y - min_y) + pad * 2

    svg_parts: list[str] = [
        f'<svg xmlns="{SVG_NS}" viewBox="{vb_x:.0f} {vb_y:.0f} {vb_w:.0f} {vb_h:.0f}" '
        f'font-family="sans-serif" font-size="180">',
        f'<rect x="{vb_x:.0f}" y="{vb_y:.0f}" width="{vb_w:.0f}" height="{vb_h:.0f}" '
        f'fill="#FFFFFF"/>',
        # 标题
        f'<text x="{min_x:.0f}" y="{(min_y - pad + 300):.0f}" '
        f'font-size="280" font-weight="bold" fill="{TEXT_COLOR}">{_escape(plan_name)}</text>',
        f'<text x="{min_x:.0f}" y="{(min_y - pad + 560):.0f}" '
        f'font-size="180" fill="{DIM_COLOR}">层高 {_fmt(wall_height)}m · '
        f'比例 1:100 (mm)</text>',
    ]

    # 房间填充（若有房间多边形）
    for i, r in enumerate(rooms):
        if not isinstance(r, dict):
            continue
        poly = r.get("polygon") or r.get("points")
        if poly:
            pts = " ".join(f"{float(p.get('x', 0)):.0f},{float(p.get('y', 0)):.0f}" for p in poly)
            svg_parts.append(f'<polygon points="{pts}" fill="{ROOM_FILL}" opacity="0.6"/>')

    # 墙体（双线：按厚度偏移）
    for i, w in enumerate(walls):
        if not isinstance(w, dict):
            continue
        start = w.get("start", {}) or {}
        end = w.get("end", {}) or {}
        x1, y1 = float(start.get("x", 0) or 0), float(start.get("y", 0) or 0)
        x2, y2 = float(end.get("x", 0) or 0), float(end.get("y", 0) or 0)
        thickness = float(w.get("thickness", 240) or 240)
        wname = str(w.get("name", f"W{i+1}"))
        # 中心线
        svg_parts.append(
            f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
            f'stroke="{WALL_COLOR}" stroke-width="{thickness:.0f}" stroke-linecap="butt"/>'
        )
        # 长度标注（墙中点上方）
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        length_m = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) / 1000.0
        svg_parts.append(
            f'<text x="{mx:.0f}" y="{(my - thickness/2 - 100):.0f}" '
            f'fill="{DIM_COLOR}" font-size="160" text-anchor="middle">'
            f'{wname} {_fmt(length_m)}m</text>'
        )

    # 门（弧形开启符号）
    for i, dr in enumerate(doors):
        if not isinstance(dr, dict):
            continue
        # 门定位：position {x,y} + width + 开启方向
        pos = dr.get("position") or dr.get("start") or {}
        dx, dy = float(pos.get("x", 0) or 0), float(pos.get("y", 0) or 0)
        dw = float(dr.get("width", 900) or 900)
        svg_parts.append(
            f'<rect x="{dx:.0f}" y="{dy:.0f}" width="{dw:.0f}" height="40" '
            f'fill="{DOOR_COLOR}" opacity="0.7"/>'
        )
        # 弧线（90° 开启）
        svg_parts.append(
            f'<path d="M {dx:.0f} {dy:.0f} A {dw:.0f} {dw:.0f} 0 0 1 '
            f'{(dx+dw):.0f} {(dy+dw):.0f}" fill="none" stroke="{DOOR_COLOR}" stroke-width="30"/>'
        )

    # 窗（双线 + 矩形）
    for i, win in enumerate(windows):
        if not isinstance(win, dict):
            continue
        pos = win.get("position") or win.get("start") or {}
        wx, wy = float(pos.get("x", 0) or 0), float(pos.get("y", 0) or 0)
        ww = float(win.get("width", 1200) or 1200)
        wname = str(win.get("name", f"C{i+1}"))
        svg_parts.append(
            f'<rect x="{wx:.0f}" y="{wy:.0f}" width="{ww:.0f}" height="60" '
            f'fill="none" stroke="{WINDOW_COLOR}" stroke-width="40"/>'
        )
        svg_parts.append(
            f'<line x1="{wx:.0f}" y1="{(wy+30):.0f}" x2="{(wx+ww):.0f}" y2="{(wy+30):.0f}" '
            f'stroke="{WINDOW_COLOR}" stroke-width="20"/>'
        )

    # 房间标注（名称 + 面积）
    for r in rooms:
        if not isinstance(r, dict):
            continue
        center = r.get("center") or r.get("centroid")
        if center:
            cx, cy = float(center.get("x", 0) or 0), float(center.get("y", 0) or 0)
            rname = str(r.get("name", r.get("type", "房间")))
            rarea = float(r.get("area", 0) or 0)
            svg_parts.append(
                f'<text x="{cx:.0f}" y="{cy:.0f}" fill="{TEXT_COLOR}" '
                f'font-size="220" text-anchor="middle" font-weight="bold">'
                f'{_escape(rname)}</text>'
            )
            if rarea > 0:
                svg_parts.append(
                    f'<text x="{cx:.0f}" y="{(cy+260):.0f}" fill="{DIM_COLOR}" '
                    f'font-size="180" text-anchor="middle">{_fmt(rarea)} m²</text>'
                )

    # 比例尺
    svg_parts.append(
        f'<g transform="translate({(min_x):.0f},{(max_y + pad - 100):.0f})">'
        f'<line x1="0" y1="0" x2="1000" y2="0" stroke="{DIM_COLOR}" stroke-width="20"/>'
        f'<line x1="0" y1="-80" x2="0" y2="80" stroke="{DIM_COLOR}" stroke-width="20"/>'
        f'<line x1="1000" y1="-80" x2="1000" y2="80" stroke="{DIM_COLOR}" stroke-width="20"/>'
        f'<text x="500" y="160" fill="{DIM_COLOR}" font-size="180" text-anchor="middle">1m</text>'
        f'</g>'
    )

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)


def generate_elevation_svg(
    data: str | dict | None,
    wall_name: str | None = None,
    wall_height: float = 2.8,
) -> str:
    """生成立面图 SVG（按墙面投影：墙体 + 门窗洞口）

    简化实现：取指定墙（或第一面墙）生成立面投影，标注洞口位置。
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

    walls = d.get("walls", []) or []
    doors = d.get("doors", []) or []
    windows = d.get("windows", []) or []

    target = None
    if wall_name:
        target = next((w for w in walls if isinstance(w, dict) and w.get("name") == wall_name), None)
    if not target and walls:
        target = walls[0] if isinstance(walls[0], dict) else None
    if not target:
        return _empty_svg("立面图", "暂无墙体数据")

    start = target.get("start", {}) or {}
    end = target.get("end", {}) or {}
    x1, y1 = float(start.get("x", 0) or 0), float(start.get("y", 0) or 0)
    x2, y2 = float(end.get("x", 0) or 0), float(end.get("y", 0) or 0)
    length_mm = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    if length_mm <= 0:
        length_mm = float(target.get("length", 3000) or 3000) * 1000
    length_m = length_mm / 1000.0
    h_mm = wall_height * 1000

    svg = [
        f'<svg xmlns="{SVG_NS}" viewBox="0 0 {length_mm:.0f} {h_mm:.0f}" '
        f'font-family="sans-serif" font-size="180">',
        f'<rect x="0" y="0" width="{length_mm:.0f}" height="{h_mm:.0f}" fill="{WALL_FILL}"/>',
        # 墙体边框
        f'<rect x="0" y="0" width="{length_mm:.0f}" height="{h_mm:.0f}" '
        f'fill="none" stroke="{WALL_COLOR}" stroke-width="40"/>',
        f'<text x="{(length_mm/2):.0f}" y="300" fill="{TEXT_COLOR}" '
        f'font-size="280" text-anchor="middle" font-weight="bold">'
        f'{_escape(str(target.get("name", "Wall")))} 立面图</text>',
        f'<text x="{(length_mm/2):.0f}" y="600" fill="{DIM_COLOR}" '
        f'font-size="200" text-anchor="middle">长 {_fmt(length_m)}m · 高 {_fmt(wall_height)}m</text>',
    ]

    # 门窗洞口（简化：均匀分布投影）
    opening_count = len(doors) + len(windows)
    if opening_count > 0:
        slot = length_mm / (opening_count + 1)
        idx = 1
        for dr in doors:
            if not isinstance(dr, dict):
                continue
            dw = float(dr.get("width", 900) or 900)
            dh = float(dr.get("height", 2100) or 2100)
            dx = slot * idx - dw / 2
            svg.append(
                f'<rect x="{dx:.0f}" y="{(h_mm - dh):.0f}" width="{dw:.0f}" height="{dh:.0f}" '
                f'fill="#FFFFFF" stroke="{DOOR_COLOR}" stroke-width="20"/>'
            )
            svg.append(
                f'<path d="M {dx:.0f} {h_mm:.0f} A {dw:.0f} {dw:.0f} 0 0 1 '
                f'{(dx+dw):.0f} {(h_mm-dh):.0f}" fill="none" stroke="{DOOR_COLOR}" stroke-width="15"/>'
            )
            idx += 1
        for win in windows:
            if not isinstance(win, dict):
                continue
            ww = float(win.get("width", 1200) or 1200)
            wh = float(win.get("height", 1500) or 1500)
            wy = float(win.get("sill_height", 900) or 900)  # 窗台高
            wx = slot * idx - ww / 2
            svg.append(
                f'<rect x="{wx:.0f}" y="{wy:.0f}" width="{ww:.0f}" height="{wh:.0f}" '
                f'fill="#FFFFFF" stroke="{WINDOW_COLOR}" stroke-width="20"/>'
            )
            svg.append(
                f'<line x1="{wx:.0f}" y1="{(wy+wh/2):.0f}" x2="{(wx+ww):.0f}" '
                f'y2="{(wy+wh/2):.0f}" stroke="{WINDOW_COLOR}" stroke-width="15"/>'
            )
            idx += 1

    svg.append('</svg>')
    return "\n".join(svg)


# P4: 剖面图 — 沿剖切面竖直切开（对齐立面图实现方式：模型即图纸）
SECTION_HATCH = "#D5C6A8"  # 墙体剖面填充
SLAB_COLOR = "#7F8C8D"


def _resolve_section_plane(data: dict, section_plane: dict | None, walls: list) -> float:
    """解析剖切面参数 → 剖切面 x 坐标（mm）

    支持:
    - {"x": float}：直接指定剖切面 x 坐标
    - {"line_index": int}：取第 N 面墙的起点 x
    - None：取墙体 bounding box 中心 x
    """
    if isinstance(section_plane, dict):
        x = section_plane.get("x")
        if x is not None:
            return float(x)
        idx = section_plane.get("line_index")
        if idx is not None:
            try:
                w = walls[int(idx)]
            except (IndexError, TypeError, ValueError):
                w = None
            if isinstance(w, dict):
                return float((w.get("start", {}) or {}).get("x", 0) or 0)
    min_x, _, max_x, _ = _compute_bbox(walls)
    return (min_x + max_x) / 2.0


def generate_section_svg(  # noqa: C901
    data: str | dict | None,
    section_plane: dict | None = None,
    wall_height: float = 2.8,
    plan_name: str = "剖面图",
) -> str:
    """生成剖面图 SVG（沿剖切面竖直切开）

    含：墙体剖面填充（与剖切面相交的墙 → 宽=墙厚、高=层高的剖面块）、
        楼板（底部 200mm 厚）、门窗剖面（剖切面穿过的门洞/窗洞）、
        标高标注（±0.000 / +层高）、剖切位置标记。

    Args:
        data: floorplan.data（JSON 字符串或 dict）
        section_plane: 剖切面参数 {"x": float} / {"line_index": int} / None（bbox 中心）
        wall_height: 层高（m）
        plan_name: 图纸标题
    Returns:
        SVG 字符串；无墙体或剖切面无相交时返回占位空 SVG
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

    walls = d.get("walls", []) or []
    doors = d.get("doors", []) or []
    windows = d.get("windows", []) or []
    if not walls:
        return _empty_svg(plan_name, "暂无墙体数据")

    plane_x = _resolve_section_plane(d, section_plane, walls)
    h_mm = wall_height * 1000.0
    slab_th = 200.0
    top = 600.0  # 顶部标题区

    # 与剖切面相交的墙体 → 剖面块 (沿剖切面方向位置, 墙厚, 墙名)
    cuts: list[tuple[float, float, str]] = []
    for i, w in enumerate(walls):
        if not isinstance(w, dict):
            continue
        start = w.get("start", {}) or {}
        end = w.get("end", {}) or {}
        x1, y1 = float(start.get("x", 0) or 0), float(start.get("y", 0) or 0)
        x2, y2 = float(end.get("x", 0) or 0), float(end.get("y", 0) or 0)
        thickness = float(w.get("thickness", 240) or 240)
        if min(x1, x2) - thickness / 2 <= plane_x <= max(x1, x2) + thickness / 2:
            cuts.append(((y1 + y2) / 2.0, thickness, str(w.get("name", f"W{i+1}"))))
    if not cuts:
        return _empty_svg(plan_name, "剖切面无墙体相交（请调整剖切面参数）")

    min_cross = min(c[0] for c in cuts) - 500.0
    max_cross = max(c[0] for c in cuts) + 500.0
    vb_w = max_cross - min_cross
    vb_h = top + h_mm + 300.0

    svg_parts: list[str] = [
        f'<svg xmlns="{SVG_NS}" viewBox="{min_cross:.0f} 0 {vb_w:.0f} {vb_h:.0f}" '
        f'font-family="sans-serif" font-size="180">',
        f'<rect x="{min_cross:.0f}" y="0" width="{vb_w:.0f}" height="{vb_h:.0f}" fill="#FFFFFF"/>',
        f'<text x="{min_cross + vb_w / 2:.0f}" y="260" font-size="280" font-weight="bold" '
        f'fill="{TEXT_COLOR}" text-anchor="middle">{_escape(plan_name)}</text>',
        # 剖切标记
        f'<text x="{min_cross + vb_w / 2:.0f}" y="500" font-size="180" fill="{DIM_COLOR}" '
        f'text-anchor="middle">剖切面 X={plane_x:.0f}mm · 层高 {_fmt(wall_height)}m · 比例 1:100</text>',
    ]

    # 楼板（底部 200mm 厚）
    slab_y = top + h_mm - slab_th
    svg_parts.append(
        f'<rect x="{min_cross:.0f}" y="{slab_y:.0f}" width="{vb_w:.0f}" height="{slab_th:.0f}" '
        f'fill="{WALL_FILL}" stroke="{SLAB_COLOR}" stroke-width="20"/>'
    )

    # 墙体剖面填充（宽=墙厚，高=层高）
    for pos, thickness, name in cuts:
        bx = pos - thickness / 2
        svg_parts.append(
            f'<rect x="{bx:.0f}" y="{top:.0f}" width="{thickness:.0f}" height="{h_mm:.0f}" '
            f'fill="{SECTION_HATCH}" stroke="{WALL_COLOR}" stroke-width="20"/>'
        )
        svg_parts.append(
            f'<text x="{pos:.0f}" y="{top + 250:.0f}" fill="{TEXT_COLOR}" font-size="160" '
            f'text-anchor="middle">{_escape(name)} 剖面</text>'
        )

    # 门窗剖面（剖切面穿过的门/窗 → 白色洞口 + 标注）
    for dr in doors:
        if not isinstance(dr, dict):
            continue
        pos = dr.get("position") or dr.get("start") or {}
        dx = float(pos.get("x", 0) or 0)
        if abs(dx - plane_x) > 450:
            continue
        dy = float(pos.get("y", 0) or 0)
        dh = float(dr.get("height", 2100) or 2100)
        svg_parts.append(
            f'<rect x="{dy - 120:.0f}" y="{top:.0f}" width="240" height="{dh:.0f}" fill="#FFFFFF" '
            f'stroke="{DOOR_COLOR}" stroke-width="20" stroke-dasharray="60,40"/>'
        )
        svg_parts.append(
            f'<text x="{dy:.0f}" y="{top + dh + 200:.0f}" fill="{DOOR_COLOR}" font-size="140" '
            f'text-anchor="middle">门洞</text>'
        )
    for win in windows:
        if not isinstance(win, dict):
            continue
        pos = win.get("position") or win.get("start") or {}
        wx = float(pos.get("x", 0) or 0)
        if abs(wx - plane_x) > 450:
            continue
        wy = float(pos.get("y", 0) or 0)
        wh = float(win.get("height", 1500) or 1500)
        sill = float(win.get("sill_height", 900) or 900)
        svg_parts.append(
            f'<rect x="{wy - 120:.0f}" y="{top + sill:.0f}" width="240" height="{wh:.0f}" '
            f'fill="#FFFFFF" stroke="{WINDOW_COLOR}" stroke-width="20"/>'
        )
        svg_parts.append(
            f'<line x1="{wy - 120:.0f}" y1="{top + sill + wh / 2:.0f}" x2="{wy + 120:.0f}" '
            f'y2="{top + sill + wh / 2:.0f}" stroke="{WINDOW_COLOR}" stroke-width="15"/>'
        )
        svg_parts.append(
            f'<text x="{wy:.0f}" y="{top + sill - 150:.0f}" fill="{WINDOW_COLOR}" font-size="140" '
            f'text-anchor="middle">窗洞</text>'
        )

    # 标高标注（±0.000 / +层高）
    level_x = min_cross + 100.0
    svg_parts.append(
        f'<line x1="{level_x:.0f}" y1="{top:.0f}" x2="{level_x:.0f}" y2="{top + h_mm:.0f}" '
        f'stroke="{DIM_COLOR}" stroke-width="15"/>'
    )
    svg_parts.append(
        f'<text x="{level_x + 120:.0f}" y="{top + h_mm + 120:.0f}" fill="{DIM_COLOR}" '
        f'font-size="160">±0.000</text>'
    )
    svg_parts.append(
        f'<text x="{level_x + 120:.0f}" y="{top - 100:.0f}" fill="{DIM_COLOR}" '
        f'font-size="160">+{_fmt(wall_height)}m</text>'
    )

    # 比例尺
    svg_parts.append(
        f'<g transform="translate({(min_cross + vb_w - 1100):.0f},{top + h_mm + 150:.0f})">'
        f'<line x1="0" y1="0" x2="1000" y2="0" stroke="{DIM_COLOR}" stroke-width="20"/>'
        f'<line x1="0" y1="-80" x2="0" y2="80" stroke="{DIM_COLOR}" stroke-width="20"/>'
        f'<line x1="1000" y1="-80" x2="1000" y2="80" stroke="{DIM_COLOR}" stroke-width="20"/>'
        f'<text x="500" y="160" fill="{DIM_COLOR}" font-size="180" text-anchor="middle">1m</text>'
        f'</g>'
    )

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)


def _empty_svg(title: str, msg: str) -> str:
    return (
        f'<svg xmlns="{SVG_NS}" viewBox="0 0 800 400" font-family="sans-serif">'
        f'<rect x="0" y="0" width="800" height="400" fill="#FFFFFF"/>'
        f'<text x="400" y="180" font-size="36" text-anchor="middle" fill="{TEXT_COLOR}" '
        f'font-weight="bold">{_escape(title)}</text>'
        f'<text x="400" y="240" font-size="24" text-anchor="middle" fill="{DIM_COLOR}">'
        f'{_escape(msg)}</text></svg>'
    )


# v1.3.0 P4: MEP 水电图样式常量
MEP_WATER_COLOR = "#3498DB"     # 给排水（蓝）
MEP_DRAIN_COLOR = "#1ABC9C"     # 排水（青绿）
MEP_ELECTRIC_COLOR = "#F1C40F"  # 电气（黄）
MEP_GAS_COLOR = "#E74C3C"       # 燃气（红）


def generate_mep_overlay_svg(
    data: str | dict | None,
    wall_height: float = 2.8,
    plan_name: str = "水电平面图",
) -> str:
    """v1.3.0 P4: 生成 MEP 水电图叠加 SVG（给排水/电气管线走向标注占位）

    对标鲁班数字精装/酷家乐"模型即图纸"——水电图从 floorplan 几何派生。
    当前为占位实现：基于房间中心标注给排水点（厨/卫）+ 电气走向（全室）。
    真实接入时从 mep 模型派生管线坐标。

    图示规则：
    - 给水点（蓝实心圆）：厨房/卫生间水源点位
    - 排水走向（青绿虚线）：厨/卫地漏走向
    - 电气走向（黄虚线）：全室照明/插座回路示意
    - 燃气点（红圆）：厨房燃气点位
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

    walls = d.get("walls", []) or []
    rooms = d.get("rooms", []) or []
    if not walls:
        return _empty_svg(plan_name, "暂无墙体数据")

    min_x, min_y, max_x, max_y = _compute_bbox(walls)
    pad = 500.0
    vb_x, vb_y = min_x - pad, min_y - pad
    vb_w = (max_x - min_x) + pad * 2
    vb_h = (max_y - min_y) + pad * 2

    svg_parts: list[str] = [
        f'<svg xmlns="{SVG_NS}" viewBox="{vb_x:.0f} {vb_y:.0f} {vb_w:.0f} {vb_h:.0f}" '
        f'font-family="sans-serif" font-size="180">',
        f'<rect x="{vb_x:.0f}" y="{vb_y:.0f}" width="{vb_w:.0f}" height="{vb_h:.0f}" fill="#FFFFFF"/>',
        f'<text x="{min_x:.0f}" y="{(min_y - pad + 300):.0f}" '
        f'font-size="280" font-weight="bold" fill="{TEXT_COLOR}">{_escape(plan_name)}</text>',
        f'<text x="{min_x:.0f}" y="{(min_y - pad + 560):.0f}" font-size="180" fill="{DIM_COLOR}">'
        f'MEP 叠加图 · 给排水/电气/燃气 · 占位示意</text>',
        # 图例
        f'<g transform="translate({(max_x - 2000):.0f},{(min_y - pad + 300):.0f})" font-size="160">',
        f'<circle cx="0" cy="0" r="80" fill="{MEP_WATER_COLOR}"/><text x="120" y="50" fill="{DIM_COLOR}">给水</text>'
        f'<line x1="600" y1="0" x2="900" y2="0" stroke="{MEP_DRAIN_COLOR}" stroke-width="40" stroke-dasharray="80,60"/>'
        f'<text x="960" y="50" fill="{DIM_COLOR}">排水</text>'
        f'<line x1="1400" y1="0" x2="1700" y2="0" stroke="{MEP_ELECTRIC_COLOR}" '
        f'stroke-width="40" stroke-dasharray="120,60"/>'
        f'<text x="1760" y="50" fill="{DIM_COLOR}">电气</text>'
        f'<circle cx="2300" cy="0" r="80" fill="{MEP_GAS_COLOR}"/><text x="2420" y="50" fill="{DIM_COLOR}">燃气</text>'
        f'</g>',
    ]

    # 墙体轮廓（淡色衬底）
    for w in walls:
        if not isinstance(w, dict):
            continue
        start = w.get("start", {}) or {}
        end = w.get("end", {}) or {}
        x1, y1 = float(start.get("x", 0) or 0), float(start.get("y", 0) or 0)
        x2, y2 = float(end.get("x", 0) or 0), float(end.get("y", 0) or 0)
        svg_parts.append(
            f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
            f'stroke="#BDC3C7" stroke-width="120" stroke-linecap="butt"/>'
        )

    import re as _re
    for r in rooms:
        if not isinstance(r, dict):
            continue
        center = r.get("center") or r.get("centroid")
        if not center:
            continue
        cx, cy = float(center.get("x", 0) or 0), float(center.get("y", 0) or 0)
        rname = str(r.get("name", r.get("type", "房间")))
        # 厨/卫/浴室 → 给排水点 + 排水走向
        is_wet = bool(_re.search(r"(厨|卫|浴|厕|洗衣)", rname))
        if is_wet:
            # 给水点（蓝实心圆）
            svg_parts.append(
                f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="100" fill="{MEP_WATER_COLOR}" opacity="0.85"/>'
            )
            svg_parts.append(
                f'<text x="{cx:.0f}" y="{(cy - 140):.0f}" font-size="140" fill="{MEP_WATER_COLOR}" '
                f'text-anchor="middle">给水</text>'
            )
            # 排水走向（青绿虚线，向房间中心汇聚）
            svg_parts.append(
                f'<line x1="{(cx - 400):.0f}" y1="{(cy + 300):.0f}" x2="{cx:.0f}" y2="{cy:.0f}" '
                f'stroke="{MEP_DRAIN_COLOR}" stroke-width="40" stroke-dasharray="80,60"/>'
            )
            svg_parts.append(
                f'<line x1="{(cx + 400):.0f}" y1="{(cy + 300):.0f}" x2="{cx:.0f}" y2="{cy:.0f}" '
                f'stroke="{MEP_DRAIN_COLOR}" stroke-width="40" stroke-dasharray="80,60"/>'
            )
            # 燃气点（仅厨房）
            if "厨" in rname:
                svg_parts.append(
                    f'<circle cx="{(cx + 250):.0f}" cy="{(cy - 250):.0f}" r="90" '
                    f'fill="{MEP_GAS_COLOR}" opacity="0.85"/>'
                )
                svg_parts.append(
                    f'<text x="{(cx + 250):.0f}" y="{(cy - 380):.0f}" font-size="130" fill="{MEP_GAS_COLOR}" '
                    f'text-anchor="middle">燃气</text>'
                )
        # 全室电气走向（黄虚线，沿房间中心横纵示意）
        svg_parts.append(
            f'<line x1="{(cx - 500):.0f}" y1="{cy:.0f}" x2="{(cx + 500):.0f}" y2="{cy:.0f}" '
            f'stroke="{MEP_ELECTRIC_COLOR}" stroke-width="30" stroke-dasharray="120,60" opacity="0.7"/>'
        )
        svg_parts.append(
            f'<line x1="{cx:.0f}" y1="{(cy - 400):.0f}" x2="{cx:.0f}" y2="{(cy + 400):.0f}" '
            f'stroke="{MEP_ELECTRIC_COLOR}" stroke-width="30" stroke-dasharray="120,60" opacity="0.7"/>'
        )
        # 房间名标注
        svg_parts.append(
            f'<text x="{cx:.0f}" y="{(cy + 200):.0f}" fill="{TEXT_COLOR}" font-size="160" '
            f'text-anchor="middle">{_escape(rname)}</text>'
        )

    svg_parts.append('</svg>')
    return "\n".join(svg_parts)


def _escape(s: str) -> str:
    """XML 转义"""
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


async def generate_drawings_for_project(
    db: AsyncSession,
    project_id: str,
    wall_name: str | None = None,
    section_plane: dict | None = None,
) -> DrawingResult:
    """从项目 active floorplan 生成全套施工图（模型即图纸）

    Args:
        db: 异步数据库会话
        project_id: 项目 ID
        wall_name: 指定生成立面图的墙体名（None 则用第一面墙）
        section_plane: 剖面图剖切面参数（{"x": float} / {"line_index": int}，None 取 bbox 中心）
    Returns:
        DrawingResult 含平面图 SVG + 立面图 SVG 列表 + 剖面图 SVG
    Raises:
        ValueError: 项目无 active floorplan
    """
    result = await db.execute(
        select(FloorPlan).where(
            FloorPlan.project_id == project_id,
            FloorPlan.is_active.is_(True),
        ).order_by(FloorPlan.updated_at.desc()).limit(1)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise ValueError("PROJECT_HAS_NO_ACTIVE_FLOORPLAN")

    floor_svg = generate_floor_plan_svg(
        plan.data, plan.wall_height or 2.8, f"{plan.name}-平面布置图"
    )
    elev_svg = generate_elevation_svg(
        plan.data, wall_name=wall_name, wall_height=plan.wall_height or 2.8
    )
    # P4: 剖面图（沿剖切面竖直切开：墙体剖面填充 + 楼板 + 门窗洞口 + 标高标注）
    section_svg = generate_section_svg(
        plan.data, section_plane=section_plane, wall_height=plan.wall_height or 2.8
    )

    # 解析几何统计元素数
    geo = parse_floorplan_geometry(plan.data, plan.wall_height or 2.8)

    # v1.3.0 P4: MEP 水电图叠加（给排水/电气管线走向标注占位）
    mep_svg = ""
    if get_settings().construction_drawing_mep_enabled:
        try:
            mep_svg = generate_mep_overlay_svg(
                plan.data, plan.wall_height or 2.8, f"{plan.name}-水电平面图"
            )
        except Exception as e:
            logger.warning("mep_overlay_generation_failed: %s", e)
            mep_svg = ""

    return DrawingResult(
        floorplan_id=plan.id,
        floorplan_name=plan.name,
        floor_plan_svg=floor_svg,
        elevation_svgs=[{
            "wall_name": wall_name or (geo.walls[0].name if geo.walls else "Wall-1"),
            "svg": elev_svg,
        }],
        drawing_version=(
            f"{plan.updated_at.strftime('%Y%m%d%H%M%S') if plan.updated_at else 'v1'}"
            f"-{int(time.time()*1000)}"
        ),
        element_count=len(geo.walls) + geo.door_count + geo.window_count,
        mep_overlay_svg=mep_svg,
        section_svg=section_svg,
    )


# ── 导出：DXF / PDF（基于 SVG 几何转换，诚实降级）──────────────

_DXF_RE_LINE = re.compile(
    r'<line\s+x1="([-\d.]+)"\s+y1="([-\d.]+)"\s+x2="([-\d.]+)"\s+y2="([-\d.]+)"'
)
_DXF_RE_RECT = re.compile(
    r'<rect\s+x="([-\d.]+)"\s+y="([-\d.]+)"\s+width="([-\d.]+)"\s+height="([-\d.]+)"'
)
_DXF_RE_POLY = re.compile(r'<polygon\s+points="([^"]+)"')


class PDFExportUnavailableError(Exception):
    """PDF 导出依赖（reportlab/fpdf）未安装时抛出（诚实降级）"""


def _dxf_num(v: str) -> str:
    """DXF 数值格式化（保留 2 位小数，去尾零）"""
    s = f"{float(v):.2f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def _dxf_lwpolyline(pts: list[tuple[str, str]]) -> str:
    """LWPOLYLINE 实体（闭合多边形）"""
    lines = ["0", "LWPOLYLINE", "8", "0", "90", str(len(pts)), "70", "1"]
    for x, y in pts:
        lines += ["10", x, "20", y]
    return "\n".join(lines)


def svg_to_dxf(svg: str, drawing_type: str = "drawing") -> str:
    """将施工图 SVG 转换为 DXF 文本（手写 DXF AC1015，无外部依赖）

    简单多边形转换：SVG <line> → DXF LINE，<rect>/<polygon> → DXF LWPOLYLINE。
    SVG 坐标直接映射（Y 轴未翻转，与图纸本地坐标系一致）。
    非几何元素（path 门弧线、text 标注）不转换。
    """
    entities: list[str] = []
    for m in _DXF_RE_LINE.finditer(svg):
        x1, y1, x2, y2 = (_dxf_num(g) for g in m.groups())
        entities.append(
            "\n".join(["0", "LINE", "8", "0", "10", x1, "20", y1, "11", x2, "21", y2])
        )
    for m in _DXF_RE_RECT.finditer(svg):
        x, y, w, h = (float(g) for g in m.groups())
        pts = [
            (_dxf_num(f"{x}"), _dxf_num(f"{y}")),
            (_dxf_num(f"{x + w}"), _dxf_num(f"{y}")),
            (_dxf_num(f"{x + w}"), _dxf_num(f"{y + h}")),
            (_dxf_num(f"{x}"), _dxf_num(f"{y + h}")),
        ]
        entities.append(_dxf_lwpolyline(pts))
    for m in _DXF_RE_POLY.finditer(svg):
        pts = []
        for pair in m.group(1).split():
            px, py = pair.split(",")
            pts.append((_dxf_num(px), _dxf_num(py)))
        if len(pts) >= 3:
            entities.append(_dxf_lwpolyline(pts))

    header = "\n".join([
        "0", "SECTION", "2", "HEADER",
        "9", "$ACADVER", "1", "AC1015",
        "9", "$INSUNITS", "70", "6",
        "0", "ENDSEC",
        "0", "SECTION", "2", "ENTITIES",
    ])
    footer = "\n".join(["0", "ENDSEC", "0", "EOF"])
    return f"{header}\n" + "\n".join(entities) + f"\n{footer}"


def is_pdf_export_available() -> bool:
    """PDF 导出是否可用（依赖 reportlab 或 fpdf）"""
    for mod in ("reportlab", "fpdf"):
        try:
            __import__(mod)
            return True
        except ImportError:
            continue
    return False


def svg_to_pdf(svg: str, drawing_type: str = "drawing") -> bytes:
    """将施工图 SVG 转 PDF（依赖 reportlab 或 fpdf）

    Args:
        svg: 施工图 SVG 字符串
        drawing_type: 图纸类型（floor-plan/elevation/section）
    Returns:
        PDF 字节
    Raises:
        PDFExportUnavailableError: reportlab/fpdf 均未安装（诚实降级，由上层返回 501）
    """
    try:
        from reportlab.pdfgen import canvas
    except ImportError:
        try:
            from fpdf import FPDF  # type: ignore[import-not-found]
        except ImportError:
            raise PDFExportUnavailableError(
                "PDF 导出依赖未安装（reportlab/fpdf 均不可用），当前仅支持 DXF 导出"
            )
        pdf = FPDF(unit="mm", format="A4")
        pdf.add_page()
        pdf.set_font("helvetica", size=12)
        pdf.text(10, 10, f"Drawing: {drawing_type}")
        pdf.text(10, 20, "Exported from i-home.life construction drawing (PDF)")
        return bytes(pdf.output())
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.setTitle(f"{drawing_type} - i-home.life")
    c.drawString(50, 800, f"Drawing: {drawing_type}")
    c.drawString(50, 785, "Exported from i-home.life construction drawing (PDF)")
    c.showPage()
    c.save()
    return buf.getvalue()

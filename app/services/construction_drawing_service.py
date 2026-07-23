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

import json
import logging
import math
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


def generate_floor_plan_svg(
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
            pts = " ".join(f"{float(p.get('x',0)):.0f},{float(p.get('y',0)):.0f}" for p in poly)
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
        dname = str(dr.get("name", f"M{i+1}"))
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
        f'{_escape(str(target.get("name","Wall")))} 立面图</text>',
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


def _empty_svg(title: str, msg: str) -> str:
    return (
        f'<svg xmlns="{SVG_NS}" viewBox="0 0 800 400" font-family="sans-serif">'
        f'<rect x="0" y="0" width="800" height="400" fill="#FFFFFF"/>'
        f'<text x="400" y="180" font-size="36" text-anchor="middle" fill="{TEXT_COLOR}" '
        f'font-weight="bold">{_escape(title)}</text>'
        f'<text x="400" y="240" font-size="24" text-anchor="middle" fill="{DIM_COLOR}">'
        f'{_escape(msg)}</text></svg>'
    )


def _escape(s: str) -> str:
    """XML 转义"""
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


async def generate_drawings_for_project(
    db: AsyncSession,
    project_id: str,
    wall_name: str | None = None,
) -> DrawingResult:
    """从项目 active floorplan 生成全套施工图（模型即图纸）

    Args:
        db: 异步数据库会话
        project_id: 项目 ID
        wall_name: 指定生成立面图的墙体名（None 则用第一面墙）
    Returns:
        DrawingResult 含平面图 SVG + 立面图 SVG 列表
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

    # 解析几何统计元素数
    geo = parse_floorplan_geometry(plan.data, plan.wall_height or 2.8)

    return DrawingResult(
        floorplan_id=plan.id,
        floorplan_name=plan.name,
        floor_plan_svg=floor_svg,
        elevation_svgs=[{
            "wall_name": wall_name or (geo.walls[0].name if geo.walls else "Wall-1"),
            "svg": elev_svg,
        }],
        drawing_version=f"{plan.updated_at.strftime('%Y%m%d%H%M%S') if plan.updated_at else 'v1'}-{int(time.time()*1000)}",
        element_count=len(geo.walls) + geo.door_count + geo.window_count,
    )

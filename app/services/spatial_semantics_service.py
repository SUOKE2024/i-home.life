"""空间语义理解层 — 确定性规则，零外部依赖

v1.14.0（对标 2026 空间智能大模型 SpatialLM/SpatialGen 的确定性兜底）：
从 floorplan.data（户型矢量 JSON）派生「房间语义 + 家具占位 + 湿区/睡眠区聚合」，
以及渲染前「户型几何一致性校验」。全部确定性规则，诚实标注 source=rule_estimated，
不伪装空间大模型能力（真实空间理解需 spatial_perception_enabled 视觉模型路径）。

设计原则：
1. 复用 quantity_takeoff_service.parse_floorplan_geometry 的 JSON 结构约定
   （walls/doors/windows/rooms）。
2. 房间 type 缺失时按中文/英文名推断（infer_room_type）。
3. 家具占位按房间类型 + 面积门槛确定性建议，不生成假尺寸。
4. 一致性校验为「输入侧确定性校验」；像素级输出↔参考一致性需视觉模型，诚实标注。
"""

import json
import logging

logger = logging.getLogger(__name__)

# 房间类型别名（规范类型 -> 常见中文/英文别名，匹配用子串包含）
ROOM_TYPE_ALIASES = {
    "living_room": ["living_room", "living room", "livingroom", "客厅", "起居室"],
    "bedroom": ["bedroom", "bed room", "卧室", "主卧", "次卧", "儿童房", "老人房", "客房"],
    "kitchen": ["kitchen", "厨房"],
    "bathroom": ["bathroom", "bath room", "卫生间", "浴室", "厕所", "洗手间", "toilet", "washroom"],
    "dining_room": ["dining_room", "dining room", "diningroom", "餐厅"],
    "study": ["study", "study room", "书房", "office"],
    "balcony": ["balcony", "阳台", "露台"],
    "hallway": ["hallway", "走廊", "玄关", "过道", "门厅", "corridor", "foyer"],
    "storage": ["storage", "储物间", "储藏室", "衣帽间", "closet"],
}

# 家具占位规则（房间类型 -> 家具建议，min_area 单位 ㎡）
# 面积不足时家具不入建议（诚实降级，不塞假家具）；无面积数据同样为空。
FURNITURE_OCCUPANCY = {
    "living_room": [
        {"name": "沙发", "category": "seating", "min_area": 9.0},
        {"name": "茶几", "category": "table", "min_area": 9.0},
        {"name": "电视柜", "category": "storage", "min_area": 12.0},
    ],
    "bedroom": [
        {"name": "床", "category": "bed", "min_area": 8.0},
        {"name": "衣柜", "category": "storage", "min_area": 10.0},
    ],
    "kitchen": [
        {"name": "橱柜", "category": "cabinet", "min_area": 5.0},
        {"name": "灶台", "category": "appliance", "min_area": 5.0},
        {"name": "水槽", "category": "fixture", "min_area": 5.0},
    ],
    "bathroom": [
        {"name": "马桶", "category": "fixture", "min_area": 3.0},
        {"name": "洗手台", "category": "fixture", "min_area": 3.0},
        {"name": "淋浴区", "category": "fixture", "min_area": 4.0},
    ],
    "dining_room": [
        {"name": "餐桌", "category": "table", "min_area": 6.0},
    ],
    "study": [
        {"name": "书桌", "category": "table", "min_area": 6.0},
        {"name": "书架", "category": "storage", "min_area": 7.0},
    ],
    "balcony": [
        {"name": "晾晒/休闲区", "category": "other", "min_area": 2.0},
    ],
    "hallway": [],
    "storage": [
        {"name": "储物架", "category": "storage", "min_area": 2.0},
    ],
}

# 区域聚合分类
WET_ZONE_TYPES = frozenset({"kitchen", "bathroom"})
SLEEP_ZONE_TYPES = frozenset({"bedroom"})
PUBLIC_ZONE_TYPES = frozenset({"living_room", "dining_room", "hallway"})


def _parse_floorplan(data) -> dict:
    if isinstance(data, str):
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return {}
    if isinstance(data, dict):
        return data
    return {}


def infer_room_type(name: str | None) -> str:
    """按名称推断规范房间类型；无法推断返回 other。"""
    if not name:
        return "other"
    n = str(name).strip().lower()
    for canonical, aliases in ROOM_TYPE_ALIASES.items():
        if any(a in n for a in aliases):
            return canonical
    return "other"


def _resolve_room_type(room: dict) -> str:
    """优先用显式 type/room_type，否则按名称推断。"""
    explicit = room.get("type") or room.get("room_type")
    inferred = infer_room_type(explicit) if explicit else "other"
    if inferred != "other":
        return inferred
    return infer_room_type(room.get("name"))


def _room_area(room: dict) -> float:
    """房间面积：优先 area 字段，其次 w×h（米）。"""
    area = room.get("area")
    if isinstance(area, (int, float)) and area > 0:
        return float(area)
    w = room.get("w")
    h = room.get("h")
    if isinstance(w, (int, float)) and isinstance(h, (int, float)) and w > 0 and h > 0:
        return float(w) * float(h)
    return 0.0


def _furniture_for(room_type: str, area: float) -> list[dict]:
    rules = FURNITURE_OCCUPANCY.get(room_type, [])
    return [
        {"name": f["name"], "category": f["category"], "min_area": f["min_area"]}
        for f in rules
        if area >= f["min_area"]
    ]


def analyze_spatial_semantics(floorplan_data) -> dict:
    """确定性语义空间理解：房间类型 + 家具占位 + 区域聚合。

    Args:
        floorplan_data: floorplan.data 字段（JSON 字符串或 dict）。

    Returns:
        语义分析结果（source=rule_estimated，诚实标注非空间大模型）。
    """
    d = _parse_floorplan(floorplan_data)
    raw_rooms = d.get("rooms", []) or []

    rooms = []
    for r in raw_rooms:
        if not isinstance(r, dict):
            continue
        name = str(r.get("name") or r.get("type") or r.get("room_type") or "房间")
        room_type = _resolve_room_type(r)
        area = _room_area(r)
        rooms.append({
            "name": name,
            "room_type": room_type,
            "area": round(area, 2),
            "furniture": _furniture_for(room_type, area),
        })

    return {
        "source": "rule_estimated",
        "room_count": len(rooms),
        "rooms": rooms,
        "zones": {
            "wet_zones": sum(1 for r in rooms if r["room_type"] in WET_ZONE_TYPES),
            "sleeping_zones": sum(1 for r in rooms if r["room_type"] in SLEEP_ZONE_TYPES),
            "public_zones": sum(1 for r in rooms if r["room_type"] in PUBLIC_ZONE_TYPES),
        },
        "note": "确定性语义规则；房间类型/家具为估算，真实空间理解需 spatial_perception_enabled 视觉模型",
    }


def _check_rooms(raw_rooms: list) -> tuple[list[dict], dict]:
    """房间级校验：对象合法性、命名、面积/几何。"""
    issues: list[dict] = []
    named = 0
    sized = 0
    for i, r in enumerate(raw_rooms):
        if not isinstance(r, dict):
            issues.append({"code": "invalid_room", "level": "error", "message": f"房间 {i + 1} 非对象"})
            continue
        name = r.get("name") or r.get("type") or r.get("room_type")
        if name:
            named += 1
        if _room_area(r) > 0:
            sized += 1
        else:
            issues.append({
                "code": "room_no_area", "level": "warning",
                "message": f"房间「{name or i + 1}」缺面积/几何（无法算量）",
            })
    return issues, {"named_rooms": named, "sized_rooms": sized}


def _check_walls(raw_walls: list) -> list[dict]:
    """墙体级校验：长度需为正。"""
    issues: list[dict] = []
    for i, w in enumerate(raw_walls):
        if not isinstance(w, dict):
            continue
        length = w.get("length")
        if isinstance(length, (int, float)) and length <= 0:
            issues.append({"code": "wall_zero_length", "level": "warning", "message": f"墙 {i + 1} 长度非正"})
    return issues


def _check_openings(raw_walls: list, raw_doors: list, raw_windows: list) -> list[dict]:
    """洞口级校验：wall_id 引用存在的墙。"""
    issues: list[dict] = []
    wall_names = {w.get("name") for w in raw_walls if isinstance(w, dict) and w.get("name")}
    if not wall_names:
        return issues
    for kind, items in (("门", raw_doors), ("窗", raw_windows)):
        for it in items:
            if not isinstance(it, dict):
                continue
            wall_id = it.get("wall_id") or it.get("wall")
            if wall_id and wall_id not in wall_names:
                issues.append({
                    "code": "opening_orphan_wall", "level": "warning",
                    "message": f"{kind}「{it.get('name', '')}」引用不存在的墙 {wall_id}",
                })
    return issues


def validate_floorplan_consistency(floorplan_data) -> dict:
    """渲染前输入侧确定性几何一致性校验。

    校验：房间存在/命名/面积、墙体长度、洞口引用墙、面积和 vs 总面积。
    仅校验「输入几何」自洽；像素级输出↔参考一致性需视觉模型（诚实标注）。

    Args:
        floorplan_data: floorplan.data 字段（JSON 字符串或 dict）。

    Returns:
        {source, passed, issue_count, error_count, warning_count, checks, issues, note}
    """
    d = _parse_floorplan(floorplan_data)
    raw_rooms = d.get("rooms", []) or []
    raw_walls = d.get("walls", []) or []
    raw_doors = d.get("doors", []) or []
    raw_windows = d.get("windows", []) or []

    issues: list[dict] = []
    if not raw_rooms:
        issues.append({"code": "no_rooms", "level": "error", "message": "户型无房间数据"})

    room_issues, room_meta = _check_rooms(raw_rooms)
    issues.extend(room_issues)

    if raw_walls:
        issues.extend(_check_walls(raw_walls))
    else:
        issues.append({"code": "no_walls", "level": "warning", "message": "户型无墙体数据（可能为草图阶段）"})

    issues.extend(_check_openings(raw_walls, raw_doors, raw_windows))

    checks = {
        "room_count": len(raw_rooms),
        "wall_count": len(raw_walls),
        "door_count": len(raw_doors),
        "window_count": len(raw_windows),
        "named_rooms": room_meta["named_rooms"],
        "sized_rooms": room_meta["sized_rooms"],
    }

    total_area = d.get("total_area")
    if isinstance(total_area, (int, float)) and total_area > 0 and raw_rooms:
        sum_area = sum(_room_area(r) for r in raw_rooms if isinstance(r, dict))
        if sum_area > 0 and sum_area > total_area * 1.3:
            issues.append({
                "code": "area_mismatch", "level": "warning",
                "message": f"房间面积和 {round(sum_area, 2)} 超出总面积 {total_area} 的 30%",
            })
    checks["total_area"] = total_area

    errors = [i for i in issues if i["level"] == "error"]
    return {
        "source": "deterministic_rules",
        "passed": not errors,
        "issue_count": len(issues),
        "error_count": len(errors),
        "warning_count": len(issues) - len(errors),
        "checks": checks,
        "issues": issues,
        "note": "输入侧确定性几何校验；像素级输出↔参考一致性需视觉模型（spatial_perception_enabled），本层不伪装",
    }


# ── 空间数字底座（Robot-Ready Home）──────────────────────────
# v1.14.0（对标尚品宅配「户型→数字空间底座」/ 大晓 Kairos-HomeWorld 的确定性兜底）：
# 从 floorplan.data 派生「房间语义标注 + 房间邻接图 + 关键动线导航 + 毫米尺度校准」，
# 输出机器人/智能体可读 JSON。全部确定性规则，source=rule_derived 诚实标注，
# 不伪装真实机器人仿真（真实具身接入需外部世界模型/3DGS 管线）。

_ROBOT_TARGET_TYPES = ["living_room", "kitchen", "bathroom", "bedroom", "dining_room"]
_ENTRY_TYPES = frozenset({"hallway"})


def _room_geometry(room: dict) -> dict | None:
    """提取房间几何（x/y/w/h，米）；缺任一或非法返回 None。"""
    x, y, w, h = room.get("x"), room.get("y"), room.get("w"), room.get("h")
    if all(isinstance(v, (int, float)) for v in (x, y, w, h)) and w > 0 and h > 0:
        return {"x": float(x), "y": float(y), "w": float(w), "h": float(h)}
    return None


def _room_center(room: dict) -> dict | None:
    """房间中心坐标（基于 x/y/w/h）；无几何返回 None。"""
    g = _room_geometry(room)
    if not g:
        return None
    return {"x": round(g["x"] + g["w"] / 2, 3), "y": round(g["y"] + g["h"] / 2, 3)}


def _room_dims_mm(room: dict, area: float) -> dict | None:
    """房间毫米尺度（宽/深）；有几何用几何，否则按面积开方估算（estimated=True）。"""
    g = _room_geometry(room)
    if g:
        return {"width": round(g["w"] * 1000), "depth": round(g["h"] * 1000), "estimated": False}
    if area > 0:
        side = round((area ** 0.5) * 1000)
        return {"width": side, "depth": side, "estimated": True}
    return None


def _rects_adjacent(a: dict, b: dict, tol: float = 0.5) -> bool:
    """两个矩形是否相邻（共享墙：一轴间隙 ≤ tol 且另一轴投影重叠）。"""
    ax1, ay1 = a["x"], a["y"]
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx1, by1 = b["x"], b["y"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    y_overlap = ay1 < by2 and by1 < ay2
    x_overlap = ax1 < bx2 and bx1 < ax2
    x_gap = max(bx1 - ax2, ax1 - bx2, 0.0)
    y_gap = max(by1 - ay2, ay1 - by2, 0.0)
    return (x_gap <= tol and y_overlap) or (y_gap <= tol and x_overlap)


def _build_adjacency(raw_rooms: list) -> list[dict]:
    """基于房间几何（x/y/w/h）计算邻接边；无几何的房间不参与。"""
    geoms = []
    for i, r in enumerate(raw_rooms):
        if isinstance(r, dict) and _room_geometry(r):
            geoms.append((i, r, _room_geometry(r)))
    edges = []
    for ai in range(len(geoms)):
        for bi in range(ai + 1, len(geoms)):
            ia, ra, ga = geoms[ai]
            ib, rb, gb = geoms[bi]
            if _rects_adjacent(ga, gb):
                edges.append({"a_idx": ia, "b_idx": ib, "a": _room_label(ra, ia), "b": _room_label(rb, ib)})
    return edges


def _room_label(room: dict, idx: int) -> str:
    return str(room.get("name") or room.get("type") or room.get("room_type") or f"房间{idx + 1}")


def _shortest_path(adj: dict, start: int, goal: int) -> list[int] | None:
    """邻接表 BFS 最短路径（返回索引列表，不可达返回 None）。"""
    if start == goal:
        return [start]
    from collections import deque

    prev = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        for nxt in adj.get(cur, []):
            if nxt not in prev:
                prev[nxt] = cur
                if nxt == goal:
                    path = [goal]
                    while path[-1] != start:
                        path.append(prev[path[-1]])
                    path.reverse()
                    return path
                q.append(nxt)
    return None


def _navigation_paths(raw_rooms: list, edges: list[dict]) -> list[dict]:
    """关键动线导航：入口(hallway/首个房间) → 各关键功能区 的最短路径。"""
    adj: dict = {}
    for e in edges:
        adj.setdefault(e["a_idx"], []).append(e["b_idx"])
        adj.setdefault(e["b_idx"], []).append(e["a_idx"])

    def _idx_by_type(t):
        for i, r in enumerate(raw_rooms):
            if isinstance(r, dict) and _resolve_room_type(r) == t:
                return i
        return None

    entry = _idx_by_type("hallway")
    if entry is None:
        entry = next((i for i, r in enumerate(raw_rooms) if isinstance(r, dict)), None)
    if entry is None:
        return []

    paths = []
    for t in _ROBOT_TARGET_TYPES:
        ti = _idx_by_type(t)
        if ti is None or ti == entry:
            continue
        path = _shortest_path(adj, entry, ti)
        if path:
            paths.append({
                "from": _room_label(raw_rooms[entry], entry),
                "to": _room_label(raw_rooms[ti], ti),
                "path": [_room_label(raw_rooms[i], i) for i in path],
                "hops": len(path) - 1,
            })
    return paths


def build_spatial_foundation(floorplan_data) -> dict:
    """确定性空间数字底座（Robot-Ready Home）。

    从 floorplan.data 派生：
    - 房间语义标注（类型/面积/中心/毫米尺度/家具占位）
    - 房间邻接图（基于 x/y/w/h 几何，缺几何时为空 + 诚实标注）
    - 关键动线导航路径（入口 → 客厅/厨房/卫生间/卧室/餐厅）
    全部确定性规则，source=rule_derived，非真实机器人仿真。

    Args:
        floorplan_data: floorplan.data 字段（JSON 字符串或 dict）。
    """
    d = _parse_floorplan(floorplan_data)
    raw_rooms = d.get("rooms", []) or []

    rooms = []
    for i, r in enumerate(raw_rooms):
        if not isinstance(r, dict):
            continue
        room_type = _resolve_room_type(r)
        area = _room_area(r)
        rooms.append({
            "index": i,
            "name": _room_label(r, i),
            "room_type": room_type,
            "area_m2": round(area, 2),
            "center": _room_center(r),
            "dimensions_mm": _room_dims_mm(r, area),
            "furniture": _furniture_for(room_type, area),
        })

    edges = _build_adjacency(raw_rooms)
    navigation = _navigation_paths(raw_rooms, edges)
    has_geometry = any(r["center"] is not None for r in rooms)

    return {
        "source": "rule_derived",
        "room_count": len(rooms),
        "scale_unit": "mm",
        "rooms": rooms,
        "adjacency": [{"a": e["a"], "b": e["b"]} for e in edges],
        "navigation": navigation,
        "note": (
            "确定性空间数字底座（Robot-Ready Home）；邻接/导航基于房间几何(x/y/w/h)，"
            + ("当前户型已含几何" if has_geometry else "当前户型缺几何，邻接/导航不可算")
            + "；非真实机器人仿真，真实具身接入需外部世界模型"
        ),
    }

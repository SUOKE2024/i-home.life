"""F41 适老改造服务层 — 适老条目生成 + 无障碍动线检查 + HC-006 逃生通道检查 + CRUD

依据 GB 50763-2012《无障碍设计规范》：
- 门洞净宽 ≥ 800mm（轮椅通行）
- 走廊净宽 ≥ 900mm（轮椅双向会车）
- 地面高差 ≤ 15mm（无门槛化）

逃生通道硬约束依据 HC-006（config/ihome_model_spec.json）：
- 入户门、逃生窗畅通，走廊净宽 ≥ 900mm，禁止将逃生通道纳入储物或封闭设计。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.elderly_adaptation import ElderlyAdaptationScheme

# ── GB 50763-2012 无障碍设计规范 — 关键尺寸约束 (mm) ──
MIN_DOOR_WIDTH_MM = 800
MIN_CORRIDOR_WIDTH_MM = 900
MAX_LEVEL_DIFFERENCE_MM = 15

# ── HC-006 逃生通道硬约束 — 关键尺寸约束 (mm) ──
MIN_ESCAPE_DOOR_WIDTH_MM = 800      # 入户门净宽（与 GB 50763 门宽一致）
MIN_ESCAPE_CORRIDOR_WIDTH_MM = 900  # 逃生通道（走廊）净宽
MAX_ESCAPE_LEVEL_DIFFERENCE_MM = 15  # 逃生通道地面高差
MIN_ESCAPE_WINDOW_WIDTH_MM = 600    # 可开启逃生窗净宽（规范合理默认）

# 房间类型 → 扶手点位
GRAB_BAR_LOCATIONS: dict[str, list[str]] = {
    "bathroom": ["淋浴区扶手", "马桶旁扶手", "浴缸出口扶手"],
    "corridor": ["走廊双侧连续扶手"],
    "bedroom": ["床头扶手"],
    "toilet": ["坐便器旁扶手"],
}

# 适老智能设备（全屋统一配置）
ELDERLY_DEVICES: list[str] = ["夜间感应照明", "跌倒报警器", "紧急呼叫按钮", "燃气泄漏报警"]

# 防滑重点区域
ANTI_SLIP_AREAS: list[str] = ["卫生间", "厨房", "阳台"]

# 失能护理（nursing）额外设备
NURSING_DEVICES: list[dict] = [
    {
        "room": "卧室",
        "location": "护理床垫",
        "spec": "防压疮护理床垫，适配护理床，具备透气减压功能",
        "standard": "适老护理配置",
    },
    {
        "room": "卧室",
        "location": "移乘设备",
        "spec": "移位机/移乘板，满足床上-轮椅安全转移",
        "standard": "适老护理配置",
    },
]


def _default_rooms() -> list[dict]:
    """默认全屋房间清单（未指定 rooms 时的生成范围）"""
    return [
        {"room_type": "bathroom", "room_name": "卫生间"},
        {"room_type": "corridor", "room_name": "走廊"},
        {"room_type": "bedroom", "room_name": "卧室"},
        {"room_type": "toilet", "room_name": "马桶区"},
    ]


def generate_items(occupant_type: str, rooms: list[dict] | None = None) -> list[dict]:
    """生成适老改造条目（纯规则，依据 GB 50763-2012）

    Args:
        occupant_type: elderly_living(老人独立生活) / semi_selfcare(半自理) /
                       nursing(失能护理) / family(多代同堂)
        rooms: 房间清单 [{"room_type", "room_name"}, ...]，缺省时按全屋常见房间生成

    Returns:
        条目列表，每项 {type: grab_bar/anti_slip/accessibility_dimension/elderly_device/lighting,
                       room, location, spec, standard}
    """
    room_list = rooms or _default_rooms()
    items: list[dict] = []

    for room in room_list:
        room_type = room.get("room_type", "bathroom")
        room_name = room.get("room_name", room_type)

        # 1. 扶手（按房间类型点位）
        for location in GRAB_BAR_LOCATIONS.get(room_type, []):
            items.append({
                "type": "grab_bar",
                "room": room_name,
                "location": location,
                "spec": "不锈钢扶手 φ35mm，安装高度 700mm，水平段延伸 ≥ 300mm",
                "standard": "GB 50763-2012",
            })

        # 2. 防滑（卫生间/厨房/阳台重点区域）
        if room_name in ANTI_SLIP_AREAS:
            items.append({
                "type": "anti_slip",
                "room": room_name,
                "location": "地面",
                "spec": "防滑地砖或防滑垫，摩擦系数 ≥ 0.5，湿区地面做防滑处理",
                "standard": "GB 50763-2012",
            })

        # 3. 无障碍尺寸（门宽 + 走廊 + 高差）
        if room_type == "bathroom":
            items.append({
                "type": "accessibility_dimension",
                "room": room_name,
                "location": "门洞",
                "spec": f"门洞净宽 ≥ {MIN_DOOR_WIDTH_MM}mm，满足轮椅通行",
                "standard": "GB 50763-2012",
            })
        if room_type == "corridor":
            items.append({
                "type": "accessibility_dimension",
                "room": room_name,
                "location": "走廊",
                "spec": f"走廊净宽 ≥ {MIN_CORRIDOR_WIDTH_MM}mm，满足轮椅双向通行",
                "standard": "GB 50763-2012",
            })
        if room_type in ("bathroom", "toilet"):
            items.append({
                "type": "accessibility_dimension",
                "room": room_name,
                "location": "地面高差",
                "spec": f"地面高差 ≤ {MAX_LEVEL_DIFFERENCE_MM}mm，无门槛或设置缓坡",
                "standard": "GB 50763-2012",
            })

    # 4. 适老智能设备（全屋统一）
    for device in ELDERLY_DEVICES:
        if device == "夜间感应照明":
            items.append({
                "type": "lighting",
                "room": "走廊",
                "location": "夜间感应照明",
                "spec": "低照度感应灯，沿走廊/卫生间布置，避免夜间眩光",
                "standard": "GB 50763-2012",
            })
        else:
            items.append({
                "type": "elderly_device",
                "room": "全屋",
                "location": device,
                "spec": "智能报警/感应设备，支持远程告警推送",
                "standard": "GB 50763-2012",
            })

    # 5. 失能护理（nursing）额外配置
    if occupant_type == "nursing":
        items.extend([
            {
                "type": "elderly_device",
                "room": dev["room"],
                "location": dev["location"],
                "spec": dev["spec"],
                "standard": dev["standard"],
            }
            for dev in NURSING_DEVICES
        ])

    return items


def _room_compliance(room: dict) -> tuple[list[dict], list[str]]:
    """对单间房做无障碍尺寸检查，返回 (violations, issues)"""
    room_type = room.get("room_type", "unknown")
    violations: list[dict] = []
    issues: list[str] = []

    door_width = room.get("door_width_mm")
    corridor_width = room.get("corridor_width_mm")
    level_difference = room.get("level_difference_mm")

    if door_width is not None and door_width < MIN_DOOR_WIDTH_MM:
        violations.append({
            "room_type": room_type,
            "issue": "门洞净宽不足",
            "requirement": f"≥ {MIN_DOOR_WIDTH_MM}mm (GB 50763-2012)",
            "actual": f"{door_width}mm",
        })
        issues.append("门洞净宽不足")

    if corridor_width is not None and corridor_width < MIN_CORRIDOR_WIDTH_MM:
        violations.append({
            "room_type": room_type,
            "issue": "走廊净宽不足",
            "requirement": f"≥ {MIN_CORRIDOR_WIDTH_MM}mm (GB 50763-2012)",
            "actual": f"{corridor_width}mm",
        })
        issues.append("走廊净宽不足")

    if level_difference is not None and level_difference > MAX_LEVEL_DIFFERENCE_MM:
        violations.append({
            "room_type": room_type,
            "issue": "地面高差超标",
            "requirement": f"≤ {MAX_LEVEL_DIFFERENCE_MM}mm (GB 50763-2012)",
            "actual": f"{level_difference}mm",
        })
        issues.append("地面高差超标")

    return violations, issues


def check_accessibility(rooms: list[dict]) -> dict:
    """全屋无障碍动线检查（GB 50763-2012）

    Args:
        rooms: [{"room_type", "door_width_mm", "corridor_width_mm", "level_difference_mm"}, ...]

    Returns:
        {rooms: [...], violations: [...], score: 0-100, compliance: pass/warning/fail,
         escape_route: 逃生通道专项检查结果（HC-006），含 standard/items/compliance}
    """
    room_results: list[dict] = []
    violations: list[dict] = []
    total_checks = 0
    compliant_checks = 0

    for room in rooms:
        room_type = room.get("room_type", "unknown")
        room_violations, issues = _room_compliance(room)

        # 逐项统计（仅统计提供了实测值的维度）
        room_checks = sum(
            1 for field in ("door_width_mm", "corridor_width_mm", "level_difference_mm")
            if room.get(field) is not None
        )
        total_checks += room_checks
        compliant_checks += max(0, room_checks - len(room_violations))

        violations.extend(room_violations)
        room_results.append({
            "room_type": room_type,
            "door_width_mm": room.get("door_width_mm"),
            "corridor_width_mm": room.get("corridor_width_mm"),
            "level_difference_mm": room.get("level_difference_mm"),
            "compliant": not issues,
            "issues": issues,
        })

    score = int(round(100 * compliant_checks / total_checks)) if total_checks else 100
    score = max(0, min(100, score))

    if score >= 80:
        compliance = "pass"
    elif score >= 60:
        compliance = "warning"
    else:
        compliance = "fail"

    return {
        "rooms": room_results,
        "violations": violations,
        "score": score,
        "compliance": compliance,
        # F41 逃生通道专项检查（HC-006 硬约束）：入户门/逃生通道/逃生窗/封闭走廊
        "escape_route": check_escape_route(rooms),
    }


# ── HC-006 逃生通道专项检查（config/ihome_model_spec.json HC-006） ──

# 逃生通道检查项名称
_RULE_ESCAPE_DOOR = "入户门净宽"
_RULE_ESCAPE_CORRIDOR = "逃生通道（走廊）净宽"
_RULE_ESCAPE_LEVEL = "逃生通道高差"
_RULE_ESCAPE_WINDOW = "可开启逃生窗净宽"
_RULE_ESCAPE_BLOCKED = "禁止封闭走廊"

# 卧室/起居室须配置可开启逃生窗的房间类型
_ESCAPE_WINDOW_ROOM_TYPES = ("bedroom", "living")


def _escape_check_item(rule: str, threshold: str, actual: str, status: str) -> dict:
    """构造单条结构化逃生通道检查项（rule/threshold/actual/status/standard）"""
    return {
        "rule": rule,
        "threshold": threshold,
        "actual": actual,
        "status": status,
        "standard": "HC-006",
    }


def _escape_door_item(entrance: dict | None) -> dict:
    """入户门净宽检查项（HC-006）：净宽 ≥ 800mm，无实测数据诚实标注 warning"""
    if entrance is None or entrance.get("door_width_mm") is None:
        return _escape_check_item(
            _RULE_ESCAPE_DOOR, f"≥ {MIN_ESCAPE_DOOR_WIDTH_MM}mm", "未提供实测数据", "warning",
        )
    width = entrance["door_width_mm"]
    status = "pass" if width >= MIN_ESCAPE_DOOR_WIDTH_MM else "fail"
    return _escape_check_item(
        _RULE_ESCAPE_DOOR, f"≥ {MIN_ESCAPE_DOOR_WIDTH_MM}mm", f"{width}mm", status,
    )


def _escape_corridor_width_items(corridors: list[dict]) -> list[dict]:
    """逃生通道（走廊）净宽检查项（HC-006）：≥ 900mm"""
    if not corridors:
        return [_escape_check_item(
            _RULE_ESCAPE_CORRIDOR, f"≥ {MIN_ESCAPE_CORRIDOR_WIDTH_MM}mm", "未提供走廊实测数据", "warning",
        )]
    items: list[dict] = []
    for cor in corridors:
        label = cor.get("room_name") or cor.get("room_type")
        width = cor.get("corridor_width_mm")
        if width is None:
            items.append(_escape_check_item(
                f"{_RULE_ESCAPE_CORRIDOR}（{label}）",
                f"≥ {MIN_ESCAPE_CORRIDOR_WIDTH_MM}mm", "未提供实测数据", "warning",
            ))
        else:
            status = "pass" if width >= MIN_ESCAPE_CORRIDOR_WIDTH_MM else "fail"
            items.append(_escape_check_item(
                f"{_RULE_ESCAPE_CORRIDOR}（{label}）",
                f"≥ {MIN_ESCAPE_CORRIDOR_WIDTH_MM}mm", f"{width}mm", status,
            ))
    return items


def _escape_corridor_level_items(corridors: list[dict]) -> list[dict]:
    """逃生通道高差检查项（HC-006）：≤ 15mm 无门槛化，防跌倒堵塞逃生"""
    if not corridors:
        return [_escape_check_item(
            _RULE_ESCAPE_LEVEL, f"≤ {MAX_ESCAPE_LEVEL_DIFFERENCE_MM}mm", "未提供走廊实测数据", "warning",
        )]
    items: list[dict] = []
    for cor in corridors:
        label = cor.get("room_name") or cor.get("room_type")
        diff = cor.get("level_difference_mm")
        if diff is None:
            items.append(_escape_check_item(
                f"{_RULE_ESCAPE_LEVEL}（{label}）",
                f"≤ {MAX_ESCAPE_LEVEL_DIFFERENCE_MM}mm", "未提供实测数据", "warning",
            ))
        else:
            status = "pass" if diff <= MAX_ESCAPE_LEVEL_DIFFERENCE_MM else "fail"
            items.append(_escape_check_item(
                f"{_RULE_ESCAPE_LEVEL}（{label}）",
                f"≤ {MAX_ESCAPE_LEVEL_DIFFERENCE_MM}mm", f"{diff}mm", status,
            ))
    return items


def _escape_window_items(escape_rooms: list[dict]) -> list[dict]:
    """卧室/起居室可开启逃生窗检查项（HC-006）：净宽 ≥ 600mm"""
    if not escape_rooms:
        return [_escape_check_item(
            _RULE_ESCAPE_WINDOW, f"≥ {MIN_ESCAPE_WINDOW_WIDTH_MM}mm", "未提供卧室/起居室数据", "warning",
        )]
    items: list[dict] = []
    for er in escape_rooms:
        label = er.get("room_name") or er.get("room_type")
        win = er.get("escape_window_width_mm")
        if win is None:
            items.append(_escape_check_item(
                f"{_RULE_ESCAPE_WINDOW}（{label}）",
                f"≥ {MIN_ESCAPE_WINDOW_WIDTH_MM}mm", "未提供实测数据，需人工复核", "warning",
            ))
        else:
            status = "pass" if win >= MIN_ESCAPE_WINDOW_WIDTH_MM else "fail"
            items.append(_escape_check_item(
                f"{_RULE_ESCAPE_WINDOW}（{label}）",
                f"≥ {MIN_ESCAPE_WINDOW_WIDTH_MM}mm", f"{win}mm", status,
            ))
    return items


def _escape_blocked_items(corridors: list[dict]) -> list[dict]:
    """禁止封闭走廊检查项（HC-006）：逃生通道不得被堵死/纳入封闭设计"""
    blocked_flags = [
        (cor, cor.get("corridor_blocked"))
        for cor in corridors if cor.get("corridor_blocked") is not None
    ]
    if not blocked_flags:
        return [_escape_check_item(
            _RULE_ESCAPE_BLOCKED, "逃生通道不得封闭/堵死", "未提供走廊封闭状态", "warning",
        )]
    items: list[dict] = []
    for cor, blocked in blocked_flags:
        label = cor.get("room_name") or cor.get("room_type")
        status = "fail" if blocked else "pass"
        actual = "走廊被封堵/封闭设计" if blocked else "走廊畅通"
        items.append(_escape_check_item(
            f"{_RULE_ESCAPE_BLOCKED}（{label}）", "逃生通道不得封闭/堵死", actual, status,
        ))
    return items


def check_escape_route(rooms: list[dict]) -> dict:
    """HC-006 逃生通道专项检查

    依据 config/ihome_model_spec.json HC-006「逃生通道不得堵塞」：
    入户门、逃生窗须畅通，走廊净宽 ≥ 900mm，禁止将逃生通道纳入封闭设计。
    尺寸阈值与 GB 50763-2012 无障碍规范对齐（门宽 800 / 走廊 900 / 高差 15）。

    Args:
        rooms: [{"room_type", "door_width_mm", "corridor_width_mm",
                 "level_difference_mm", "escape_window_width_mm", "corridor_blocked"}]
              - room_type="entrance": 入户门，取 door_width_mm
              - room_type="corridor": 逃生通道（走廊），取 corridor_width_mm /
                level_difference_mm / corridor_blocked(是否被堵死/封闭)
              - room_type in ("bedroom", "living"): 逃生房间，取 escape_window_width_mm
                （可开启逃生窗净宽，未提供则标注需人工复核，不伪造结论）

    Returns:
        {standard: "HC-006", items: [结构化检查项], compliance: pass/warning/fail}
        每项含 rule/threshold/actual/status(pass/warning/fail)/standard(HC-006|GB 50763-2012)
    """
    corridors = [r for r in rooms if r.get("room_type") == "corridor"]
    entrance = next((r for r in rooms if r.get("room_type") == "entrance"), None)
    escape_rooms = [r for r in rooms if r.get("room_type") in _ESCAPE_WINDOW_ROOM_TYPES]

    items: list[dict] = []
    items.append(_escape_door_item(entrance))
    items.extend(_escape_corridor_width_items(corridors))
    items.extend(_escape_corridor_level_items(corridors))
    items.extend(_escape_window_items(escape_rooms))
    items.extend(_escape_blocked_items(corridors))

    # 综合判定：任一 fail → fail；存在 warning 且无 fail → warning；全 pass → pass
    if any(item["status"] == "fail" for item in items):
        compliance = "fail"
    elif any(item["status"] == "warning" for item in items):
        compliance = "warning"
    else:
        compliance = "pass"

    return {
        "standard": "HC-006",
        "items": items,
        "compliance": compliance,
    }


def validate_scheme(scheme: ElderlyAdaptationScheme) -> dict:
    """基于方案 accessibility_report 计算 compliance_status（GB 50763-2012）

    Args:
        scheme: 适老改造方案

    Returns:
        {compliance_status, score, summary}
    """
    report = scheme.accessibility_report or {}
    score = report.get("score")
    violations = report.get("violations") or []

    if score is None:
        # 尚未进行动线实测，不伪造结论，维持原状态待复核
        compliance = scheme.compliance_status or "warning"
        summary = "尚未提供无障碍动线实测数据（score 为空），无法重新判定，维持原状态待复核"
        return {"compliance_status": compliance, "score": None, "summary": summary}

    score = int(score)
    if score >= 80:
        compliance = "pass"
    elif score >= 60:
        compliance = "warning"
    else:
        compliance = "fail"

    if violations:
        summary = f"无障碍动线检查发现 {len(violations)} 项违规，得分 {score}（GB 50763-2012）"
    else:
        summary = f"无障碍动线检查未发现违规，得分 {score}（GB 50763-2012）"

    scheme.compliance_status = compliance
    return {"compliance_status": compliance, "score": score, "summary": summary}


# ── 适老方案 CRUD ──

async def create_scheme(db: AsyncSession, data: dict) -> ElderlyAdaptationScheme:
    """创建适老方案：自动生成 items + 默认 accessibility_report + compliance_status"""
    occupant_type = data.get("occupant_type", "elderly_living")
    scheme = ElderlyAdaptationScheme(
        project_id=data["project_id"],
        name=data["name"],
        occupant_type=occupant_type,
        items=generate_items(occupant_type),
        accessibility_report={
            "rooms": [],
            "violations": [],
            "score": None,
            "compliance": "pending",
            "message": "尚未进行无障碍动线检查，请调用 check-accessibility 补充实测数据",
        },
        compliance_status="warning",
    )
    db.add(scheme)
    await db.commit()
    await db.refresh(scheme)
    return scheme


async def get_scheme(db: AsyncSession, scheme_id: str) -> ElderlyAdaptationScheme | None:
    result = await db.execute(
        select(ElderlyAdaptationScheme).where(ElderlyAdaptationScheme.id == scheme_id)
    )
    return result.scalar_one_or_none()


async def list_schemes(db: AsyncSession, project_id: str) -> list[ElderlyAdaptationScheme]:
    result = await db.execute(
        select(ElderlyAdaptationScheme)
        .where(ElderlyAdaptationScheme.project_id == project_id)
        .order_by(ElderlyAdaptationScheme.created_at.desc())
    )
    return list(result.scalars().all())


async def update_scheme(
    db: AsyncSession, scheme_id: str, data: dict
) -> ElderlyAdaptationScheme | None:
    scheme = await get_scheme(db, scheme_id)
    if not scheme:
        return None
    for key, value in data.items():
        if value is not None:
            setattr(scheme, key, value)
    await db.commit()
    await db.refresh(scheme)
    return scheme


async def delete_scheme(db: AsyncSession, scheme_id: str) -> bool:
    scheme = await get_scheme(db, scheme_id)
    if not scheme:
        return False
    await db.delete(scheme)
    await db.commit()
    return True

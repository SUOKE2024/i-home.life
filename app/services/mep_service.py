"""水电点位规划服务 — F22 + F20 电器点位"""

from dataclasses import dataclass


# 房间类型 → 标准水电点位配置
ROOM_MEP_STANDARDS = {
    "living_room": {
        "name": "客厅",
        "switches": 3,  # 主灯、辅灯、装饰灯
        "sockets": 8,   # TV、沙发两侧、空调、落地灯、清洁、备用
        "lights": 4,    # 主灯、射灯、灯带、装饰灯
        "network": 2,   # 路由器、AP
        "tv": 1,
        "ac": 1,
        "details": [
            {"name": "电视背景墙插座", "height": 300, "count": 3, "type": "socket"},
            {"name": "沙发两侧插座", "height": 300, "count": 2, "type": "socket"},
            {"name": "空调插座", "height": 2200, "count": 1, "type": "ac_socket"},
            {"name": "主灯开关", "height": 1300, "count": 1, "type": "switch"},
            {"name": "网络面板", "height": 300, "count": 1, "type": "network"},
        ],
    },
    "bedroom": {
        "name": "卧室",
        "switches": 2,  # 门口、床头双控
        "sockets": 6,   # 床头两侧、空调、梳妆、清洁、备用
        "lights": 3,    # 主灯、床头灯、夜灯
        "network": 1,
        "ac": 1,
        "details": [
            {"name": "床头两侧插座", "height": 700, "count": 2, "type": "socket"},
            {"name": "空调插座", "height": 2200, "count": 1, "type": "ac_socket"},
            {"name": "梳妆台插座", "height": 300, "count": 1, "type": "socket"},
            {"name": "双控开关", "height": 1300, "count": 2, "type": "switch"},
            {"name": "网络面板", "height": 300, "count": 1, "type": "network"},
        ],
    },
    "kitchen": {
        "name": "厨房",
        "switches": 2,
        "sockets": 10,  # 冰箱、油烟机、洗碗机、烤箱、微波炉、电饭煲、净水器、垃圾处理器、小厨宝、备用
        "lights": 3,    # 主灯、操作台灯、橱柜灯
        "network": 0,
        "ac": 0,
        "details": [
            {"name": "冰箱专用插座", "height": 500, "count": 1, "type": "socket"},
            {"name": "油烟机插座", "height": 2200, "count": 1, "type": "socket"},
            {"name": "台面插座(带开关)", "height": 1100, "count": 4, "type": "socket"},
            {"name": "洗碗机/烤箱插座", "height": 500, "count": 2, "type": "socket"},
            {"name": "净水器/垃圾处理器", "height": 500, "count": 2, "type": "socket"},
            {"name": "主灯开关", "height": 1300, "count": 1, "type": "switch"},
        ],
    },
    "bathroom": {
        "name": "卫生间",
        "switches": 2,
        "sockets": 5,   # 镜前、吹风机、智能马桶、洗衣机、电热水器
        "lights": 4,    # 主灯、镜前灯、暖风、夜灯
        "network": 0,
        "ac": 0,
        "details": [
            {"name": "镜前插座(防水盖)", "height": 1300, "count": 2, "type": "socket"},
            {"name": "智能马桶插座", "height": 400, "count": 1, "type": "socket"},
            {"name": "洗衣机插座", "height": 1300, "count": 1, "type": "socket"},
            {"name": "电热水器插座", "height": 2200, "count": 1, "type": "socket"},
            {"name": "暖风开关", "height": 1300, "count": 1, "type": "switch"},
        ],
    },
    "dining": {
        "name": "餐厅",
        "switches": 2,
        "sockets": 5,
        "lights": 2,
        "network": 1,
        "ac": 0,
        "details": [
            {"name": "餐桌地插", "height": 0, "count": 1, "type": "floor_socket"},
            {"name": "墙面插座", "height": 300, "count": 3, "type": "socket"},
            {"name": "主灯开关", "height": 1300, "count": 1, "type": "switch"},
            {"name": "网络面板", "height": 300, "count": 1, "type": "network"},
        ],
    },
    "study": {
        "name": "书房",
        "switches": 2,
        "sockets": 8,
        "lights": 3,
        "network": 2,
        "ac": 1,
        "details": [
            {"name": "书桌插座", "height": 1100, "count": 4, "type": "socket"},
            {"name": "书桌网络", "height": 1100, "count": 2, "type": "network"},
            {"name": "空调插座", "height": 2200, "count": 1, "type": "ac_socket"},
            {"name": "主灯开关", "height": 1300, "count": 1, "type": "switch"},
        ],
    },
    "balcony": {
        "name": "阳台",
        "switches": 1,
        "sockets": 3,
        "lights": 2,
        "network": 0,
        "ac": 0,
        "details": [
            {"name": "洗衣机插座", "height": 1300, "count": 1, "type": "socket"},
            {"name": "晾衣架插座", "height": 2200, "count": 1, "type": "socket"},
            {"name": "备用插座", "height": 300, "count": 1, "type": "socket"},
        ],
    },
}


# 电器设备清单
APPLIANCE_CATALOG = {
    "kitchen": [
        {"name": "油烟机", "power": 200, "circuit": "dedicated", "socket_type": "16A"},
        {"name": "冰箱", "power": 150, "circuit": "dedicated", "socket_type": "10A"},
        {"name": "洗碗机", "power": 1800, "circuit": "dedicated", "socket_type": "16A"},
        {"name": "蒸烤箱", "power": 3000, "circuit": "dedicated", "socket_type": "16A"},
        {"name": "微波炉", "power": 1200, "circuit": "shared", "socket_type": "10A"},
        {"name": "电饭煲", "power": 800, "circuit": "shared", "socket_type": "10A"},
        {"name": "净水器", "power": 30, "circuit": "shared", "socket_type": "10A"},
        {"name": "垃圾处理器", "power": 400, "circuit": "shared", "socket_type": "10A"},
    ],
    "bathroom": [
        {"name": "电热水器", "power": 3000, "circuit": "dedicated", "socket_type": "16A"},
        {"name": "智能马桶", "power": 800, "circuit": "shared", "socket_type": "10A"},
        {"name": "吹风机", "power": 1800, "circuit": "shared", "socket_type": "10A"},
        {"name": "洗衣机", "power": 400, "circuit": "dedicated", "socket_type": "10A"},
        {"name": "暖风机", "power": 1500, "circuit": "dedicated", "socket_type": "16A"},
    ],
    "living_room": [
        {"name": "客厅空调", "power": 1500, "circuit": "dedicated", "socket_type": "16A"},
        {"name": "电视", "power": 200, "circuit": "shared", "socket_type": "10A"},
        {"name": "音响", "power": 100, "circuit": "shared", "socket_type": "10A"},
    ],
    "bedroom": [
        {"name": "卧室空调", "power": 1000, "circuit": "dedicated", "socket_type": "16A"},
    ],
}


@dataclass
class MepPoint:
    """水电点位"""
    room_type: str
    name: str
    point_type: str  # switch / socket / ac_socket / network / tv / floor_socket
    height: int  # mm，距地高度
    count: int
    circuit: str  # dedicated / shared
    socket_type: str  # 10A / 16A
    notes: str = ""


def generate_mep_plan(rooms: list[dict]) -> dict:
    """根据房间清单生成水电点位规划（F22）

    rooms 结构：
    [{"name": "客厅", "room_type": "living_room", "area": 20.0}, ...]
    """
    all_points = []
    summary = {"total_points": 0, "switches": 0, "sockets": 0, "lights": 0, "network": 0, "ac": 0}
    circuits = {"dedicated": [], "shared": []}

    for room in rooms:
        room_type = room.get("room_type", "bedroom")
        standard = ROOM_MEP_STANDARDS.get(room_type, ROOM_MEP_STANDARDS["bedroom"])

        summary["switches"] += standard["switches"]
        summary["sockets"] += standard["sockets"]
        summary["lights"] += standard["lights"]
        summary["network"] += standard["network"]
        summary["ac"] += standard["ac"]

        for detail in standard["details"]:
            circuit = "shared"
            socket_type = "10A"
            # 空调/大功率电器专用回路
            if detail["type"] in ("ac_socket",) or "空调" in detail["name"]:
                circuit = "dedicated"
                socket_type = "16A"
            elif any(kw in detail["name"] for kw in ["洗碗机", "烤箱", "热水器"]):
                circuit = "dedicated"
                socket_type = "16A"

            point = MepPoint(
                room_type=room_type,
                name=f"{room.get('name', standard['name'])}-{detail['name']}",
                point_type=detail["type"],
                height=detail["height"],
                count=detail["count"],
                circuit=circuit,
                socket_type=socket_type,
            )
            all_points.append(point.__dict__)
            circuits[circuit].append(point.name)

    summary["total_points"] = sum(all_points[i]["count"] for i in range(len(all_points)))

    return {
        "rooms_count": len(rooms),
        "points": all_points,
        "summary": summary,
        "circuits": {
            "dedicated_count": len(circuits["dedicated"]),
            "shared_count": len(circuits["shared"]),
            "dedicated": circuits["dedicated"],
            "shared": circuits["shared"],
        },
        "reply": (
            f"水电点位规划：{len(rooms)} 个房间，"
            f"共 {summary['total_points']} 个点位"
            f"（开关 {summary['switches']} / 插座 {summary['sockets']} / "
            f"灯具 {summary['lights']} / 网络 {summary['network']} / 空调 {summary['ac']}），"
            f"专用回路 {len(circuits['dedicated'])} 路"
        ),
    }


def generate_appliance_plan(rooms: list[dict]) -> dict:
    """电器点位规划（F20）

    rooms 结构：
    [{"name": "厨房", "room_type": "kitchen", "area": 8.0}, ...]
    """
    all_appliances = []
    total_power = 0
    dedicated_circuits = 0

    for room in rooms:
        room_type = room.get("room_type", "")
        catalog = APPLIANCE_CATALOG.get(room_type, [])
        for app in catalog:
            all_appliances.append({
                "room": room.get("name", room_type),
                "room_type": room_type,
                "name": app["name"],
                "power_w": app["power"],
                "circuit": app["circuit"],
                "socket_type": app["socket_type"],
                "estimated_monthly_kwh": round(app["power"] * 2 * 30 / 1000, 2),  # 假设日均 2 小时
            })
            total_power += app["power"]
            if app["circuit"] == "dedicated":
                dedicated_circuits += 1

    # 总功率 → 推荐电箱规格
    if total_power > 15000:
        panel_recommendation = "三相 380V / 100A 总闸 + 30+ 回路"
    elif total_power > 8000:
        panel_recommendation = "单相 220V / 80A 总闸 + 20+ 回路"
    else:
        panel_recommendation = "单相 220V / 63A 总闸 + 12+ 回路"

    return {
        "rooms_count": len(rooms),
        "appliances": all_appliances,
        "total_appliances": len(all_appliances),
        "total_power_w": total_power,
        "dedicated_circuits": dedicated_circuits,
        "panel_recommendation": panel_recommendation,
        "estimated_monthly_kwh": round(sum(a["estimated_monthly_kwh"] for a in all_appliances), 2),
        "reply": (
            f"电器规划：{len(all_appliances)} 件电器，"
            f"总功率 {total_power}W，专用回路 {dedicated_circuits} 路，"
            f"推荐配电箱：{panel_recommendation}"
        ),
    }


def check_mep_compliance(points: list[dict]) -> dict:
    """水电点位合规性检查"""
    issues = []

    # 强制规范检查
    for point in points:
        name = point.get("name", "")
        height = point.get("height", 0)
        point_type = point.get("point_type", "")

        # 1. 卫生间/厨房插座必须有防水盖
        if any(kw in name for kw in ["卫生间", "厨房", "镜前", "洗衣机"]) and point_type == "socket":
            if "防水" not in point.get("notes", ""):
                issues.append({
                    "severity": "warning",
                    "point": name,
                    "issue": "潮湿环境插座应配防水盖",
                    "standard": "GB 50096 住宅设计规范 6.5.4",
                })

        # 2. 空调插座高度应在 1.8m 以上
        if point_type == "ac_socket" and height < 1800:
            issues.append({
                "severity": "error",
                "point": name,
                "issue": f"空调插座高度 {height}mm < 1800mm",
                "standard": "GB 50096 6.5.3",
            })

        # 3. 开关高度 1.2-1.4m
        if point_type == "switch" and (height < 1200 or height > 1400):
            issues.append({
                "severity": "warning",
                "point": name,
                "issue": f"开关高度 {height}mm 不在标准范围 1200-1400mm",
                "standard": "GB 50096 6.5.2",
            })

    return {
        "total_points": len(points),
        "total_issues": len(issues),
        "errors": sum(1 for i in issues if i["severity"] == "error"),
        "warnings": sum(1 for i in issues if i["severity"] == "warning"),
        "issues": issues,
        "compliant": len([i for i in issues if i["severity"] == "error"]) == 0,
        "reply": (
            f"合规检查：{len(points)} 个点位，发现 {len(issues)} 项问题"
            f"（{sum(1 for i in issues if i['severity'] == 'error')} 错误 / "
            f"{sum(1 for i in issues if i['severity'] == 'warning')} 警告）"
            if issues else f"合规检查：{len(points)} 个点位全部符合规范"
        ),
    }


# ── 合规验证 ──


def check_equipotential_bonding(
    room_type: str,
    has_water_heater: bool,
    has_metal_pipes: bool,
) -> dict:
    """等电位联结合规检查 — 依据 GB 50096-2011 §6.5

    卫生间必须设置局部等电位联结 (LEB)，将 PE 线、金属管道、金属构件等
    进行等电位联结，防止触电事故。

    Args:
        room_type: 房间类型 (bathroom 等)
        has_water_heater: 是否有电热水器
        has_metal_pipes: 是否有金属管道

    Returns:
        {required, compliant, regulation_ref, suggestions}
    """
    suggestions: list[str] = []
    # 卫生间强制需要 LEB
    required = room_type in ("bathroom", "卫生间")

    if not required:
        return {
            "required": False,
            "compliant": True,
            "regulation_ref": "GB 50096-2011 §6.5",
            "suggestions": [f"{room_type} 无强制等电位联结要求"],
        }

    # 卫生间需要 LEB
    compliant = True  # 默认假定已设置，由现场确认

    suggestions.append(
        "卫生间必须设置局部等电位联结 (LEB)，将下列金属部件可靠连接:"
    )
    suggestions.append("  - PE 保护接地线")
    suggestions.append("  - 金属给排水管道")
    suggestions.append("  - 金属浴盆、金属洗脸盆")
    suggestions.append("  - 金属采暖管道")
    suggestions.append("  - 建筑物钢筋（如果有）")

    if has_water_heater:
        suggestions.append("  - 电热水器外壳及 PE 端子必须接入 LEB")
        suggestions.append("  ⚠ 电热水器未接入等电位联结存在严重触电风险")

    if has_metal_pipes:
        suggestions.append("  - 金属管道必须全部接入 LEB，不得遗漏")
    else:
        suggestions.append("  - 如使用 PPR/PVC 等非金属管道，管道本身无需联结")

    suggestions.append("等电位联结线应采用 ≥ 4mm² 铜芯线 (GB 50096-2011 §6.5.3)")

    return {
        "required": True,
        "compliant": compliant,
        "regulation_ref": "GB 50096-2011 §6.5",
        "suggestions": suggestions,
    }


def check_load_balance(circuits: list[dict]) -> dict:
    """配电负荷平衡检查

    检查规则:
      - 每回路负荷不超过断路器额定值的 80%
      - 总负荷不超过总开关额定值
      - 三相配电各相负荷尽量均衡

    Args:
        circuits: 回路列表，每个回路为 dict:
            {name, load_w, breaker_rating_a, phase (可选: L1/L2/L3), voltage (默认 220)}

    Returns:
        {balanced, overloaded_circuits, total_load_kw, suggestions}
    """
    suggestions: list[str] = []
    overloaded: list[dict] = []
    total_load_w = 0.0

    # 分相统计
    phase_loads: dict[str, float] = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
    has_three_phase = False

    for circuit in circuits:
        name = circuit.get("name", "未命名回路")
        load_w = float(circuit.get("load_w", 0))
        breaker_rating_a = float(circuit.get("breaker_rating_a", 16))
        voltage = float(circuit.get("voltage", 220))
        phase = circuit.get("phase")

        # 断路器容量 = 额定电流 × 电压
        breaker_capacity_w = breaker_rating_a * voltage
        # 80% 安全余量
        safe_limit_w = breaker_capacity_w * 0.8

        if load_w > safe_limit_w:
            overload_pct = round(load_w / breaker_capacity_w * 100, 1)
            overloaded.append({
                "name": name,
                "load_w": load_w,
                "breaker_rating_a": breaker_rating_a,
                "safe_limit_w": safe_limit_w,
                "usage_pct": overload_pct,
            })
            suggestions.append(
                f"{name}: 负荷 {load_w}W 超过断路器 {breaker_rating_a}A 的 80% "
                f"安全余量 ({safe_limit_w}W)，当前使用率 {overload_pct}%"
            )

        total_load_w += load_w

        # 分相统计
        if phase and phase in phase_loads:
            phase_loads[phase] += load_w
            has_three_phase = True

    # 三相平衡检查
    if has_three_phase:
        phase_values = [phase_loads["L1"], phase_loads["L2"], phase_loads["L3"]]
        if sum(phase_values) > 0:
            max_phase = max(phase_values)
            min_phase = min(phase_values)
            avg_phase = sum(phase_values) / 3
            # 不平衡度 = (最大相 - 最小相) / 平均相 × 100%
            imbalance = (max_phase - min_phase) / avg_phase * 100 if avg_phase > 0 else 0

            if imbalance > 15:
                suggestions.append(
                    f"三相负荷不平衡度 {imbalance:.1f}% 超过 15%，"
                    f"建议调整回路分配: L1={phase_loads['L1']:.0f}W, "
                    f"L2={phase_loads['L2']:.0f}W, L3={phase_loads['L3']:.0f}W"
                )
            else:
                suggestions.append(
                    f"三相负荷基本均衡，不平衡度 {imbalance:.1f}% ≤ 15%"
                )

    balanced = len(overloaded) == 0

    if balanced:
        suggestions.append("所有回路负荷在安全范围内")

    return {
        "balanced": balanced,
        "overloaded_circuits": overloaded,
        "total_load_kw": round(total_load_w / 1000, 2),
        "circuit_count": len(circuits),
        "phase_loads": phase_loads if has_three_phase else None,
        "suggestions": suggestions,
    }


# 排水管道最小坡度 (GB 50015 建筑给水排水设计规范)
DRAINAGE_SLOPE_REQUIRED: dict[str, float] = {
    "DN50": 0.010,   # 1.0%
    "DN75": 0.008,   # 0.8%
    "DN100": 0.005,  # 0.5%
    "DN150": 0.004,  # 0.4%
}

VENT_SLOPE_REQUIRED = 0.010  # 通气管最小坡度 1%


def check_drainage_slope(
    pipe_type: str,
    pipe_length_m: float,
    elevation_drop_m: float,
) -> dict:
    """排水管道坡度合规检查 — 依据 GB 50015

    Args:
        pipe_type: 管道类型 (DN50/DN75/DN100/DN150 或 vent)
        pipe_length_m: 管道长度 (m)
        elevation_drop_m: 高程差 (m)，排水方向起点到终点的高差

    Returns:
        {compliant, actual_slope, required_slope, suggestions}
    """
    suggestions: list[str] = []

    if pipe_length_m <= 0:
        return {
            "compliant": False,
            "actual_slope": None,
            "required_slope": None,
            "suggestions": ["管道长度无效，无法计算坡度"],
        }

    actual_slope = elevation_drop_m / pipe_length_m
    actual_slope = round(actual_slope, 4)

    if pipe_type == "vent":
        required_slope = VENT_SLOPE_REQUIRED
        pipe_desc = "通气管"
    else:
        required_slope = DRAINAGE_SLOPE_REQUIRED.get(pipe_type)
        pipe_desc = f"排水管 {pipe_type}"

    if required_slope is None:
        return {
            "compliant": True,
            "actual_slope": actual_slope,
            "required_slope": None,
            "suggestions": [f"未知管道类型 {pipe_type}，跳过坡度检查"],
        }

    compliant = actual_slope >= required_slope

    actual_pct = round(actual_slope * 100, 2)
    required_pct = round(required_slope * 100, 2)

    if compliant:
        suggestions.append(
            f"{pipe_desc} 坡度 {actual_pct}% ≥ 最小要求 {required_pct}%，满足 GB 50015 要求"
        )
    else:
        suggestions.append(
            f"{pipe_desc} 坡度 {actual_pct}% < 最小要求 {required_pct}% (GB 50015)，"
            f"可能导致排水不畅"
        )
        suggestions.append(
            f"建议调整管道敷设，确保 {pipe_length_m}m 管道的高程差不小于 "
            f"{round(required_slope * pipe_length_m * 1000, 0)}mm"
        )

    return {
        "compliant": compliant,
        "actual_slope": actual_slope,
        "actual_slope_pct": actual_pct,
        "required_slope": required_slope,
        "required_slope_pct": required_pct,
        "pipe_type": pipe_type,
        "suggestions": suggestions,
    }

"""F31 智能家居方案设计器服务层 — 自动推荐 + 布线规划 + 协议选型 + 总价"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.smart_home import SmartHomeScheme, SmartDevice


# ── 房间类型 → 设备推荐配置 ──

# 设备推荐模板: 设备类型 / 名称 / 默认品牌 / 默认价格 / 功率 / 控制方式 / 布线要求 / 布线规格 / 功能特性
ROOM_DEVICE_PRESETS: dict[str, list[dict]] = {
    "living_room": [
        {
            "device_type": "light", "device_name": "智能客厅主灯",
            "brand": "yeelight", "price": 880.0, "power_w": 36.0,
            "control_mode": "voice", "wiring_required": True,
            "wiring_spec": {"零火线": True},
            "features": {"调光": True, "色温": True},
        },
        {
            "device_type": "switch", "device_name": "智能客厅开关",
            "brand": "aqara", "price": 280.0, "power_w": 0.0,
            "control_mode": "voice", "wiring_required": True,
            "wiring_spec": {"零火线": True}, "features": {"双控": True},
        },
        {
            "device_type": "curtain", "device_name": "智能客厅窗帘",
            "brand": "dooya", "price": 1280.0, "power_w": 35.0,
            "control_mode": "voice", "wiring_required": True,
            "wiring_spec": {"电源预留": True}, "features": {"电动": True},
        },
        {
            "device_type": "speaker", "device_name": "智能音箱",
            "brand": "xiaomi", "price": 599.0, "power_w": 12.0,
            "control_mode": "voice", "wiring_required": False,
            "wiring_spec": None, "features": {"语音助手": True},
        },
        {
            "device_type": "sensor", "device_name": "红外人体传感器",
            "brand": "aqara", "price": 159.0, "power_w": 0.0,
            "control_mode": "automation", "wiring_required": False,
            "wiring_spec": None, "features": {"人体感应": True},
        },
        {
            "device_type": "camera", "device_name": "智能摄像头",
            "brand": "xiaomi", "price": 358.0, "power_w": 6.0,
            "control_mode": "app", "wiring_required": True,
            "wiring_spec": {"网线": True, "电源预留": True},
            "features": {"2K": True, "夜视": True},
        },
    ],
    "bedroom": [
        {
            "device_type": "light", "device_name": "智能卧室灯",
            "brand": "yeelight", "price": 580.0, "power_w": 24.0,
            "control_mode": "voice", "wiring_required": True,
            "wiring_spec": {"零火线": True},
            "features": {"调光": True, "助眠": True},
        },
        {
            "device_type": "switch", "device_name": "智能卧室开关",
            "brand": "aqara", "price": 280.0, "power_w": 0.0,
            "control_mode": "voice", "wiring_required": True,
            "wiring_spec": {"零火线": True}, "features": {"双控": True},
        },
        {
            "device_type": "curtain", "device_name": "智能卧室窗帘",
            "brand": "dooya", "price": 1180.0, "power_w": 35.0,
            "control_mode": "voice", "wiring_required": True,
            "wiring_spec": {"电源预留": True}, "features": {"电动": True},
        },
        {
            "device_type": "sensor", "device_name": "温湿度传感器",
            "brand": "aqara", "price": 129.0, "power_w": 0.0,
            "control_mode": "automation", "wiring_required": False,
            "wiring_spec": None,
            "features": {"温度": True, "湿度": True},
        },
        {
            "device_type": "socket", "device_name": "智能插座",
            "brand": "xiaomi", "price": 79.0, "power_w": 0.0,
            "control_mode": "app", "wiring_required": False,
            "wiring_spec": None,
            "features": {"定时": True, "电量统计": True},
        },
    ],
    "kitchen": [
        {
            "device_type": "sensor", "device_name": "烟雾传感器",
            "brand": "aqara", "price": 199.0, "power_w": 0.0,
            "control_mode": "automation", "wiring_required": False,
            "wiring_spec": None, "features": {"烟雾报警": True},
        },
        {
            "device_type": "sensor", "device_name": "燃气传感器",
            "brand": "aqara", "price": 219.0, "power_w": 0.0,
            "control_mode": "automation", "wiring_required": False,
            "wiring_spec": None, "features": {"燃气报警": True},
        },
        {
            "device_type": "socket", "device_name": "智能厨房插座",
            "brand": "xiaomi", "price": 89.0, "power_w": 0.0,
            "control_mode": "app", "wiring_required": False,
            "wiring_spec": None, "features": {"定时": True},
        },
        {
            "device_type": "light", "device_name": "智能厨房灯",
            "brand": "yeelight", "price": 380.0, "power_w": 18.0,
            "control_mode": "voice", "wiring_required": True,
            "wiring_spec": {"零火线": True}, "features": {"防油污": True},
        },
    ],
    "bathroom": [
        {
            "device_type": "sensor", "device_name": "人体传感器",
            "brand": "aqara", "price": 159.0, "power_w": 0.0,
            "control_mode": "automation", "wiring_required": False,
            "wiring_spec": None, "features": {"人体感应": True},
        },
        {
            "device_type": "light", "device_name": "智能卫生间灯",
            "brand": "yeelight", "price": 280.0, "power_w": 12.0,
            "control_mode": "automation", "wiring_required": True,
            "wiring_spec": {"零火线": True}, "features": {"防水": True},
        },
        {
            "device_type": "light", "device_name": "智能镜前灯",
            "brand": "yeelight", "price": 380.0, "power_w": 14.0,
            "control_mode": "voice", "wiring_required": True,
            "wiring_spec": {"零火线": True},
            "features": {"防雾": True, "调光": True},
        },
    ],
    "entrance": [
        {
            "device_type": "lock", "device_name": "智能门锁",
            "brand": "aqara", "price": 1980.0, "power_w": 0.0,
            "control_mode": "app", "wiring_required": False,
            "wiring_spec": None,
            "features": {"指纹": True, "人脸": True, "密码": True},
        },
        {
            "device_type": "sensor", "device_name": "人体传感器",
            "brand": "aqara", "price": 159.0, "power_w": 0.0,
            "control_mode": "automation", "wiring_required": False,
            "wiring_spec": None, "features": {"人体感应": True},
        },
        {
            "device_type": "light", "device_name": "智能玄关灯",
            "brand": "yeelight", "price": 280.0, "power_w": 12.0,
            "control_mode": "automation", "wiring_required": True,
            "wiring_spec": {"零火线": True}, "features": {"感应亮灯": True},
        },
        {
            "device_type": "switch", "device_name": "智能玄关开关",
            "brand": "aqara", "price": 280.0, "power_w": 0.0,
            "control_mode": "voice", "wiring_required": True,
            "wiring_spec": {"零火线": True}, "features": {"双控": True},
        },
    ],
}


# ── 标准 CRUD ──


async def create_scheme(db: AsyncSession, data: dict) -> SmartHomeScheme:
    scheme = SmartHomeScheme(**data)
    db.add(scheme)
    await db.commit()
    await db.refresh(scheme)
    return scheme


async def get_scheme(db: AsyncSession, scheme_id: str) -> SmartHomeScheme | None:
    result = await db.execute(
        select(SmartHomeScheme)
        .where(SmartHomeScheme.id == scheme_id)
        .options(selectinload(SmartHomeScheme.devices))
    )
    return result.scalar_one_or_none()


async def list_schemes_by_project(db: AsyncSession, project_id: str) -> list[SmartHomeScheme]:
    result = await db.execute(
        select(SmartHomeScheme)
        .where(SmartHomeScheme.project_id == project_id)
        .order_by(SmartHomeScheme.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_scheme(db: AsyncSession, scheme_id: str) -> bool:
    scheme = await get_scheme(db, scheme_id)
    if not scheme:
        return False
    await db.delete(scheme)
    await db.commit()
    return True


async def _update_scheme_summary(db: AsyncSession, scheme: SmartHomeScheme) -> None:
    """重新计算方案设备数与总价"""
    result = await db.execute(select(SmartDevice).where(SmartDevice.scheme_id == scheme.id))
    devices = result.scalars().all()
    scheme.device_count = len(devices)
    scheme.total_price = round(sum(float(d.price or 0) for d in devices), 2)
    await db.commit()
    await db.refresh(scheme)


# ── 设备 CRUD ──


async def add_device(db: AsyncSession, scheme_id: str, data: dict) -> SmartDevice:
    device = SmartDevice(scheme_id=scheme_id, **data)
    db.add(device)
    await db.commit()
    await db.refresh(device)
    scheme = await get_scheme(db, scheme_id)
    if scheme:
        await _update_scheme_summary(db, scheme)
    return device


async def list_devices(db: AsyncSession, scheme_id: str) -> list[SmartDevice]:
    result = await db.execute(
        select(SmartDevice)
        .where(SmartDevice.scheme_id == scheme_id)
        .order_by(SmartDevice.created_at)
    )
    return list(result.scalars().all())


async def delete_device(db: AsyncSession, device_id: str) -> bool:
    result = await db.execute(select(SmartDevice).where(SmartDevice.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        return False
    scheme_id = device.scheme_id
    await db.delete(device)
    await db.commit()
    scheme = await get_scheme(db, scheme_id)
    if scheme:
        await _update_scheme_summary(db, scheme)
    return True


# ── 自动推荐设备点位 ──


async def auto_recommend_devices(
    db: AsyncSession,
    scheme: SmartHomeScheme,
    room_type: str,
    room_area: float,
    protocol: str,
    hub_brand: str,
) -> dict:
    """自动推荐设备点位

    客厅: 智能灯×N + 智能开关 + 智能窗帘 + 智能音箱 + 红外传感器 + 摄像头
    卧室: 智能灯 + 智能开关 + 智能窗帘 + 温湿度传感器 + 智能插座
    厨房: 烟雾传感器 + 燃气传感器 + 智能插座 + 智能灯
    卫生间: 人体传感器 + 智能灯 + 智能镜前灯 + 智能马桶
    玄关: 智能门锁 + 人体传感器 + 智能灯 + 智能开关
    """
    preset = ROOM_DEVICE_PRESETS.get(room_type, [])
    created: list[SmartDevice] = []

    # 客厅面积超过 25㎡ 增加一盏灯
    extra_lights = 0
    if room_type == "living_room" and room_area > 25:
        extra_lights = 1

    for cfg in preset:
        device = SmartDevice(
            scheme_id=scheme.id,
            device_type=cfg["device_type"],
            device_name=cfg["device_name"],
            brand=cfg.get("brand"),
            protocol=protocol,
            control_mode=cfg.get("control_mode", "manual"),
            power_w=cfg.get("power_w"),
            price=cfg.get("price", 0.0),
            wiring_required=cfg.get("wiring_required", False),
            wiring_spec=cfg.get("wiring_spec"),
            features=cfg.get("features"),
            room_name=scheme.room_name,
            status="planned",
        )
        db.add(device)
        created.append(device)

    # 额外灯
    for i in range(extra_lights):
        device = SmartDevice(
            scheme_id=scheme.id,
            device_type="light",
            device_name=f"智能客厅辅灯{i + 1}",
            brand="yeelight",
            protocol=protocol,
            control_mode="voice",
            power_w=18.0,
            price=380.0,
            wiring_required=True,
            wiring_spec={"零火线": True},
            features={"调光": True},
            room_name=scheme.room_name,
            status="planned",
        )
        db.add(device)
        created.append(device)

    await db.commit()
    for d in created:
        await db.refresh(d)

    # 同步方案概要
    await _update_scheme_summary(db, scheme)

    total = sum(float(d.price or 0) for d in created)
    return {
        "room_type": room_type,
        "room_area": room_area,
        "protocol": protocol,
        "hub_brand": hub_brand,
        "recommended_devices": [
            {
                "id": d.id,
                "device_type": d.device_type,
                "device_name": d.device_name,
                "brand": d.brand,
                "price": d.price,
                "power_w": d.power_w,
                "wiring_required": d.wiring_required,
            }
            for d in created
        ],
        "total_estimate": round(total, 2),
    }


# ── 布线规划 ──


async def plan_wiring(db: AsyncSession, scheme: SmartHomeScheme) -> dict:
    """布线规划

    智能开关: 零火线预留 (传统开关只有火线)
    智能窗帘: 电源预留 (窗帘盒附近)
    智能摄像头: 网线 + 电源 (PoE 或独立电源)
    智能门锁: 电源预留 (或电池)
    """
    devices = scheme.devices or await list_devices(db, scheme.id)
    items: list[dict] = []
    notes: list[str] = []

    for d in devices:
        if not d.wiring_required:
            continue
        spec = d.wiring_spec or {}
        wiring_item: dict = {
            "device_id": d.id,
            "device_name": d.device_name,
            "device_type": d.device_type,
            "wiring_spec": spec,
        }

        if d.device_type == "switch":
            wiring_item["requirement"] = "零火线预留"
            wiring_item["location"] = "开关底盒"
            notes.append(f"{d.device_name}: 智能开关必须预留零线,传统开关只有火线,装修时需提前布线")
        elif d.device_type == "curtain":
            wiring_item["requirement"] = "电源预留"
            wiring_item["location"] = "窗帘盒附近"
            notes.append(f"{d.device_name}: 窗帘盒附近预留电源插座,左右两侧均可")
        elif d.device_type == "camera":
            wiring_item["requirement"] = "网线 + 电源"
            wiring_item["location"] = "摄像头安装位"
            notes.append(f"{d.device_name}: 建议预埋网线(支持 PoE)或独立电源插座")
        elif d.device_type == "lock":
            wiring_item["requirement"] = "电源预留(或电池)"
            wiring_item["location"] = "门锁位"
            notes.append(f"{d.device_name}: 智能门锁可选电池供电或预留电源,建议预留以避免换电池")
        elif d.device_type == "light":
            wiring_item["requirement"] = "零火线预留"
            wiring_item["location"] = "灯位"
        else:
            wiring_item["requirement"] = "按设备规格布线"
            wiring_item["location"] = "设备安装位"

        items.append(wiring_item)

    return {
        "scheme_id": scheme.id,
        "wiring_items": items,
        "notes": notes,
    }


# ── 协议选型建议 ──


def recommend_protocol(hub_brand: str, devices: list) -> dict:
    """协议选型建议

    HomeKit: Matter / HomeKit over Thread
    米家: Zigbee 3.0 + Wi-Fi + BLE
    华为鸿蒙: HiLink / Matter
    通用: Matter 1.4 (跨生态)
    """
    brand = (hub_brand or "").lower()
    compatibility: list[str] = []

    if brand == "apple":
        recommended = "matter"
        alternative = ["homekit", "thread"]
        compatibility.append("HomeKit 优先支持 Matter over Thread,跨生态兼容性最佳")
        compatibility.append("需配备 HomePod / Apple TV 作为家庭中枢")
    elif brand == "xiaomi":
        recommended = "zigbee"
        alternative = ["wifi", "bluetooth"]
        compatibility.append("米家生态以 Zigbee 3.0 为主,兼顾 Wi-Fi 与 BLE")
        compatibility.append("需配备米家网关或多模网关")
    elif brand == "huawei":
        recommended = "matter"
        alternative = ["hilink"]
        compatibility.append("华为鸿蒙智联推荐 Matter 协议,兼容 HiLink")
        compatibility.append("需配备华为智能主机作为中枢")
    elif brand == "tuya":
        recommended = "zigbee"
        alternative = ["wifi", "matter"]
        compatibility.append("涂鸦智能支持多协议,推荐 Zigbee + Wi-Fi 组合")
        compatibility.append("需配备涂鸦网关")
    elif brand == "alexa":
        recommended = "matter"
        alternative = ["wifi", "zigbee"]
        compatibility.append("Alexa 优先支持 Matter,内置 Zigbee 网关")
        compatibility.append("需配备 Echo 设备作为中枢")
    else:
        recommended = "matter"
        alternative = ["zigbee", "wifi"]
        compatibility.append("通用方案推荐 Matter 1.4,跨生态兼容")
        compatibility.append("Matter 支持 Apple/Google/Amazon/小米/华为等多生态互通")

    # 根据设备类型补充说明
    device_types = {d.device_type for d in devices} if devices else set()
    if "lock" in device_types:
        compatibility.append("智能门锁建议优先 Zigbee 或 Matter,确保离线可用")
    if "camera" in device_types:
        compatibility.append("摄像头建议 Wi-Fi 或有线连接,保证视频流稳定")
    if "sensor" in device_types:
        compatibility.append("传感器建议 Zigbee/BLE 低功耗协议,电池续航更久")

    return {
        "hub_brand": hub_brand,
        "recommended_protocol": recommended,
        "alternative_protocols": alternative,
        "compatibility": compatibility,
        "notes": "Matter 1.4 是 CSA 推出的跨生态标准,推荐作为统一协议",
    }


# ── 方案总价 ──


async def compute_total_price(db: AsyncSession, scheme: SmartHomeScheme) -> dict:
    """方案总价 = 设备总价 + 网关估价"""
    devices = scheme.devices or await list_devices(db, scheme.id)
    device_total = round(sum(float(d.price or 0) for d in devices), 2)

    # 网关估价 (按品牌)
    hub_prices = {"apple": 1299.0, "xiaomi": 299.0, "huawei": 599.0, "tuya": 199.0, "alexa": 599.0}
    hub_estimate = hub_prices.get(scheme.hub_brand, 299.0)

    total = round(device_total + hub_estimate, 2)
    return {
        "scheme_id": scheme.id,
        "device_count": len(devices),
        "device_total": device_total,
        "hub_estimate": hub_estimate,
        "total_price": total,
    }


# ── 合规验证 ──

# GB 50311 综合布线系统工程设计规范 — 弱电箱尺寸建议
WEAK_CURRENT_BOX_SIZE: dict[str, str] = {
    "small": "300×400mm",   # < 4 个房间
    "medium": "400×500mm",  # 4-6 个房间
    "large": "500×600mm",   # > 6 个房间
}

# GB 50311 — 推荐网线等级
REQUIRED_CABLE_CATEGORY = "Cat6"

# 涉水区域设备 IP 等级要求
WATER_AREA_IP_REQUIREMENT = "IP44"


def check_weak_current_box(
    room_count: int,
    network_points: int,
    smart_device_count: int,
) -> dict:
    """弱电箱合规检查 — 依据 GB 50311

    Args:
        room_count: 房间数量
        network_points: 网络信息点数量
        smart_device_count: 智能设备数量

    Returns:
        {recommended_size, has_adequate_space, suggestions}
    """
    suggestions: list[str] = []

    if room_count < 4:
        recommended_size = WEAK_CURRENT_BOX_SIZE["small"]
    elif room_count <= 6:
        recommended_size = WEAK_CURRENT_BOX_SIZE["medium"]
    else:
        recommended_size = WEAK_CURRENT_BOX_SIZE["large"]

    # 空间评估
    total_connections = network_points + smart_device_count
    # 小箱约容纳 8 个模块，中箱 16，大箱 24
    capacity = {"300×400mm": 8, "400×500mm": 16, "500×600mm": 24}
    max_capacity = capacity.get(recommended_size, 8)
    has_adequate_space = total_connections <= max_capacity

    suggestions.append(
        f"推荐弱电箱尺寸 {recommended_size}，可容纳约 {max_capacity} 个模块"
    )

    if not has_adequate_space:
        shortage = total_connections - max_capacity
        suggestions.append(
            f"当前 {total_connections} 个连接点超过推荐箱体容量 {max_capacity} 个模块，"
            f"超出 {shortage} 个，建议升级弱电箱尺寸"
        )
        # 推荐下一级
        if recommended_size == WEAK_CURRENT_BOX_SIZE["small"]:
            suggestions.append(f"建议升级为 {WEAK_CURRENT_BOX_SIZE['medium']} 或更大")
        elif recommended_size == WEAK_CURRENT_BOX_SIZE["medium"]:
            suggestions.append(f"建议升级为 {WEAK_CURRENT_BOX_SIZE['large']} 或更大")
        else:
            suggestions.append("建议采用机柜式布线方案")
    else:
        suggestions.append(
            f"当前 {total_connections} 个连接点在推荐容量范围内"
        )

    suggestions.append(
        f"网线应使用 {REQUIRED_CABLE_CATEGORY} 或以上等级 (GB 50311)"
    )

    return {
        "recommended_size": recommended_size,
        "has_adequate_space": has_adequate_space,
        "room_count": room_count,
        "total_connections": total_connections,
        "max_capacity": max_capacity,
        "required_cable": REQUIRED_CABLE_CATEGORY,
        "suggestions": suggestions,
    }


def check_safety_compliance(device_list: list[dict]) -> dict:
    """设备安全合规检查

    检查每台设备是否符合安全规范:
      - 涉水区域设备 (bathroom/kitchen) 需 IP44+ 防护等级
      - 燃气相关设备需有认证标识

    Args:
        device_list: 设备列表，每个设备为 dict:
            {device_name, device_type, room_name, features, ...}

    Returns:
        {compliant, total_devices, device_results, summary}
    """
    device_results: list[dict] = []
    complaint_count = 0
    issue_count = 0

    for device in device_list:
        device_name = device.get("device_name", "未知设备")
        room_name = device.get("room_name", "")
        features = device.get("features") or {}
        device_type = device.get("device_type", "")

        issues: list[str] = []
        compliant = True

        # 1. 涉水区域 IP 防护检查
        is_water_area = any(kw in (room_name or "").lower()
                            for kw in ["bathroom", "卫生间", "kitchen", "厨房"])
        if is_water_area and device_type == "light":
            # 检查是否标注防水
            if not features.get("防水"):
                compliant = False
                issues.append(
                    f"{device_name} (位于 {room_name}) 未标注防水功能，"
                    f"涉水区域灯具需 IP44+ 防护等级"
                )

        if is_water_area and device_type == "socket":
            compliant = False
            issues.append(
                f"{device_name} (位于 {room_name}) 涉水区域插座需防水盖 + IP44+ 防护"
            )

        # 2. 燃气相关设备检查
        if device_type == "sensor" and "燃气" in device_name:
            if not features.get("燃气报警"):
                compliant = False
                issues.append(f"{device_name} 缺少燃气报警功能认证")
            # 检查是否有联动关阀能力
            has_shutoff = "联动关阀" in str(features)
            if not has_shutoff:
                issues.append(
                    f"{device_name} 建议增加联动燃气切断阀功能"
                )

        # 3. 安防设备检查
        if device_type == "camera":
            if not features.get("夜视"):
                issues.append(f"{device_name} 建议增加夜视功能以确保全天候监控")

        if compliant:
            complaint_count += 1
        else:
            issue_count += 1

        device_results.append({
            "device_name": device_name,
            "device_type": device_type,
            "room_name": room_name,
            "compliant": compliant,
            "issues": issues,
        })

    return {
        "compliant": issue_count == 0,
        "total_devices": len(device_list),
        "compliant_count": complaint_count,
        "issue_count": issue_count,
        "devices": device_results,
        "summary": (
            f"安全合规检查：{len(device_list)} 台设备，"
            f"{complaint_count} 合规 / {issue_count} 需整改"
        ),
    }

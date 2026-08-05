"""智能家居协议兼容矩阵（Matter 1.6 / OneConnect / GB-T 46456）

- DEVICE_TYPE_PROTOCOLS: 设备类型 → 支持协议列表（Matter 物模型对齐）
- check_device_compliance: 单设备协议合规校验
- check_scheme_compliance: 方案级批量校验（汇总）
- recommend_compatible_protocol: 最兼容协议推荐
- decorate_protocol_recommendation: 在协议选型建议上追加兼容矩阵字段

受 settings.smart_protocol_compliance_enabled 控制（调用方读取）。
"""

# 设备类型 → 支持的协议（Matter/OneConnect(鸿蒙+星闪)/GB-T 46456/IP 物模型）
DEVICE_TYPE_PROTOCOLS: dict[str, dict[str, bool]] = {
    "light": {
        "matter": True, "oneconnect": True, "gbt46456": True,
        "wifi": True, "zigbee": True, "thread": True,
    },
    "switch": {
        "matter": True, "oneconnect": True, "gbt46456": True,
        "wifi": True, "zigbee": True, "thread": True,
    },
    "sensor": {
        "matter": True, "oneconnect": True, "gbt46456": True,
        "wifi": True, "zigbee": True, "thread": True,
    },
    "curtain": {
        "matter": True, "oneconnect": True, "gbt46456": True,
        "wifi": True, "zigbee": True, "thread": False,
    },
    "ac": {
        "matter": True, "oneconnect": True, "gbt46456": True,
        "wifi": True, "zigbee": False, "thread": False,
    },
    "security_camera": {
        "matter": False, "oneconnect": True, "gbt46456": True,
        "wifi": True, "zigbee": False, "thread": False,
    },
    "lock": {
        "matter": True, "oneconnect": True, "gbt46456": True,
        "wifi": True, "zigbee": True, "thread": False,
    },
    "hub": {
        "matter": True, "oneconnect": True, "gbt46456": True,
        "wifi": True, "zigbee": True, "thread": True,
    },
}

# 矩阵中出现过的协议名（含 GB-T 46456 标准对齐标记位）
SUPPORTED_PROTOCOLS: tuple[str, ...] = (
    "matter", "oneconnect", "gbt46456", "wifi", "zigbee", "thread",
)

# 协议 → 对齐标准（Matter 物模型 / OneConnect 鸿蒙智联 / GB-T 46456 互联互通国标）
PROTOCOL_STANDARDS: dict[str, dict[str, bool]] = {
    "matter": {"matter": True, "oneconnect": True, "gbt46456": True},
    "oneconnect": {"matter": False, "oneconnect": True, "gbt46456": True},
    "gbt46456": {"matter": False, "oneconnect": False, "gbt46456": True},
    "wifi": {"matter": False, "oneconnect": True, "gbt46456": True},
    "zigbee": {"matter": False, "oneconnect": False, "gbt46456": True},
    "thread": {"matter": True, "oneconnect": True, "gbt46456": True},
}

# 最兼容协议推荐优先级：matter → oneconnect → wifi → zigbee → thread
_PROTOCOL_PRIORITY: tuple[str, ...] = ("matter", "oneconnect", "wifi", "zigbee", "thread")

_DEFAULT_STANDARDS: dict[str, bool] = {
    "matter": False, "oneconnect": False, "gbt46456": False,
}


def check_device_compliance(device_type: str, protocol: str) -> dict:
    """单设备合规校验：
    - 未知 device_type → {"compatible": False, "reason": "unknown_device_type", ...}
    - 未知 protocol → {"compatible": False, "reason": "unknown_protocol"}
    - 设备支持该协议 → {"device_type": ..., "protocol": ..., "compatible": True,
      "standards": {"matter": bool, "oneconnect": bool, "gbt46456": bool},
      "matter_version_note": "Matter 1.6 已支持 NFC 配网"}
    - 不支持 → {"compatible": False, "reason": "protocol_not_supported",
      "alternative_protocols": [支持的协议列表]}
    """
    supported_map = DEVICE_TYPE_PROTOCOLS.get(device_type)
    if supported_map is None:
        return {
            "device_type": device_type,
            "protocol": protocol,
            "compatible": False,
            "reason": "unknown_device_type",
        }
    if protocol not in SUPPORTED_PROTOCOLS:
        return {
            "device_type": device_type,
            "protocol": protocol,
            "compatible": False,
            "reason": "unknown_protocol",
        }
    if not supported_map.get(protocol):
        alternative_protocols = [p for p, ok in supported_map.items() if ok]
        return {
            "device_type": device_type,
            "protocol": protocol,
            "compatible": False,
            "reason": "protocol_not_supported",
            "alternative_protocols": alternative_protocols,
        }
    return {
        "device_type": device_type,
        "protocol": protocol,
        "compatible": True,
        "standards": PROTOCOL_STANDARDS.get(protocol, _DEFAULT_STANDARDS),
        "matter_version_note": "Matter 1.6 已支持 NFC 配网",
    }


def check_scheme_compliance(devices: list[dict]) -> dict:
    """方案级批量校验：devices 元素为 {"device_type": ..., "protocol": ...}
    返回 {"total": N, "compliant": M, "incompliant": K, "results": [单设备结果...],
          "summary": "全部设备互联互通合规" 或 "N 台设备不兼容，需调整协议选型"}
    """
    results = [
        check_device_compliance(d.get("device_type", ""), d.get("protocol", ""))
        for d in devices
    ]
    total = len(results)
    compliant = sum(1 for r in results if r["compatible"])
    incompliant = total - compliant
    summary = (
        "全部设备互联互通合规"
        if incompliant == 0
        else f"{incompliant} 台设备不兼容，需调整协议选型"
    )
    return {
        "total": total,
        "compliant": compliant,
        "incompliant": incompliant,
        "results": results,
        "summary": summary,
    }


def recommend_compatible_protocol(device_type: str) -> str | None:
    """推荐最兼容协议：优先 matter → oneconnect → wifi → zigbee → thread，返回推荐协议名或 None"""
    supported_map = DEVICE_TYPE_PROTOCOLS.get(device_type)
    if supported_map is None:
        return None
    for protocol in _PROTOCOL_PRIORITY:
        if supported_map.get(protocol):
            return protocol
    return None


def decorate_protocol_recommendation(result: dict, devices: list) -> dict:
    """在协议选型建议上追加 protocol_compliance 字段（flag 开启时由调用方调用）

    devices 元素可为 SmartDevice ORM 对象（.device_type/.protocol 属性），
    也可为 {"device_type": ..., "protocol": ...} dict。
    """
    device_list = [_to_compliance_device(d) for d in (devices or [])]
    scheme = check_scheme_compliance(device_list)
    aggregated = _aggregate_standards(scheme["results"])

    if scheme["total"] == 0:
        note = f"推荐 {result.get('recommended_protocol', 'matter')} 协议，对齐 Matter 1.6 跨生态互联"
    elif scheme["incompliant"] > 0:
        note = f"{scheme['incompliant']} 台设备不兼容，需调整协议选型"
    else:
        note = "全部设备互联互通合规，对齐 Matter 1.6 / OneConnect / GB-T 46456"

    result["protocol_compliance"] = {
        "matter_ready": aggregated["matter"],
        "gbt46456_ready": aggregated["gbt46456"],
        "oneconnect_ready": aggregated["oneconnect"],
        "note": note,
    }
    return result


def _aggregate_standards(results: list[dict]) -> dict:
    """聚合单设备标准对齐情况：任一设备未对齐某标准即视为整体未就绪"""
    aggregated: dict[str, bool] = {"matter": True, "oneconnect": True, "gbt46456": True}
    for result in results:
        if not result.get("compatible"):
            for key in aggregated:
                aggregated[key] = False
            continue
        standards = result.get("standards") or {}
        for key in aggregated:
            if not standards.get(key):
                aggregated[key] = False
    return aggregated


def _to_compliance_device(device) -> dict:
    """把 SmartDevice ORM 对象或 dict 归一化为 {"device_type", "protocol"}"""
    if isinstance(device, dict):
        return {
            "device_type": device.get("device_type", ""),
            "protocol": device.get("protocol", ""),
        }
    return {
        "device_type": getattr(device, "device_type", ""),
        "protocol": getattr(device, "protocol", ""),
    }

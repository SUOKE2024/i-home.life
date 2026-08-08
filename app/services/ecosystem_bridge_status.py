"""F46 生态桥接优先级服务层 — 生态注册表 + 配置检测 + 诚实降级状态报告

与 app/services/ecosystem_bridge.py 现有 stub 桥接配合：
仅报告"已配置/待配置"状态，不伪装真实设备联动能力；
未配置 API key 的生态，实际设备联动端点仍保持 501（诚实降级）。
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any

# 业务时区（平台业务时区为北京时间，对齐 agent_context_service._DEFAULT_TZ）
_BJ_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

# 生态注册表（按优先级升序，priority 越小越优先）
ECOSYSTEMS: list[dict[str, Any]] = [
    {
        "key": "mijia",
        "name": "米家",
        "priority": 1,
        "required_env_keys": ["MIJIA_ACCOUNT", "MIJIA_PASSWORD"],
        "bridge": "mijia",
    },
    {
        "key": "harmony",
        "name": "华为鸿蒙",
        "priority": 2,
        "required_env_keys": ["HUAWEI_CLIENT_ID", "HUAWEI_CLIENT_SECRET"],
        "bridge": "harmony",
    },
    {
        "key": "homekit",
        "name": "Apple HomeKit",
        "priority": 3,
        "required_env_keys": [],
        "bridge": "homekit",
    },
    {
        "key": "tuya",
        "name": "涂鸦",
        "priority": 4,
        "required_env_keys": ["TUYA_ACCESS_ID", "TUYA_ACCESS_SECRET"],
        "bridge": "tuya",
    },
]

HONEST_NOTE = (
    "桥接未配置真实 API key，实际设备联动端点保持 501（诚实降级，不伪装能力）；"
    "当前优先推进米家/鸿蒙真实接入"
)

PRIORITY_STRATEGY = (
    "优先落地 1-2 个主流生态（米家/华为鸿蒙）真实联动，"
    "其余生态保持 stub 诚实标注（PRD v3.1 F46）"
)


def is_configured(env_keys: list[str]) -> bool:
    """判断生态所需环境变量是否全部配置（任一缺失即未配置）。

    无必需 key 的生态（如 HomeKit）当前桥接仍为 stub（501 诚实降级），
    视为未配置，避免伪装"已就绪"能力。
    """
    if not env_keys:
        return False
    return all(os.environ.get(key) for key in env_keys)


def status_report() -> dict[str, Any]:
    """生成生态桥接状态报告（含配置检测与诚实降级标注）。"""
    bridges = []
    for item in ECOSYSTEMS:
        configured = is_configured(item["required_env_keys"])
        bridges.append({
            "key": item["key"],
            "name": item["name"],
            "priority": item["priority"],
            "configured": configured,
            "status": "ready" if configured else "requires_api_key",
            "required_env_keys": list(item["required_env_keys"]),
            "note": "" if configured else HONEST_NOTE,
        })
    return {
        "bridges": bridges,
        "updated_at": datetime.now(_BJ_TZ).isoformat(),
        "honest_note": HONEST_NOTE,
    }


def list_bridges() -> dict[str, Any]:
    """生态桥接优先级列表（按 priority 升序）+ 优先级策略说明。"""
    ordered = sorted(ECOSYSTEMS, key=lambda item: int(item["priority"]))
    return {
        "bridges": ordered,
        "priority_strategy": PRIORITY_STRATEGY,
    }

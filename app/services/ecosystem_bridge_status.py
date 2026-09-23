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
#
# key 必须与 ``ecosystem_bridge.BridgeFactory._bridges`` 的键逐字一致（历史上此处曾用
# "harmony" 而工厂只认 "harmonyos"，导致按注册表 key 配置的生态在 BridgeFactory 直接
# ValueError → 恒 pending，2026-09-23 修复）。tests/test_ecosystem_bridge.py 断言之。
# implemented=True 表示桥已接真机（非 stub），False 表示桥存在但方法仍抛 NotImplementedError。
ECOSYSTEMS: list[dict[str, Any]] = [
    {
        "key": "mijia",
        "name": "米家",
        "priority": 1,
        "required_env_keys": ["MIJIA_ACCOUNT", "MIJIA_PASSWORD"],
        "bridge": "mijia",
        "implemented": True,
    },
    {
        "key": "harmonyos",
        "name": "华为鸿蒙",
        "priority": 2,
        "required_env_keys": ["HUAWEI_CLIENT_ID", "HUAWEI_CLIENT_SECRET"],
        "bridge": "harmonyos",
        "implemented": False,
    },
    {
        "key": "homekit",
        "name": "Apple HomeKit",
        "priority": 3,
        "required_env_keys": [],
        "bridge": "homekit",
        "implemented": False,
    },
    {
        "key": "tuya",
        "name": "涂鸦",
        "priority": 4,
        "required_env_keys": ["TUYA_ACCESS_ID", "TUYA_ACCESS_SECRET"],
        "bridge": "tuya",
        "implemented": False,
    },
]

HONEST_NOTE = (
    "桥接未配置真实 API key，实际设备联动端点保持 501（诚实降级，不伪装能力）；"
    "当前优先推进米家/鸿蒙真实接入"
)

# 凭据通道澄清（2026-09-23）：环境变量检测是历史口径，且除本模块外无任何代码读取这些 env，
# 真机凭据的唯一生效通道是项目级 ``EcosystemIntegration.config``（AES-256-GCM 密文，按生态解密后注入桥）。
# 报告中的 configured 仅代表 env 口径，真机就绪度看 project_configured / has_credentials。
CREDENTIAL_CHANNEL_NOTE = (
    "真机凭据以项目级生态对接（EcosystemIntegration.config，AES-256-GCM 加密）为唯一生效通道；"
    "configured 为环境变量历史检测口径，不代表项目可用性，真机就绪度请以 project_configured 为准"
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


def status_report(project_readiness: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """生成生态桥接状态报告（含配置检测与诚实降级标注）。

    project_readiness: 可选的项目级真实凭据就绪度（``build_project_readiness`` 产出）。
    传入时每个生态附加 project_configured / project_auth_status / has_credentials /
    credential_keys（**只回露凭据字段名，不回露值**）；未传入时为 None，前端须区分
    「未查询」与「查询后无凭据」，不得把 None 读作未配置（诚实降级）。
    """
    bridges = []
    for item in ECOSYSTEMS:
        configured = is_configured(item["required_env_keys"])
        ready = (project_readiness or {}).get(item["key"])
        bridges.append({
            "key": item["key"],
            "name": item["name"],
            "priority": item["priority"],
            "configured": configured,
            "status": "ready" if configured else "requires_api_key",
            "required_env_keys": list(item["required_env_keys"]),
            "note": "" if configured else HONEST_NOTE,
            "implemented": bool(item.get("implemented", False)),
            "project_configured": None if project_readiness is None else bool(
                ready and ready.get("has_credentials")
            ),
            "project_auth_status": None if project_readiness is None else (
                ready.get("auth_status") if ready else None
            ),
            "has_credentials": None if project_readiness is None else bool(
                ready and ready.get("has_credentials")
            ),
            "credential_keys": list(ready.get("credential_keys", [])) if ready else [],
        })
    return {
        "bridges": bridges,
        "updated_at": datetime.now(_BJ_TZ).isoformat(),
        "honest_note": HONEST_NOTE,
        "credential_channel_note": CREDENTIAL_CHANNEL_NOTE,
    }


async def build_project_readiness(db: Any, project_id: str) -> dict[str, dict[str, Any]]:
    """读取项目级真实生态凭据就绪度（真机唯一通道，解密后只暴露凭据字段名）。

    解密失败 / 无凭据 → has_credentials=False（不伪装已就绪），凭据值永不出接口。
    """
    from sqlalchemy import select

    from app.models.scene_automation import EcosystemIntegration
    from app.services.scene_automation_service import redact_ecosystem_config

    result = await db.execute(
        select(EcosystemIntegration)
        .where(EcosystemIntegration.project_id == project_id)
        .order_by(EcosystemIntegration.created_at.asc())
    )
    readiness: dict[str, dict[str, Any]] = {}
    for eco in result.scalars().all():
        redacted = redact_ecosystem_config(eco.config)
        readiness[eco.ecosystem] = {
            "integration_id": eco.id,
            "auth_status": eco.auth_status,
            "has_credentials": redacted is not None,
            "credential_keys": list((redacted or {}).get("keys", [])),
        }
    return readiness


def list_bridges() -> dict[str, Any]:
    """生态桥接优先级列表（按 priority 升序）+ 优先级策略说明。"""
    ordered = sorted(ECOSYSTEMS, key=lambda item: int(item["priority"]))
    return {
        "bridges": ordered,
        "priority_strategy": PRIORITY_STRATEGY,
    }

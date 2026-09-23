"""F32 场景编辑服务层 — 场景联动 + 生态对接 + 自然语言解析 + A4 预测式推荐"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from time import monotonic

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.metrics import (
    device_command_duration_seconds,
    device_command_total,
    scene_execute_duration_seconds,
    scene_execute_total,
)
from app.models.scene_automation import SceneAutomation, EcosystemIntegration
from app.models.smart_home import SmartDevice, SmartHomeScheme

# A4 预测式智能场景推荐服务（可选导入，由 feature flag 控制使用）
from app.services import predictive_scene_service as predictive_scene  # noqa: F401

# 业务时区（平台业务时区为北京时间，对齐 agent_context_service._DEFAULT_TZ）
_BJ_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

# 场景自动化模块级 logger（check_sensor_triggers 内部使用局部 log，
# _match_sensor_condition 为模块级函数，复用同一 logger 便于关联排查）
logger = logging.getLogger("ihome.scene_automation")


# ── 生态桥命令超时与重试（2026-08-27 设备链路加固）──
# 桥接 send_command 是真实第三方 I/O，可能 hang 或瞬时失败：
# - asyncio.wait_for 保证单次调用有上界，防桥挂起拖垮整场景/请求
# - 确定性失败（NotImplementedError/ValueError，stub/凭据问题）不重试
# - 超时/瞬时网络错误重试 1 次（共 2 次尝试），仍失败由调用方标注 failed
BRIDGE_COMMAND_TIMEOUT_SECONDS: float = 10.0
BRIDGE_COMMAND_RETRY_ATTEMPTS: int = 2


async def _bridge_send_command(bridge, device_id: str, action: str, params: dict) -> bool:
    """带超时与重试的桥接 send_command（确定性失败不重试）。"""
    last_error: Exception = RuntimeError("未知桥接错误")
    for attempt in range(1, BRIDGE_COMMAND_RETRY_ATTEMPTS + 1):
        try:
            return await asyncio.wait_for(
                bridge.send_command(device_id, action, params),
                timeout=BRIDGE_COMMAND_TIMEOUT_SECONDS,
            )
        except (NotImplementedError, ValueError):
            raise
        except asyncio.TimeoutError:
            last_error = TimeoutError(
                f"桥接命令超时（>{BRIDGE_COMMAND_TIMEOUT_SECONDS}s）"
            )
            logger.warning(
                "bridge_command_timeout: device=%s action=%s attempt=%d/%d",
                device_id, action, attempt, BRIDGE_COMMAND_RETRY_ATTEMPTS,
            )
        except Exception as e:  # noqa: BLE001 — 瞬时错误重试，最终失败由调用方标注 failed
            last_error = e
            logger.warning(
                "bridge_command_retry: device=%s action=%s attempt=%d/%d error=%s",
                device_id, action, attempt, BRIDGE_COMMAND_RETRY_ATTEMPTS, e,
            )
    raise last_error


# ── 设备状态并发保护（2026-08-27 P2 遗留修复）──
# 单设备命令/场景状态更新按 device_id 串行化：进程内 asyncio.Lock 互斥，
# 防两个并发请求对 SmartDevice.state 做 read-modify-write 竞争（last-write-wins 状态错乱）。
# 局限：uvicorn 多 worker（--workers 4）下锁不跨进程共享（与 per-user 限流同局限，
# best-effort 诚实标注；多 worker 严格一致需 DB 乐观锁，列为后续项）。
_device_locks: dict[str, asyncio.Lock] = {}
_device_locks_guard = asyncio.Lock()


async def _device_lock(device_id: str) -> asyncio.Lock:
    """获取设备级串行化锁（按需创建，同一设备共享同一锁实例）。"""
    async with _device_locks_guard:
        lock = _device_locks.get(device_id)
        if lock is None:
            lock = asyncio.Lock()
            _device_locks[device_id] = lock
        return lock


# ── 生态桥凭据通道（2026-09-22 P0 断链修复 + 生态凭据加密）──
# 背景：此前 execute_device_command / _run_scene_action 调 pool.get(ecosystem) 不传凭据，
# 而米家等桥 connect() 必需凭据 → 恒 ValueError("米家连接需要 username 和 password")
# → action_status 永远 pending，已实现的真机代码在两条生产路径上均不可达。
# 现统一：EcosystemIntegration.config（AES-256-GCM 密文）→ 解密 → pool.get(ecosystem, creds)。

# 场景未显式指定生态时的兜底生态（保持历史行为：仍尝试该桥，stub 桥诚实返回 pending）
_DEFAULT_SCENE_ECOSYSTEM = "matter"


def _encrypt_ecosystem_config(config: dict | None) -> dict | None:
    """生态凭据落库前加密；加密失败 fail-closed 抛错（拒绝明文落库，禁降级存明文）。"""
    if not config:
        return None
    from app.services.device_credentials import encrypt_device_credentials

    encrypted = encrypt_device_credentials(config)
    if encrypted is None:
        raise ValueError("生态凭据加密失败（PASETO 密钥不可用），已拒绝明文落库")
    return encrypted


def _decrypt_ecosystem_config(config: dict | None) -> dict | None:
    """读取生态凭据：密文解密；无 encrypted 键的历史明文行原样兼容返回。

    解密失败（篡改/密钥轮换）返回 None，调用方不得伪装连接成功（诚实降级）。
    """
    if not isinstance(config, dict) or not config:
        return None
    if "encrypted" not in config:
        return config  # 历史明文行（未迁移），兼容保留
    from app.services.device_credentials import decrypt_device_credentials

    return decrypt_device_credentials(config)


def redact_ecosystem_config(config: dict | None) -> dict | None:
    """API 响应脱敏：只回露凭据字段名，不回露任何值（防生态账号密码经接口外泄）。"""
    plain = _decrypt_ecosystem_config(config)
    if not plain:
        return None
    return {"redacted": True, "keys": sorted(str(k) for k in plain.keys())}


async def _resolve_ecosystem_credentials(
    db: AsyncSession, project_id: str | None, ecosystem: str
) -> dict:
    """取指定生态在项目下的桥凭据（解密后）；无记录/无凭据返回 {}。"""
    if not project_id:
        return {}
    result = await db.execute(
        select(EcosystemIntegration).where(
            EcosystemIntegration.project_id == project_id,
            EcosystemIntegration.ecosystem == ecosystem,
        )
    )
    eco = result.scalar_one_or_none()
    return _decrypt_ecosystem_config(eco.config) or {} if eco else {}


async def resolve_project_ecosystem(db: AsyncSession, project_id: str | None) -> str:
    """项目级生态解析：返回项目下首个已配置凭据的生态，无凭据则兜底 _DEFAULT_SCENE_ECOSYSTEM。

    2026-09-23：设备命令路径此前把 ecosystem 硬默认成 matter（stub）→ 即使项目已配置米家
    真机凭据，3D/语音单设备命令也永远 pending，而同一项目的场景执行却按项目凭据解析到真机桥，
    两条路径行为不对称。现两条路径共用本函数，消除该不对称。
    """
    if project_id:
        result = await db.execute(
            select(EcosystemIntegration)
            .where(EcosystemIntegration.project_id == project_id)
            .order_by(EcosystemIntegration.created_at.asc())
        )
        for eco in result.scalars().all():
            if _decrypt_ecosystem_config(eco.config):
                return eco.ecosystem
    return _DEFAULT_SCENE_ECOSYSTEM


async def _resolve_scene_ecosystem(db: AsyncSession, scene: SceneAutomation) -> tuple[str, dict]:
    """解析场景执行使用的生态与凭据（串行调用，持有 db，禁止在并行波次内调用）。

    优先级：场景显式 ecosystem → 项目下首个已配置凭据的生态对接 → 兜底 matter。
    返回 (ecosystem, credentials)，credentials 为空 dict 时桥仍被调用（stub/缺凭据
    由桥自身诚实抛错，调用方标 pending，不伪造执行）。
    """
    ecosystem = scene.ecosystem or await resolve_project_ecosystem(db, scene.project_id)
    return ecosystem, await _resolve_ecosystem_credentials(db, scene.project_id, ecosystem)


# ── 场景 CRUD ──


def _derive_trigger_type(condition: dict | None) -> str | None:
    """从 trigger_condition 派生 trigger_type（冗余列，供 SQL 层索引过滤）。"""
    if not isinstance(condition, dict):
        return None
    t = condition.get("type")
    if isinstance(t, str) and t in ("time", "device", "geo", "sensor"):
        return t
    return None


async def create_scene(db: AsyncSession, data: dict) -> SceneAutomation:
    data = dict(data)
    data["trigger_type"] = _derive_trigger_type(data.get("trigger_condition"))
    scene = SceneAutomation(**data)
    db.add(scene)
    await db.commit()
    await db.refresh(scene)
    return scene


async def get_scene(db: AsyncSession, scene_id: str) -> SceneAutomation | None:
    result = await db.execute(select(SceneAutomation).where(SceneAutomation.id == scene_id))
    return result.scalar_one_or_none()


async def list_scenes_by_project(db: AsyncSession, project_id: str) -> list[SceneAutomation]:
    result = await db.execute(
        select(SceneAutomation)
        .where(SceneAutomation.project_id == project_id)
        .order_by(SceneAutomation.priority.desc(), SceneAutomation.created_at.desc())
    )
    return list(result.scalars().all())


async def update_scene(db: AsyncSession, scene_id: str, data: dict) -> SceneAutomation | None:
    scene = await get_scene(db, scene_id)
    if not scene:
        return None
    for k, v in data.items():
        if v is not None:
            setattr(scene, k, v)
    # trigger_condition 变更后重派 trigger_type（冗余列一致性）
    scene.trigger_type = _derive_trigger_type(scene.trigger_condition)
    await db.commit()
    await db.refresh(scene)
    return scene


async def delete_scene(db: AsyncSession, scene_id: str) -> bool:
    scene = await get_scene(db, scene_id)
    if not scene:
        return False
    await db.delete(scene)
    await db.commit()
    return True


# ── 生态对接 CRUD ──


async def create_ecosystem(db: AsyncSession, data: dict) -> EcosystemIntegration:
    data = dict(data)
    # 生态凭据加密落库（2026-09-22 P1 修复）：此前 config 明文入库且经 API 原样回露
    data["config"] = _encrypt_ecosystem_config(data.get("config"))
    eco = EcosystemIntegration(**data)
    db.add(eco)
    await db.commit()
    await db.refresh(eco)
    return eco


async def list_ecosystems_by_project(db: AsyncSession, project_id: str) -> list[EcosystemIntegration]:
    result = await db.execute(
        select(EcosystemIntegration)
        .where(EcosystemIntegration.project_id == project_id)
        .order_by(EcosystemIntegration.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_ecosystem(db: AsyncSession, ecosystem_id: str) -> bool:
    result = await db.execute(select(EcosystemIntegration).where(EcosystemIntegration.id == ecosystem_id))
    eco = result.scalar_one_or_none()
    if not eco:
        return False
    await db.delete(eco)
    await db.commit()
    return True


async def _get_or_create_ecosystem(db: AsyncSession, project_id: str, ecosystem: str) -> EcosystemIntegration | None:
    result = await db.execute(
        select(EcosystemIntegration).where(
            EcosystemIntegration.project_id == project_id,
            EcosystemIntegration.ecosystem == ecosystem,
        )
    )
    eco = result.scalar_one_or_none()
    if eco:
        return eco
    eco = EcosystemIntegration(
        project_id=project_id,
        ecosystem=ecosystem,
        auth_status="disconnected",
    )
    db.add(eco)
    await db.commit()
    await db.refresh(eco)
    return eco


# ── 触发条件校验 ──


def _validate_cron(cron: str) -> bool:
    """简单 cron 表达式校验 (5 段: 分 时 日 月 周)"""
    if not cron or not isinstance(cron, str):
        return False
    parts = cron.strip().split()
    if len(parts) != 5:
        return False
    # 每段允许: * / 数字 / */n / 数字-n / 数字,数字
    pattern = re.compile(r"^(\*|\d+|\*\/\d+|\d+-\d+|\d+(,\d+)*)$")
    return all(pattern.match(p) for p in parts)


def validate_trigger(condition: dict | None) -> dict:
    """触发条件校验 (cron 表达式 / 设备状态 / 地理位置)"""
    if not condition or not isinstance(condition, dict):
        return {"valid": False, "errors": ["触发条件不能为空"]}

    trig_type = condition.get("type")
    errors: list[str] = []

    if not trig_type:
        errors.append("触发条件缺少 type 字段")
    elif trig_type == "time":
        cron = condition.get("cron")
        if not cron:
            errors.append("定时触发缺少 cron 表达式")
        elif not _validate_cron(cron):
            errors.append(f"cron 表达式格式无效: {cron}(应为 5 段: 分 时 日 月 周)")
    elif trig_type == "device":
        if not condition.get("device_id"):
            errors.append("设备触发缺少 device_id")
        if "state" not in condition:
            errors.append("设备触发缺少 state 字段")
    elif trig_type == "geo":
        if not condition.get("latitude"):
            errors.append("地理触发缺少 latitude")
        if not condition.get("longitude"):
            errors.append("地理触发缺少 longitude")
        if "radius" not in condition:
            errors.append("地理触发缺少 radius 字段")
    elif trig_type == "sensor":
        sensor_cond = condition.get("condition")
        if not isinstance(sensor_cond, dict) or not sensor_cond:
            errors.append(
                "传感器触发缺少 condition 字段（键值对：键为传感器名，"
                "值可为标量或 {\"gt\"/\"gte\"/\"lt\"/\"lte\"/\"eq\"} 比较符）"
            )
    else:
        errors.append(f"不支持的触发类型: {trig_type}")

    return {"valid": len(errors) == 0, "errors": errors}


# ── 动作校验 ──


# 设备类型 → 允许的动作集合
DEVICE_ACTION_WHITELIST: dict[str, set[str]] = {
    "light": {"turn_on", "turn_off", "set_brightness", "set_color", "set_color_temp"},
    "switch": {"turn_on", "turn_off"},
    "socket": {"turn_on", "turn_off"},
    "curtain": {"open", "close", "stop", "set_position"},
    "speaker": {"play", "pause", "set_volume", "speak"},
    "thermostat": {"set_temperature", "turn_on", "turn_off"},
    "air_purifier": {"turn_on", "turn_off", "set_mode", "set_speed"},
    "robot_vacuum": {"start", "stop", "pause", "return_dock"},
    "camera": {"start_record", "stop_record", "set_mode"},
    "lock": {"lock", "unlock"},
    "sensor": {},  # 传感器只读,不可控
}


async def validate_actions(db: AsyncSession, actions: list | None, devices: list) -> dict:
    """动作校验 (设备存在性 + 动作合法性)"""
    if not actions or not isinstance(actions, list):
        return {"valid": False, "errors": ["动作列表不能为空"]}

    device_map: dict[str, SmartDevice] = {}
    for d in devices:
        device_map[d.id] = d

    errors: list[str] = []
    for idx, act in enumerate(actions):
        if not isinstance(act, dict):
            errors.append(f"动作 {idx}: 格式无效,应为对象")
            continue
        device_id = act.get("device_id")
        action = act.get("action")
        if not device_id:
            errors.append(f"动作 {idx}: 缺少 device_id")
            continue
        if not action:
            errors.append(f"动作 {idx}: 缺少 action")
            continue
        device = device_map.get(device_id)
        if not device:
            errors.append(f"动作 {idx}: 设备 {device_id} 不存在")
            continue
        allowed = DEVICE_ACTION_WHITELIST.get(device.device_type)
        if not allowed or action not in allowed:
            errors.append(
                f"动作 {idx}: 设备 {device.device_name}({device.device_type}) 不支持动作 {action}"
            )

    return {"valid": len(errors) == 0, "errors": errors}


# ── 场景校验 ──


async def validate_scene(db: AsyncSession, scene: SceneAutomation) -> dict:
    """场景校验 (触发条件 + 动作合法性)，返回 {valid, errors}"""
    trig_check = validate_trigger(scene.trigger_condition)

    devices: list[SmartDevice] = []
    if scene.scheme_id:
        result = await db.execute(
            select(SmartDevice).where(SmartDevice.scheme_id == scene.scheme_id)
        )
        devices = list(result.scalars().all())

    action_check = await validate_actions(db, scene.actions, devices)

    valid = trig_check["valid"] and action_check["valid"]
    errors = list(trig_check["errors"]) + list(action_check["errors"])
    return {"valid": valid, "errors": errors}


# ── 场景模拟执行 ──


async def simulate_scene(db: AsyncSession, scene: SceneAutomation) -> dict:
    """场景模拟执行 (返回预期结果,不实际触发)"""
    # 校验触发条件
    trig_check = validate_trigger(scene.trigger_condition)

    # 加载设备
    devices: list[SmartDevice] = []
    if scene.scheme_id:
        result = await db.execute(
            select(SmartDevice).where(SmartDevice.scheme_id == scene.scheme_id)
        )
        devices = list(result.scalars().all())

    # 校验动作
    action_check = await validate_actions(db, scene.actions, devices)

    would_execute = trig_check["valid"] and action_check["valid"]
    notes: list[str] = []
    if not trig_check["valid"]:
        notes.append(f"触发条件不满足: {'; '.join(trig_check['errors'])}")
    if not action_check["valid"]:
        notes.append(f"动作校验失败: {'; '.join(action_check['errors'])}")
    if would_execute:
        notes.append(f"场景 {scene.scene_name} 将按预期执行 {len(scene.actions or [])} 个动作")

    return {
        "scene_id": scene.id,
        "scene_name": scene.scene_name,
        "would_execute": would_execute,
        "actions_preview": scene.actions or [],
        "notes": notes,
    }


# ── 场景推荐 ──


# 生活场景模板
LIFESTYLE_SCENE_PRESETS: dict[str, list[dict]] = {
    "living_room": [
        {
            "scene_name": "回家模式",
            "scene_type": "triggered",
            "trigger_condition": {"type": "device", "device_id": "lock", "state": "unlock"},
            "actions": [
                {"device_id": "light", "action": "turn_on", "params": {"brightness": 80}},
                {"device_id": "curtain", "action": "open"},
                {"device_id": "speaker", "action": "play"},
            ],
            "description": "开门后自动亮灯、拉开窗帘、播放音乐",
        },
        {
            "scene_name": "离家模式",
            "scene_type": "triggered",
            "trigger_condition": {"type": "device", "device_id": "lock", "state": "lock"},
            "actions": [
                {"device_id": "light", "action": "turn_off"},
                {"device_id": "curtain", "action": "close"},
                {"device_id": "socket", "action": "turn_off"},
            ],
            "description": "锁门后关闭所有灯、窗帘和插座",
        },
        {
            "scene_name": "观影模式",
            "scene_type": "manual",
            "trigger_condition": None,
            "actions": [
                {"device_id": "light", "action": "set_brightness", "params": {"brightness": 20}},
                {"device_id": "curtain", "action": "close"},
            ],
            "description": "调暗灯光、关闭窗帘,营造观影氛围",
        },
    ],
    "bedroom": [
        {
            "scene_name": "睡眠模式",
            "scene_type": "scheduled",
            "trigger_condition": {"type": "time", "cron": "0 23 * * *"},
            "actions": [
                {"device_id": "light", "action": "turn_off"},
                {"device_id": "curtain", "action": "close"},
            ],
            "description": "每晚 23:00 自动关灯、关窗帘",
        },
        {
            "scene_name": "起夜模式",
            "scene_type": "triggered",
            "trigger_condition": {"type": "device", "device_id": "sensor", "state": "motion"},
            "actions": [
                {"device_id": "light", "action": "set_brightness", "params": {"brightness": 10}},
            ],
            "description": "检测到人体移动,自动开启低亮度夜灯",
        },
        {
            "scene_name": "起床模式",
            "scene_type": "scheduled",
            "trigger_condition": {"type": "time", "cron": "0 7 * * *"},
            "actions": [
                {"device_id": "curtain", "action": "open"},
                {"device_id": "speaker", "action": "play"},
            ],
            "description": "每天早上 7:00 自动拉开窗帘、播放音乐",
        },
    ],
    "kitchen": [
        {
            "scene_name": "烹饪模式",
            "scene_type": "manual",
            "trigger_condition": None,
            "actions": [
                {"device_id": "light", "action": "turn_on"},
                {"device_id": "socket", "action": "turn_on"},
            ],
            "description": "开启厨房灯和插座电源",
        },
    ],
    "bathroom": [
        {
            "scene_name": "夜间如厕模式",
            "scene_type": "triggered",
            "trigger_condition": {"type": "device", "device_id": "sensor", "state": "motion"},
            "actions": [
                {"device_id": "light", "action": "set_brightness", "params": {"brightness": 15}},
            ],
            "description": "检测到人体移动,自动开启低亮度灯",
        },
    ],
    "entrance": [
        {
            "scene_name": "回家模式",
            "scene_type": "triggered",
            "trigger_condition": {"type": "device", "device_id": "lock", "state": "unlock"},
            "actions": [
                {"device_id": "light", "action": "turn_on"},
            ],
            "description": "开锁后自动亮起玄关灯",
        },
    ],
    "study": [
        {
            "scene_name": "学习模式",
            "scene_type": "manual",
            "trigger_condition": None,
            "actions": [
                {"device_id": "light", "action": "set_brightness", "params": {"brightness": 90}},
                {"device_id": "curtain", "action": "open"},
            ],
            "description": "调亮灯光、拉开窗帘,营造学习氛围",
        },
    ],
}


def recommend_scenes(room_type: str, lifestyle: str = "") -> dict:
    """场景推荐 (回家模式/离家模式/睡眠模式/观影模式/起夜模式)"""
    preset = LIFESTYLE_SCENE_PRESETS.get(room_type, [])

    # lifestyle 关键词过滤
    if lifestyle:
        keywords = [k.strip() for k in lifestyle.replace("，", ",").split(",") if k.strip()]
        if keywords:
            filtered = []
            for scene in preset:
                name = scene.get("scene_name", "")
                desc = scene.get("description", "")
                if any(kw in name or kw in desc for kw in keywords):
                    filtered.append(scene)
            if filtered:
                preset = filtered

    return {
        "room_type": room_type,
        "lifestyle": lifestyle,
        "recommended_scenes": preset,
    }


# ── 同步到第三方生态 ──


async def sync_to_ecosystem(
    db: AsyncSession,
    scene: SceneAutomation,
    ecosystem: str,
) -> dict:
    """同步到第三方生态 (HomeKit/米家/鸿蒙/Matter/涂鸦)

    通过 BridgeFactory 获取对应生态桥接实例, 调用真实接口完成场景同步。
    若桥接层抛出 NotImplementedError, 返回 stubbed 结果并标注 not_implemented。

    归因纪律（2026-09-23）：生态无桥接实现（BridgeFactory ValueError）与「凭据不合规」
    是两类原因，此前混为一谈导致前端看到「凭据未配置或不完整」的错误归因；现分列
    unsupported_ecosystem / invalid_credentials，且无桥生态不再落库生态对接记录。
    """
    import logging

    from app.services.ecosystem_bridge import BridgeFactory

    log = logging.getLogger("ihome.scene_automation")

    try:
        bridge = BridgeFactory.get_bridge(ecosystem)
    except ValueError as e:
        log.warning(f"sync_to_ecosystem: {ecosystem} 无桥接实现 — {e}")
        return {
            "scene_id": scene.id,
            "ecosystem": ecosystem,
            "synced": False,
            "message": f"不支持的生态类型（无桥接实现），同步未完成：{e}",
            "reason": f"unsupported_ecosystem: {e}",
        }

    eco = await _get_or_create_ecosystem(db, scene.project_id, ecosystem)
    if not eco:
        return {
            "scene_id": scene.id,
            "ecosystem": ecosystem,
            "synced": False,
            "message": "生态对接创建失败",
        }

    # 不同生态的消息描述
    messages = {
        "homekit": "场景已同步至 HomeKit,可通过家庭 App 触发",
        "mijia": "场景已同步至米家,可通过小爱同学语音触发",
        "harmonyos": "场景已同步至华为鸿蒙,可通过小艺语音触发",
        "tuya": "场景已同步至涂鸦智能,可通过 Smart Life App 触发",
        "matter": "场景已同步至 Matter Fabric,跨生态互通",
    }

    # ── 调用真机接口 ──
    success = False
    reason = None
    try:
        creds = _decrypt_ecosystem_config(eco.config) or {}
        await bridge.connect(creds)

        # 构造场景数据
        scenes = [{
            "scene_id": scene.id,
            "scene_name": scene.scene_name,
            "scene_type": scene.scene_type,
            "trigger_condition": scene.trigger_condition,
            "actions": scene.actions,
            "enabled": scene.enabled,
        }]
        await bridge.sync_scenes(scenes)
        await bridge.disconnect()
        success = True
        log.info(f"sync_to_ecosystem: {ecosystem} sync succeeded for scene {scene.id}")
    except NotImplementedError as e:
        reason = f"not_implemented: {e}"
        log.warning(f"sync_to_ecosystem: {ecosystem} bridge not implemented — {e}")
        # 桥接未实现时仍标记为 stubbed synced, 记录原因
        success = False
    except ValueError as e:
        reason = f"invalid_credentials: {e}"
        log.error(f"sync_to_ecosystem: {ecosystem} invalid credentials — {e}")
        success = False
    except Exception as e:
        reason = f"bridge_error: {e}"
        log.error(f"sync_to_ecosystem: {ecosystem} bridge error — {e}")
        success = False

    # ── 更新 DB 记录 ──
    if success or reason:
        eco.auth_status = "connected" if success else eco.auth_status
    eco.last_synced_at = datetime.now(timezone.utc)
    if success:
        eco.device_count = int(eco.device_count or 0) + 1
    eco.notes = reason
    await db.commit()
    await db.refresh(eco)

    msg = messages.get(ecosystem, f"场景已同步至 {ecosystem}")
    if not success:
        # v1.2.2 诚实标注：任何失败原因都不应显示"已同步"误导用户。
        # 原 code 仅在 not_implemented 时追加 [stubbed]，其他失败（凭据缺失/桥接错误）
        # 仍返回成功文案，造成"已同步"假象。现按失败类型给出诚实描述。
        eco_display = {
            "homekit": "HomeKit", "mijia": "米家", "harmonyos": "华为鸿蒙",
            "tuya": "涂鸦智能", "matter": "Matter Fabric",
        }.get(ecosystem, ecosystem)
        if reason and reason.startswith("not_implemented"):
            msg = f"[stubbed] {eco_display} 桥接层未就绪，同步未完成"
        elif reason and reason.startswith("invalid_credentials"):
            msg = f"{eco_display} 凭据未配置或不完整，同步未完成"
        elif reason and reason.startswith("bridge_error"):
            msg = f"{eco_display} 同步失败（桥接错误）"
        else:
            msg = f"{eco_display} 同步未完成"

    return {
        "scene_id": scene.id,
        "ecosystem": ecosystem,
        "synced": success,
        "message": msg,
        "reason": reason,
    }


# ── 自然语言解析场景 ──


def parse_natural_language_scene(text: str) -> dict:
    """自然语言解析场景 (如"每天早上 7 点打开客厅灯")"""
    if not text or not text.strip():
        return {
            "parsed": False,
            "raw_text": text or "",
            "scene_name": None,
            "scene_type": None,
            "trigger_condition": None,
            "actions": None,
        }

    raw = text.strip()
    scene_type: str | None = None
    trigger_condition: dict | None = None
    actions: list[dict] | None = None
    scene_name: str | None = None

    # 时间解析: 每天/每天早上/每晚 + 数字点
    # 示例: "每天早上 7 点打开客厅灯"
    time_match = re.search(r"(每天|每日)?\s*(早上|早晨|上午|下午|晚上|夜间|每晚|每日)?\s*(\d{1,2})\s*[点时:：](\d{1,2})?", raw)
    if time_match:
        hour = int(time_match.group(3))
        minute = int(time_match.group(4)) if time_match.group(4) else 0
        # 下午/晚上 +12
        period = time_match.group(2) or ""
        if ("下午" in period or "晚上" in period or "晚" in period) and hour < 12:
            hour += 12
        scene_type = "scheduled"
        trigger_condition = {"type": "time", "cron": f"{minute} {hour} * * *"}

    # 动作解析: 打开/关闭/调节 + 设备名
    action_match = re.search(r"(打开|关闭|开启|关掉|调节|调亮|调暗|拉开|关上|播放|暂停)\s*(客厅|卧室|厨房|卫生间|玄关|书房)?\s*(灯|窗帘|空调|电视|音箱|插座|开关)", raw)
    if action_match:
        verb = action_match.group(1)
        room = action_match.group(2) or ""
        device = action_match.group(3)
        action_map = {
            "打开": "turn_on", "开启": "turn_on",
            "关闭": "turn_off", "关掉": "turn_off",
            "调节": "set_brightness",
            "调亮": "set_brightness",
            "调暗": "set_brightness",
            "拉开": "open", "关上": "close",
            "播放": "play", "暂停": "pause",
        }
        action = action_map.get(verb, "turn_on")
        device_type_map = {
            "灯": "light", "窗帘": "curtain", "空调": "thermostat",
            "电视": "tv", "音箱": "speaker", "插座": "socket", "开关": "switch",
        }
        device_type = device_type_map.get(device, "light")
        actions = [{"device_id": device_type, "action": action, "params": {}}]
        scene_name = scene_name or f"{room}{device}{verb}".strip()

    # 亮度参数
    bright_match = re.search(r"亮度\s*(\d{1,3})", raw)
    if bright_match and actions:
        actions[0]["params"]["brightness"] = int(bright_match.group(1))

    # 触发型场景: 回家/离家
    if "回家" in raw or "开门" in raw:
        scene_type = "triggered"
        trigger_condition = {"type": "device", "device_id": "lock", "state": "unlock"}
        scene_name = "回家模式"
        if not actions:
            actions = [{"device_id": "light", "action": "turn_on", "params": {"brightness": 80}}]
    elif "离家" in raw or "锁门" in raw:
        scene_type = "triggered"
        trigger_condition = {"type": "device", "device_id": "lock", "state": "lock"}
        scene_name = "离家模式"
        if not actions:
            actions = [{"device_id": "light", "action": "turn_off", "params": {}}]

    parsed = scene_type is not None or actions is not None
    if not scene_name:
        scene_name = raw[:20]

    return {
        "parsed": parsed,
        "scene_name": scene_name,
        "scene_type": scene_type or "manual",
        "trigger_condition": trigger_condition,
        "actions": actions,
        "raw_text": raw,
    }


# ── 传感器实时触发检查 ──


async def check_sensor_triggers(
    db: AsyncSession,
    user_id: str,
    ambient_data: dict,
    device_id: str | None = None,
) -> list[dict]:
    """检查传感器数据是否触发了任何场景自动化的 sensor_trigger 条件。

    真实闭环：
    1. 查询用户项目下 enabled 且 trigger_condition.type == "sensor" 的场景
    2. 将 ambient_data 与场景触发条件逐项匹配（值可为标量精确匹配，
       或 {"gt"/"gte"/"lt"/"lte"/"eq"} 比较符）
    3. 命中场景写入 scene_behavior_logs（action_type=sensor_trigger），记录真实触发
    4. **命中后真实执行动作**（2026-09-22 P0 修复）：复用 execute_scene_actions
       （含生态凭据解析 / 波次并行 / 设备状态回写），此前仅写日志不执行，
       "温度>30 开空调"类核心卖点在代码层不成立；桥未接真机时动作仍诚实标 pending

    Returns:
        被触发的场景列表（含触发时间与动作执行状态）
    """
    import logging
    from datetime import datetime

    from sqlalchemy import select

    from app.models.project import Project
    from app.models.scene_automation import SceneAutomation
    from app.models.scene_behavior import SceneBehaviorLog

    log = logging.getLogger("ihome.scene_automation")

    # 1. 查询用户所有项目下启用的 sensor 触发场景（trigger_type 索引列 SQL 层预过滤，
    #    避免每次快照上传全量扫描所有 enabled 场景再 Python 过滤——2026-08-27 加固）
    result = await db.execute(
        select(SceneAutomation)
        .join(Project, Project.id == SceneAutomation.project_id)
        .where(
            Project.owner_id == user_id,
            SceneAutomation.enabled.is_(True),
            SceneAutomation.trigger_type == "sensor",
        )
    )
    scenes = list(result.scalars().all())
    log.info(
        "sensor_trigger_scan: user=%s candidate_scenes=%d ambient_data=%s",
        user_id, len(scenes), ambient_data,
    )

    triggered: list[dict] = []
    for scene in scenes:
        cond = scene.trigger_condition
        if not isinstance(cond, dict) or cond.get("type") != "sensor":
            continue
        sensor_cond = cond.get("condition")
        if not isinstance(sensor_cond, dict):
            log.debug(
                "sensor_trigger_skip_invalid_condition: scene=%s condition=%s",
                scene.id, cond,
            )
            continue
        # 2. 逐项匹配传感器条件
        match = _match_sensor_condition(sensor_cond, ambient_data)
        log.info(
            "sensor_trigger_match: user=%s scene=%s scene_name=%s "
            "condition=%s ambient_data=%s matched=%s",
            user_id,
            scene.id,
            scene.scene_name,
            sensor_cond,
            ambient_data,
            match,
        )
        if not match:
            continue

        # 3. 写入真实触发日志
        log_entry = SceneBehaviorLog(
            project_id=scene.project_id,
            user_id=user_id,
            action_type="sensor_trigger",
            scene_id=scene.id,
            ambient_data=ambient_data,
        )
        db.add(log_entry)
        await db.commit()

        # 4. 真实执行场景动作（P0 修复：此前仅标注 pending 不执行）
        #    串行调用（持 db）——execute_scene_actions 内部自行完成生态凭据解析与落库
        action_status = "pending"
        action_note = None
        try:
            exec_result = await execute_scene_actions(
                db, scene, user_id,
                trigger_source="sensor",
                log_action_type="sensor_trigger",
            )
            statuses = {
                s: sum(1 for a in exec_result["actions"] if a["action_status"] == s)
                for s in ("success", "pending", "failed", "skipped", "rejected")
            }
            if statuses["success"]:
                action_status = "success"
                action_note = f"已执行成功 {statuses['success']} 个动作"
            elif statuses["failed"]:
                action_status = "failed"
                action_note = f"执行失败 {statuses['failed']} 个动作（其余 pending/skipped）"
            else:
                action_note = (
                    "生态桥未接真机或未配置凭据，已记录触发意图未实际执行"
                    f"（pending={statuses['pending']}）"
                )
            log.info(
                "sensor_trigger_action_executed: user=%s scene=%s status=%s summary=%s",
                user_id, scene.id, action_status, statuses,
            )
        except Exception as e:  # noqa: BLE001 — 动作执行失败不阻断其余场景匹配
            action_status = "failed"
            action_note = f"场景动作执行异常: {e}"
            log.warning(
                "sensor_trigger_action_error: user=%s scene=%s error=%s",
                user_id, scene.id, e,
            )
        log.info(
            "sensor_trigger_hit: user=%s scene=%s scene_name=%s actions=%s action_status=%s device_id=%s",
            user_id,
            scene.id,
            scene.scene_name,
            len(scene.actions or []),
            action_status,
            device_id,
        )
        triggered.append({
            "scene_id": scene.id,
            "scene_name": scene.scene_name,
            "actions": scene.actions or [],
            "action_status": action_status,
            "action_note": action_note,
            "triggered_at": datetime.now(_BJ_TZ).isoformat(),
        })

    await db.commit()

    if triggered:
        log.info(
            "sensor_triggers_executed: user=%s triggered_count=%s",
            user_id,
            len(triggered),
        )
    return triggered


def _match_sensor_condition(condition: dict, ambient_data: dict) -> bool:
    """传感器条件匹配。

    支持两种取值形式：
    - 标量：与 ambient_data 精确相等（如 {"occupancy": True}）
    - 比较符 dict：{"gt": x, "gte": x, "lt": x, "lte": x, "eq": x} 任意组合

    ambient_data 中缺失的键不参与判定（避免 humidity=0 占位误触发）；
    但所有键均缺失时返回 False——无任何真实数据可判定，禁止空匹配误触发
    （2026-08-12 设备链路诊断修复：此前空匹配返回 True，GPS-only ambient_data
    会触发所有 sensor 场景）。
    """
    matched_keys = 0
    for key, expected in condition.items():
        if key not in ambient_data:
            logger.debug(
                "sensor_condition_key_missing: key=%s expected=%s 不在 ambient_data 中，跳过",
                key, expected,
            )
            continue
        matched_keys += 1
        actual = ambient_data[key]
        if isinstance(expected, dict):
            if "gt" in expected and not actual > expected["gt"]:
                logger.debug(
                    "sensor_condition_fail: key=%s actual=%s 不满足 gt=%s",
                    key, actual, expected["gt"],
                )
                return False
            if "gte" in expected and not actual >= expected["gte"]:
                logger.debug(
                    "sensor_condition_fail: key=%s actual=%s 不满足 gte=%s",
                    key, actual, expected["gte"],
                )
                return False
            if "lt" in expected and not actual < expected["lt"]:
                logger.debug(
                    "sensor_condition_fail: key=%s actual=%s 不满足 lt=%s",
                    key, actual, expected["lt"],
                )
                return False
            if "lte" in expected and not actual <= expected["lte"]:
                logger.debug(
                    "sensor_condition_fail: key=%s actual=%s 不满足 lte=%s",
                    key, actual, expected["lte"],
                )
                return False
            if expected.get("eq") is not None and actual != expected["eq"]:
                logger.debug(
                    "sensor_condition_fail: key=%s actual=%s 不满足 eq=%s",
                    key, actual, expected["eq"],
                )
                return False
        else:
            if actual != expected:
                logger.debug(
                    "sensor_condition_fail: key=%s actual=%s 不匹配 expected=%s",
                    key, actual, expected,
                )
                return False
        logger.debug(
            "sensor_condition_pass: key=%s actual=%s expected=%s",
            key, actual, expected,
        )
    logger.debug(
        "sensor_condition_result: matched_keys=%d total_keys=%d matched=%s",
        matched_keys, len(condition), matched_keys > 0,
    )
    return matched_keys > 0


# ── 动作执行管线（P0 设备热点联动，2026-08-12 工程落地）──
# 手动触发（3D 场景点击 / 语音）与传感器自动触发共用执行语义：
# 写 SceneBehaviorLog + 生态桥执行 + 未接真机 action_status=pending 诚实标注。


def _action_state_delta(action: str, params: dict) -> dict:
    """动作 → 设备实时状态增量。

    仅生态桥真机执行成功（send_command 返回 ok）时应用，保证 state 为真实数据源。
    未映射动作 / 缺参返回空 dict（不覆盖已存在状态）。
    """
    deltas = {
        "turn_on": {"power": True},
        "turn_off": {"power": False},
        "open": {"position": 100},
        "close": {"position": 0},
        "set_brightness": {"brightness": params.get("brightness")},
        "set_volume": {"volume": params.get("volume")},
        "set_temperature": {"temperature": params.get("temperature")},
        "set_position": {"position": params.get("position")},
    }
    delta = deltas.get(action)
    if not delta:
        return {}
    return {k: v for k, v in delta.items() if v is not None}


async def _latest_sensor_context(db: AsyncSession, user_id: str) -> dict:
    """取用户最近真实 SensorSnapshot 的环境量作为触发上下文（诚实数据，不伪造）。"""
    from app.models.sensor_snapshot import SensorSnapshot

    result = await db.execute(
        select(SensorSnapshot)
        .where(SensorSnapshot.user_id == user_id)
        .order_by(SensorSnapshot.sampled_at.desc())
        .limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return {}
    ctx: dict = {}
    if snap.temperature is not None:
        ctx["temperature"] = snap.temperature
    if snap.humidity is not None:
        ctx["humidity"] = snap.humidity
    if snap.light_lux is not None:
        ctx["light_lux"] = snap.light_lux
    return ctx


async def execute_device_command(
    db: AsyncSession,
    device: SmartDevice,
    project_id: str,
    action: str,
    params: dict,
    user_id: str,
    source: str = "app",
    scene_id: str | None = None,
    ecosystem: str = "matter",
) -> dict:
    """执行单设备命令（3D 场景 / 语音入口）。

    1. 动作白名单校验（复用 DEVICE_ACTION_WHITELIST）
    2. 写入 SceneBehaviorLog(action_type=device_command)，ambient_data 取最近真实传感器快照
    3. 生态桥 send_command 执行 → 未接真机（NotImplementedError）action_status=pending 诚实标注
    """
    from app.models.scene_behavior import SceneBehaviorLog

    allowed = DEVICE_ACTION_WHITELIST.get(device.device_type)
    logger.info(
        "device_command_received: user=%s device=%s name=%s type=%s "
        "action=%s params=%s source=%s ecosystem=%s scene_id=%s",
        user_id, device.id, device.device_name, device.device_type,
        action, params or {}, source, ecosystem, scene_id,
    )
    if not allowed or action not in allowed:
        # 空白名单（sensor 只读 / 未知设备类型）或动作不合法 → 拒绝，防止绕过动作校验
        logger.warning(
            "device_command_rejected: device=%s type=%s action=%s allowed=%s",
            device.id, device.device_type, action, sorted(allowed or ()),
        )
        return {
            "accepted": False,
            "error": f"设备 {device.device_name}({device.device_type}) 不支持动作 {action}",
        }

    ambient = await _latest_sensor_context(db, user_id)
    logger.debug(
        "device_command_context: device=%s ambient_data=%s",
        device.id, ambient,
    )
    log_entry = SceneBehaviorLog(
        project_id=project_id,
        user_id=user_id,
        action_type="device_command",
        scene_id=scene_id,
        ambient_data=ambient or None,
    )
    db.add(log_entry)

    # 生态桥执行（诚实降级：未配置 API key / 未实现时标注 pending，不伪装已执行）
    action_status = "pending"
    note = (
        "设备动作执行依赖生态桥接（ecosystem_bridge），当前未配置 API key，"
        "已记录触发意图，待桥接接入真机后执行"
    )
    _cmd_start = monotonic()
    # 同设备命令串行化（防 state read-modify-write 竞争，best-effort 跨 worker）
    lock = await _device_lock(device.id)
    async with lock:
        pool = None
        try:
            from app.services.ecosystem_bridge import BridgeConnectionPool
            pool = BridgeConnectionPool()
            logger.info(
                "device_command_bridge_dispatch: device=%s action=%s ecosystem=%s → connect(池化)",
                device.id, action, ecosystem,
            )
            # 凭据注入（P0 修复）：项目下该生态的 config 解密后传入桥，
            # 否则米家等真机桥恒因缺凭据抛 ValueError，真机路径不可达
            # 注：SmartDevice 无 project_id 列，经 scheme 反查（串行，持 db）
            _scheme = (await db.execute(
                select(SmartHomeScheme).where(SmartHomeScheme.id == device.scheme_id)
            )).scalar_one_or_none()
            bridge_creds = await _resolve_ecosystem_credentials(
                db, _scheme.project_id if _scheme else None, ecosystem,
            )
            bridge = await asyncio.wait_for(
                pool.get(ecosystem, bridge_creds), timeout=BRIDGE_COMMAND_TIMEOUT_SECONDS,
            )
            logger.info(
                "device_command_bridge_dispatch: device=%s action=%s ecosystem=%s → send_command",
                device.id, action, ecosystem,
            )
            ok = await _bridge_send_command(bridge, device.id, action, params or {})
            logger.info(
                "device_command_bridge_dispatch: device=%s action=%s ecosystem=%s → result=%s",
                device.id, action, ecosystem, ok,
            )
            if ok:
                action_status = "success"
                note = None
                # 真机执行成功才写入实时状态（诚实数据源，pending 不写）
                delta = _action_state_delta(action, params or {})
                if delta:
                    device.state = {**(device.state or {}), **delta}
                    logger.info(
                        "device_command_state_applied: device=%s action=%s delta=%s",
                        device.id, action, delta,
                    )
        except (NotImplementedError, ValueError) as e:
            # 桥未实现 / 凭据未配置 → 未接真机，诚实标注 pending（不伪装已执行）
            note = f"bridge_not_configured: {e}"
            logger.info(
                "device_command_bridge_not_configured: device=%s action=%s ecosystem=%s error=%s",
                device.id, action, ecosystem, e,
            )
        except Exception as e:
            action_status = "failed"
            note = f"bridge_error: {e}"
            logger.warning(
                "device_command_bridge_error: device=%s action=%s ecosystem=%s error=%s",
                device.id, action, ecosystem, e,
            )
        finally:
            if pool:
                await pool.close_all()

    await db.commit()
    # 可观测性：命令耗时分布 + 状态计数（2026-08-27 加固）
    device_command_duration_seconds.observe(monotonic() - _cmd_start)
    device_command_total.labels(status=action_status).inc()
    logger.info(
        "device_command_executed: user=%s device=%s name=%s action=%s "
        "status=%s source=%s note=%s",
        user_id, device.id, device.device_name, action, action_status, source, note,
    )
    return {
        "device_id": device.id,
        "device_name": device.device_name,
        "action": action,
        "params": params or {},
        "accepted": True,
        "action_status": action_status,
        "note": note,
        "state": device.state,
    }


def _plan_scene_actions(
    actions: list,
    device_map: dict,
) -> tuple[list, list]:
    """动作规划：白名单校验 + depends_on 波次拆分。

    - 无 depends_on 的动作一波并行；depends_on 指向已完成动作 idx 的动作进入下一波
    - 依赖无法满足（环/前序被跳过）→ 退化串行，保证不悬挂
    - 返回 (waves, plan)：waves 仅含 status=="ok" 的动作；plan 含全部动作（含 skipped/rejected）
    """
    plan: list[dict] = []
    for idx, act in enumerate(actions):
        if not isinstance(act, dict):
            continue
        device_id = act.get("device_id")
        action = act.get("action")
        params = act.get("params") or {}
        device = device_map.get(device_id)
        item = {
            "idx": idx, "device": device, "action": action, "params": params,
            "depends_on": act.get("depends_on"), "status": "ok", "note": None,
        }
        if not device or not action:
            item["status"] = "skipped"
            item["note"] = "设备不存在或动作缺失"
            logger.info(
                "scene_execute_action_skipped: index=%d device_id=%s action=%s 设备不存在或动作缺失",
                idx, device_id, action,
            )
        else:
            allowed = DEVICE_ACTION_WHITELIST.get(device.device_type)
            if not allowed or action not in allowed:
                item["status"] = "rejected"
                item["note"] = f"设备 {device.device_name}({device.device_type}) 不支持动作 {action}"
                logger.info(
                    "scene_execute_action_rejected: index=%d device=%s name=%s action=%s allowed=%s",
                    idx, device.id, device.device_name, action, sorted(allowed or ()),
                )
        plan.append(item)

    waves: list[list] = []
    remaining = [it for it in plan if it["status"] == "ok"]
    done_idx: set[int] = set()
    while remaining:
        ready = [
            it for it in remaining
            if it.get("depends_on") is None or it["depends_on"] in done_idx
        ]
        if not ready:
            # 依赖无法满足（环/前序被跳过）→ 退化串行
            ready = [remaining[0]]
        waves.append(ready)
        done_idx.update(it["idx"] for it in ready)
        remaining = [it for it in remaining if it not in ready]
    return waves, plan


async def _run_scene_action(
    pool, scene: SceneAutomation, item: dict, ecosystem: str, credentials: dict,
) -> dict:
    """单动作桥命令执行（阶段 A，无 DB 操作，可并行）。

    ecosystem / credentials 由调用方在并行波次前串行解析传入（P0 修复）：
    此前此处 getattr(scene, "ecosystem", None) or "matter" 且 pool.get 不传凭据，
    导致米家等真机桥恒 pending。
    """
    device = item["device"]
    action = item["action"]
    params = item["params"]
    logger.info(
        "scene_execute_action_dispatch: scene=%s index=%d device=%s name=%s "
        "action=%s params=%s",
        scene.id, item["idx"], device.id, device.device_name, action, params,
    )
    action_status = "pending"
    note = (
        "设备动作执行依赖生态桥接（ecosystem_bridge），当前未配置 API key，"
        "已记录触发意图，待桥接接入真机后执行"
    )
    try:
        logger.info(
            "scene_execute_action_bridge: scene=%s device=%s action=%s ecosystem=%s → connect(池化)",
            scene.id, device.id, action, ecosystem,
        )
        bridge = await asyncio.wait_for(
            pool.get(ecosystem, credentials), timeout=BRIDGE_COMMAND_TIMEOUT_SECONDS,
        )
        logger.info(
            "scene_execute_action_bridge: scene=%s device=%s action=%s → send_command",
            scene.id, device.id, action,
        )
        ok = await _bridge_send_command(bridge, device.id, action, params)
        logger.info(
            "scene_execute_action_bridge: scene=%s device=%s action=%s → result=%s",
            scene.id, device.id, action, ok,
        )
        if ok:
            action_status = "success"
            note = None
    except (NotImplementedError, ValueError) as e:
        # 桥未实现 / 凭据未配置 → 未接真机，诚实标注 pending
        note = f"bridge_not_configured: {e}"
        logger.info(
            "scene_execute_action_bridge_not_configured: scene=%s device=%s action=%s error=%s",
            scene.id, device.id, action, e,
        )
    except Exception as e:
        action_status = "failed"
        note = f"bridge_error: {e}"
        logger.warning(
            "scene_action_bridge_error: scene=%s device=%s action=%s error=%s",
            scene.id, device.id, action, e,
        )
    logger.info(
        "scene_execute_action_result: scene=%s device=%s action=%s status=%s",
        scene.id, device.id, action, action_status,
    )
    return {
        "idx": item["idx"],
        "device_id": device.id,
        "device_name": device.device_name,
        "action": action,
        "params": params,
        "action_status": action_status,
        "note": note,
    }


async def execute_scene_actions(
    db: AsyncSession,
    scene: SceneAutomation,
    user_id: str,
    trigger_source: str = "vr_overlay",
    log_action_type: str = "manual_trigger",
) -> dict:
    """执行场景动作（手动触发入口，两阶段并行重构 2026-08-12）。

    两阶段拆分（遵守「有 db 串行、无 db 并行」硬约束）：
    - 阶段 A（并行，无 DB）：生态桥命令 asyncio.gather 并行（纯 I/O，不触碰共享 session），
      depends_on 动作按波次串行依赖
    - 阶段 B（串行，有 DB）：SceneBehaviorLog 逐条 add + 单次 commit
    - 连接复用：BridgeConnectionPool 场景级 1 次 connect，N 动作共享
    """
    _scene_start = monotonic()
    from app.models.scene_behavior import SceneBehaviorLog

    logger.info(
        "scene_execute_start: user=%s scene=%s name=%s trigger_source=%s "
        "scheme_id=%s actions_count=%d",
        user_id, scene.id, scene.scene_name, trigger_source,
        scene.scheme_id, len(scene.actions or []),
    )

    # ── 准备（串行，读 DB）──
    devices: list[SmartDevice] = []
    if scene.scheme_id:
        result = await db.execute(
            select(SmartDevice).where(SmartDevice.scheme_id == scene.scheme_id)
        )
        devices = list(result.scalars().all())
    device_map = {d.id: d for d in devices}
    logger.debug(
        "scene_execute_devices: scene=%s matched_devices=%d",
        scene.id, len(devices),
    )
    ambient = await _latest_sensor_context(db, user_id)
    # 生态与凭据解析（串行，持 db；严禁移入并行波次内 —— 共享 AsyncSession 并行会触发 ISCE）
    ecosystem, scene_creds = await _resolve_scene_ecosystem(db, scene)
    logger.info(
        "scene_execute_ecosystem: scene=%s ecosystem=%s credentials=%s",
        scene.id, ecosystem, "configured" if scene_creds else "none",
    )

    # ── 动作规划（白名单校验 + 波次拆分）──
    waves, plan = _plan_scene_actions(scene.actions or [], device_map)

    # ── 阶段 A：逐波并行执行桥命令（无 DB，可并行）──
    # results 在 try 外初始化：即使阶段 A 抛异常，异常传播前变量已定义，
    # 组装阶段也不会 UnboundLocalError（2026-08-12 根因修复：外部并发写入半成品
    # 曾使 final_results 未初始化即被引用，导致 7 个场景执行用例失败）
    results: list[dict] = []
    pool = None
    try:
        from app.services.ecosystem_bridge import BridgeConnectionPool
        pool = BridgeConnectionPool()
        for wave_idx, wave in enumerate(waves):
            logger.debug(
                "scene_execute_wave: scene=%s wave=%d actions=%d",
                scene.id, wave_idx, len(wave),
            )
            wave_results = await asyncio.gather(
                *(
                    _run_scene_action(pool, scene, item, ecosystem, scene_creds)
                    for item in wave
                ),
                return_exceptions=True,  # 单动作未捕获异常不中断整波，结果组装仍可达
            )
            # 过滤非 dict 结果（异常对象由 _run_scene_action 内部 except 兜底，此处防万一）
            results.extend(r for r in wave_results if isinstance(r, dict))
    finally:
        if pool:
            await pool.close_all()

    # ── 阶段 B：串行落库（共享 db session，禁止并行）──
    for item in plan:
        if item["status"] != "ok":
            continue
        db.add(SceneBehaviorLog(
            project_id=scene.project_id,
            user_id=user_id,
            action_type=log_action_type,
            scene_id=scene.id,
            ambient_data=ambient or None,
        ))

    # ── 组装结果（保持与 actions 原始顺序一致）──
    result_by_idx = {r["idx"]: r for r in results}
    final_results: list[dict] = []
    for item in plan:
        if item["status"] == "ok":
            r = result_by_idx[item["idx"]]
            final_results.append({k: v for k, v in r.items() if k != "idx"})
        else:
            final_results.append({
                "device_id": item["device"].id if item["device"] else None,
                "action": item["action"],
                "params": item["params"],
                "action_status": item["status"],
                "note": item["note"],
            })

    # 真机执行成功的动作写实时状态（诚实数据源，pending 不写；
    # 同设备 state 更新加锁串行化，防与单设备命令 read-modify-write 竞争）
    for r in final_results:
        if r["action_status"] != "success":
            continue
        device = device_map.get(r["device_id"])
        if not device:
            continue
        delta = _action_state_delta(r["action"], r["params"] or {})
        if not delta:
            continue
        lock = await _device_lock(device.id)
        async with lock:
            # 锁内刷新最新 state 再合并：防独立 session 快照陈旧互相覆盖
            await db.refresh(device)
            device.state = {**(device.state or {}), **delta}
            logger.info(
                "scene_execute_state_applied: scene=%s device=%s action=%s delta=%s",
                scene.id, device.id, r["action"], delta,
            )
    await db.commit()

    status_summary = {
        s: sum(1 for r in final_results if r["action_status"] == s)
        for s in ("pending", "success", "failed", "skipped", "rejected")
    }
    logger.info(
        "scene_execute_done: user=%s scene=%s name=%s source=%s actions=%d "
        "status_summary=%s",
        user_id, scene.id, scene.scene_name, trigger_source, len(final_results),
        status_summary,
    )
    # 可观测性：场景执行耗时分布 + 触发源计数（2026-08-27 加固）
    scene_execute_duration_seconds.observe(monotonic() - _scene_start)
    scene_execute_total.labels(trigger_source=trigger_source).inc()
    return {
        "scene_id": scene.id,
        "scene_name": scene.scene_name,
        "executed": True,
        "actions": final_results,
        "triggered_at": datetime.now(_BJ_TZ).isoformat(),
    }

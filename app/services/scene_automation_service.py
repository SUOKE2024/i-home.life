"""F32 场景编辑服务层 — 场景联动 + 生态对接 + 自然语言解析 + A4 预测式推荐"""

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scene_automation import SceneAutomation, EcosystemIntegration
from app.models.smart_home import SmartDevice

# A4 预测式智能场景推荐服务（可选导入，由 feature flag 控制使用）
from app.services import predictive_scene_service as predictive_scene  # noqa: F401


# ── 场景 CRUD ──


async def create_scene(db: AsyncSession, data: dict) -> SceneAutomation:
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
        allowed = DEVICE_ACTION_WHITELIST.get(device.device_type, set())
        if allowed and action not in allowed:
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
    """
    import logging

    from app.services.ecosystem_bridge import BridgeFactory

    log = logging.getLogger("ihome.scene_automation")

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
        "alexa": "场景已同步至 Alexa,可通过 Alexa 语音触发",
        "google_home": "场景已同步至 Google Home,可通过 Hey Google 触发",
        "tuya": "场景已同步至涂鸦智能,可通过 Smart Life App 触发",
        "matter": "场景已同步至 Matter Fabric,跨生态互通",
    }

    # ── 通过 BridgeFactory 获取桥接实例并调用真机接口 ──
    success = False
    reason = None
    try:
        bridge = BridgeFactory.get_bridge(ecosystem)
        creds = eco.config or {}
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
            "alexa": "Alexa", "google_home": "Google Home",
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

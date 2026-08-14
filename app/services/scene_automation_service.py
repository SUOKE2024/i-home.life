"""F32 场景编辑服务层 — 场景联动 + 生态对接 + 自然语言解析 + A4 预测式推荐"""

import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scene_automation import SceneAutomation, EcosystemIntegration
from app.models.smart_home import SmartDevice

# A4 预测式智能场景推荐服务（可选导入，由 feature flag 控制使用）
from app.services import predictive_scene_service as predictive_scene  # noqa: F401

# 业务时区（平台业务时区为北京时间，对齐 agent_context_service._DEFAULT_TZ）
_BJ_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

# 场景自动化模块级 logger（check_sensor_triggers 内部使用局部 log，
# _match_sensor_condition 为模块级函数，复用同一 logger 便于关联排查）
logger = logging.getLogger("ihome.scene_automation")


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
    4. 设备动作执行依赖生态桥接（EcosystemBridge，HomeKit/Matter/米家等），
       未接入真机/未配置 API key 前诚实标注 action_status=pending，不伪装为已执行

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

    # 1. 查询用户所有项目下启用的 sensor 触发场景
    result = await db.execute(
        select(SceneAutomation)
        .join(Project, Project.id == SceneAutomation.project_id)
        .where(
            Project.owner_id == user_id,
            SceneAutomation.enabled.is_(True),
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

        # 4. 动作执行依赖生态桥接，未接入前诚实标注 pending
        action_status = "pending"
        action_note = (
            "设备动作执行依赖生态桥接（ecosystem_bridge），当前未配置 API key，"
            "已记录触发意图，待桥接接入真机后执行"
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
    pool = None
    try:
        from app.services.ecosystem_bridge import BridgeConnectionPool
        pool = BridgeConnectionPool()
        logger.info(
            "device_command_bridge_dispatch: device=%s action=%s ecosystem=%s → connect(池化)",
            device.id, action, ecosystem,
        )
        bridge = await pool.get(ecosystem)
        logger.info(
            "device_command_bridge_dispatch: device=%s action=%s ecosystem=%s → send_command",
            device.id, action, ecosystem,
        )
        ok = await bridge.send_command(device.id, action, params or {})
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


async def _run_scene_action(pool, scene: SceneAutomation, item: dict) -> dict:
    """单动作桥命令执行（阶段 A，无 DB 操作，可并行）。返回含 idx 的结果 dict。"""
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
        ecosystem = getattr(scene, "ecosystem", None) or "matter"
        logger.info(
            "scene_execute_action_bridge: scene=%s device=%s action=%s ecosystem=%s → connect(池化)",
            scene.id, device.id, action, ecosystem,
        )
        bridge = await pool.get(ecosystem)
        logger.info(
            "scene_execute_action_bridge: scene=%s device=%s action=%s → send_command",
            scene.id, device.id, action,
        )
        ok = await bridge.send_command(device.id, action, params)
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
) -> dict:
    """执行场景动作（手动触发入口，两阶段并行重构 2026-08-12）。

    两阶段拆分（遵守「有 db 串行、无 db 并行」硬约束）：
    - 阶段 A（并行，无 DB）：生态桥命令 asyncio.gather 并行（纯 I/O，不触碰共享 session），
      depends_on 动作按波次串行依赖
    - 阶段 B（串行，有 DB）：SceneBehaviorLog 逐条 add + 单次 commit
    - 连接复用：BridgeConnectionPool 场景级 1 次 connect，N 动作共享
    """
    import asyncio

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
                *(_run_scene_action(pool, scene, item) for item in wave),
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
            action_type="manual_trigger",
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

    # 真机执行成功的动作写实时状态（诚实数据源，pending 不写）
    for r in final_results:
        if r["action_status"] != "success":
            continue
        device = device_map.get(r["device_id"])
        if not device:
            continue
        delta = _action_state_delta(r["action"], r["params"] or {})
        if delta:
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
    from datetime import datetime
    return {
        "scene_id": scene.id,
        "scene_name": scene.scene_name,
        "executed": True,
        "actions": final_results,
        "triggered_at": datetime.now(_BJ_TZ).isoformat(),
    }

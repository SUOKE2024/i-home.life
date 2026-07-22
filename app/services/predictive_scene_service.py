"""A4 预测式智能场景推荐服务 — 行为日志记录 + 预测生成"""

import logging
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scene_behavior import SceneBehaviorLog, PredictedScene
from app.models.scene_automation import SceneAutomation
from app.models.project import Project

log = logging.getLogger("ihome.predictive_scene")

# ── 房间类型 → 场景模板的行动库 ──

ROOM_TEMPLATE_ACTIONS: dict[str, list[dict]] = {
    "living_room": [
        {"device_id": "light", "action": "turn_on", "params": {"brightness": 80}},
        {"device_id": "curtain", "action": "open"},
    ],
    "bedroom": [
        {"device_id": "light", "action": "turn_off"},
        {"device_id": "curtain", "action": "close"},
    ],
    "kitchen": [
        {"device_id": "light", "action": "turn_on"},
        {"device_id": "socket", "action": "turn_on"},
    ],
    "bathroom": [
        {"device_id": "light", "action": "set_brightness", "params": {"brightness": 15}},
    ],
    "entrance": [
        {"device_id": "light", "action": "turn_on"},
    ],
    "study": [
        {"device_id": "light", "action": "set_brightness", "params": {"brightness": 90}},
    ],
}

TIME_HINT_MAP: dict[int, str] = {
    0: "午夜时段",
    6: "清晨时段",
    7: "早晨时段",
    8: "上午时段",
    12: "中午时段",
    14: "下午时段",
    18: "傍晚时段",
    19: "晚间时段",
    22: "夜间时段",
    23: "深夜时段",
}


def _closest_hint(hour: int, day_of_week: int | None) -> str:
    """根据时段和星期生成人性化的触发时间提示"""
    weekday_hint = "工作日" if (day_of_week is not None and day_of_week < 5) else "周末"
    for h in sorted(TIME_HINT_MAP.keys(), reverse=True):
        if hour >= h:
            return f"{weekday_hint}{hour}:00（{TIME_HINT_MAP[h]}）"
    return f"{weekday_hint}{hour}:00"


# ── 行为日志 ──


async def log_behavior(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    action_type: str,
    scene_id: str | None = None,
    room_type: str | None = None,
    time_of_day: int | None = None,
    day_of_week: int | None = None,
    duration_seconds: int | None = None,
    device_states_before: dict | None = None,
    device_states_after: dict | None = None,
    ambient_data: dict | None = None,
) -> SceneBehaviorLog:
    """记录用户场景行为日志"""
    entry = SceneBehaviorLog(
        project_id=project_id,
        user_id=user_id,
        action_type=action_type,
        scene_id=scene_id,
        room_type=room_type,
        time_of_day=time_of_day,
        day_of_week=day_of_week,
        duration_seconds=duration_seconds,
        device_states_before=device_states_before,
        device_states_after=device_states_after,
        ambient_data=ambient_data,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


# ── 预测生成核心 ──


async def predict_scenes(project_id: str, db: AsyncSession) -> list[PredictedScene]:
    """基于行为日志为指定项目生成预测场景。

    策略：
    1. 按时间模式分析：统计每个时段 + 房间类型的场景激活次数 → TOP1
    2. 按条件模式分析：分析 device_states_before/after 的转移模式
    3. 按环境数据分析：温湿度/照度与场景的关联
    4. 置信度 = min(based_on_count / 7, 0.95)
    """
    # ── 查询项目下最近 30 天的行为日志 ──
    logs_result = await db.execute(
        select(SceneBehaviorLog)
        .where(
            SceneBehaviorLog.project_id == project_id,
            SceneBehaviorLog.action_type.in_(
                ["scene_activate", "manual_trigger", "time_trigger", "sensor_trigger"]
            ),
        )
        .order_by(SceneBehaviorLog.created_at.desc())
    )
    logs = list(logs_result.scalars().all())

    if len(logs) < 3:
        log.debug(f"predict_scenes: project={project_id} 行为日志不足 ({len(logs)}), 跳过")
        return []

    predictions: list[PredictedScene] = []

    # ── 策略 1：时间模式分析 ──
    time_pattern_predictions = _predict_by_time_pattern(project_id, logs)
    predictions.extend(time_pattern_predictions)

    # ── 策略 2：条件模式分析（设备状态转换） ──
    condition_predictions = _predict_by_device_transition(project_id, logs)
    predictions.extend(condition_predictions)

    # ── 策略 3：环境数据分析 ──
    ambient_predictions = _predict_by_ambient(project_id, logs)
    predictions.extend(ambient_predictions)

    # ── 去重：同一 user_id + room_type + scene_name 只保留置信度最高的 ──
    unique: dict[tuple, PredictedScene] = {}
    for p in predictions:
        key = (p.user_id or "", p.room_type or "", p.scene_name)
        if key not in unique or p.confidence > unique[key].confidence:
            unique[key] = p

    # ── 清除旧预测并写入新预测 ──
    await db.execute(
        delete(PredictedScene).where(
            PredictedScene.project_id == project_id,
            PredictedScene.status == "suggested",
        )
    )

    for p in unique.values():
        db.add(p)

    await db.commit()

    # refresh 所有预测
    final_result = await db.execute(
        select(PredictedScene)
        .where(
            PredictedScene.project_id == project_id,
            PredictedScene.status == "suggested",
        )
        .order_by(PredictedScene.confidence.desc())
    )
    return list(final_result.scalars().all())


# ── 策略 1：时间模式 ──


def _predict_by_time_pattern(project_id: str, logs: list[SceneBehaviorLog]) -> list[PredictedScene]:
    """按（room_type, time_of_day）组合统计激活次数，推荐 TOP1 场景"""
    counts: dict[tuple[str | None, int], int] = defaultdict(int)
    samples: dict[tuple[str | None, int], list[SceneBehaviorLog]] = defaultdict(list)

    for entry in logs:
        if entry.scene_id and entry.time_of_day is not None:
            key = (entry.room_type, entry.time_of_day)
            counts[key] += 1
            samples[key].append(entry)

    results: list[PredictedScene] = []
    for (room_type, hour), count in counts.items():
        if count < 2:
            continue
        sample = samples[(room_type, hour)][0]
        confidence = min(count / 7.0, 0.95)
        day_of_week = sample.day_of_week
        scene_name = f"自动{_room_label(room_type)}场景"
        trigger_condition = {"type": "time", "cron": f"0 {hour} * * *"}
        actions = ROOM_TEMPLATE_ACTIONS.get(room_type or "living_room", [])

        results.append(
            PredictedScene(
                project_id=project_id,
                user_id=sample.user_id,
                scene_name=scene_name,
                room_type=room_type or "",
                trigger_time_hint=_closest_hint(hour, day_of_week),
                trigger_condition=trigger_condition,
                actions=actions,
                confidence=round(confidence, 3),
                based_on_count=count,
                status="suggested",
                explanation=f"在过去一周中，您在{_closest_hint(hour, day_of_week)}共触发了 {count} 次该房间场景。"
                f"系统推荐自动为您执行此场景。",
            )
        )
    return results


# ── 策略 2：设备状态转换（条件触发） ──


def _predict_by_device_transition(
    project_id: str, logs: list[SceneBehaviorLog]
) -> list[PredictedScene]:
    """分析 device_states_before → device_states_after 的转换模式。
    例如 "开锁 → 客厅灯亮" → 预测"回家模式"为 device trigger。
    """
    transition_counts: dict[tuple[str, str], int] = defaultdict(int)
    transition_samples: dict[tuple[str, str], SceneBehaviorLog] = {}

    for entry in logs:
        before = entry.device_states_before or {}
        after = entry.device_states_after or {}
        if not before or not after:
            continue
        # 找 before 中与 after 中状态不同且变化相关的设备
        for device_id, after_state in after.items():
            before_state = before.get(device_id)
            if before_state != after_state:
                tkey = (device_id, str(after_state))
                transition_counts[tkey] += 1
                if tkey not in transition_samples:
                    transition_samples[tkey] = entry

    results: list[PredictedScene] = []
    for (device_id, target_state), count in transition_counts.items():
        if count < 3:
            continue
        sample = transition_samples[(device_id, target_state)]
        confidence = min(count / 7.0, 0.95)
        trigger_condition = {"type": "device", "device_id": device_id, "state": target_state}

        room_type = sample.room_type or "living_room"
        scene_name = _transition_scene_name(device_id, target_state)

        results.append(
            PredictedScene(
                project_id=project_id,
                user_id=sample.user_id,
                scene_name=scene_name,
                room_type=room_type,
                trigger_time_hint=f"当 {device_id} 变为 {target_state} 时",
                trigger_condition=trigger_condition,
                actions=ROOM_TEMPLATE_ACTIONS.get(room_type, []),
                confidence=round(confidence, 3),
                based_on_count=count,
                status="suggested",
                explanation=f"系统发现每当设备 {device_id} 状态变为 {target_state} 时，"
                f"您都会执行相关场景操作（已发生 {count} 次），推荐设置条件触发场景。",
            )
        )
    return results


# ── 策略 3：环境数据分析 ──


def _predict_by_ambient(project_id: str, logs: list[SceneBehaviorLog]) -> list[PredictedScene]:
    """分析温湿度/照度与场景激活的关联。"""
    temp_bins: dict[int, int] = defaultdict(int)
    temp_samples: dict[int, SceneBehaviorLog] = {}

    for entry in logs:
        ambient = entry.ambient_data or {}
        temperature = ambient.get("temperature")
        if temperature is None:
            continue
        t_bin = int(temperature // 5 * 5)  # 每 5°C 一个桶
        temp_bins[t_bin] += 1
        if t_bin not in temp_samples:
            temp_samples[t_bin] = entry

    results: list[PredictedScene] = []
    for t_bin, count in temp_bins.items():
        if count < 2:
            continue
        sample = temp_samples[t_bin]
        confidence = min(count / 7.0, 0.95)
        room_type = sample.room_type or "living_room"

        if t_bin < 15:
            scene_name = "低温保暖场景"
            explanation = f"温度低于 {t_bin + 5}°C 时您多次触发场景，推荐低温自动供暖。"
        elif t_bin > 28:
            scene_name = "高温降温场景"
            explanation = f"温度高于 {t_bin}°C 时您多次触发场景，推荐高温自动降温。"
        else:
            scene_name = f"温度自适应场景（{t_bin}~{t_bin + 5}°C）"
            explanation = f"温度在 {t_bin}~{t_bin + 5}°C 时您有 {count} 次场景操作习惯。"

        trigger_condition = {
            "type": "ambient",
            "condition": "temperature",
            "operator": ">" if t_bin > 28 else "<",
            "value": t_bin,
        }

        results.append(
            PredictedScene(
                project_id=project_id,
                user_id=sample.user_id,
                scene_name=scene_name,
                room_type=room_type,
                trigger_time_hint=f"温度{'高于' if t_bin > 28 else '低于'}{t_bin}°C时",
                trigger_condition=trigger_condition,
                actions=ROOM_TEMPLATE_ACTIONS.get(room_type, []),
                confidence=round(confidence, 3),
                based_on_count=count,
                status="suggested",
                explanation=explanation,
            )
        )
    return results


# ── 辅助函数 ──


def _room_label(room_type: str | None) -> str:
    labels = {
        "living_room": "客厅",
        "bedroom": "卧室",
        "kitchen": "厨房",
        "bathroom": "卫生间",
        "entrance": "玄关",
        "study": "书房",
    }
    return labels.get(room_type or "", "客厅")


def _transition_scene_name(device_id: str, target_state: str) -> str:
    """根据设备 ID 和转换状态生成场景名称"""
    if device_id == "lock" and target_state == "unlock":
        return "回家模式（预测）"
    if device_id == "lock" and target_state == "lock":
        return "离家模式（预测）"
    if device_id in ("sensor", "motion"):
        return "人体感应模式（预测）"
    if target_state in ("on", "true", "open"):
        return f"自动开启模式（预测）"
    return f"智能联动模式（预测）"


# ── 生成预测（批量） ──


async def generate_predictions(db: AsyncSession) -> dict:
    """对全部活跃项目生成预测场景"""
    active_projects_result = await db.execute(
        select(Project.id).where(Project.status == "active")
    )
    project_ids = [row[0] for row in active_projects_result.fetchall()]

    total_generated = 0
    project_results: dict[str, int] = {}

    for pid in project_ids:
        try:
            preds = await predict_scenes(pid, db)
            project_results[pid] = len(preds)
            total_generated += len(preds)
        except Exception as e:
            log.error(f"generate_predictions: project={pid} failed: {e}")
            project_results[pid] = 0

    return {
        "total_projects": len(project_ids),
        "total_predictions": total_generated,
        "per_project": project_results,
    }


# ── 查询预测 ──


async def get_predictions_by_project(
    db: AsyncSession, project_id: str, status: str | None = None
) -> list[PredictedScene]:
    """查询项目的预测场景列表"""
    stmt = select(PredictedScene).where(PredictedScene.project_id == project_id)
    if status:
        stmt = stmt.where(PredictedScene.status == status)
    stmt = stmt.order_by(PredictedScene.confidence.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── 接受 / 忽略预测 ──


async def accept_prediction(
    db: AsyncSession, prediction_id: str, user_id: str
) -> dict | None:
    """接受预测并创建为真实场景"""
    result = await db.execute(
        select(PredictedScene).where(PredictedScene.id == prediction_id)
    )
    pred = result.scalar_one_or_none()
    if not pred:
        return None

    # 创建真实场景
    scene = SceneAutomation(
        project_id=pred.project_id,
        scene_name=pred.scene_name,
        scene_type="scheduled" if (pred.trigger_condition or {}).get("type") == "time"
        else "triggered",
        trigger_condition=pred.trigger_condition,
        actions=pred.actions,
        enabled=True,
    )
    db.add(scene)
    await db.flush()

    # 更新预测状态
    pred.status = "accepted"
    pred.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(scene)

    return {
        "prediction_id": prediction_id,
        "scene_id": scene.id,
        "scene_name": scene.scene_name,
        "message": f"预测场景「{scene.scene_name}」已创建为真实场景",
    }


async def dismiss_prediction(db: AsyncSession, prediction_id: str) -> bool:
    """忽略预测"""
    result = await db.execute(
        select(PredictedScene).where(PredictedScene.id == prediction_id)
    )
    pred = result.scalar_one_or_none()
    if not pred:
        return False

    pred.status = "dismissed"
    pred.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return True

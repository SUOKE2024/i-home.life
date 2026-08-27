"""传感器快照 API — 接收 Flutter 端 SensorService.getSnapshot() 输出

桥接 Flutter sensor_service.dart → 后端，使传感器数据可用于：
- 真实落库（sensor_snapshots 表，供审计/健康分析/跌倒检测加速度模式分析）
- 场景自动化的 sensor_trigger 实时触发（仅传真实可用的 GPS 数据，
  手机传感器无法提供温度/湿度/光照/占用率等环境量，禁止硬编码伪造）

端点:
- POST /api/sensors/snapshot — 上传传感器快照（真实落库）
- GET  /api/sensors/capabilities — 查询传感器能力
"""
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.sensor_snapshot import SensorSnapshot
from app.models.user import User
from app.auth import get_current_user
from app.config import get_settings
from app.schemas.sensor_snapshot import (
    SensorSnapshotRequest,
    SensorSnapshotResponse,
    SensorCapabilityResponse,
)

router = APIRouter(prefix="/sensors", tags=["传感器"])

settings = get_settings()

logger = logging.getLogger("ihome.sensors")

# ── 传感器快照 per-user 上传限流（2026-08-27 设备链路加固）──
# 通用 rate_limit 中间件按 IP 限流（60/min），与设备高频上报场景错配：
# 多设备共享出口 IP 会互相挤占配额，伪造上传又可按 IP 轮换绕过。
# 此处按用户维度滑动窗口限流（user_id → deque[ts]），配额取
# settings.sensor_snapshot_rate_limit_per_minute（0/负值不限流）。
# 局限：进程内存储，多 worker 不共享（与 rate_limit 中间件同局限，best-effort）。
_UPLOAD_WINDOW_SECONDS = 60
_upload_windows: dict[str, deque[float]] = defaultdict(deque)
_upload_check_counter = 0


def reset_sensor_upload_rate_store() -> None:
    """清空传感器上传限流存储（测试隔离用）。"""
    _upload_windows.clear()


def _check_upload_rate(user_id: str, limit: int) -> bool:
    """按用户限流传感器快照上传；窗口内超限返回 False（调用方返回 429）。"""
    global _upload_check_counter
    if limit <= 0:
        return True  # 0/负值视为不限流
    _upload_check_counter += 1
    if _upload_check_counter % 100 == 0:
        # 按需清理过期条目，防内存无限增长
        cutoff = time.time() - _UPLOAD_WINDOW_SECONDS
        stale = [u for u, w in _upload_windows.items() if not w or w[-1] < cutoff]
        for u in stale:
            del _upload_windows[u]
    now = time.time()
    cutoff = now - _UPLOAD_WINDOW_SECONDS
    window = _upload_windows[user_id]
    while window and window[0] < cutoff:
        window.popleft()
    if len(window) >= limit:
        return False
    window.append(now)
    return True


def _require_feature():
    """校验 sensor_snapshot_enabled feature flag"""
    if not getattr(settings, "sensor_snapshot_enabled", True):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="传感器快照功能未启用",
        )


def _parse_timestamp(raw: str) -> datetime:
    """解析客户端 ISO8601 时间戳；解析失败回退当前 UTC 时间。"""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


@router.post("/snapshot", response_model=SensorSnapshotResponse, status_code=status.HTTP_201_CREATED)
async def upload_sensor_snapshot(
    body: SensorSnapshotRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传当前设备传感器快照。

    Flutter 端调用 SensorService().getSnapshot() 获取数据，
    然后 POST 到此端点。后端将客户端真实读数落库到 sensor_snapshots 表。

    数据用途：
    - 真实数据落库（审计 / 健康分析 / 跌倒检测加速度模式分析）
    - 场景自动化 sensor_trigger 触发（仅真实 GPS 数据参与，
      环境量（温度/湿度/光照/占用率）不伪造、不参与匹配）
    """
    _require_feature()

    # per-user 上传限流（2026-08-27 加固）：防伪造上传刷场景触发
    limit = getattr(settings, "sensor_snapshot_rate_limit_per_minute", 30)
    if not _check_upload_rate(current_user.id, limit):
        logger.warning(
            "sensor_snapshot_rate_limited: user=%s limit=%d/min",
            current_user.id, limit,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="传感器快照上传过于频繁，请稍后再试",
        )

    accel = body.accelerometer
    gyro = body.gyroscope
    mag = body.magnetometer
    gps = body.gps

    logger.info(
        "sensor_snapshot_received: user=%s platform=%s timestamp=%s accel=%s gyro=%s mag=%s gps=%s",
        current_user.id,
        body.platform,
        body.timestamp,
        accel.available if accel else False,
        gyro.available if gyro else False,
        mag.available if mag else False,
        gps.available if gps else False,
    )

    # ── 1. 真实落库：仅存储客户端实际采集到的读数 ──
    logger.debug(
        "sensor_snapshot_raw: user=%s device_id=%s accel=%s gyro=%s mag=%s gps=%s",
        current_user.id,
        body.device_id,
        {
            "x": accel.x, "y": accel.y, "z": accel.z,
            "available": accel.available,
        } if accel else None,
        {
            "x": gyro.x, "y": gyro.y, "z": gyro.z,
            "available": gyro.available,
        } if gyro else None,
        {
            "x": mag.x, "y": mag.y, "z": mag.z,
            "heading_deg": mag.heading_deg, "available": mag.available,
        } if mag else None,
        {
            "latitude": gps.latitude, "longitude": gps.longitude,
            "accuracy": gps.accuracy, "altitude": gps.altitude,
            "available": gps.available,
        } if gps else None,
    )

    snapshot = SensorSnapshot(
        user_id=current_user.id,
        device_id=body.device_id,
        platform=body.platform,
        accelerometer_available=accel.available if accel else False,
        accelerometer_x=accel.x if accel and accel.available else None,
        accelerometer_y=accel.y if accel and accel.available else None,
        accelerometer_z=accel.z if accel and accel.available else None,
        gyroscope_available=gyro.available if gyro else False,
        gyroscope_x=gyro.x if gyro and gyro.available else None,
        gyroscope_y=gyro.y if gyro and gyro.available else None,
        gyroscope_z=gyro.z if gyro and gyro.available else None,
        magnetometer_available=mag.available if mag else False,
        magnetometer_x=mag.x if mag and mag.available else None,
        magnetometer_y=mag.y if mag and mag.available else None,
        magnetometer_z=mag.z if mag and mag.available else None,
        magnetometer_heading_deg=mag.heading_deg if mag and mag.available else None,
        gps_available=gps.available if gps else False,
        gps_latitude=gps.latitude if gps and gps.available else None,
        gps_longitude=gps.longitude if gps and gps.available else None,
        gps_accuracy=gps.accuracy if gps and gps.available else None,
        gps_altitude=gps.altitude if gps and gps.available else None,
        temperature=body.temperature,
        humidity=body.humidity,
        light_lux=body.light_lux,
        sampled_at=_parse_timestamp(body.timestamp),
    )
    db.add(snapshot)
    await db.commit()
    logger.info(
        "sensor_snapshot_persisted: snapshot_id=%s user=%s platform=%s "
        "accel=%s gyro=%s mag=%s gps=%s temp=%s humidity=%s lux=%s sampled_at=%s",
        snapshot.id,
        current_user.id,
        snapshot.platform,
        snapshot.accelerometer_available,
        snapshot.gyroscope_available,
        snapshot.magnetometer_available,
        snapshot.gps_available,
        snapshot.temperature,
        snapshot.humidity,
        snapshot.light_lux,
        snapshot.sampled_at,
    )

    # ── 2. 场景触发检查：仅传真实数据 ──
    # 手机传感器无法提供环境量，不构造假 ambient_data（历史 bug 已修复）。
    # ambient_data 仅包含客户端真实上报的数据：
    #   - 环境量（temperature/humidity/light_lux）由环境传感器/生态桥接上报时参与匹配
    #   - GPS 可用时传真实坐标
    try:
        from app.services.scene_automation_service import check_sensor_triggers
        ambient_data: dict = {}
        if body.temperature is not None:
            ambient_data["temperature"] = body.temperature
        if body.humidity is not None:
            ambient_data["humidity"] = body.humidity
        if body.light_lux is not None:
            ambient_data["light_lux"] = body.light_lux
        if gps and gps.available:
            ambient_data["latitude"] = gps.latitude
            ambient_data["longitude"] = gps.longitude
            ambient_data["accuracy"] = gps.accuracy
        logger.info(
            "sensor_trigger_check_start: snapshot_id=%s user=%s ambient_data=%s",
            snapshot.id, current_user.id, ambient_data,
        )
        if ambient_data:
            triggered = await check_sensor_triggers(
                db=db,
                user_id=current_user.id,
                ambient_data=ambient_data,
                device_id=body.device_id,
            )
            logger.info(
                "sensor_trigger_check_done: snapshot_id=%s triggered=%d",
                snapshot.id, len(triggered),
            )
        else:
            logger.info(
                "sensor_trigger_check_skipped: snapshot_id=%s 无可用环境/GPS 数据，跳过场景匹配",
                snapshot.id,
            )
    except Exception as e:
        logger.exception(
            "sensor_trigger_check_failed: snapshot_id=%s error=%s",
            snapshot.id, e,
        )

    # 可观测性：上报计数按平台（2026-08-27 加固）
    from app.metrics import sensor_snapshot_upload_total
    sensor_snapshot_upload_total.labels(platform=body.platform or "unknown").inc()

    return SensorSnapshotResponse(
        received=True,
        timestamp=body.timestamp,
        sensors_count=sum([
            1 if accel and accel.available else 0,
            1 if gyro and gyro.available else 0,
            1 if mag and mag.available else 0,
            1 if gps and gps.available else 0,
        ]),
    )


@router.get("/capabilities", response_model=SensorCapabilityResponse)
async def get_sensor_capabilities(
    current_user: User = Depends(get_current_user),
):
    """返回支持的后端传感器能力声明。

    用于 Flutter 端在连接后端时了解哪些传感器数据可被消费。
    """
    return SensorCapabilityResponse(
        supported_sensors=["accelerometer", "gyroscope", "magnetometer", "gps"],
        upload_endpoint="/api/sensors/snapshot",
        sampling_rate_hz=60,
        auto_trigger_enabled=True,
    )

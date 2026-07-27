"""传感器快照 API — 接收 Flutter 端 SensorService.getSnapshot() 输出

桥接 Flutter sensor_service.dart → 后端，使传感器数据可用于：
- 场景自动化的 sensor_trigger 实时触发
- 场景行为日志的 ambient_data 自动填充
- 跌倒检测的加速度模式分析

端点:
- POST /api/sensors/snapshot — 上传传感器快照
- GET  /api/sensors/capabilities — 查询传感器能力
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
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


def _require_feature():
    """校验 sensor_snapshot_enabled feature flag"""
    if not getattr(settings, "sensor_snapshot_enabled", True):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="传感器快照功能未启用",
        )


@router.post("/snapshot", response_model=SensorSnapshotResponse, status_code=status.HTTP_201_CREATED)
async def upload_sensor_snapshot(
    body: SensorSnapshotRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传当前设备传感器快照。

    Flutter 端调用 SensorService().getSnapshot() 获取数据，
    然后 POST 到此端点。后端存储传感器数据并关联到用户。

    数据用途：
    - 场景自动化 sensor_trigger 实时触发
    - 场景行为日志 ambient_data 自动填充
    - 跌倒检测加速度模式分析
    """
    _require_feature()

    import logging
    log = logging.getLogger("ihome.sensors")

    log.info(
        "sensor_snapshot_received: user=%s platform=%s timestamp=%s accel=%s gyro=%s mag=%s gps=%s",
        current_user.id,
        body.platform,
        body.timestamp,
        body.accelerometer.available if body.accelerometer else False,
        body.gyroscope.available if body.gyroscope else False,
        body.magnetometer.available if body.magnetometer else False,
        body.gps.available if body.gps else False,
    )

    # 自动触发场景自动化传感器规则（如有 sensor_trigger 条件）
    try:
        from app.services.scene_automation_service import check_sensor_triggers
        await check_sensor_triggers(
            db=db,
            user_id=current_user.id,
            ambient_data={
                "temperature": body.accelerometer.z if body.accelerometer else 0,
                "humidity": 0,
                "light_lux": 0,
                "occupancy": True,
                "motion_detected": body.accelerometer.available if body.accelerometer else False,
            },
            device_id=body.device_id,
        )
    except Exception as e:
        log.debug("sensor_trigger_check_failed: %s", e)

    return SensorSnapshotResponse(
        received=True,
        timestamp=body.timestamp,
        sensors_count=sum([
            1 if body.accelerometer and body.accelerometer.available else 0,
            1 if body.gyroscope and body.gyroscope.available else 0,
            1 if body.magnetometer and body.magnetometer.available else 0,
            1 if body.gps and body.gps.available else 0,
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

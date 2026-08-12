"""传感器快照 Pydantic Schema — 对齐 Flutter SensorService.getSnapshot() 输出格式

Flutter 端输出结构:
{
  'accelerometer': {'x','y','z','available'},
  'gyroscope':     {'x','y','z','available'},
  'magnetometer':  {'x','y','z','heading_deg','available'},
  'gps':           {'latitude','longitude','accuracy','altitude?','available'},
  'timestamp':     ISO8601 字符串,
}
"""
from pydantic import BaseModel, Field


class SensorAxisReadout(BaseModel):
    """三轴传感器读数"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    available: bool = False


class MagnetometerReadout(SensorAxisReadout):
    """磁力计读数（含航向角）"""
    heading_deg: float = 0.0


class GpsReadout(BaseModel):
    """GPS 定位读数"""
    latitude: float = 0.0
    longitude: float = 0.0
    accuracy: float = 0.0
    altitude: float | None = None
    available: bool = False


class SensorSnapshotRequest(BaseModel):
    """传感器快照上传请求 — 对齐 Flutter getSnapshot() 输出

    环境量（temperature/humidity/light_lux）由环境传感器/生态桥接真实上报，
    手机传感器无法提供时不传（None），禁止伪造（诚实降级红线）。
    """
    accelerometer: SensorAxisReadout | None = None
    gyroscope: SensorAxisReadout | None = None
    magnetometer: MagnetometerReadout | None = None
    gps: GpsReadout | None = None
    temperature: float | None = Field(default=None, description="温度 (°C)，环境传感器真实上报")
    humidity: float | None = Field(default=None, description="湿度 (%)，环境传感器真实上报")
    light_lux: float | None = Field(default=None, description="光照度 (lux)，环境传感器真实上报")
    timestamp: str = Field(description="ISO8601 时间戳")
    platform: str = Field(default="unknown", description="ios / android / harmonyos / web")
    device_id: str | None = Field(default=None, description="设备推送令牌 ID（可选）")


class SensorSnapshotResponse(BaseModel):
    """传感器快照接收确认"""
    received: bool = True
    timestamp: str
    sensors_count: int = 0


class SensorCapabilityResponse(BaseModel):
    """后端传感器能力声明"""
    supported_sensors: list[str]
    upload_endpoint: str
    sampling_rate_hz: int = 60
    auto_trigger_enabled: bool = True

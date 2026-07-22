"""A2 智能家居健康监测系统 Pydantic 模型"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 健康监测记录 ──


class HealthMonitorCreate(BaseModel):
    project_id: str
    scheme_id: str
    monitor_type: str = Field(
        description="监测类型: sleep_quality / air_quality / fall_detection / activity_tracking / heart_rate / spo2"
    )
    value: dict[str, Any]
    alert_level: str = Field(default="normal", description="预警级别: normal / warning / critical")
    alert_message: str | None = None
    device_id: str | None = None
    recorded_at: datetime | None = None


class HealthMonitorResponse(BaseModel):
    id: str
    project_id: str
    scheme_id: str
    monitor_type: str
    value: dict[str, Any]
    alert_level: str
    alert_message: str | None
    device_id: str | None
    recorded_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ── 空气质量记录 ──


class AirQualityRecordCreate(BaseModel):
    project_id: str
    scheme_id: str
    room_name: str
    pm25: float = Field(default=0.0, description="PM2.5 浓度 (μg/m³)")
    pm10: float = Field(default=0.0, description="PM10 浓度")
    co2: float = Field(default=0.0, description="CO2 浓度 (ppm)")
    tvoc: float = Field(default=0.0, description="总挥发性有机物 (ppb)")
    formaldehyde: float = Field(default=0.0, description="甲醛浓度 (mg/m³)")
    temperature: float = Field(default=0.0, description="温度 (°C)")
    humidity: float = Field(default=0.0, description="湿度 (%)")
    aqi_index: int = Field(default=0, description="综合 AQI 指数")
    aqi_level: str = Field(
        default="good",
        description="AQI 等级: good / moderate / unhealthy_sensitive / unhealthy / very_unhealthy / hazardous"
    )
    recorded_at: datetime | None = None


class AirQualityRecordResponse(BaseModel):
    id: str
    project_id: str
    scheme_id: str
    room_name: str
    pm25: float
    pm10: float
    co2: float
    tvoc: float
    formaldehyde: float
    temperature: float
    humidity: float
    aqi_index: int
    aqi_level: str
    recorded_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ── 健康报告 ──


class AlertItem(BaseModel):
    monitor_type: str
    alert_level: str
    alert_message: str | None
    value: dict[str, Any]
    recorded_at: datetime


class HealthReportResponse(BaseModel):
    project_id: str
    generated_at: datetime
    summary: str
    total_records: int
    alert_records: int
    sleep_avg_score: float | None = Field(default=None, description="睡眠平均分（如有睡眠数据）")
    latest_air_quality: AirQualityRecordResponse | None = Field(default=None, description="最新空气质量记录")
    recent_alerts: list[AlertItem] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

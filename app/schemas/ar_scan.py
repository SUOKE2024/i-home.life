"""F1 AR 空间测量 Pydantic 验证模型"""

from datetime import datetime

from pydantic import BaseModel, Field


class ScanSessionCreate(BaseModel):
    project_id: str
    survey_id: str | None = None
    name: str = Field(default="AR 扫描", max_length=200)
    scanner: str | None = None
    device_model: str | None = None
    platform: str = Field(default="ios")  # ios / android / harmonyos / web
    requested_method: str = Field(default="lidar")  # lidar / visual_slam / photogrammetry / manual
    device_capability: dict | None = None  # {lidar_supported, arkit_version, ...}
    floor_count: int = Field(default=1, ge=1, le=10)
    wall_height: float = Field(default=2.8, ge=2.0, le=5.0)
    notes: str | None = None


class ScanSessionUpdate(BaseModel):
    name: str | None = None
    scanner: str | None = None
    scan_method: str | None = None
    floor_count: int | None = None
    room_count: int | None = None
    total_area: float | None = None
    wall_height: float | None = None
    scan_duration_sec: int | None = None
    scan_points_count: int | None = None
    model_url: str | None = None
    model_format: str | None = None
    raw_data_url: str | None = None
    panoramas: list[str] | None = None
    status: str | None = None
    notes: str | None = None


class ScanSessionResponse(BaseModel):
    id: str
    project_id: str
    survey_id: str | None
    name: str
    scanner: str | None
    device_model: str | None
    platform: str
    scan_method: str
    requested_method: str | None
    device_capability: str | None
    floor_count: int
    room_count: int
    total_area: float
    wall_height: float
    scan_duration_sec: int
    scan_points_count: int
    model_url: str | None
    model_format: str | None
    raw_data_url: str | None
    panorama_urls: str | None
    accuracy_rms_error: float | None
    accuracy_level: str | None
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScanSessionListItem(BaseModel):
    id: str
    project_id: str
    name: str
    scanner: str | None
    platform: str
    scan_method: str
    total_area: float
    room_count: int
    accuracy_level: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WallFeatureCreate(BaseModel):
    session_id: str
    room_name: str = Field(..., max_length=100)
    wall_id: str | None = None
    feature_type: str  # door / window / opening / beam / column / pipe / socket / switch / ac_hole
    position_x: float = Field(default=0.0, ge=0.0, le=100.0)
    position_y: float = Field(default=0.0, ge=0.0, le=10.0)
    width: float = Field(default=0.0, ge=0.0, le=20.0)
    height: float = Field(default=0.0, ge=0.0, le=10.0)
    depth: float = Field(default=0.0, ge=0.0, le=5.0)
    sill_height: float | None = None
    load_bearing: bool = False
    material: str | None = None
    direction: str | None = None
    extra: dict | None = None
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    detected_by: str = Field(default="ai")  # ai / manual


class WallFeatureResponse(BaseModel):
    id: str
    session_id: str
    room_name: str
    wall_id: str | None
    feature_type: str
    position_x: float
    position_y: float
    width: float
    height: float
    depth: float
    sill_height: float | None
    load_bearing: bool
    material: str | None
    direction: str | None
    extra: str | None
    confidence: float
    detected_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MeasurementPointCreate(BaseModel):
    session_id: str
    label: str = Field(..., max_length=100)
    room_name: str | None = None
    point_type: str = Field(default="distance")  # distance / height / diagonal / area
    ar_value: float
    reference_value: float
    unit: str = Field(default="m")  # m / cm / ㎡
    notes: str | None = None


class MeasurementPointResponse(BaseModel):
    id: str
    session_id: str
    label: str
    room_name: str | None
    point_type: str
    ar_value: float
    reference_value: float
    unit: str
    deviation: float
    deviation_percent: float
    measured_at: datetime
    notes: str | None

    model_config = {"from_attributes": True}


class DeviceCapabilityRequest(BaseModel):
    """设备能力检测请求 — 由客户端上报硬件能力"""
    platform: str = Field(default="ios")
    device_model: str | None = None
    os_version: str | None = None
    has_lidar: bool = False
    has_depth_sensor: bool = False
    arkit_version: str | None = None
    arcore_version: str | None = None
    ar_engine_version: str | None = None
    camera_resolution: str | None = None
    supports_roomplan: bool = False
    supports_photogrammetry: bool = True


class ProcessScanRequest(BaseModel):
    """触发扫描数据处理 — 解析 USDZ/点云并生成精度报告"""
    model_url: str | None = None
    model_format: str | None = Field(default="usdz")  # usdz / glb / obj / ply
    raw_data_url: str | None = None
    panoramas: list[str] | None = None
    scan_points_count: int = Field(default=0, ge=0)
    scan_duration_sec: int = Field(default=0, ge=0)


class AccuracyReportResponse(BaseModel):
    """精度校验报告"""
    session_id: str
    rms_error_cm: float
    accuracy_level: str  # high / medium / low
    max_deviation_cm: float
    avg_deviation_cm: float
    passed_count: int
    total_count: int
    pass_rate: float
    degradation_path: list[str]  # e.g. ["lidar", "visual_slam"]
    recommendations: list[str]
    points: list[MeasurementPointResponse]


class ARDeviceCapabilityResponse(BaseModel):
    """AR 设备能力查询响应"""
    platform: str
    recommended_method: str
    available_methods: list[str]
    lidar_supported: bool
    fallback_chain: list[str]
    estimated_accuracy_cm: float
    estimated_scan_time_per_room_min: int

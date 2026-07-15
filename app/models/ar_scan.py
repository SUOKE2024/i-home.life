"""F1 AR 空间测量完整模型 — 扫描会话 + 墙面特征 + 测量点 + 精度报告

支持 LiDAR / 视觉 SLAM / 摄影测量 / 手动 四级降级策略,
覆盖墙面物理属性(材质/承重)、门窗洞口、梁柱、管道等结构化扫描要素。
"""

import uuid
import json
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Text, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ScanSession(Base):
    """AR 扫描会话 — 一次完整的房屋扫描任务

    对应 PRD F1: AR 空间测量。覆盖 iOS RoomPlan / ARKit、Android ARCore、
    HarmonyOS AR Engine 三端能力,通过 device_capability 字段记录实际降级路径。
    """

    __tablename__ = "ar_scan_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    survey_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("surveys.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="AR 扫描")
    scanner: Mapped[str | None] = mapped_column(String(100), nullable=True)              # 扫描人
    # 设备型号: iPhone 15 Pro / MatePad Pro 13.2 等
    device_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False, default="ios")
    # platform: ios / android / harmonyos / web
    scan_method: Mapped[str] = mapped_column(String(30), nullable=False, default="lidar")
    # scan_method: lidar (LiDAR SceneReconstruction)
    #            | visual_slam (ARKit/ARCore without LiDAR)
    #            | photogrammetry (照片建模)
    #            | manual (手动辅助测量)
    # 实际策略可能跨级降级: lidar → visual_slam → photogrammetry → manual
    requested_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # 用户最初请求的方法,用于与 scan_method 对比计算降级路径
    device_capability: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON: {lidar_supported, arkit_version, arcore_version, depth_api, ...}
    floor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    room_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_area: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)        # 实测总面积 ㎡
    wall_height: Mapped[float] = mapped_column(Float, nullable=False, default=2.8)        # 层高 m
    scan_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)    # 扫描耗时(秒)
    scan_points_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)    # 点云点数
    model_url: Mapped[str | None] = mapped_column(String(500), nullable=True)             # USDZ/GLB 模型存储 URL
    model_format: Mapped[str | None] = mapped_column(String(20), nullable=True)           # usdz / glb / obj / ply
    raw_data_url: Mapped[str | None] = mapped_column(String(500), nullable=True)          # 原始点云/图片包 URL
    panorama_urls: Mapped[str | None] = mapped_column(Text, nullable=True)                # JSON: 全景图 URL 列表
    accuracy_rms_error: Mapped[float | None] = mapped_column(Float, nullable=True)        # RMS 误差 (cm)
    accuracy_level: Mapped[str | None] = mapped_column(String(20), nullable=True)         # high / medium / low
    # high: <2cm, medium: 2-5cm, low: >5cm
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created")
    # status: created / scanning / uploaded / processing / completed / failed
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    survey = relationship("Survey", foreign_keys=[survey_id])
    wall_features = relationship("WallFeature", back_populates="session", cascade="all, delete-orphan")
    measurement_points = relationship("MeasurementPoint", back_populates="session", cascade="all, delete-orphan")

    @property
    def panoramas(self) -> list[str]:
        try:
            return json.loads(self.panorama_urls or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    @panoramas.setter
    def panoramas(self, value: list[str]):
        self.panorama_urls = json.dumps(value, ensure_ascii=False)


class WallFeature(Base):
    """墙面结构特征 — 门/窗/洞口/梁/柱/管道/开关插座

    用于 AR 扫描后的结构化标注,辅助施工图深化和 BOM 生成。
    """

    __tablename__ = "ar_wall_features"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("ar_scan_sessions.id"), nullable=False)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)                  # 所属房间
    wall_id: Mapped[str | None] = mapped_column(String(50), nullable=True)               # 墙体编号 wall_n
    feature_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # feature_type: door / window / opening / beam / column / pipe / socket / switch / ac_hole
    position_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)        # 距墙左端距离 (m)
    position_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)        # 距地面高度 (m)
    width: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)             # 宽 (m)
    height: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)            # 高 (m)
    depth: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)             # 深/厚度 (m)
    sill_height: Mapped[float | None] = mapped_column(Float, nullable=True)              # 窗台高 (m),仅 window
    load_bearing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)   # 是否承重
    material: Mapped[str | None] = mapped_column(String(100), nullable=True)             # 墙体材质
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)             # N/S/E/W/NE/...
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)                       # JSON 扩展属性
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.95)        # AI 识别置信度 0-1
    detected_by: Mapped[str] = mapped_column(String(20), nullable=False, default="ai")
    # detected_by: ai / manual
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session = relationship("ScanSession", back_populates="wall_features")

    @property
    def extras(self) -> dict:
        try:
            return json.loads(self.extra or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    @extras.setter
    def extras(self, value: dict):
        self.extra = json.dumps(value, ensure_ascii=False)


class MeasurementPoint(Base):
    """测量校准点 — 用于精度校验和重复测量

    AR 扫描的关键质量保证环节:每个校准点同时记录 AR 测量值和人工参考值,
    通过 RMS 误差评估整次扫描的精度等级。
    """

    __tablename__ = "ar_measurement_points"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("ar_scan_sessions.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)                      # 测点标识: 主卧-对角线
    room_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    point_type: Mapped[str] = mapped_column(String(20), nullable=False, default="distance")
    # point_type: distance / height / diagonal / area
    ar_value: Mapped[float] = mapped_column(Float, nullable=False)                       # AR 测量值
    reference_value: Mapped[float] = mapped_column(Float, nullable=False)                # 人工参考值(钢尺/激光仪)
    unit: Mapped[str] = mapped_column(String(10), nullable=False, default="m")           # m / cm / ㎡
    deviation: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)         # 偏差=ar_value-reference_value
    deviation_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 偏差百分比
    measured_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    session = relationship("ScanSession", back_populates="measurement_points")

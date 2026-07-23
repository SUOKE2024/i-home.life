"""F17 卫生间设计器模型 — 卫生间设计 + 卫浴设备"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, Float, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BathroomDesign(Base):
    """卫生间设计"""

    __tablename__ = "bathroom_designs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    layout_type: Mapped[str] = mapped_column(String(30), nullable=False, default="dry_wet_separation")
    # layout_type: dry_wet_separation(干湿分离) / three_separation(三分离) / traditional(传统)
    room_width: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    room_length: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    ceiling_height: Mapped[float] = mapped_column(Float, nullable=False, default=2.6)
    dry_area: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 干区面积 (m²)
    wet_area: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 湿区面积 (m²)
    floor_drain_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    waterproof_height_mm: Mapped[int] = mapped_column(Integer, nullable=False, default=1800)
    # 防水高度，默认 1800mm（淋浴区墙面）
    # ── 防水真校验字段（v1.1.31 FP-2 修复：原 validate_waterproof 后4项硬编码 passed=True，现补字段做真校验）──
    other_wall_waterproof_height_mm: Mapped[int] = mapped_column(Integer, nullable=True, default=300)
    # 其他墙面防水高度（翻边），默认 300mm，标准 ≥ 300mm
    floor_waterproof_done: Mapped[bool] = mapped_column(
        # 地面是否满做防水涂层，默认 True（设计阶段默认全做，施工阶段按实际）
        Integer, nullable=True, default=1
    )
    waterproof_thickness_mm: Mapped[float] = mapped_column(Float, nullable=True, default=1.5)
    # 防水层厚度，默认 1.5mm，标准 ≥ 1.5mm（聚氨酯防水涂料）
    water_test_hours: Mapped[float] = mapped_column(Float, nullable=True, default=48.0)
    # 闭水试验时长，默认 48h，标准 ≥ 48h（与 HC-005 对齐，原误写 24h）
    has_natural_window: Mapped[bool] = mapped_column(
        # 是否有自然通风窗，默认 False（无窗需依赖机械通风）
        Integer, nullable=True, default=0
    )
    window_area_m2: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    # 窗户面积（m²），有窗时填实际值；None 时按 has_natural_window 推断
    mechanical_vent_airflow: Mapped[float] = mapped_column(Float, nullable=True, default=80.0)
    # 机械通风风量（m³/h），默认 80，标准 ≥ 80
    drain_slope_percent: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)
    # 地漏坡度，默认 1.5%
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # status: draft / completed
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    fixtures = relationship("BathroomFixture", back_populates="design", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "layout_type IN ('dry_wet_separation', 'three_separation', 'traditional', 'single')",
            name="chk_bathroom_design_layout_type",
        ),
        CheckConstraint("room_width > 0", name="chk_bathroom_design_room_width_positive"),
        CheckConstraint("room_length > 0", name="chk_bathroom_design_room_length_positive"),
        CheckConstraint("ceiling_height > 0", name="chk_bathroom_design_ceiling_height_positive"),
        CheckConstraint("status IN ('draft', 'completed')", name="chk_bathroom_design_status"),
    )


class BathroomFixture(Base):
    """卫浴设备"""

    __tablename__ = "bathroom_fixtures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    design_id: Mapped[str] = mapped_column(String(36), ForeignKey("bathroom_designs.id"), nullable=False, index=True)
    fixture_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # fixture_type: toilet(马桶) / basin(洗手盆) / bathtub(浴缸) / shower(淋浴) /
    #   urinal(小便器) / bidet(妇洗器) / mirror(镜子) / cabinet(浴室柜) /
    #   towel_rack(毛巾架) / vent_fan(换气扇) / heater(暖风机)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    width: Mapped[float] = mapped_column(Float, nullable=False, default=600.0)
    depth: Mapped[float] = mapped_column(Float, nullable=False, default=500.0)
    height: Mapped[float] = mapped_column(Float, nullable=False, default=800.0)
    position_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_z: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    material: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    design = relationship("BathroomDesign", back_populates="fixtures")

    __table_args__ = (
        CheckConstraint(
            "fixture_type IN ('toilet', 'basin', 'bathtub', 'shower', 'urinal', 'bidet', 'mirror', 'cabinet', 'towel_rack', 'vent_fan', 'heater')",
            name="chk_bathroom_fixture_type",
        ),
        CheckConstraint("width > 0", name="chk_bathroom_fixture_width_positive"),
        CheckConstraint("depth > 0", name="chk_bathroom_fixture_depth_positive"),
        CheckConstraint("height > 0", name="chk_bathroom_fixture_height_positive"),
        CheckConstraint("price >= 0", name="chk_bathroom_fixture_price_positive"),
    )

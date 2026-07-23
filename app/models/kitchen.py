"""F16 厨房设计器模型 — 厨房设计 + 厨房组件"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Float, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KitchenDesign(Base):
    """厨房设计"""

    __tablename__ = "kitchen_designs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    layout_type: Mapped[str] = mapped_column(String(30), nullable=False, default="L")
    # layout_type: L / U / I / G / double_i(双一字) / island(岛台)
    room_width: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    room_length: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    ceiling_height: Mapped[float] = mapped_column(Float, nullable=False, default=2.8)
    counter_height: Mapped[float] = mapped_column(Float, nullable=False, default=850.0)
    # 橱柜台面高度，默认 850mm
    counter_depth: Mapped[float] = mapped_column(Float, nullable=False, default=600.0)
    # 橱柜台面深度，默认 600mm
    water_inlet_pos: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 进水口位置 (JSON 字符串)
    drain_pos: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 排水口位置
    gas_pos: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 燃气接口位置
    vent_pos: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 排烟口位置
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # status: draft / completed
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    components = relationship("KitchenComponent", back_populates="design", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("layout_type IN ('L', 'U', 'I', 'G', 'double_i', 'island')", name="chk_kitchen_design_layout_type"),
        CheckConstraint("room_width > 0", name="chk_kitchen_design_room_width_positive"),
        CheckConstraint("room_length > 0", name="chk_kitchen_design_room_length_positive"),
        CheckConstraint("ceiling_height > 0", name="chk_kitchen_design_ceiling_height_positive"),
        CheckConstraint("counter_height > 0", name="chk_kitchen_design_counter_height_positive"),
        CheckConstraint("counter_depth > 0", name="chk_kitchen_design_counter_depth_positive"),
        CheckConstraint("status IN ('draft', 'completed')", name="chk_kitchen_design_status"),
    )


class KitchenComponent(Base):
    """厨房组件"""

    __tablename__ = "kitchen_components"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    design_id: Mapped[str] = mapped_column(String(36), ForeignKey("kitchen_designs.id"), nullable=False, index=True)
    component_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # component_type: cabinet_base(地柜) / wall_cabinet(吊柜) / island(岛台) /
    #   countertop(台面) / sink(水槽) / stove(灶台) / range_hood(抽油烟机) /
    #   dishwasher(洗碗机) / fridge(冰箱) / microwave(微波炉) / oven(烤箱)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    width: Mapped[float] = mapped_column(Float, nullable=False, default=600.0)
    depth: Mapped[float] = mapped_column(Float, nullable=False, default=600.0)
    height: Mapped[float] = mapped_column(Float, nullable=False, default=720.0)
    position_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_z: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rotation: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    material: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    design = relationship("KitchenDesign", back_populates="components")

    __table_args__ = (
        CheckConstraint(
            "component_type IN ('cabinet_base', 'wall_cabinet', 'island', 'countertop', 'sink', 'stove', 'range_hood', 'dishwasher', 'fridge', 'microwave', 'oven')",
            name="chk_kitchen_component_type",
        ),
        CheckConstraint("width > 0", name="chk_kitchen_component_width_positive"),
        CheckConstraint("depth > 0", name="chk_kitchen_component_depth_positive"),
        CheckConstraint("height > 0", name="chk_kitchen_component_height_positive"),
        CheckConstraint("price >= 0", name="chk_kitchen_component_price_positive"),
    )

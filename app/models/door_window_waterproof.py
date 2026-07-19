"""F23 门窗/防水工程模型 — 门窗选型 + 防水方案"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, Float, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DoorWindowSpec(Base):
    """门窗选型"""

    __tablename__ = "door_window_specs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 安装位置
    spec_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # spec_type: entry_door(入户门) / interior_door(室内门) / window(窗户) / sliding_door(推拉门) / french_window(法式窗)
    material: Mapped[str] = mapped_column(String(30), nullable=False)
    # material: solid_wood(实木) / wood_composite(实木复合) / aluminum(铝合金) / pvc(PVC) / steel(钢质)
    width: Mapped[float] = mapped_column(Float, nullable=False, default=800.0)
    # 宽度 (mm)
    height: Mapped[float] = mapped_column(Float, nullable=False, default=2000.0)
    # 高度 (mm)
    thickness: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 厚度 (mm)
    opening_direction: Mapped[str] = mapped_column(String(30), nullable=False, default="inward")
    # opening_direction: inward(内开) / outward(外开) / sliding(推拉) / folding(折叠)
    glass_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # glass_type: single(单层) / double(双层中空) / triple(三层中空) / laminated(夹胶) / low_e(低辐射)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    has_screen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 是否带纱窗
    has_lock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 是否带锁
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")


class WaterproofPlan(Base):
    """防水方案"""

    __tablename__ = "waterproof_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    room_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # room_type: bathroom(卫生间) / kitchen(厨房) / balcony(阳台) / terrace(露台) / laundry(洗衣房)
    wall_height_mm: Mapped[int] = mapped_column(Integer, nullable=False, default=1800)
    # 防水高度 (卫生间 ≥1800mm, 厨房 ≥300mm)
    floor_area: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 地面面积 (m²)
    wall_area: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 墙面防水面积 (m²)
    waterproof_material: Mapped[str] = mapped_column(String(30), nullable=False, default="polyurethane")
    # waterproof_material: polyurethane(聚氨酯) / JS(JS聚合物水泥) / cement_based(水泥基渗透结晶) / SBS(SBS改性沥青)
    coating_layers: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    # 涂刷遍数 (默认 2-3)
    thickness_mm: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)
    # 涂膜厚度 (1.5-2.0mm)
    closure_test_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    # 闭水试验时长 (默认 24-48h)
    material_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 材料用量 (kg)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # status: draft / completed
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")

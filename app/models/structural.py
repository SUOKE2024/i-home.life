"""F8-F9 土建模块模型 — 结构属性 + 工程量计算"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, Float, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LoadBearingWall(Base):
    """承重墙标注 — 关联 projects 和 rooms"""

    __tablename__ = "load_bearing_walls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    room_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("rooms.id"), nullable=True)
    wall_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_load_bearing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # True: 承重墙, False: 非承重墙
    thickness_mm: Mapped[int] = mapped_column(Integer, nullable=False, default=240)
    # 墙体厚度 (mm), 常见值: 120/180/240/370
    length_m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 墙体长度 (m)
    height_m: Mapped[float] = mapped_column(Float, nullable=False, default=2.8)
    # 墙体高度 (m)
    material: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 材料: 砖砌体 / 钢筋混凝土 / 加气混凝土
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    room = relationship("Room")


class Beam(Base):
    """梁建模 — 尺寸/材料/位置"""

    __tablename__ = "beams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    beam_name: Mapped[str] = mapped_column(String(100), nullable=False)
    beam_type: Mapped[str] = mapped_column(String(30), nullable=False, default="main_beam")
    # beam_type: main_beam(主梁) / secondary_beam(次梁) / ring_beam(圈梁)
    width_mm: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    # 梁宽 (mm)
    height_mm: Mapped[int] = mapped_column(Integer, nullable=False, default=400)
    # 梁高 (mm)
    length_m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 梁长 (m)
    material: Mapped[str] = mapped_column(String(30), nullable=False, default="reinforced_concrete")
    # material: reinforced_concrete(钢筋混凝土) / steel(钢结构) / prestressed(预应力)
    concrete_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # 混凝土强度等级: C25/C30/C35/C40
    position_desc: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # 位置描述: 客厅横梁 / 卧室上方
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")


class Column(Base):
    """柱建模 — 尺寸/材料/位置"""

    __tablename__ = "columns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    column_name: Mapped[str] = mapped_column(String(100), nullable=False)
    column_type: Mapped[str] = mapped_column(String(30), nullable=False, default="rectangular")
    # column_type: rectangular(矩形柱) / circular(圆形柱) / l_shape(L形) / t_shape(T形)
    width_mm: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    # 柱截面宽 (mm)
    depth_mm: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    # 柱截面深 (mm), 圆形柱为直径
    height_m: Mapped[float] = mapped_column(Float, nullable=False, default=2.8)
    # 柱高 (m)
    material: Mapped[str] = mapped_column(String(30), nullable=False, default="reinforced_concrete")
    concrete_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    position_desc: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")


class FloorSlab(Base):
    """楼板 — 厚度/混凝土等级"""

    __tablename__ = "floor_slabs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    slab_name: Mapped[str] = mapped_column(String(100), nullable=False)
    slab_type: Mapped[str] = mapped_column(String(30), nullable=False, default="solid")
    # slab_type: solid(实心板) / hollow(空心板) / composite(叠合板)
    thickness_mm: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    # 板厚 (mm), 常见值: 100/120/150/180
    area_m2: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 楼板面积 (m²)
    concrete_grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # 混凝土等级: C25/C30/C35
    rebar_diameter_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 钢筋直径 (mm)
    rebar_spacing_mm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 钢筋间距 (mm)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")


class FoundationType(Base):
    """基础类型 — 类型枚举/承载力"""

    __tablename__ = "foundation_types"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    found_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # found_type: strip(条形基础) / isolated(独立基础) / raft(筏板基础) / pile(桩基础)
    #            / caisson(沉井基础) / stepped(阶梯基础)
    bearing_capacity_kpa: Mapped[float] = mapped_column(Float, nullable=False, default=150.0)
    # 地基承载力 (kPa), 常见: 80-300
    embed_depth_m: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)
    # 埋深 (m)
    foundation_width_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 基础宽度 (m)
    soil_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 土质类型: 粘土 / 砂土 / 粉土 / 岩石
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 是否为项目选定方案
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")


class StructureLoadEstimate(Base):
    """荷载估算 — 荷载类型/数值"""

    __tablename__ = "structure_load_estimates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    load_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # load_type: dead_load(恒载) / live_load(活载) / wind_load(风载) / snow_load(雪载) / seismic(地震)
    load_value_kn_m2: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 荷载标准值 (kN/m²)
    area_m2: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 作用面积 (m²)
    total_load_kn: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 总荷载 (kN) = load_value * area
    floor_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 楼层, None 表示屋面
    usage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 使用功能: 住宅 / 办公 / 商业 / 屋面
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")


class BayCompliance(Base):
    """开间合规检查 — 开间/进深/层高合规记录"""

    __tablename__ = "bay_compliance"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bay_width_m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 开间 (m)
    depth_m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 进深 (m)
    floor_height_m: Mapped[float] = mapped_column(Float, nullable=False, default=2.8)
    # 层高 (m)
    is_bay_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # 开间合规: 住宅 ≥ 2.7m (GB 50096)
    is_depth_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # 进深合规: 不宜超过开间 2 倍
    is_height_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # 层高合规: 住宅 ≥ 2.8m / 卧室≥2.4m (GB 50096)
    checks: Mapped[str | None] = mapped_column(JSON, nullable=True)
    # 详细检查结果 (JSON)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")


class QuantityCalculation(Base):
    """工程量计算 — 墙体体积/砖/砂浆/混凝土/钢筋/模板"""

    __tablename__ = "quantity_calculations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    calc_name: Mapped[str] = mapped_column(String(100), nullable=False)
    calc_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # calc_type: brickwork(砖砌体) / concrete(混凝土) / formwork(模板) / rebar(钢筋) / total(汇总)
    wall_volume_m3: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 墙体体积 (m³)
    brick_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 砖数量 (块)
    mortar_m3: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 砂浆用量 (m³)
    concrete_m3: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 混凝土用量 (m³)
    rebar_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 钢筋用量 (kg)
    formwork_m2: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 模板面积 (m²)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 预估总费用
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # status: draft / confirmed
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    line_items = relationship("QuantityLineItem", back_populates="calculation", cascade="all, delete-orphan")


class QuantityLineItem(Base):
    """工程量明细 — 材料类型/数量/单位"""

    __tablename__ = "quantity_line_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    calculation_id: Mapped[str] = mapped_column(String(36), ForeignKey("quantity_calculations.id"), nullable=False)
    material_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # material_type: brick(标准砖) / mortar(砂浆) / concrete(混凝土) / rebar(钢筋)
    #               / formwork_plywood(模板木板) / formwork_steel(钢模板) / scaffolding(脚手架)
    material_name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="m³")
    # unit: m³ / kg / m² / 块 / 根 / 套
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    calculation = relationship("QuantityCalculation", back_populates="line_items")

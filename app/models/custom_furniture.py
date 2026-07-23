"""F27 定制家具设计器模型 — 设计 + 模块 + 拆单 BOM"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Integer, Float, Text, JSON, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CustomFurnitureDesign(Base):
    """定制家具设计"""

    __tablename__ = "custom_furniture_designs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    furniture_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # furniture_type: wardrobe(衣柜) / cabinet(橱柜) / bookshelf(书柜) / shoe_cabinet(鞋柜) / tv_cabinet(电视柜) / bed(床) / door(门)
    total_width: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 总宽 mm
    total_height: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 总高 mm
    total_depth: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 总深 mm
    panel_material: Mapped[str] = mapped_column(String(50), nullable=False, default="颗粒板")
    # panel_material: 颗粒板 / 多层板 / 欧松板 / 实木
    panel_thickness: Mapped[float] = mapped_column(Float, nullable=False, default=18.0)
    # 板厚 mm,默认 18mm
    edge_banding: Mapped[str] = mapped_column(String(50), nullable=False, default="PVC")
    # edge_banding: PVC / ABS / 亚克力
    hardware_brand: Mapped[str] = mapped_column(String(50), nullable=False, default="海蒂诗")
    # hardware_brand: 海蒂诗 / 百隆 / 东泰
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    style: Mapped[str] = mapped_column(String(50), nullable=False, default="modern")
    # style: modern / 轻奢 / 北欧 / 中式 / 法式
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # status: draft(草稿) / designed(已设计) / quoted(已报价) / ordered(已下单) / produced(生产中) / delivered(已交付)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    modules = relationship(
        "FurnitureModule",
        back_populates="design",
        cascade="all, delete-orphan",
        order_by="FurnitureModule.position_index",
    )
    boms = relationship(
        "FurnitureBOM",
        back_populates="design",
        cascade="all, delete-orphan",
        order_by="FurnitureBOM.item_type",
    )

    __table_args__ = (
        CheckConstraint(
            "furniture_type IN ('wardrobe', 'cabinet', 'bookshelf', 'shoe_cabinet', 'tv_cabinet', 'bed', 'door')",
            name="chk_custom_furniture_design_type",
        ),
        CheckConstraint("total_width >= 0", name="chk_custom_furniture_total_width_positive"),
        CheckConstraint("total_height >= 0", name="chk_custom_furniture_total_height_positive"),
        CheckConstraint("total_depth >= 0", name="chk_custom_furniture_total_depth_positive"),
        CheckConstraint("total_price >= 0", name="chk_custom_furniture_total_price_positive"),
        CheckConstraint(
            "panel_material IN ('颗粒板', '多层板', '欧松板', '实木')",
            name="chk_custom_furniture_panel_material",
        ),
        CheckConstraint("panel_thickness >= 0", name="chk_custom_furniture_panel_thickness_positive"),
        CheckConstraint(
            "edge_banding IN ('PVC', 'ABS', '亚克力')",
            name="chk_custom_furniture_edge_banding",
        ),
        CheckConstraint(
            "hardware_brand IN ('海蒂诗', '百隆', '东泰')",
            name="chk_custom_furniture_hardware_brand",
        ),
        CheckConstraint(
            "style IN ('modern', '轻奢', '北欧', '中式', '法式')",
            name="chk_custom_furniture_style",
        ),
        CheckConstraint(
            "status IN ('draft', 'designed', 'quoted', 'ordered', 'produced', 'delivered')",
            name="chk_custom_furniture_status",
        ),
    )


class FurnitureModule(Base):
    """家具模块 — 柜体由多个模块组成"""

    __tablename__ = "furniture_modules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    design_id: Mapped[str] = mapped_column(String(36), ForeignKey("custom_furniture_designs.id"), nullable=False, index=True)
    module_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # module_type: top(顶板) / bottom(底板) / side(侧板) / back(背板) / shelf(层板) /
    #   drawer(抽屉) / door(门板) / hanging_rod(挂衣杆) / mirror(镜面)
    position_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 宽 mm
    height: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 高 mm
    depth: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 深 mm
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    material: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hardware_specs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 五金规格,JSON 结构: {"slide": "450mm 缓冲", "hinge": "全阻尼"}
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    design = relationship("CustomFurnitureDesign", back_populates="modules")

    __table_args__ = (
        CheckConstraint(
            "module_type IN ('top', 'bottom', 'side', 'back', 'shelf', 'drawer', 'door', 'hanging_rod', 'mirror')",
            name="chk_furniture_module_type",
        ),
        CheckConstraint("position_index >= 0", name="chk_furniture_module_position_index_positive"),
        CheckConstraint("width >= 0", name="chk_furniture_module_width_positive"),
        CheckConstraint("height >= 0", name="chk_furniture_module_height_positive"),
        CheckConstraint("depth >= 0", name="chk_furniture_module_depth_positive"),
        CheckConstraint("quantity >= 0", name="chk_furniture_module_quantity_positive"),
        CheckConstraint("price >= 0", name="chk_furniture_module_price_positive"),
    )


class FurnitureBOM(Base):
    """拆单 BOM — 板材 + 五金 + 配件 + 门板"""

    __tablename__ = "furniture_boms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    design_id: Mapped[str] = mapped_column(String(36), ForeignKey("custom_furniture_designs.id"), nullable=False, index=True)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    item_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # item_type: panel(板材) / hardware(五金) / accessory(配件) / door(门板)
    spec: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 规格,例如 "600×1800×18mm"
    material: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="块")
    # unit: 块 / 个 / 米 / 套
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    supplier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    design = relationship("CustomFurnitureDesign", back_populates="boms")

    __table_args__ = (
        CheckConstraint(
            "item_type IN ('panel', 'hardware', 'accessory', 'door')",
            name="chk_furniture_bom_item_type",
        ),
        CheckConstraint("quantity >= 0", name="chk_furniture_bom_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="chk_furniture_bom_unit_price_positive"),
        CheckConstraint("total_price >= 0", name="chk_furniture_bom_total_price_positive"),
    )

"""窗帘智能展厅模型 — 单店铺固定「官渡区帘享空间窗帘布艺经营部」

设计 4.x（2026-08-14）：把窗帘/布艺做成可 3D 交互的智能展厅。
- 系列/品牌/材质（面料）→ 展品 catalog，驱动 3D 换装贴图
- 安装方式 → 驱动 3D 窗帘几何（罗马杆/轨道/挂钩/打孔/百叶/卷帘）
- 时间/灯光预设 → 驱动 3D 场景光色/强度
- 展示区域 → 命名分区，各绑默认安装方式 + 默认展品
- 展品 material_id 映射 materials.id，复用现有 BOM 加入链路
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CurtainShowroom(Base):
    """窗帘展厅锚点（单店铺固定，seed 1 条）"""

    __tablename__ = "curtain_showrooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    series = relationship("CurtainSeries", back_populates="showroom")
    products = relationship("CurtainProduct", back_populates="showroom")
    areas = relationship("CurtainShowroomArea", back_populates="showroom")


class CurtainSeries(Base):
    """窗帘系列（轻奢提花 / 现代简约 / 新中式 …）"""

    __tablename__ = "curtain_series"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    showroom_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("curtain_showrooms.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    showroom = relationship("CurtainShowroom", back_populates="series")
    products = relationship("CurtainProduct", back_populates="series")


class CurtainProduct(Base):
    """窗帘展品（面料）— 3D 换装的纹理来源，material_id 映射 BOM"""

    __tablename__ = "curtain_products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    showroom_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("curtain_showrooms.id"), nullable=False, index=True
    )
    series_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("curtain_series.id"), nullable=False, index=True
    )
    # 关联平台材料库（复用现有 /api/materials/bom 加入 BOM）
    material_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("materials.id"), nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fabric: Mapped[str] = mapped_column(String(50), nullable=False)  # 材质（棉麻/雪尼尔/绒布/纱/遮光）
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 颜色（供程序化纹理 + 色卡）
    texture_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # 3D 贴图（无则程序化）
    texture_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)  # 真实面料贴图原始字节
    texture_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 贴图 MIME 类型
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 实拍/缩略图
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="米")
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    showroom = relationship("CurtainShowroom", back_populates="products")
    series = relationship("CurtainSeries", back_populates="products")


class CurtainInstallation(Base):
    """窗帘安装方式 — render_type 驱动 3D 几何"""

    __tablename__ = "curtain_installations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # render_type: roman_rod(罗马杆) / track(轨道) / hook(挂钩) / grommet(打孔) / blind(百叶) / roller(卷帘)
    render_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    areas = relationship("CurtainShowroomArea", back_populates="installation")


class CurtainLightingPreset(Base):
    """时间/灯光预设 — 驱动 3D 场景光色与强度"""

    __tablename__ = "curtain_lighting_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # time_of_day: morning / noon / dusk / night / warm / cool
    time_of_day: Mapped[str] = mapped_column(String(30), nullable=False)
    light_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#ffffff")  # 主光色 hex
    ambient_intensity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CurtainShowroomArea(Base):
    """展示区域 — 命名分区，各绑默认安装方式 + 默认展品"""

    __tablename__ = "curtain_showroom_areas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    showroom_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("curtain_showrooms.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    installation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("curtain_installations.id"), nullable=False
    )
    default_product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("curtain_products.id"), nullable=True
    )
    position: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 3D 锚点（可扩展）
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    showroom = relationship("CurtainShowroom", back_populates="areas")
    installation = relationship("CurtainInstallation", back_populates="areas")
    default_product = relationship("CurtainProduct")

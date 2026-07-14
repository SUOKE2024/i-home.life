"""F19 电器品类库 + F20 电器点位规划模型"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func, Float, Text, JSON, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ApplianceCategory(Base):
    """电器品类"""

    __tablename__ = "appliance_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    # code: major_appliance / kitchen_appliance / home_appliance
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    appliances = relationship(
        "Appliance",
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="Appliance.created_at",
    )


class Appliance(Base):
    """电器实例"""

    __tablename__ = "appliances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey("appliance_categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 子类型: air_conditioner / refrigerator / washing_machine / water_heater / tv / range_hood /
    #   cooktop / dishwasher / steam_oven / microwave / water_purifier / garbage_disposal /
    #   robot_vacuum / vacuum_cleaner / dehumidifier / fresh_air_system
    subcategory: Mapped[str] = mapped_column(String(50), nullable=False)
    spec: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 规格文字描述
    power_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 额定功率 W
    energy_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 能效等级: 一级/二级/三级
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    install_requirements: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 安装要求 JSON: {"电源": "16A", "给水": true, "排水": true, "燃气": false, "墙孔": "φ65mm", "散热空间": "左右100mm"}
    dimensions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 尺寸 JSON: {"width": 600, "depth": 650, "height": 850} 单位 mm
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 标签: ["节能", "静音", "智能"]
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # status: active / discontinued
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    category = relationship("ApplianceCategory", back_populates="appliances")
    points = relationship(
        "AppliancePoint",
        back_populates="appliance",
        cascade="all, delete-orphan",
    )


class AppliancePoint(Base):
    """电器点位规划"""

    __tablename__ = "appliance_points"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    room_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("rooms.id"), nullable=True)
    appliance_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("appliances.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # 点位名称,如"客厅空调插座"
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 点位位置描述
    outlet_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 插座类型: 10A/16A/三相/防水/带USB
    circuit: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 回路名称: "厨房回路"/"空调回路"
    water_supply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 是否需要给水
    drainage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 是否需要排水
    gas_supply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 是否需要燃气
    wall_hole: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 墙孔规格: "φ65mm (空调孔)"/"φ110mm (烟道)"
    embedding_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 预埋注意事项
    power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 点位预估功率
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    # status: planned / completed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")
    room = relationship("Room")
    appliance = relationship("Appliance", back_populates="points")


class ApplianceLoadCalc(Base):
    """全屋负载计算结果"""

    __tablename__ = "appliance_load_calcs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    circuit_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 回路名称
    total_power: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 总功率 W
    voltage: Mapped[float] = mapped_column(Float, nullable=False, default=220.0)
    # 电压 V
    max_current: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 最大电流 A
    wire_gauge: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 推荐线径: "2.5mm²"/"4mm²"/"6mm²"
    breaker_rating: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 推荐断路器: "16A"/"20A"/"25A"/"32A"
    is_compliant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # 是否符合安全规范
    warning_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 超标警告信息
    appliance_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 回路下电器数量
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project")

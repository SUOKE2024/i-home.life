"""F17 卫生间设计器 Pydantic 模型"""

from datetime import datetime
from pydantic import BaseModel


class BathroomDesignCreate(BaseModel):
    project_id: str
    room_name: str
    layout_type: str = "dry_wet_separation"
    room_width: float = 2.0
    room_length: float = 3.0
    ceiling_height: float = 2.6
    dry_area: float | None = None
    wet_area: float | None = None
    floor_drain_count: int = 1
    waterproof_height_mm: int = 1800
    drain_slope_percent: float = 1.5
    status: str = "draft"
    # v1.2.2：补齐 FP-2 通风真校验所需字段。原 FP-2 在 service 层按这些字段真校验，
    # 但 create/update schema 未暴露，导致 API 创建的设计 has_natural_window 恒为 False、
    # natural_ventilation.compliant 恒为 False（功能不可达）。现补齐使通风分析可用。
    has_natural_window: bool = False            # 是否有自然通风窗（无窗需依赖机械通风）
    window_area_m2: float | None = None         # 窗户面积 m²，None 时按 has_natural_window 推断
    mechanical_vent_airflow: float | None = 80.0  # 机械通风风量 m³/h，默认 80（标准 ≥ 80）


class BathroomDesignUpdate(BaseModel):
    layout_type: str | None = None
    room_width: float | None = None
    room_length: float | None = None
    ceiling_height: float | None = None
    dry_area: float | None = None
    wet_area: float | None = None
    floor_drain_count: int | None = None
    waterproof_height_mm: int | None = None
    drain_slope_percent: float | None = None
    status: str | None = None
    has_natural_window: bool | None = None
    window_area_m2: float | None = None
    mechanical_vent_airflow: float | None = None


class BathroomDesignResponse(BaseModel):
    id: str
    project_id: str
    room_name: str
    layout_type: str
    room_width: float
    room_length: float
    ceiling_height: float
    dry_area: float | None
    wet_area: float | None
    floor_drain_count: int
    waterproof_height_mm: int
    drain_slope_percent: float
    status: str
    has_natural_window: bool
    window_area_m2: float | None
    mechanical_vent_airflow: float | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BathroomFixtureCreate(BaseModel):
    design_id: str
    fixture_type: str
    brand: str | None = None
    model: str | None = None
    width: float = 600.0
    depth: float = 500.0
    height: float = 800.0
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    material: str | None = None
    color: str | None = None
    price: float = 0.0
    notes: str | None = None


class BathroomFixtureResponse(BaseModel):
    id: str
    design_id: str
    fixture_type: str
    brand: str | None
    model: str | None
    width: float
    depth: float
    height: float
    position_x: float
    position_y: float
    position_z: float
    material: str | None
    color: str | None
    price: float
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

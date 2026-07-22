"""A1 智能家居能耗监测系统 Pydantic 模型"""

from datetime import datetime

from pydantic import BaseModel, Field


# ── 能耗记录 ──


class EnergyMonitorCreate(BaseModel):
    project_id: str
    scheme_id: str
    period: str = Field(default="daily", description="统计周期: daily/weekly/monthly")
    total_consumption_kwh: float = Field(default=0.0, description="总能耗 kWh")
    device_breakdown: dict | None = Field(default=None, description="设备级能耗明细")
    peak_power_w: float = Field(default=0.0, description="峰值功率 W")
    avg_power_w: float = Field(default=0.0, description="平均功率 W")
    standby_consumption_kwh: float = Field(default=0.0, description="待机能耗 kWh")
    estimated_cost: float = Field(default=0.0, description="预估电费 元")
    carbon_footprint_kg: float = Field(default=0.0, description="碳排放量 kgCO2")
    recorded_at: datetime = Field(description="记录时间")


class EnergyMonitorResponse(BaseModel):
    id: str
    project_id: str
    scheme_id: str
    period: str
    total_consumption_kwh: float
    device_breakdown: dict | None
    peak_power_w: float
    avg_power_w: float
    standby_consumption_kwh: float
    estimated_cost: float
    carbon_footprint_kg: float
    recorded_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ── 节能建议 ──


class EnergySavingTipCreate(BaseModel):
    scheme_id: str
    tip_type: str = Field(description="建议类型: bill_optimization/device_replacement/schedule_optimization/standby_reduction")
    device_type: str | None = None
    device_name: str | None = None
    current_consumption: float | None = None
    potential_saving_pct: float | None = None
    suggestion: str = Field(description="建议内容")
    priority: str = Field(default="medium", description="优先级: high/medium/low")


class EnergySavingTipResponse(BaseModel):
    id: str
    scheme_id: str
    tip_type: str
    device_type: str | None
    device_name: str | None
    current_consumption: float | None
    potential_saving_pct: float | None
    suggestion: str
    priority: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── 汇总报告 ──


class EnergyTrendPoint(BaseModel):
    """趋势数据点"""
    recorded_at: datetime
    total_consumption_kwh: float
    estimated_cost: float


class DeviceRanking(BaseModel):
    """设备能耗排行"""
    device_name: str
    consumption_kwh: float
    percentage: float


class EnergyReportResponse(BaseModel):
    """能耗汇总报告"""
    scheme_id: str
    period: str
    total_consumption_kwh: float
    estimated_cost: float
    carbon_footprint_kg: float
    peak_power_w: float
    avg_power_w: float
    standby_consumption_kwh: float
    standby_ratio: float = Field(description="待机能耗占比 %")
    trend: list[EnergyTrendPoint] = Field(default_factory=list, description="能耗趋势数据")
    device_ranking: list[DeviceRanking] = Field(default_factory=list, description="设备能耗排行")
    tips: list[EnergySavingTipResponse] = Field(default_factory=list, description="节能建议")
    generated_at: datetime = Field(default_factory=datetime.utcnow)

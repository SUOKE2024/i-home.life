"""F41 适老改造模块 — 适老方案 + 无障碍动线检查

PRD v3.1 F41（2026-08-03 行业调研新增）：
- 适老卫浴（扶手/防滑/无障碍尺寸）
- 全屋无障碍动线检查（门宽/通道/无高差）
- 适老智能设备点位（夜间照明/跌倒报警/紧急呼叫）
对接 HC-006 逃生通道硬约束与 GB 50763-2012《无障碍设计规范》。
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ElderlyAdaptationScheme(Base):
    """适老改造方案（表 elderly_adaptation_schemes）"""

    __tablename__ = "elderly_adaptation_schemes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # occupant_type: elderly_living(老人独立生活) / semi_selfcare(半自理) / nursing(失能护理) / family(多代同堂)
    occupant_type: Mapped[str] = mapped_column(String(30), nullable=False, default="elderly_living")
    # items: JSON [{type: grab_bar/anti_slip/accessibility_dimension/elderly_device/lighting,
    #               room, location, spec, standard}]
    items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # accessibility_report: JSON {room_type, door_width_mm, corridor_width_mm, level_difference_mm,
    #                             violations: [], score}
    accessibility_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # compliance_status: pass / warning / fail
    compliance_status: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project = relationship("Project")

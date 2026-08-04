"""F44 环保材料库标签 — 材料 SKU 增加 ENF/E0/E1 环保等级与绿色认证

PRD v3.1 F44（2026-08-03 行业调研新增）：
近九成消费者首选环保建材，环保为硬性刚需（强化 HC-003 环保等级硬约束）。
材料 SKU 增加 ENF/E0 环保等级与绿色建材认证字段与筛选；
AI 选材强制提示环保等级。
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MaterialEcoCert(Base):
    """材料环保认证标签（表 material_eco_certs，一材料一条）"""

    __tablename__ = "material_eco_certs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    material_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("materials.id"), nullable=False, unique=True, index=True
    )
    # eco_grade: ENF(无醛添加,国标最高) / E0(低醛) / E1(国标限量)
    eco_grade: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    # F50 HENF 等级预埋（HENF 无醛最高级，GB18580-2025 强制 + HENF 新标准）
    # HENF > ENF > E0 > E1；未检测时为空，绝不伪造更高级别
    henf_grade: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    # certification: 绿色建材产品认证 / 中国环境标志(十环) / 森林认证(FSC) / 无认证
    certification: Mapped[str] = mapped_column(String(100), nullable=False, default="无认证")
    # source: manufacturer(厂家自报) / third_party(第三方检测)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="third_party")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    material = relationship("Material")


class MaterialBoardTrace(Base):
    """F50 一板一码溯源 — 每块板材的产地/批次/物流/环保等级全链路追溯

    PRD v3.1 F50（2026-08-03 行业调研新增）：
    板材从生产到交付全程可追溯（产地/批次/物流/环保），一板一码。
    环保强化：HENF 等级（GB18580-2025 强制 + HENF 新标准）可追溯。
    """

    __tablename__ = "material_board_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    board_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    material_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("materials.id"), nullable=False, index=True
    )
    batch_no: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    origin: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    vendor: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    produced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # logistics: 物流轨迹（JSON，如 [{"stage":"出厂","location":"佛山","time":".."}]）
    logistics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # F50 HENF 等级预埋（HENF/ENF/E0/E1，未检测为空，诚实标注）
    henf_grade: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    material = relationship("Material")

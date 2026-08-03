"""F44 环保材料库标签 — 材料 SKU 增加 ENF/E0/E1 环保等级与绿色认证

PRD v3.1 F44（2026-08-03 行业调研新增）：
近九成消费者首选环保建材，环保为硬性刚需（强化 HC-003 环保等级硬约束）。
材料 SKU 增加 ENF/E0 环保等级与绿色建材认证字段与筛选；
AI 选材强制提示环保等级。
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
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
    # certification: 绿色建材产品认证 / 中国环境标志(十环) / 森林认证(FSC) / 无认证
    certification: Mapped[str] = mapped_column(String(100), nullable=False, default="无认证")
    # source: manufacturer(厂家自报) / third_party(第三方检测)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="third_party")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    material = relationship("Material")

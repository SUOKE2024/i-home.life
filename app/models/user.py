import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    # 微信开放平台登录用户无手机号（phone=NULL），绑手机前短信类能力不可用（诚实降级）
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="homeowner")
    # 主角色: homeowner / designer / contractor / supplier / admin
    # 工种子角色（可选，用于 contractor 细分）:
    #   electrician(电工) / carpenter(木工) / plumber(水暖安装工) /
    #   painter(油漆工) / mason(泥瓦工) / installer(安装工) /
    #   curtain_installer(窗帘安装工) / supervisor(监理) / general(通用工长)
    # designer 细分: curtain_designer(窗帘设计师)
    sub_role: Mapped[str | None] = mapped_column(String(30), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # ── 微信开放平台「网站应用」扫码登录绑定（openid 唯一）──
    wechat_openid: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    wechat_unionid: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_verified: Mapped[bool] = mapped_column(default=False)  # 是否已实名认证
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    projects = relationship("Project", back_populates="owner")
    webauthn_credentials = relationship("WebAuthnCredential", back_populates="user", cascade="all, delete-orphan")

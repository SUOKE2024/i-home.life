"""FIDO2/WebAuthn 凭证 ORM 模型

一个用户可以有多个凭证（多台设备、多个安全密钥），
支持 Passkey 跨设备同步（通过云平台同步 credential_id）。
"""

import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Text, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WebAuthnCredential(Base):
    """用户绑定的 WebAuthn/Passkey 凭证"""

    __tablename__ = "webauthn_credentials"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── WebAuthn 核心字段 ──
    # Base64URL 编码的凭证 ID（浏览器的 PublicKeyCredential.rawId）
    credential_id: Mapped[str] = mapped_column(
        String(512), unique=True, nullable=False, index=True
    )
    # Base64URL 编码的公钥（COSE 格式）
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    # 签名计数器（防重放攻击）
    sign_count: Mapped[int] = mapped_column(Integer, default=0)

    # ── 设备信息（便于用户管理多设备） ──
    # 设备名称（如 "iPhone 16 Pro"、"Chrome on macOS"）
    device_name: Mapped[str] = mapped_column(String(200), nullable=True)
    # 凭证类型: "platform"（平台内置，如 Touch ID/Face ID/Windows Hello）
    #           "cross-platform"（外部安全密钥，如 YubiKey）
    credential_type: Mapped[str] = mapped_column(String(50), nullable=True)
    # AAGUID（认证器唯一标识符）
    aaguid: Mapped[str] = mapped_column(String(36), nullable=True)
    # 是否支持 Passkey 跨设备同步（云同步）
    is_passkey: Mapped[bool] = mapped_column(Boolean, default=False)
    # 是否已被吊销/移除
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 最后使用时间
    last_used_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 反向关联
    user = relationship("User", back_populates="webauthn_credentials")

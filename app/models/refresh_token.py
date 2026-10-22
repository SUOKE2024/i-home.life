import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RefreshToken(Base):
    """刷新令牌服务端会话行（v4.public 轮换 + 复用检测 + 族撤销）。

    与 suoke_club auth-svc 的 refresh 会话表对齐：同一令牌族（family_id 滚动轮换），
    旧令牌首次使用即标记 used/rotated_to；grace 窗口内重放返回轮换后的令牌，
    超窗重放视为被盗 → 撤销整族。

    说明：刷新令牌 claim 与访问令牌一致，靠 PASETO footer typ=rt 区分；
    本表存 jti/族/原文等会话元数据，作为复用检测与主动撤销的 SSOT。
    """

    __tablename__ = "refresh_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    family_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # 令牌密文（v1. 前缀，AES-GCM；grace 窗口内解密回写轮换后的 refresh_token 原文）
    token_text: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rotated_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())

"""微信小程序（索克家居业主端）登录端点。

端点：
- POST /api/auth/miniprogram/login       静默登录（wx.login code → openid → PASETO）
- POST /api/auth/miniprogram/bind-phone  手机号快速验证并绑定（getPhoneNumber code）

账号策略：小程序 openid 与「网站应用」openid 命名空间不同，落库时统一加 `mp:` 前缀，
避免两类 openid 撞唯一索引；同一微信用户在小程序与网站首登会各自建号，
后续可通过手机号绑定收敛（已知边界，不做静默合并）。
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import _issue_and_persist, _token_response
from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import TokenResponse, UserResponse
from app.services import wechat_miniprogram_service, wechat_oauth_service
from app.services.audit_log_service import log_audit_event
from app.services.user_service import bind_phone_to_user, get_or_create_wechat_user

router = APIRouter(prefix="/auth/miniprogram", tags=["微信小程序"])
settings = get_settings()

MINIPROGRAM_OPENID_PREFIX = "mp:"


class MiniProgramLoginRequest(BaseModel):
    """静默登录请求。nickname/avatar_url 为小程序端可选补充（profile 授权已受控）。"""

    code: str = Field(min_length=1, max_length=256)
    nickname: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)


class MiniProgramBindPhoneRequest(BaseModel):
    """手机号快速验证：<button open-type="getPhoneNumber"> 回传的 code。"""

    code: str = Field(min_length=1, max_length=256)


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.post("/login", response_model=TokenResponse)
async def miniprogram_login(
    data: MiniProgramLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """小程序静默登录：code 换 openid，首登建号（role=homeowner，无手机号），复用则直接签发。"""
    if not settings.miniprogram_login_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="小程序登录功能已关闭"
        )

    try:
        session_info = await wechat_miniprogram_service.code_to_session(data.code)
    except wechat_miniprogram_service.WeChatMiniProgramError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    openid = f"{MINIPROGRAM_OPENID_PREFIX}{session_info['openid']}"
    nickname = wechat_oauth_service.sanitize_nickname(data.nickname or "")

    user = await get_or_create_wechat_user(
        db,
        openid,
        session_info.get("unionid"),
        nickname or "小程序用户",
        data.avatar_url,
    )
    pair = await _issue_and_persist(db, user)

    await log_audit_event(
        db=db,
        user_id=user.id,
        action="MINIPROGRAM_LOGIN",
        resource_type="user",
        resource_id=user.id,
        details={"role": user.role, "channel": "miniprogram", "bound_phone": user.phone is not None},
        request_ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    return _token_response(user, pair)


@router.post("/bind-phone", response_model=UserResponse)
async def miniprogram_bind_phone(
    data: MiniProgramBindPhoneRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """小程序手机号一键绑定：getPhoneNumber code → purePhoneNumber → 落库。"""
    if not settings.miniprogram_phone_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="手机号绑定功能已关闭"
        )

    # 以 DB 真实状态为准（current_user 可能为缓存 detached 对象）
    db_user = await db.get(User, current_user.id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    if not (db_user.wechat_openid or "").startswith(MINIPROGRAM_OPENID_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前账号非小程序登录账号，不支持微信手机号绑定",
        )
    if db_user.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="当前账号已绑定手机号"
        )

    try:
        phone = await wechat_miniprogram_service.get_phone_number(data.code)
    except wechat_miniprogram_service.WeChatMiniProgramError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

    try:
        db_user = await bind_phone_to_user(db, db_user, phone)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await log_audit_event(
        db=db,
        user_id=db_user.id,
        action="MINIPROGRAM_BIND_PHONE",
        resource_type="user",
        resource_id=db_user.id,
        details={"channel": "miniprogram"},
        request_ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    await db.refresh(db_user)

    return UserResponse.model_validate(db_user)

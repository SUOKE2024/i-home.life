from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.webauthn_credential import WebAuthnCredential
from app.schemas.user import UserCreate, UserLogin, TokenResponse, UserResponse
from app.schemas.webauthn import (
    WebAuthnRegisterBeginRequest,
    WebAuthnRegisterCompleteRequest,
    WebAuthnRegisterCompleteResponse,
    WebAuthnLoginBeginRequest,
    WebAuthnLoginCompleteRequest,
    WebAuthnLoginCompleteResponse,
    WebAuthnCredentialResponse,
)
from app.auth.paseto_handler import create_token
from app.auth import get_current_user
from app.services.user_service import create_user, authenticate_user
from app.services.webauthn_service import (
    webauthn_register_begin,
    webauthn_register_complete,
    webauthn_login_begin,
    webauthn_login_complete,
)

router = APIRouter(prefix="/auth", tags=["认证"])


# ═══════════════════════════════════════════
#  传统密码登录/注册
# ═══════════════════════════════════════════


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.phone == data.phone))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="手机号已注册",
        )

    user = await create_user(db, data)
    token = create_token(user.id, user.role)

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, data.phone, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号或密码错误",
        )

    token = create_token(user.id, user.role)

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


# ═══════════════════════════════════════════
#  WebAuthn / Passkey 注册
# ═══════════════════════════════════════════


@router.post("/webauthn/register/begin")
async def webauthn_register_start(
    body: WebAuthnRegisterBeginRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成 Passkey 注册挑战。返回 PublicKeyCredentialCreationOptions JSON。"""
    return await webauthn_register_begin(db, current_user, body.device_name)


@router.post("/webauthn/register/complete", response_model=WebAuthnRegisterCompleteResponse)
async def webauthn_register_finish(
    body: WebAuthnRegisterCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """完成 Passkey 注册。

    客户端调用 `navigator.credentials.create()` 后将完整的 credential JSON 提交至此端点。
    服务端验证 attestation，存储公钥和凭证 ID。
    """
    try:
        credential = await webauthn_register_complete(
            db,
            credential_json=body.credential,
            device_name=body.device_name,
            transports=body.transports,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return WebAuthnRegisterCompleteResponse(
        credential_id=credential.credential_id,
    )


# ═══════════════════════════════════════════
#  WebAuthn / Passkey 登录
# ═══════════════════════════════════════════


@router.post("/webauthn/login/begin")
async def webauthn_login_start(
    body: WebAuthnLoginBeginRequest,
    db: AsyncSession = Depends(get_db),
):
    """生成 Passkey 登录挑战。返回 PublicKeyCredentialRequestOptions JSON。"""
    return await webauthn_login_begin(db, phone=body.phone)


@router.post("/webauthn/login/complete", response_model=WebAuthnLoginCompleteResponse)
async def webauthn_login_finish(
    body: WebAuthnLoginCompleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """完成 Passkey 登录。

    客户端调用 `navigator.credentials.get()` 后将完整的 credential JSON 提交至此端点。
    服务端验证 assertion 签名后返回 PASETO Token。
    """
    try:
        user, credential = await webauthn_login_complete(
            db,
            credential_json=body.credential,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    token = create_token(user.id, user.role)

    return WebAuthnLoginCompleteResponse(
        access_token=token,
        user=UserResponse.model_validate(user).model_dump(),
    )


# ═══════════════════════════════════════════
#  凭证管理
# ═══════════════════════════════════════════


@router.get("/webauthn/credentials", response_model=list[WebAuthnCredentialResponse])
async def list_credentials(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的所有 Passkey 凭证（用于管理多设备）。"""
    result = await db.execute(
        select(WebAuthnCredential)
        .where(WebAuthnCredential.user_id == current_user.id)
        .order_by(WebAuthnCredential.created_at.desc())
    )
    credentials = result.scalars().all()
    return [WebAuthnCredentialResponse.model_validate(c) for c in credentials]


@router.delete("/webauthn/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除（吊销）指定的 Passkey 凭证。

    凭证将被标记为 inactive（软删除），不会影响其他设备的 Passkey。
    """
    result = await db.execute(
        select(WebAuthnCredential).where(
            WebAuthnCredential.id == credential_id,
            WebAuthnCredential.user_id == current_user.id,
        )
    )
    credential = result.scalar_one_or_none()
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到该凭证",
        )
    credential.is_active = False
    await db.commit()

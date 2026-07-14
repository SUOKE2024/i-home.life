"""WebAuthn / FIDO2 / Passkey 的 Pydantic Schemas"""

from datetime import datetime
from pydantic import BaseModel, Field


# ── 注册流程 ──


class WebAuthnRegisterBeginRequest(BaseModel):
    """客户端请求注册挑战"""
    device_name: str | None = Field(None, max_length=200, description="设备名称，如 'iPhone 16 Pro'")


class WebAuthnRegisterBeginResponse(BaseModel):
    """服务端返回注册挑战（PublicKeyCredentialCreationOptions 的序列化 JSON）"""
    challenge: str
    rp: dict
    user: dict
    public_key: list[dict] = Field(validation_alias="pubKeyCredParams")  # webauthn v3: list of alg entries
    timeout: int
    attestation: str = "none"
    authenticator_selection: dict | None = Field(default=None, validation_alias="authenticatorSelection")
    exclude_credentials: list[dict] = Field(default_factory=list, validation_alias="excludeCredentials")
    hints: list[str] | None = None

    model_config = {"extra": "allow", "populate_by_name": True}


class WebAuthnRegisterCompleteRequest(BaseModel):
    """客户端提交注册结果（完整的 Credential JSON）"""
    credential: dict = Field(..., description="浏览器 navigator.credentials.create() 返回的完整 JSON")
    device_name: str | None = Field(None, max_length=200)
    transports: list[str] | None = None  # ["internal", "hybrid", "usb", ...]


class WebAuthnRegisterCompleteResponse(BaseModel):
    """注册完成"""
    status: str = "ok"
    credential_id: str
    message: str = "Passkey 注册成功"


# ── 登录/认证流程 ──


class WebAuthnLoginBeginRequest(BaseModel):
    """客户端请求登录挑战"""
    phone: str | None = Field(None, description="可选：手机号，用于查找用户已有的凭证")


class WebAuthnLoginBeginResponse(BaseModel):
    """服务端返回登录挑战（PublicKeyCredentialRequestOptions 的序列化 JSON）"""
    challenge: str
    timeout: int
    rp_id: str = Field(validation_alias="rpId")
    allow_credentials: list[dict] = Field(default_factory=list, validation_alias="allowCredentials")
    user_verification: str = Field(default="preferred", validation_alias="userVerification")

    model_config = {"extra": "allow", "populate_by_name": True}


class WebAuthnLoginCompleteRequest(BaseModel):
    """客户端提交登录结果（完整的 Credential JSON）"""
    credential: dict = Field(..., description="浏览器 navigator.credentials.get() 返回的完整 JSON")


class WebAuthnLoginCompleteResponse(BaseModel):
    """登录完成，返回 PASETO Token"""
    access_token: str
    token_type: str = "Bearer"
    user: dict


# ── 凭证管理 ──


class WebAuthnCredentialResponse(BaseModel):
    """单个凭证信息（用于管理列表）"""
    id: str
    credential_id: str
    device_name: str | None
    credential_type: str | None
    is_passkey: bool
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}

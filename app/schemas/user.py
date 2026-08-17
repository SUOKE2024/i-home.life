from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    phone: str = Field(min_length=11, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=100)
    role: str = Field(default="homeowner")
    # 主角色: homeowner / designer / contractor / supplier / admin
    # 工种子角色（可选）:
    #   contractor子: electrician / carpenter / plumber / painter / mason / installer / curtain_installer / supervisor
    #   designer子: curtain_designer
    sub_role: str | None = None


class UserLogin(BaseModel):
    phone: str
    password: str


class OneClickLoginRequest(BaseModel):
    """App 一键登录请求：access_token 由阿里云号码认证 SDK 获取"""

    access_token: str = Field(min_length=1)


class H5OneClickLoginRequest(BaseModel):
    """H5 一键登录请求：sp_token 由 H5 JS SDK 获取"""

    sp_token: str = Field(min_length=1)


class WeChatLoginRequest(BaseModel):
    """微信扫码登录请求：code/state 来自 qrconnect 回调参数"""

    code: str = Field(min_length=1)
    state: str = Field(min_length=1)


class WeChatBindPhoneRequest(BaseModel):
    """微信账号绑定手机号：复用运营商 H5 一键登录 sp_token 验真"""

    sp_token: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: str
    phone: str | None = None  # 微信登录用户未绑手机前为 None
    name: str
    role: str
    sub_role: str | None = None
    avatar_url: str | None = None
    is_active: bool
    is_verified: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    user: UserResponse

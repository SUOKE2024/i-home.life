"""通知 Schema"""
from datetime import datetime
from pydantic import BaseModel, Field


class RegisterDeviceRequest(BaseModel):
    """注册设备推送令牌"""
    # 端点从当前登录用户（token）推导 user_id，无需客户端显式传；
    # 字段保留为可选以兼容历史调用方（服务端忽略该值）。
    user_id: str = Field(default="", max_length=50)
    device_token: str = Field(min_length=1, max_length=500)
    platform: str = Field(pattern=r"^(ios|android|harmonyos)$")


class DeviceTokenResponse(BaseModel):
    id: str
    user_id: str
    device_token: str
    platform: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

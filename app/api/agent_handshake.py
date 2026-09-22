"""ATH 握手凭证 API — v1.16.x（信通院 ATH 1.0 对齐）

端点（均需 PASETO 鉴权）：
- POST /api/agents/handshake/issue         签发握手凭证（ATH ⑦）
- POST /api/agents/handshake/verify        校验握手凭证（ATH ⑤ 智能体核验应用身份）
- POST /api/agents/handshake/verify-agent  应用核验智能体身份（ATH ④）

受 settings.agent_handshake_enabled feature flag 控制（默认 True），
关闭时 503 诚实降级，不暴露能力。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.config import get_settings
from app.models.user import User

router = APIRouter(prefix="/agents/handshake", tags=["ATH 握手凭证"])

settings = get_settings()


def _check_enabled() -> None:
    """flag 关闭时 503 诚实降级。"""
    if not settings.agent_handshake_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ATH 握手凭证未启用（agent_handshake_enabled=False）",
        )


class HandshakeIssueRequest(BaseModel):
    app_id: str = Field(description="应用/调用方标识，须为已登记应用（flutter/webapp/console/suoke_life）")
    agent_name: str = Field(description="目标智能体名")
    scope: str = Field(default="a2a:task", description="最小权限声明，须在该应用白名单内")


class HandshakeVerifyRequest(BaseModel):
    token: str
    app_id: str
    agent_name: str
    actor_user_id: str


class AgentIdentityVerifyRequest(BaseModel):
    agent_name: str
    expected_aid: str | None = Field(default=None, description="期望的 28 位 AID，可选")


@router.post("/issue")
async def issue_handshake(
    data: HandshakeIssueRequest,
    current_user: User = Depends(get_current_user),
):
    """签发握手凭证（ATH ⑦ 握手协商签发凭证）。

    v1.17.x：app_id + scope 经应用注册表校验（`agent_handshake.REGISTERED_APPS`），
    未登记的 app_id 或越权 scope 返回 400 拒签——应用侧身份不得自报。
    """
    _check_enabled()
    from app.services.agent_handshake import create_handshake_credential

    try:
        credential = create_handshake_credential(
            app_id=data.app_id,
            agent_name=data.agent_name,
            actor_user_id=current_user.id,
            scope=data.scope,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"握手凭证签发被拒（应用注册表校验）：{e}",
        )
    return {
        **credential,
        "note": "握手凭证仅证明「获授权与哪个智能体在哪个 scope 交互」，不触发任何业务动作",
    }


@router.post("/verify")
async def verify_handshake(
    data: HandshakeVerifyRequest,
    current_user: User = Depends(get_current_user),
):
    """校验握手凭证（ATH ⑤ 智能体核验应用/用户身份）。无状态，不泄露私有数据。"""
    _check_enabled()
    from app.services.agent_handshake import verify_handshake_credential

    return verify_handshake_credential(
        data.token,
        app_id=data.app_id,
        agent_name=data.agent_name,
        actor_user_id=data.actor_user_id,
    )


@router.post("/verify-agent")
async def verify_agent_identity_endpoint(
    data: AgentIdentityVerifyRequest,
    current_user: User = Depends(get_current_user),
):
    """应用核验智能体身份（ATH ④）：查询目标智能体 AID + ACDL，可选 AID 比对。"""
    _check_enabled()
    from app.services.agent_handshake import verify_agent_identity

    return verify_agent_identity(data.agent_name, expected_aid=data.expected_aid)

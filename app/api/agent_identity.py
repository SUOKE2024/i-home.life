"""GB/Z 185 智能体身份码/ACDL 查询 API（v1.9.0 预研，元数据预埋不硬接外部系统）

端点：
- GET /api/agents/identity/{name}   查询单个 Agent 的 28 位 AID 身份码 + ACDL 能力描述
- GET /api/agents/identity          支持身份码的 Agent 列表

所有端点需 PASETO 鉴权（get_current_user）。身份卡查询不涉及用户私有数据，
故只需认证依赖、无需项目归属校验。
受 ``settings.gbz185_agent_card_enabled`` feature flag 控制（默认 False），
关闭时端点返回 404 诚实降级，不暴露能力。
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from app.config import get_settings
from app.models.user import User
from app.services.agent_identity_card import get_agent_identity, list_supported_agents

router = APIRouter(prefix="/agents/identity", tags=["AI Agent"])

settings = get_settings()


def _check_enabled() -> None:
    """flag 关闭时 404 诚实降级，不暴露身份卡能力。"""
    if not settings.gbz185_agent_card_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GBZ185 身份卡未启用",
        )


@router.get("/{name}")
async def get_identity_card(
    name: str,
    current_user: User = Depends(get_current_user),
):
    """查询单个 Agent 的 GB/Z 185 身份卡（28 位 AID + ACDL 能力描述）。"""
    _check_enabled()
    return get_agent_identity(name)


@router.get("")
async def list_identity_cards(
    current_user: User = Depends(get_current_user),
):
    """列出支持 GB/Z 185 身份码的 Agent（含类型码与默认安全分级）。"""
    _check_enabled()
    return list_supported_agents()

"""配置查询 API — 暴露 feature flags 给前端，支持按需加载长线技术决策模块"""
from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.models.user import User
from app.config import get_settings

router = APIRouter(prefix="/config", tags=["配置"])
settings = get_settings()


@router.get("/feature-flags")
async def get_feature_flags(current_user: User = Depends(get_current_user)):
    """返回前端可用的 feature flags，用于按需加载 Filament/OpenCascade.js 等"""
    return {
        "filament_enabled": settings.filament_enabled,
        "opencascade_enabled": settings.opencascade_enabled,
        "agent_learning_enabled": settings.agent_learning_enabled,
        "agent_function_call_enabled": settings.agent_function_call_enabled,
        "vector_db_url_configured": bool(settings.vector_db_url),
    }

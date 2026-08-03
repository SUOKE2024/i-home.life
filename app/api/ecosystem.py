"""F46 生态桥接优先级 API 端点（v1.5.0, PRD v3.1 F46）

端点：
- GET /api/ecosystem/status    生态桥接状态报告（含配置检测与诚实降级标注）
- GET /api/ecosystem/bridges   生态桥接优先级列表

所有端点需 PASETO 鉴权。
受 ``settings.ecosystem_bridge_priority_enabled`` feature flag 控制（默认开启）。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.services import ecosystem_bridge_status

router = APIRouter(prefix="/ecosystem", tags=["生态桥接"])
settings = get_settings()


@router.get("/status")
async def get_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生态桥接状态报告（未配置 API key 的生态诚实标注 requires_api_key）。"""
    if not settings.ecosystem_bridge_priority_enabled:
        raise HTTPException(status_code=404, detail="该功能未启用")
    return ecosystem_bridge_status.status_report()


@router.get("/bridges")
async def list_bridges(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生态桥接优先级列表（按 priority 升序）。"""
    if not settings.ecosystem_bridge_priority_enabled:
        raise HTTPException(status_code=404, detail="该功能未启用")
    return ecosystem_bridge_status.list_bridges()

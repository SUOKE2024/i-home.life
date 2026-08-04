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
from app.services import smart_level_service
from app.rbac import verify_project_access

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


@router.get("/smart-levels")
async def list_smart_levels(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """五级智能等级定义（对齐智能家电国标，L3 起算真智能）。"""
    if not settings.ecosystem_bridge_priority_enabled:
        raise HTTPException(status_code=404, detail="该功能未启用")
    return smart_level_service.list_levels()


@router.get("/smart-level/{project_id}")
async def get_project_smart_level(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """项目全屋智能 L1-L5 等级评定（预适配国标，诚实聚合实际数据）。"""
    if not settings.ecosystem_bridge_priority_enabled:
        raise HTTPException(status_code=404, detail="该功能未启用")
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    snapshot = await smart_level_service.build_snapshot(db, project_id)
    evaluation = smart_level_service.evaluate_smart_level(snapshot)
    return {
        "project_id": project_id,
        "snapshot": snapshot,
        "evaluation": evaluation,
    }

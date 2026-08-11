"""首页 Feed API — 空间即导航 × 时间叙事的 A2UI 主动卡片流

GET /api/feed/{project_id} → {"cards": [...A2UI 卡片], "source_note": "按现有数据生成"}

数据来源见 home_feed_service：全部来自现有业务表（progress_alerts / floor_plans /
milestone_trackers / budgets / procurement_orders / quality_assessments /
settlements / materials），前端按 A2UI 协议渲染，诚实标注不伪造。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.rbac import verify_project_collaborator_access
from app.services import home_feed_service

router = APIRouter(prefix="/feed", tags=["首页 Feed"])

SOURCE_NOTE = "卡片由项目现有数据按 A2UI 协议生成，仅供导航参考"


@router.get("/{project_id}")
async def get_project_feed(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """拉取项目的 A2UI 主动卡片流（8 类卡片，按现有数据组合）"""
    await verify_project_collaborator_access(
        project_id=project_id, current_user=current_user, db=db
    )
    cards = await home_feed_service.build_feed_cards(db, project_id)
    return {"cards": cards, "source_note": SOURCE_NOTE}

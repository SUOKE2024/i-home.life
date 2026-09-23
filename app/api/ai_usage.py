"""AI Token 用量计量 API（v1.17.4）

政策依据：工信厅科函〔2026〕414号 任务三（大模型 / 智能体 / Token 三类服务采购），
要求用量可量化、可核算、可审计。详见 app/services/ai_token_metering.py。

端点（均需 PASETO 鉴权）：
- GET /api/ai-usage/tokens         当前用户 Token 用量（本人；project_id 可选）
- GET /api/admin/ai-usage/tokens   平台级汇总（管理员；user_id / project_id 可选）

诚实红线：计量 ≠ 计费，响应恒带 metering_only=True / billing_ready=False；
轨迹未落库时 data_source_available=False（不返回 0 伪装无用量）。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.rbac import require_platform_manage, verify_project_access
from app.services.ai_token_metering import TOKEN_GROUP_BY, aggregate_token_usage

router = APIRouter(prefix="/ai-usage", tags=["AI 用量计量"])
admin_router = APIRouter(prefix="/admin/ai-usage", tags=["AI 用量计量（管理端）"])

settings = get_settings()


def _require_feature() -> None:
    if not settings.ai_token_metering_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Token 计量未启用（ai_token_metering_enabled=False）",
        )


def _validate_group_by(group_by: str) -> None:
    if group_by not in TOKEN_GROUP_BY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"group_by 不合法：{group_by}（允许 {list(TOKEN_GROUP_BY)}）",
        )


@router.get("/tokens")
async def get_my_token_usage(
    project_id: str | None = Query(default=None, description="可选：限定项目（校验项目归属）"),
    window_days: int = Query(default=30, ge=1, le=365),
    group_by: str = Query(default="agent_name", description="agent_name | model | provider"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """当前用户的 Token 用量计量（仅计量口径，不含计费金额）。"""
    _require_feature()
    _validate_group_by(group_by)
    if project_id:
        await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    return await aggregate_token_usage(
        db, user_id=current_user.id, project_id=project_id,
        window_days=window_days, group_by=group_by,
    )


@admin_router.get("/tokens")
async def get_platform_token_usage(
    user_id: str | None = Query(default=None, description="可选：限定归属用户"),
    project_id: str | None = Query(default=None, description="可选：限定归属项目"),
    window_days: int = Query(default=30, ge=1, le=365),
    group_by: str = Query(default="agent_name", description="agent_name | model | provider"),
    current_user: User = Depends(require_platform_manage),
    db: AsyncSession = Depends(get_db),
):
    """平台级 Token 用量汇总（管理员）。仅计量口径，不含计费金额。"""
    _require_feature()
    _validate_group_by(group_by)
    return await aggregate_token_usage(
        db, user_id=user_id, project_id=project_id,
        window_days=window_days, group_by=group_by,
    )

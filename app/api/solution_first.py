"""F45 方案前置决策 API 端点（v1.5.0, PRD v3.1 F45）

端点：
- POST /api/solution-first/generate   上传户型后先生成 3 套方案 + 预算区间
- GET  /api/solution-first/entry      查询项目方案前置决策入口状态

所有端点需 PASETO 鉴权，涉及项目访问校验（admin 或 owner）。
受 ``settings.solution_first_enabled`` feature flag 控制（默认开启）。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.rbac import verify_project_access
from app.services import solution_first_service

router = APIRouter(prefix="/solution-first", tags=["方案前置决策"])
settings = get_settings()


class SolutionGenerateRequest(BaseModel):
    project_id: str
    style: str | None = None  # 偏好风格 key（可选，见 STYLE_CATALOG）


class SolutionRefineRequest(BaseModel):
    project_id: str
    plan_no: str  # 方案编号（A/B/C）
    feedback: str  # 用户反馈/偏好
    style: str | None = None


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def generate_package(
    data: SolutionGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成 3 套前置方案 + 预算区间（支持偏好风格；项目不存在返回 404，越权返回 403）。"""
    if not settings.solution_first_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该功能未启用")
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    return await solution_first_service.generate_package(db, data.project_id, data.style)


@router.get("/styles")
async def list_styles(
    current_user: User = Depends(get_current_user),
):
    """可选装修风格目录（多风格深化）。"""
    if not settings.solution_first_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该功能未启用")
    return solution_first_service.list_styles()


@router.post("/refine", status_code=status.HTTP_201_CREATED)
async def refine_layout(
    data: SolutionRefineRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """多轮对话：依据用户反馈深化指定方案（LLM 优先，规则兜底）。"""
    if not settings.solution_first_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该功能未启用")
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    try:
        return await solution_first_service.refine_layout(
            db, data.project_id, data.plan_no, data.feedback, data.style,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/entry")
async def get_entry(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询项目方案前置决策入口状态（是否已有户型、可用面积等）。"""
    if not settings.solution_first_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该功能未启用")
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    return await solution_first_service.get_entry(db, project_id)

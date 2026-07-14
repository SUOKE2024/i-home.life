from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.budget import (
    BudgetCreate,
    BudgetResponse,
    BudgetLineResponse,
)
from app.auth import get_current_user
from app.services import budget_service
from app.agents.budget import BudgetAgent
from app.ws import ws_manager

router = APIRouter(prefix="/budgets", tags=["预算"])


class BudgetPlanRequest(BaseModel):
    message: str = "126㎡ 舒适型"


class BudgetCompareRequest(BaseModel):
    message: str = "126㎡"


class BudgetVarianceRequest(BaseModel):
    total_estimated: float
    total_actual: float


class BudgetTemplateApplyRequest(BaseModel):
    template_code: str
    area: float | None = None


@router.get("/project/{project_id}", response_model=BudgetResponse)
async def get_project_budget(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    budget = await budget_service.get_budget(db, project_id)
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预算不存在")
    return BudgetResponse.model_validate(budget)


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_budget(
    data: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await budget_service.get_budget(db, data.project_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该项目已有预算")

    budget = await budget_service.create_budget(db, data.model_dump())
    resp = BudgetResponse.model_validate(budget)
    await ws_manager.broadcast_to_project(data.project_id, "budget.created", resp.model_dump())
    return resp


@router.post("/generate-from-bom/{project_id}", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def generate_from_bom(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await budget_service.get_budget(db, project_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该项目已有预算")

    budget = await budget_service.generate_budget_from_bom(db, project_id)
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到 BOM 物料，请先添加物料清单")

    resp = BudgetResponse.model_validate(budget)
    await ws_manager.broadcast_to_project(project_id, "budget.generated", resp.model_dump())
    return resp


# ── F10 AI 分项预算 ──
@router.post("/generate-plan")
async def generate_budget_plan(
    data: BudgetPlanRequest,
    current_user: User = Depends(get_current_user),
):
    agent = BudgetAgent()
    return agent.generate_budget_plan(data.message)


@router.patch("/lines/{line_id}", response_model=BudgetLineResponse)
async def update_budget_line(
    line_id: str,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bl = await budget_service.update_budget_line(db, line_id, data)
    if not bl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预算行不存在")
    resp = BudgetLineResponse.model_validate(bl)
    # 通过 budget_id 查询 project_id 用于广播
    from sqlalchemy import select
    from app.models.budget import Budget
    budget_result = await db.execute(select(Budget).where(Budget.id == bl.budget_id))
    budget = budget_result.scalar_one_or_none()
    if budget:
        await ws_manager.broadcast_to_project(budget.project_id, "budget.line_updated", resp.model_dump())
    return resp


# ── F11 多方案预算对比 ──
@router.post("/compare-plans")
async def compare_budget_plans(
    data: BudgetCompareRequest,
    current_user: User = Depends(get_current_user),
):
    agent = BudgetAgent()
    return agent.compare_budget_plans(data.message)


# ── F12 预算偏差预警 ──
@router.post("/variance-check")
async def check_budget_variance(
    data: BudgetVarianceRequest,
    current_user: User = Depends(get_current_user),
):
    agent = BudgetAgent()
    return agent.check_budget_variance(data.total_estimated, data.total_actual)


# ── F13 预算模板库 ──
@router.get("/templates")
async def list_budget_templates(
    current_user: User = Depends(get_current_user),
):
    agent = BudgetAgent()
    return agent.list_templates()


@router.post("/templates/apply")
async def apply_budget_template(
    data: BudgetTemplateApplyRequest,
    current_user: User = Depends(get_current_user),
):
    agent = BudgetAgent()
    return agent.apply_template(data.template_code, data.area)

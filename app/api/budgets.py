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
from app.rbac import verify_project_access
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


@router.get(
    "/project/{project_id}",
    response_model=BudgetResponse,
    summary="获取项目预算",
    description="根据项目 ID 获取该项目的预算信息，包含预算总金额和各分项明细。",
    response_description="项目预算详情",
    responses={
        200: {"description": "获取成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "预算不存在"},
    },
)
async def get_project_budget(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    budget = await budget_service.get_budget(db, project_id)
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预算不存在")
    return BudgetResponse.model_validate(budget)


@router.post(
    "",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建预算",
    description="为指定项目创建一个新的预算记录，包含预算总金额和分项明细。",
    response_description="创建成功，返回预算详情",
    responses={
        201: {"description": "创建成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        409: {"description": "该项目已有预算"},
    },
)
async def create_budget(
    data: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    existing = await budget_service.get_budget(db, data.project_id)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该项目已有预算")

    budget = await budget_service.create_budget(db, data.model_dump())
    resp = BudgetResponse.model_validate(budget)
    await ws_manager.broadcast_to_project(data.project_id, "budget.created", resp.model_dump())
    return resp


@router.post(
    "/generate-from-bom/{project_id}",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="从 BOM 生成预算",
    description="根据项目的物料清单（BOM）自动计算并生成预算，将物料价格汇总为各分项预算。",
    response_description="生成成功，返回预算详情",
    responses={
        201: {"description": "生成成功"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "未找到 BOM 物料"},
        409: {"description": "该项目已有预算"},
    },
)
async def generate_from_bom(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
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
@router.post(
    "/generate-plan",
    summary="AI 生成预算方案",
    description="AI 根据用户描述的房屋面积和装修档次自动生成分项预算方案，包含各施工阶段的预估费用。",
    responses={
        200: {"description": "生成成功"},
        400: {"description": "请求参数无效"},
    },
)
async def generate_budget_plan(
    data: BudgetPlanRequest,
    current_user: User = Depends(get_current_user),
):
    agent = BudgetAgent()
    return agent.generate_budget_plan(data.message)


@router.patch(
    "/lines/{line_id}",
    response_model=BudgetLineResponse,
    summary="更新预算明细行",
    description="更新指定预算行的金额、数量或其他信息，并自动重算预算总额。",
    response_description="更新后的预算行",
    responses={
        200: {"description": "更新成功"},
        400: {"description": "请求参数无效"},
        401: {"description": "未登录或 Token 无效"},
        403: {"description": "无权访问该项目"},
        404: {"description": "预算行不存在"},
    },
)
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
    # 通过 budget_id 查询 project_id 用于校验归属和广播
    from sqlalchemy import select
    from app.models.budget import Budget
    budget_result = await db.execute(select(Budget).where(Budget.id == bl.budget_id))
    budget = budget_result.scalar_one_or_none()
    if budget:
        await verify_project_access(project_id=budget.project_id, current_user=current_user, db=db)
        await ws_manager.broadcast_to_project(budget.project_id, "budget.line_updated", resp.model_dump())
    return resp


# ── F11 多方案预算对比 ──
@router.post(
    "/compare-plans",
    summary="多方案预算对比",
    description="AI 根据房屋面积自动生成舒适型、经济型、豪华型等多套预算方案，方便用户对比选择。",
    responses={
        200: {"description": "对比成功"},
        400: {"description": "请求参数无效"},
    },
)
async def compare_budget_plans(
    data: BudgetCompareRequest,
    current_user: User = Depends(get_current_user),
):
    agent = BudgetAgent()
    return agent.compare_budget_plans(data.message)


# ── F12 预算偏差预警 ──
@router.post(
    "/variance-check",
    summary="预算偏差预警",
    description="AI 对比预算估算金额与实际花费金额，当偏差超过阈值时发出预警和调整建议。",
    responses={
        200: {"description": "检测成功"},
        400: {"description": "请求参数无效"},
    },
)
async def check_budget_variance(
    data: BudgetVarianceRequest,
    current_user: User = Depends(get_current_user),
):
    agent = BudgetAgent()
    return agent.check_budget_variance(data.total_estimated, data.total_actual)


# ── F13 预算模板库 ──
@router.get(
    "/templates",
    summary="获取预算模板列表",
    description="获取系统预设的装修预算模板库，包含不同面积和档次的参考预算方案。",
    responses={
        200: {"description": "获取成功"},
    },
)
async def list_budget_templates(
    current_user: User = Depends(get_current_user),
):
    agent = BudgetAgent()
    return agent.list_templates()


@router.post(
    "/templates/apply",
    summary="应用预算模板",
    description="根据模板代码和房屋面积，将预设预算模板应用到项目预算中。",
    responses={
        200: {"description": "应用成功"},
        400: {"description": "请求参数无效或无匹配模板"},
    },
)
async def apply_budget_template(
    data: BudgetTemplateApplyRequest,
    current_user: User = Depends(get_current_user),
):
    agent = BudgetAgent()
    return agent.apply_template(data.template_code, data.area)

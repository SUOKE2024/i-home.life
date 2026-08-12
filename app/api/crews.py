"""工程队路由 — F36 档案 + 智能匹配"""

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.construction_crew import ConstructionCrew, CrewMatch
from app.schemas.construction_crew import (
    ConstructionCrewCreate,
    ConstructionCrewUpdate,
    ConstructionCrewResponse,
    CrewMatchRequest,
    CrewMatchResponse,
)
from app.auth import get_current_user
from app.rbac import require_admin, verify_project_access
from app.services import crew_service
from app.ws import ws_manager

router = APIRouter(prefix="/crews", tags=["工程队匹配"])


class _CrewSubmitRequest(BaseModel):
    """提交入驻审核时补充的材料字段（可选，未提供的沿用已有值）"""

    license_no: str | None = None
    license_type: str | None = None
    insurance_no: str | None = None


class _CrewReviewRequest(BaseModel):
    """管理员入驻审核动作"""

    action: Literal["approve", "reject"]
    note: str | None = None


def _crew_to_response(crew: ConstructionCrew) -> ConstructionCrewResponse:
    try:
        specialties = json.loads(crew.specialties or "[]")
    except Exception:
        specialties = []
    return ConstructionCrewResponse(
        id=crew.id,
        name=crew.name,
        leader=crew.leader,
        phone=crew.phone,
        city=crew.city,
        district=crew.district,
        qualification=crew.qualification,
        specialties=specialties,
        rating=crew.rating,
        completed_projects=crew.completed_projects,
        avg_duration=crew.avg_duration,
        daily_rate=crew.daily_rate,
        status=crew.status,
        introduction=crew.introduction,
        showcase_panorama_id=crew.showcase_panorama_id,
        created_at=crew.created_at,
        updated_at=crew.updated_at,
    )


def _match_to_response(match: CrewMatch) -> CrewMatchResponse:
    try:
        breakdown = json.loads(match.score_breakdown or "{}")
    except Exception:
        breakdown = {}
    crew_resp = _crew_to_response(match.crew) if match.crew else None
    return CrewMatchResponse(
        id=match.id,
        project_id=match.project_id,
        crew_id=match.crew_id,
        match_score=match.match_score,
        score_breakdown=breakdown,
        recommendation=match.recommendation,
        status=match.status,
        crew=crew_resp,
        created_at=match.created_at,
        updated_at=match.updated_at,
    )


async def _load_match_with_crew(db: AsyncSession, match_id: str) -> CrewMatch | None:
    result = await db.execute(
        select(CrewMatch)
        .where(CrewMatch.id == match_id)
        .options(selectinload(CrewMatch.crew))
    )
    return result.scalar_one_or_none()


@router.get("", response_model=list[ConstructionCrewResponse])
async def list_crews(
    city: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    crews = await crew_service.list_crews(db, city=city, status=status_filter, limit=limit)
    return [_crew_to_response(c) for c in crews]


@router.post("", response_model=ConstructionCrewResponse, status_code=status.HTTP_201_CREATED)
async def create_crew(
    data: ConstructionCrewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    crew = await crew_service.create_crew(db, data.model_dump())
    return _crew_to_response(crew)


@router.get("/{crew_id}", response_model=ConstructionCrewResponse)
async def get_crew(
    crew_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    crew = await crew_service.get_crew(db, crew_id)
    if not crew:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程队不存在")
    return _crew_to_response(crew)


@router.patch("/{crew_id}", response_model=ConstructionCrewResponse)
async def update_crew(
    crew_id: str,
    data: ConstructionCrewUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员更新工程队元数据（设计 4.3：绑定作品集代表作全景 showcase_panorama_id 等）。"""
    crew = await crew_service.update_crew(db, crew_id, data.model_dump(exclude_none=True))
    if not crew:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程队不存在")
    return _crew_to_response(crew)


@router.post("/{crew_id}/submit", response_model=ConstructionCrewResponse)
async def submit_crew_review(
    crew_id: str,
    data: _CrewSubmitRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """工程队提交入驻审核（F36）：补齐执照/保险材料，进入 pending 待管理员审核。

    缺必填材料（license_no/license_type/insurance_no）返回 400 并说明缺什么。
    """
    try:
        crew = await crew_service.submit_crew_review(
            db, crew_id, materials=data.model_dump() if data else None
        )
    except crew_service.CrewReviewError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    if not crew:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程队不存在")
    return _crew_to_response(crew)


@router.post("/{crew_id}/review", response_model=ConstructionCrewResponse)
async def review_crew(
    crew_id: str,
    data: _CrewReviewRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """管理员审核工程队入驻（F36）：action=approve 通过 / action=reject 驳回。

    仅 admin 可调用；非 admin 返回 403。
    """
    try:
        crew = await crew_service.review_crew(
            db, crew_id, action=data.action, note=data.note
        )
    except crew_service.CrewReviewError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    if not crew:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程队不存在")
    return _crew_to_response(crew)


@router.post("/match", response_model=list[CrewMatchResponse])
async def match_crews(
    data: CrewMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """F36 智能匹配：地域 + 专长 + 评分 + 资质 + 价格 + 工期 六维评分"""
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    matches = await crew_service.match_crews(
        db,
        project_id=data.project_id,
        city=data.city,
        district=data.district,
        required_specialties=data.required_specialties,
        budget_daily_rate_max=data.budget_daily_rate_max,
        expected_duration_days=data.expected_duration_days,
        top_n=data.top_n,
    )
    refreshed = []
    for m in matches:
        loaded = await _load_match_with_crew(db, m.id)
        if loaded:
            refreshed.append(loaded)
    resp = [_match_to_response(m) for m in refreshed]
    await ws_manager.broadcast_to_project(data.project_id, "crew.matched", [r.model_dump() for r in resp])
    return resp


@router.get("/matches/{project_id}", response_model=list[CrewMatchResponse])
async def list_project_matches(
    project_id: str,
    skip: int = Query(0, ge=0, description="分页偏移量"),
    limit: int = Query(50, ge=1, le=200, description="每页数量"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询项目工长匹配记录（v1.1.14: 支持 skip/limit 分页）"""
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    result = await db.execute(
        select(CrewMatch)
        .where(CrewMatch.project_id == project_id)
        .options(selectinload(CrewMatch.crew))
        .order_by(CrewMatch.match_score.desc())
        .offset(skip)
        .limit(limit)
    )
    return [_match_to_response(m) for m in result.scalars().all()]


@router.post("/matches/{match_id}/status", response_model=CrewMatchResponse)
async def update_match_status(
    match_id: str,
    new_status: str = Query(..., description="pending/shortlisted/hired/rejected"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    match = await crew_service.update_match_status(db, match_id, new_status)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="匹配记录不存在")
    refreshed = await _load_match_with_crew(db, match_id)
    await verify_project_access(project_id=refreshed.project_id, current_user=current_user, db=db)
    resp = _match_to_response(refreshed)
    await ws_manager.broadcast_to_project(refreshed.project_id, "crew.status_changed", resp.model_dump())
    return resp

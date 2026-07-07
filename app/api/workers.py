"""F35 服务者匹配路由 — 设计师/监理/预算师档案 + 智能匹配"""

import json

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.service_worker import ServiceWorker, ServiceWorkerMatch
from app.schemas.service_worker import (
    ServiceWorkerCreate,
    ServiceWorkerResponse,
    WorkerMatchRequest,
    WorkerMatchResponse,
)
from app.auth import get_current_user
from app.services import worker_service
from app.services.worker_service import parse_json_field
from app.ws import ws_manager

router = APIRouter(prefix="/workers", tags=["服务者匹配"])


def _worker_to_response(worker: ServiceWorker) -> ServiceWorkerResponse:
    return ServiceWorkerResponse(
        id=worker.id,
        name=worker.name,
        phone=worker.phone,
        avatar_url=worker.avatar_url,
        city=worker.city,
        district=worker.district,
        role=worker.role,
        role_attributes=parse_json_field(worker.role_attributes, {}),
        qualification=worker.qualification,
        rating=worker.rating,
        completed_projects=worker.completed_projects,
        years_of_experience=worker.years_of_experience,
        hourly_rate=worker.hourly_rate,
        daily_rate=worker.daily_rate,
        status=worker.status,
        introduction=worker.introduction,
        certifications=parse_json_field(worker.certifications, []),
        portfolio_urls=parse_json_field(worker.portfolio_urls, []),
        created_at=worker.created_at,
        updated_at=worker.updated_at,
    )


def _match_to_response(match: ServiceWorkerMatch) -> WorkerMatchResponse:
    worker_resp = _worker_to_response(match.worker) if match.worker else None
    return WorkerMatchResponse(
        id=match.id,
        project_id=match.project_id,
        worker_id=match.worker_id,
        role=match.role,
        match_score=match.match_score,
        score_breakdown=parse_json_field(match.score_breakdown, {}),
        recommendation=match.recommendation,
        status=match.status,
        worker=worker_resp,
        created_at=match.created_at,
        updated_at=match.updated_at,
    )


async def _load_match_with_worker(db: AsyncSession, match_id: str) -> ServiceWorkerMatch | None:
    result = await db.execute(
        select(ServiceWorkerMatch)
        .where(ServiceWorkerMatch.id == match_id)
        .options(selectinload(ServiceWorkerMatch.worker))
    )
    return result.scalar_one_or_none()


@router.get("", response_model=list[ServiceWorkerResponse])
async def list_workers(
    role: str | None = None,
    city: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """服务者列表（支持 role/city/status 过滤）"""
    workers = await worker_service.list_workers(db, role=role, city=city, status_filter=status_filter, limit=limit)
    return [_worker_to_response(w) for w in workers]


@router.post("", response_model=ServiceWorkerResponse, status_code=status.HTTP_201_CREATED)
async def create_worker(
    data: ServiceWorkerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建服务者档案"""
    worker = await worker_service.create_worker(db, data.model_dump())
    return _worker_to_response(worker)


@router.get("/{worker_id}", response_model=ServiceWorkerResponse)
async def get_worker(
    worker_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    worker = await worker_service.get_worker(db, worker_id)
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="服务者不存在")
    return _worker_to_response(worker)


@router.post("/match", response_model=list[WorkerMatchResponse])
async def match_workers(
    data: WorkerMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """F35 智能匹配：按角色 + 多维评分（设计师/监理/预算师）"""
    matches = await worker_service.match_workers(
        db,
        project_id=data.project_id,
        role=data.role,
        city=data.city,
        district=data.district,
        required_styles=data.required_styles,
        required_phases=data.required_phases,
        required_budget_types=data.required_budget_types,
        budget_hourly_rate_max=data.budget_hourly_rate_max,
        budget_daily_rate_max=data.budget_daily_rate_max,
        min_rating=data.min_rating,
        min_experience=data.min_experience,
        top_n=data.top_n,
    )
    refreshed = []
    for m in matches:
        loaded = await _load_match_with_worker(db, m.id)
        if loaded:
            refreshed.append(loaded)
    resp = [_match_to_response(m) for m in refreshed]
    await ws_manager.broadcast_to_project(data.project_id, "worker.matched", [r.model_dump() for r in resp])
    return resp


@router.get("/matches/{project_id}", response_model=list[WorkerMatchResponse])
async def list_project_matches(
    project_id: str,
    role: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询项目服务者匹配记录"""
    result = await db.execute(
        select(ServiceWorkerMatch)
        .where(ServiceWorkerMatch.project_id == project_id)
        .options(selectinload(ServiceWorkerMatch.worker))
        .order_by(ServiceWorkerMatch.match_score.desc())
    )
    matches = result.scalars().all()
    if role:
        matches = [m for m in matches if m.role == role]
    return [_match_to_response(m) for m in matches]


@router.patch("/matches/{match_id}/status", response_model=WorkerMatchResponse)
async def update_match_status(
    match_id: str,
    new_status: str = Query(..., description="pending/shortlisted/hired/rejected"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新匹配状态（shortlisted/hired/rejected）"""
    match = await worker_service.update_worker_match_status(db, match_id, new_status)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="匹配记录不存在")
    refreshed = await _load_match_with_worker(db, match_id)
    resp = _match_to_response(refreshed)
    await ws_manager.broadcast_to_project(refreshed.project_id, "worker.status_changed", resp.model_dump())
    return resp

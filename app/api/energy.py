"""A1 智能家居能耗监测系统 API"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.smart_home import SmartHomeScheme
from app.auth import get_current_user
from app.config import get_settings
from app.rbac import verify_project_access
from app.schemas.energy_monitor import (
    EnergyMonitorCreate,
    EnergyMonitorResponse,
    EnergySavingTipCreate,
    EnergySavingTipResponse,
    EnergyReportResponse,
)
from app.services import energy_monitor_service as svc

router = APIRouter(prefix="/energy", tags=["能耗监测"])


def _check_feature_flag():
    """检查 energy_monitor_enabled feature flag"""
    if not get_settings().energy_monitor_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="能耗监测功能未启用",
        )


# ── 能耗记录 ──


@router.post("/records", response_model=EnergyMonitorResponse, status_code=status.HTTP_201_CREATED)
async def create_record(
    data: EnergyMonitorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_feature_flag()
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    record = await svc.create_record(db, data.model_dump())
    return EnergyMonitorResponse.model_validate(record)


@router.get("/records/scheme/{scheme_id}", response_model=list[EnergyMonitorResponse])
async def get_records_by_scheme(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_feature_flag()
    # 通过 scheme 获取 project_id 做归属校验
    from sqlalchemy import select as sql_select
    result = await db.execute(sql_select(SmartHomeScheme).where(SmartHomeScheme.id == scheme_id))
    scheme = result.scalar_one_or_none()
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    records = await svc.get_records_by_scheme(db, scheme_id)
    return [EnergyMonitorResponse.model_validate(r) for r in records]


@router.get("/records/project/{project_id}", response_model=list[EnergyMonitorResponse])
async def get_records_by_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_feature_flag()
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    records = await svc.get_records_by_project(db, project_id)
    return [EnergyMonitorResponse.model_validate(r) for r in records]


# ── 能耗报告 ──


@router.get("/report/{scheme_id}", response_model=EnergyReportResponse)
async def generate_report(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_feature_flag()
    from sqlalchemy import select as sql_select
    result = await db.execute(sql_select(SmartHomeScheme).where(SmartHomeScheme.id == scheme_id))
    scheme = result.scalar_one_or_none()
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    report_data = await svc.generate_energy_report(db, scheme_id)
    # 转换报告中的 datetime 格式
    if report_data.get("generated_at"):
        report_data["generated_at"] = datetime.utcnow()
    return EnergyReportResponse(**report_data)


# ── 节能建议 ──


@router.get("/tips/{scheme_id}", response_model=list[EnergySavingTipResponse])
async def get_tips(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_feature_flag()
    from sqlalchemy import select as sql_select
    result = await db.execute(sql_select(SmartHomeScheme).where(SmartHomeScheme.id == scheme_id))
    scheme = result.scalar_one_or_none()
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    # 如果没有建议则自动生成
    tips = await svc.get_tips(db, scheme_id)
    if not tips:
        tips = await svc.generate_tips(db, scheme_id)
    return [EnergySavingTipResponse.model_validate(t) for t in tips]


@router.patch("/tips/{tip_id}/apply", response_model=EnergySavingTipResponse)
async def apply_tip(
    tip_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_feature_flag()
    tip = await svc.apply_tip(db, tip_id)
    if not tip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="建议不存在")

    # 通过 tip 关联的 scheme 做归属校验
    from sqlalchemy import select as sql_select
    scheme_result = await db.execute(sql_select(SmartHomeScheme).where(SmartHomeScheme.id == tip.scheme_id))
    scheme = scheme_result.scalar_one_or_none()
    if scheme:
        await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)

    return EnergySavingTipResponse.model_validate(tip)

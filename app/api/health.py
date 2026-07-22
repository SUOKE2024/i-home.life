"""A2 智能家居健康监测系统 API"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.auth import get_current_user
from app.rbac import verify_project_access
from app.schemas.health_monitor import (
    HealthMonitorCreate,
    HealthMonitorResponse,
    AirQualityRecordCreate,
    AirQualityRecordResponse,
    HealthReportResponse,
    AlertItem,
)
from app.services import health_monitor_service as svc

router = APIRouter(prefix="/health-monitor", tags=["智能家居健康监测"])


def _require_feature():
    """校验 health_monitor_enabled feature flag"""
    if not get_settings().health_monitor_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="健康监测功能未启用。请设置 health_monitor_enabled=true",
        )


# ── 健康监测记录 ──


@router.post("/records", response_model=HealthMonitorResponse, status_code=status.HTTP_201_CREATED)
async def record_health_data(
    data: HealthMonitorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_feature()
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)

    # 阈值检测
    alert_level, alert_message = svc.check_thresholds(data.monitor_type, data.value)
    payload = data.model_dump()
    payload["alert_level"] = alert_level
    if alert_message:
        payload["alert_message"] = alert_message

    record = await svc.create_health_record(db, payload)
    return HealthMonitorResponse.model_validate(record)


@router.get("/records/project/{project_id}", response_model=list[HealthMonitorResponse])
async def list_health_records(
    project_id: str,
    monitor_type: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_feature()
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    records = await svc.list_health_records_by_project(db, project_id, monitor_type=monitor_type, limit=limit)
    return [HealthMonitorResponse.model_validate(r) for r in records]


@router.get("/report/{project_id}", response_model=HealthReportResponse)
async def health_report(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_feature()
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    report_data = await svc.generate_health_report(db, project_id)
    return HealthReportResponse(
        project_id=report_data["project_id"],
        generated_at=report_data["generated_at"],
        summary=report_data["summary"],
        total_records=report_data["total_records"],
        alert_records=report_data["alert_records"],
        sleep_avg_score=report_data["sleep_avg_score"],
        latest_air_quality=(
            AirQualityRecordResponse.model_validate(report_data["latest_air_quality"])
            if report_data["latest_air_quality"]
            else None
        ),
        recent_alerts=[AlertItem(**a) for a in report_data["recent_alerts"]],
        recommendations=report_data["recommendations"],
    )


# ── 空气质量记录 ──


@router.post("/air-quality", response_model=AirQualityRecordResponse, status_code=status.HTTP_201_CREATED)
async def record_air_quality(
    data: AirQualityRecordCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_feature()
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)

    record = await svc.create_air_quality_record(db, data.model_dump())
    return AirQualityRecordResponse.model_validate(record)


@router.get("/air-quality/{project_id}", response_model=list[AirQualityRecordResponse])
async def list_air_quality(
    project_id: str,
    room_name: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_feature()
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    records = await svc.list_air_quality_records_by_project(db, project_id, room_name=room_name, limit=limit)
    return [AirQualityRecordResponse.model_validate(r) for r in records]


@router.get("/air-quality/{project_id}/latest", response_model=AirQualityRecordResponse)
async def latest_air_quality(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_feature()
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    record = await svc.get_latest_air_quality(db, project_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="暂无空气质量记录")
    return AirQualityRecordResponse.model_validate(record)

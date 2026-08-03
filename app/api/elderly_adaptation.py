"""F41 适老改造 API 端点（v1.5.0, PRD v3.1 F41）"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.rbac import verify_project_access
from app.services import elderly_adaptation_service

router = APIRouter(prefix="/elderly-adaptation", tags=["适老改造"])

settings = get_settings()


def _check_enabled() -> None:
    if not settings.elderly_adaptation_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该功能未启用")


class SchemeCreate(BaseModel):
    project_id: str
    name: str
    # elderly_living / semi_selfcare / nursing / family
    occupant_type: str = "elderly_living"


class SchemeUpdate(BaseModel):
    name: str | None = None
    occupant_type: str | None = None
    notes: str | None = None


class AccessibilityCheckRequest(BaseModel):
    project_id: str
    rooms: list[dict]


class SchemeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    occupant_type: str
    items: list | None = None
    accessibility_report: dict | None = None
    compliance_status: str
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@router.post("/schemes", response_model=SchemeResponse, status_code=status.HTTP_201_CREATED)
async def create_scheme(
    data: SchemeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建适老改造方案（自动生成适老条目）"""
    _check_enabled()
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    scheme = await elderly_adaptation_service.create_scheme(db, data.model_dump())
    return SchemeResponse.model_validate(scheme)


@router.get("/schemes/project/{project_id}", response_model=list[SchemeResponse])
async def list_schemes(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按项目列出适老改造方案"""
    _check_enabled()
    await verify_project_access(project_id=project_id, current_user=current_user, db=db)
    schemes = await elderly_adaptation_service.list_schemes(db, project_id)
    return [SchemeResponse.model_validate(s) for s in schemes]


@router.get("/schemes/{scheme_id}", response_model=SchemeResponse)
async def get_scheme(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """适老改造方案详情"""
    _check_enabled()
    scheme = await elderly_adaptation_service.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="适老改造方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    return SchemeResponse.model_validate(scheme)


@router.patch("/schemes/{scheme_id}", response_model=SchemeResponse)
async def update_scheme(
    scheme_id: str,
    data: SchemeUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新适老改造方案（name/occupant_type/notes）"""
    _check_enabled()
    scheme = await elderly_adaptation_service.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="适老改造方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    updated = await elderly_adaptation_service.update_scheme(
        db, scheme_id, data.model_dump(exclude_none=True)
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="适老改造方案不存在")
    return SchemeResponse.model_validate(updated)


@router.post("/schemes/{scheme_id}/validate")
async def validate_scheme(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """基于无障碍动线报告计算方案合规状态（GB 50763-2012）"""
    _check_enabled()
    scheme = await elderly_adaptation_service.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="适老改造方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    result = elderly_adaptation_service.validate_scheme(scheme)
    await db.commit()
    return result


@router.post("/check-accessibility")
async def check_accessibility(
    data: AccessibilityCheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """全屋无障碍动线检查（门宽/走廊/高差，GB 50763-2012）

    同时返回逃生通道专项检查结果（standard: HC-006）：
    入户门净宽 ≥ 800mm / 逃生通道净宽 ≥ 900mm 且高差 ≤ 15mm /
    卧室·起居室可开启逃生窗净宽 ≥ 600mm / 禁止封闭走廊。
    """
    _check_enabled()
    await verify_project_access(project_id=data.project_id, current_user=current_user, db=db)
    return elderly_adaptation_service.check_accessibility(data.rooms)


@router.delete("/schemes/{scheme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheme(
    scheme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除适老改造方案"""
    _check_enabled()
    scheme = await elderly_adaptation_service.get_scheme(db, scheme_id)
    if not scheme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="适老改造方案不存在")
    await verify_project_access(project_id=scheme.project_id, current_user=current_user, db=db)
    deleted = await elderly_adaptation_service.delete_scheme(db, scheme_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="适老改造方案不存在")

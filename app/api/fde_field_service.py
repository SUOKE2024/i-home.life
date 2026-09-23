"""FDE 现场服务记录 API（v1.17.4）

政策依据：工信厅科函〔2026〕414号 任务四——「鼓励服务商搭建前线部署工程师
（FDE）团队，扎根用户现场」。补齐缺口 G3（此前无「谁在现场、做了什么、
耗时多少、解决与否」的服务记录维度）。

端点（均需 PASETO 鉴权）：
- POST   /api/fde-field-visits
- GET    /api/fde-field-visits
- GET    /api/fde-field-visits/{visit_id}
- PATCH  /api/fde-field-visits/{visit_id}
- DELETE /api/fde-field-visits/{visit_id}

越权防护：单条操作校验 owner_id == current_user.id 或 admin（403）；
传入 project_id 时额外走 verify_project_access 项目归属校验。
诚实纪律：capability_tags 只声明实际具备的维度（不硬凑四维）；
resolved 表示现场问题是否闭环，**不构成交付验收结论**。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.fde_field_service import (
    FDE_CAPABILITY_TAGS,
    FDE_MODES,
    FDE_SERVICE_TYPES,
    FdeFieldVisit,
)
from app.models.user import User
from app.rbac import verify_project_access
from app.schemas.fde_field_service import (
    FdeFieldVisitCreate,
    FdeFieldVisitResponse,
    FdeFieldVisitUpdate,
)
from app.services import fde_field_service as svc

router = APIRouter(prefix="/fde-field-visits", tags=["FDE 现场服务记录"])

settings = get_settings()


def _require_feature() -> None:
    if not settings.fde_field_service_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FDE 现场服务记录未启用（fde_field_service_enabled=False）",
        )


async def _load_owned_visit(db: AsyncSession, visit_id: str, current_user: User) -> FdeFieldVisit:
    """加载记录并校验归属（owner 本人或平台管理员）。"""
    visit = await svc.get_visit(db, visit_id)
    if not visit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="现场服务记录不存在")
    if visit.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该现场服务记录")
    return visit


@router.get("/enums")
async def get_enums(current_user: User = Depends(get_current_user)):
    """服务类型 / 服务方式 / FDE 能力维度枚举（与政策口径对齐）。"""
    _require_feature()
    return {
        "service_types": list(FDE_SERVICE_TYPES),
        "modes": list(FDE_MODES),
        "capability_tags": list(FDE_CAPABILITY_TAGS),
        "capability_tags_note": "只声明实际具备的维度，不硬凑四维",
    }


@router.post("", response_model=FdeFieldVisitResponse, status_code=status.HTTP_201_CREATED)
async def create_visit(
    data: FdeFieldVisitCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """登记 FDE 现场服务记录。"""
    _require_feature()
    payload = data.model_dump(exclude_none=True)
    if payload.get("project_id"):
        await verify_project_access(
            project_id=payload["project_id"], current_user=current_user, db=db
        )
    payload["owner_id"] = current_user.id
    try:
        visit = await svc.create_visit(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    return FdeFieldVisitResponse.model_validate(visit)


@router.get("", response_model=list[FdeFieldVisitResponse])
async def list_visits(
    project_id: str | None = None,
    space_asset_id: str | None = None,
    service_type: str | None = None,
    mode: str | None = None,
    resolved: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出 FDE 现场服务记录（非管理员仅返回自己的记录）。"""
    _require_feature()
    owner_id = None if current_user.role == "admin" else current_user.id
    visits = await svc.list_visits(
        db, owner_id=owner_id, project_id=project_id, space_asset_id=space_asset_id,
        service_type=service_type, mode=mode, resolved=resolved, limit=limit,
    )
    return [FdeFieldVisitResponse.model_validate(v) for v in visits]


@router.get("/{visit_id}", response_model=FdeFieldVisitResponse)
async def get_visit(
    visit_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_feature()
    visit = await _load_owned_visit(db, visit_id, current_user)
    return FdeFieldVisitResponse.model_validate(visit)


@router.patch("/{visit_id}", response_model=FdeFieldVisitResponse)
async def update_visit(
    visit_id: str,
    data: FdeFieldVisitUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新现场服务记录（owner_id / id / 时间戳不可改写）。"""
    _require_feature()
    await _load_owned_visit(db, visit_id, current_user)
    payload = data.model_dump(exclude_none=True)
    if payload.get("project_id"):
        await verify_project_access(
            project_id=payload["project_id"], current_user=current_user, db=db
        )
    try:
        visit = await svc.update_visit(db, visit_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    if not visit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="现场服务记录不存在")
    return FdeFieldVisitResponse.model_validate(visit)


@router.delete("/{visit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_visit(
    visit_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_feature()
    await _load_owned_visit(db, visit_id, current_user)
    await svc.delete_visit(db, visit_id)

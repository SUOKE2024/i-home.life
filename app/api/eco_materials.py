"""F44 环保材料库标签 API 端点"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.eco_material import MaterialEcoCert
from app.models.user import User
from app.services import eco_material_service

router = APIRouter(prefix="/eco-materials", tags=["环保材料标签"])


class EcoCertCreate(BaseModel):
    """分配环保认证标签请求"""
    material_id: str
    eco_grade: str
    certification: str = "无认证"
    source: str = "third_party"
    henf_grade: str | None = None  # F50 HENF 等级预埋（HENF/ENF/E0/E1）


class ValidateRequest(BaseModel):
    """环保合规校验请求"""
    material_ids: list[str]


class BoardTraceCreate(BaseModel):
    """F50 一板一码溯源创建请求"""
    board_code: str
    material_id: str
    batch_no: str = ""
    origin: str = ""
    vendor: str = ""
    produced_at: str | None = None
    logistics: dict | None = None
    henf_grade: str | None = None


def _check_eco_enabled() -> None:
    """校验 F44 feature flag"""
    settings = get_settings()
    if not settings.eco_material_label_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该功能未启用")


def _cert_dict(cert: MaterialEcoCert) -> dict:
    """环保认证标签序列化"""
    return {
        "id": cert.id,
        "material_id": cert.material_id,
        "eco_grade": cert.eco_grade,
        "henf_grade": cert.henf_grade,  # F50 HENF 等级预埋
        "certification": cert.certification,
        "source": cert.source,
        "created_at": cert.created_at,
    }


@router.post(
    "/certs",
    status_code=status.HTTP_201_CREATED,
    summary="分配环保认证标签",
    description="为材料分配 ENF/E0/E1 环保等级与认证，已存在则更新（返回 200）。",
)
async def assign_cert(
    data: EcoCertCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为材料分配环保认证标签（ENF/E0/E1）"""
    _check_eco_enabled()
    if data.eco_grade not in eco_material_service.ECO_GRADES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="环保等级不合法，可选: HENF/ENF/E0/E1",
        )
    if data.henf_grade and data.henf_grade not in eco_material_service.ECO_GRADES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="HENF 等级不合法，可选: HENF/ENF/E0/E1",
        )
    try:
        cert, created = await eco_material_service.assign_cert(
            db,
            material_id=data.material_id,
            eco_grade=data.eco_grade,
            certification=data.certification,
            source=data.source,
            henf_grade=data.henf_grade,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if not created:
        response.status_code = status.HTTP_200_OK
    return _cert_dict(cert)


@router.get("/certs/{material_id}", summary="材料环保认证详情")
async def get_cert(
    material_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询材料环保认证（无则 404）"""
    _check_eco_enabled()
    cert = await eco_material_service.get_cert(db, material_id)
    if not cert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该材料暂无环保认证")
    return _cert_dict(cert)


@router.get("/materials", summary="按环保等级筛选材料")
async def list_materials(
    grade: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按环保等级筛选材料（grade 缺省返回全部）"""
    _check_eco_enabled()
    if grade:
        return await eco_material_service.list_by_grade(db, grade)
    return await eco_material_service.list_all(db)


@router.get("/grades", summary="环保等级统计")
async def list_grades(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """各环保等级数量统计"""
    _check_eco_enabled()
    return await eco_material_service.list_grades(db)


@router.post("/validate", summary="环保合规校验报告")
async def validate_compliance(
    data: ValidateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """逐材料环保合规校验（对标 HC-003 环保等级硬约束）"""
    _check_eco_enabled()
    try:
        return await eco_material_service.validate_compliance(db, data.material_ids)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/materials/{material_id}/alternatives", summary="环保同级/更优替代推荐")
async def recommend_alternatives(
    material_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """推荐同分类且环保等级 >= 当前等级（ENF > E0 > E1）的替代材料"""
    _check_eco_enabled()
    try:
        return await eco_material_service.recommend_alternatives(db, material_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ── F50 一板一码溯源 ──


@router.post(
    "/boards",
    status_code=status.HTTP_201_CREATED,
    summary="创建一板一码溯源记录",
    description="为板材创建产地/批次/物流/环保等级全链路溯源记录（一板一码）。",
)
async def create_board(
    data: BoardTraceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建一板一码溯源记录（F50）"""
    _check_eco_enabled()
    try:
        board = await eco_material_service.create_board_trace(
            db,
            board_code=data.board_code,
            material_id=data.material_id,
            batch_no=data.batch_no,
            origin=data.origin,
            vendor=data.vendor,
            produced_at=data.produced_at,
            logistics=data.logistics,
            henf_grade=data.henf_grade,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return await eco_material_service.get_board_trace(db, board.board_code)


@router.get("/boards/{board_code}", summary="按一板一码查询溯源")
async def get_board(
    board_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按一板一码查询溯源记录（F50，无则 404）"""
    _check_eco_enabled()
    trace = await eco_material_service.get_board_trace(db, board_code)
    if not trace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="板材溯源记录不存在")
    return trace


@router.get("/boards", summary="列出板材溯源记录")
async def list_boards(
    material_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出板材溯源记录（可选按材料筛选）"""
    _check_eco_enabled()
    return await eco_material_service.list_boards(db, material_id)

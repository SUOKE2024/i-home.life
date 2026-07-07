from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import io

from openpyxl import Workbook

from app.database import get_db
from app.models.user import User
from app.models.material import BOMItem, Material
from app.schemas.material import (
    MaterialCategoryCreate,
    MaterialCategoryResponse,
    MaterialCreate,
    MaterialResponse,
    BOMItemCreate,
    BOMItemResponse,
)
from app.auth import get_current_user
from app.services import material_service
from app.ws import ws_manager

router = APIRouter(prefix="/materials", tags=["物料"])


@router.get("/categories", response_model=list[MaterialCategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    categories = await material_service.get_categories(db)
    return [MaterialCategoryResponse.model_validate(c) for c in categories]


@router.post("/categories", response_model=MaterialCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: MaterialCategoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    category = await material_service.create_category(db, data.model_dump())
    return MaterialCategoryResponse.model_validate(category)


@router.get("", response_model=list[MaterialResponse])
async def list_materials(
    category_id: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    materials = await material_service.get_materials(db, category_id, skip, limit)
    return [MaterialResponse.model_validate(m) for m in materials]


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(material_id: str, db: AsyncSession = Depends(get_db)):
    material = await material_service.get_material_by_id(db, material_id)
    if not material:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物料不存在")
    return MaterialResponse.model_validate(material)


@router.post("", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    data: MaterialCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    material = await material_service.create_material(db, data.model_dump())
    return MaterialResponse.model_validate(material)


@router.post("/bom", response_model=BOMItemResponse, status_code=status.HTTP_201_CREATED)
async def add_bom_item(
    data: BOMItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bom_item = await material_service.add_bom_item(db, data.model_dump())
    from sqlalchemy import select as sa_select

    result = await db.execute(
        sa_select(BOMItem)
        .where(BOMItem.id == bom_item.id)
        .options(selectinload(BOMItem.material).selectinload(Material.category))
    )
    bom_item = result.scalar_one()
    resp = BOMItemResponse.model_validate(bom_item)
    await ws_manager.broadcast_to_project(bom_item.project_id, "bom.item_added", resp.model_dump())
    return resp


@router.get("/bom/{project_id}", response_model=list[BOMItemResponse])
async def get_project_bom(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bom_items = await material_service.get_project_bom(db, project_id)
    return [BOMItemResponse.model_validate(item) for item in bom_items]


@router.get("/bom/{project_id}/export")
async def export_bom_excel(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    bom_items = await material_service.get_project_bom(db, project_id)
    wb = Workbook()
    ws = wb.active
    ws.title = "BOM 物料清单"

    headers = ["序号", "物料名称", "SKU", "品牌", "规格", "分类", "数量", "单位", "单价(元)", "总价(元)", "备注"]
    ws.append(headers)

    for i, item in enumerate(bom_items, 1):
        mat = item.material
        ws.append([
            i,
            mat.name if mat else "-",
            mat.sku if mat else "-",
            mat.brand if mat else "-",
            mat.spec if mat else "-",
            mat.category.name if mat and mat.category else "-",
            item.quantity,
            mat.unit if mat else "-",
            item.unit_price,
            item.total_price,
            item.note or "",
        ])

    total_row = len(bom_items) + 2
    ws.cell(row=total_row, column=9, value="合计：")
    ws.cell(row=total_row, column=10, value=sum(item.total_price for item in bom_items))

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=bom-{project_id[:8]}.xlsx"},
    )


@router.delete("/bom/{bom_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bom_item(
    bom_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select as sa_select

    result = await db.execute(sa_select(BOMItem).where(BOMItem.id == bom_id))
    bom_item = result.scalar_one_or_none()
    if not bom_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BOM项不存在")
    project_id = bom_item.project_id
    deleted = await material_service.delete_bom_item(db, bom_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BOM项不存在")
    await ws_manager.broadcast_to_project(project_id, "bom.item_deleted", {"id": bom_id})

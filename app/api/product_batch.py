"""批量产品 API — 文件上传批量创建 + AI 文案进度查询"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models.user import User
from app.models.procurement import Supplier
from app.auth import get_current_user
from app.schemas.product_batch import (
    BatchUploadResponse,
    AIJobStatus,
)
from app.services import product_batch_service
from app.services import ai_copy_service

router = APIRouter(prefix="/products/batch", tags=["批量产品"])


@router.post("/upload", response_model=BatchUploadResponse)
async def upload_batch_products(
    file: UploadFile = File(...),
    ai_assisted: bool = Form(default=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传 Excel/CSV 文件批量创建产品"""
    # 权限校验
    if current_user.role != "supplier" and not current_user.is_verified:
        raise HTTPException(status_code=403, detail="仅已认证的供应商可发布产品")

    # 获取供应商信息
    stmt = select(Supplier).where(Supplier.phone == current_user.phone)
    result = await db.execute(stmt)
    supplier = result.scalar_one_or_none()

    # 校验文件格式
    filename = file.filename or ""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")

    if filename.lower().endswith(".xlsx"):
        products = await product_batch_service.parse_excel_file(content)
    elif filename.lower().endswith(".csv"):
        products = await product_batch_service.parse_csv_file(content)
    elif filename.lower().endswith(".xls"):
        raise HTTPException(status_code=400, detail="不支持 .xls 格式，请使用 .xlsx 格式")
    else:
        raise HTTPException(
            status_code=400,
            detail="仅支持 .xlsx 和 .csv 格式的文件",
        )

    if not products:
        raise HTTPException(status_code=400, detail="文件中未解析到有效产品数据")

    if len(products) > 500:
        raise HTTPException(status_code=400, detail="单次最多支持 500 个产品")

    # 批量创建
    response = await product_batch_service.batch_create_products(
        db=db,
        current_user=current_user,
        supplier=supplier,
        products=products,
    )

    # 异步触发 AI 文案生成
    if ai_assisted and response.success_count > 0:
        ai_product_ids = [
            r.product_id for r in response.results if r.success and r.product_id
        ]
        if ai_product_ids:
            await ai_copy_service.start_batch_ai_copy(
                batch_id=response.batch_id,
                product_ids=ai_product_ids,
                db_session_factory=async_session,
            )
            response.ai_jobs_pending = len(ai_product_ids)

    return response


@router.get("/template")
async def download_template(
    current_user: User = Depends(get_current_user),
):
    """下载产品批量导入 Excel 模板"""
    content = product_batch_service.generate_template_excel()
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=product_batch_template.xlsx",
            "Content-Length": str(len(content)),
        },
    )


@router.get("/ai-jobs/{batch_id}", response_model=AIJobStatus)
async def get_ai_job_status(
    batch_id: str,
    current_user: User = Depends(get_current_user),
):
    """查询批量 AI 文案生成任务进度"""
    job = ai_copy_service.get_job_status(batch_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return AIJobStatus(
        job_id=batch_id,
        batch_id=batch_id,
        total=job["total"],
        completed=job["completed"],
        failed=job["failed"],
        in_progress=job["in_progress"],
        created_at=job["created_at"],
        updated_at=job.get("updated_at"),
    )

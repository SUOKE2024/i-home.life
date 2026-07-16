"""摄像头扫描 API — 拍照识别产品 + 确认创建"""

import uuid
import json

from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.product import Product
from app.models.procurement import Supplier
from app.auth import get_current_user
from app.services import image_recognition_service
from app.schemas.product import ProductResponse

router = APIRouter(prefix="/products/camera", tags=["拍照上架"])


@router.post("/scan")
async def scan_product(
    image: UploadFile = File(...),
    context: str = Form(default=""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """拍照识别产品 — 返回识别结果供用户确认"""
    if current_user.role != "supplier" and not current_user.is_verified:
        raise HTTPException(status_code=403, detail="仅已认证的供应商可使用此功能")

    # 校验图片
    content_type = image.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="仅支持图片文件")

    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail="图片为空")

    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片不能超过 10MB")

    # 调用多模态 AI 识别
    result = await image_recognition_service.recognize_product_from_image(content, context)

    # 预处理缩略图用于前端预览
    try:
        thumb = image_recognition_service.preprocess_image(content, max_size=256, quality=60)
        thumb_b64 = image_recognition_service.image_to_base64(thumb)
    except Exception:
        thumb_b64 = ""

    return {
        "name": result.get("name", ""),
        "category_cn": result.get("category_cn", "其他"),
        "category_code": result.get("category_code", "other"),
        "material": result.get("material", ""),
        "color": result.get("color", ""),
        "style": result.get("style", ""),
        "confidence": round(result.get("confidence", 0), 2),
        "tags": result.get("tags", []),
        "suggested_unit": result.get("suggested_unit", "个"),
        "suggested_price": result.get("suggested_price"),
        "origin": result.get("origin", ""),
        "fallback": result.get("fallback", False),
        "thumbnail": thumb_b64,
    }


@router.post("/confirm", response_model=ProductResponse)
async def confirm_scan_product(
    name: str = Form(min_length=1, max_length=200),
    category: str = Form(default="other"),
    description: str = Form(default=""),
    price_min: float | None = Form(None),
    price_max: float | None = Form(None),
    unit: str = Form(default="个"),
    tags: str = Form(default=""),
    stock_status: str = Form(default="in_stock"),
    cover_image_data: str | None = Form(None),
    ai_assisted: bool = Form(default=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """确认拍照识别的产品并创建"""
    if current_user.role != "supplier" and not current_user.is_verified:
        raise HTTPException(status_code=403, detail="仅已认证的供应商可发布产品")

    # 获取供应商
    stmt = select(Supplier).where(Supplier.phone == current_user.phone)
    result = await db.execute(stmt)
    supplier = result.scalar_one_or_none()

    # 处理标签
    tags_list = None
    if tags:
        tags_list = [t.strip() for t in tags.replace("，", ",").split(",") if t.strip()]

    # 处理封面图（base64 → 存为 URL 或忽略）
    cover_url = None
    if cover_image_data and cover_image_data.startswith("data:image"):
        # 当前阶段先记录为占位 URL，后续 OSS 集成时替换
        cover_url = f"camera://{current_user.id}/{uuid.uuid4().hex[:8]}.webp"

    product = Product(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        supplier_id=supplier.id if supplier else "",
        name=name,
        category=category,
        description=description or None,
        price_min=price_min,
        price_max=price_max,
        unit=unit,
        cover_image=cover_url,
        images=None,
        tags=json.dumps(tags_list, ensure_ascii=False) if tags_list else None,
        specs=None,
        stock_status=stock_status,
        status="draft",
        ai_assisted=ai_assisted,
    )

    db.add(product)

    # AI 辅助文案生成
    if ai_assisted:
        from app.services.ai_copy_service import _build_marketing_prompt, _parse_ai_response, _generate_fallback_description
        from app.agents.procurement import ProcurementAgent
        try:
            prompt = _build_marketing_prompt(product)
            agent = ProcurementAgent()
            try:
                reply = await agent.think(prompt)
                desc, ai_tags = _parse_ai_response(reply)
            finally:
                await agent.close()
            if desc:
                product.ai_description = desc
                if not product.description:
                    product.description = desc
            if ai_tags:
                existing = tags_list or []
                merged = list(dict.fromkeys(existing + ai_tags))
                product.tags = json.dumps(merged, ensure_ascii=False)
            product.ai_generated = True
        except Exception:
            product.ai_description = _generate_fallback_description(product)
            product.ai_generated = True

    await db.commit()
    await db.refresh(product)

    return _product_to_response(product)


def _product_to_response(p: Product) -> ProductResponse:
    images = json.loads(p.images) if p.images else None
    tags = json.loads(p.tags) if p.tags else None
    specs = json.loads(p.specs) if p.specs else None
    return ProductResponse(
        id=p.id, user_id=p.user_id, supplier_id=p.supplier_id,
        name=p.name, category=p.category, description=p.description,
        price_min=p.price_min, price_max=p.price_max, unit=p.unit,
        images=images, cover_image=p.cover_image, tags=tags, specs=specs,
        stock_status=p.stock_status, status=p.status,
        ai_generated=p.ai_generated, ai_description=p.ai_description,
        created_at=p.created_at, updated_at=p.updated_at,
    )

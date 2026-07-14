"""产品/服务 API — 供应商发布产品、AI 辅助内容发布"""
import json

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.product import Product
from app.models.procurement import Supplier
from app.auth import get_current_user
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ProductCardData
from app.agents.procurement import ProcurementAgent
from app.ws import ws_manager

router = APIRouter(prefix="/products", tags=["产品/服务管理"])


def _product_to_response(p: Product) -> ProductResponse:
    images = json.loads(p.images) if p.images else None
    tags = json.loads(p.tags) if p.tags else None
    specs = json.loads(p.specs) if p.specs else None
    return ProductResponse(
        id=p.id,
        user_id=p.user_id,
        supplier_id=p.supplier_id,
        name=p.name,
        category=p.category,
        description=p.description,
        price_min=p.price_min,
        price_max=p.price_max,
        unit=p.unit,
        images=images,
        cover_image=p.cover_image,
        tags=tags,
        specs=specs,
        stock_status=p.stock_status,
        status=p.status,
        ai_generated=p.ai_generated,
        ai_description=p.ai_description,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.post("", response_model=ProductResponse)
async def create_product(
    data: ProductCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建产品（支持 AI 辅助生成文案）"""
    if current_user.role != "supplier" and not current_user.is_verified:
        raise HTTPException(status_code=403, detail="仅已认证的供应商可发布产品")

    # 获取供应商信息
    stmt = select(Supplier).where(Supplier.phone == current_user.phone)
    result = await db.execute(stmt)
    supplier = result.scalar_one_or_none()

    product = Product(
        user_id=current_user.id,
        supplier_id=supplier.id if supplier else "",
        name=data.name,
        category=data.category,
        description=data.description,
        price_min=data.price_min,
        price_max=data.price_max,
        unit=data.unit,
        images=json.dumps(data.images, ensure_ascii=False) if data.images else None,
        cover_image=data.cover_image,
        tags=json.dumps(data.tags, ensure_ascii=False) if data.tags else None,
        specs=json.dumps(data.specs, ensure_ascii=False) if data.specs else None,
        stock_status=data.stock_status,
        ai_assisted=data.ai_assisted,
    )

    # AI 辅助生成文案
    if data.ai_assisted:
        p_agent = ProcurementAgent()
        try:
            prompt = (
                f"请为以下产品生成吸引人的营销文案：\n"
                f"产品名称：{data.name}\n"
                f"类别：{data.category}\n"
                f"价格区间：{data.price_min}-{data.price_max} {data.unit}\n"
                f"标签：{', '.join(data.tags or [])}\n"
                f"简要描述：{data.description or ''}\n\n"
                f"请生成50-150字的专业产品描述，突出卖点，并推荐3-5个标签。"
                f"用JSON格式回复：{{\"description\": \"...\", \"tags\": [\"...\"]}}"
            )
            ai_reply = await p_agent.think(prompt)
            # 尝试解析 AI 生成的 JSON
            if "```json" in ai_reply:
                ai_reply = ai_reply.split("```json")[1].split("```")[0].strip()
            elif "```" in ai_reply:
                ai_reply = ai_reply.split("```")[1].split("```")[0].strip()
            ai_data = json.loads(ai_reply)
            if ai_data.get("description") and not product.description:
                product.description = ai_data["description"]
            product.ai_description = ai_data.get("description", "")
            if ai_data.get("tags"):
                product.tags = json.dumps(ai_data["tags"], ensure_ascii=False)
            product.ai_generated = True
        except Exception:
            pass  # AI 生成失败不影响产品创建
        finally:
            await p_agent.close()

    db.add(product)
    await db.commit()
    await db.refresh(product)
    return _product_to_response(product)


@router.get("", response_model=list[ProductResponse])
async def list_products(
    category: str | None = Query(None),
    status: str = Query("published"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """查询产品列表"""
    conditions = []
    if category:
        conditions.append(Product.category == category)
    if status:
        conditions.append(Product.status == status)

    stmt = (
        select(Product)
        .where(*conditions)
        .order_by(Product.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    products = result.scalars().all()
    return [_product_to_response(p) for p in products]


@router.get("/mine", response_model=list[ProductResponse])
async def list_my_products(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """查询当前供应商的产品"""
    stmt = (
        select(Product)
        .where(Product.user_id == current_user.id)
        .order_by(Product.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    products = result.scalars().all()
    return [_product_to_response(p) for p in products]


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取产品详情"""
    stmt = select(Product).where(Product.id == product_id)
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    return _product_to_response(product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    data: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新产品"""
    stmt = select(Product).where(Product.id == product_id, Product.user_id == current_user.id)
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在或无权限")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key in ("images", "tags"):
            setattr(product, key, json.dumps(value, ensure_ascii=False) if value else None)
        elif key == "specs":
            setattr(product, key, json.dumps(value, ensure_ascii=False) if value else None)
        else:
            setattr(product, key, value)

    await db.commit()
    await db.refresh(product)
    return _product_to_response(product)


@router.post("/{product_id}/publish", response_model=ProductResponse)
async def publish_product(
    product_id: str,
    project_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """发布产品到市场，并通过 WebSocket 推送到项目聊天室"""
    stmt = select(Product).where(Product.id == product_id, Product.user_id == current_user.id)
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在或无权限")

    product.status = "published"
    await db.commit()
    await db.refresh(product)

    # 通过 WebSocket 推送产品发布事件
    if project_id:
        tags = json.loads(product.tags) if product.tags else []
        price_range = ""
        if product.price_min and product.price_max:
            price_range = f"¥{product.price_min:.0f}-{product.price_max:.0f}/{product.unit}"
        elif product.price_min:
            price_range = f"¥{product.price_min:.0f}/{product.unit}起"

        await ws_manager.broadcast_to_project(project_id, "product.published", {
            "product_id": product.id,
            "name": product.name,
            "category": product.category,
            "description": product.description,
            "price_range": price_range,
            "cover_image": product.cover_image,
            "tags": tags,
            "supplier_name": current_user.name,
        })

    return _product_to_response(product)

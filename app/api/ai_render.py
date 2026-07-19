"""AI 渲染 API — 2D / 3D / 照片重布置三种渲染能力端点

PRD §7.x: AI 渲染端点
- POST /api/ai-render/2d        2D 效果图生成（布局 JSON + 风格 → SD prompt + 占位图）
- POST /api/ai-render/3d        3D 场景生成（户型 + 风格 → 多视角 prompt + 重建参数）
- POST /api/ai-render/restage   照片重布置（UploadFile + 模式 → 重布置结果）
- GET  /api/ai-render/capabilities  返回支持的渲染模式与风格列表

所有端点均需 PASETO 认证（get_current_user），
若请求携带 project_id 则额外校验项目归属（verify_project_access）。
"""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.rbac import verify_project_access
from app.services.ai_render_service import (
    SUPPORTED_RESTAGE_MODES,
    SUPPORTED_STYLES,
    ai_render_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-render", tags=["AI 渲染"])


# ── 请求模型 ──────────────────────────────────────────────


class Render2DRequest(BaseModel):
    """2D 渲染请求"""
    layout_json: dict = Field(..., description="布局 JSON（含 rooms / walls 等）")
    style: str = Field("modern", description="装修风格")
    project_id: str | None = Field(None, description="项目 ID（可选，用于归属校验）")


class Render3DRequest(BaseModel):
    """3D 渲染请求"""
    floorplan: dict = Field(..., description="户型数据")
    style: str = Field("modern", description="装修风格")
    project_id: str | None = Field(None, description="项目 ID（可选）")


class RestageRequest(BaseModel):
    """照片重布置请求（photo 通过 UploadFile 单独传，不在此 BaseModel 中）

    mode / style / project_id 通过 multipart form 字段提交
    """
    mode: str = Field("inpainting", description="重布置模式: inpainting | full_regen")
    style: str = Field("modern", description="装修风格")
    project_id: str | None = Field(None, description="项目 ID（可选）")


# ── 端点 ──────────────────────────────────────────────────


@router.post("/2d")
async def render_2d(
    body: Render2DRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """2D 效果图生成 — 根据布局 JSON + 风格生成 SD prompt + 自然语言描述 + 占位图

    若携带 project_id，会先校验项目归属权（防 IDOR）。
    """
    # 可选项目归属校验：仅当显式传入 project_id 时执行
    if body.project_id:
        await verify_project_access(body.project_id, current_user, db)

    return await ai_render_service.render_2d(
        layout_json=body.layout_json,
        style=body.style,
        user_id=current_user.id,
        db=db,
    )


@router.post("/3d")
async def render_3d(
    body: Render3DRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """3D 场景生成 — 户型 + 风格 → SpatialGen 多视角 prompt + 高斯重建参数

    若携带 project_id，会先校验项目归属权（防 IDOR）。
    """
    if body.project_id:
        await verify_project_access(body.project_id, current_user, db)

    return await ai_render_service.render_3d(
        floorplan=body.floorplan,
        style=body.style,
        user_id=current_user.id,
        db=db,
    )


@router.post("/restage")
async def restage_photo(
    mode: str = Form("inpainting", description="重布置模式: inpainting | full_regen"),
    style: str = Form("modern", description="装修风格"),
    project_id: str | None = Form(None, description="项目 ID（可选）"),
    photo: UploadFile = File(..., description="待重布置的照片"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """照片重布置 — 上传照片 + 模式 → 重布置结果

    mode:
    - inpainting: 局部重绘（保留主体结构，替换家具/装饰）
    - full_regen: 完全重生（基于照片整体重新生成）

    若携带 project_id，会先校验项目归属权（防 IDOR）。
    """
    # 校验 mode 取值
    if mode not in SUPPORTED_RESTAGE_MODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"无效的 mode: {mode}，支持: {', '.join(SUPPORTED_RESTAGE_MODES)}",
        )

    # 可选项目归属校验
    if project_id:
        await verify_project_access(project_id, current_user, db)

    # 读取照片内容
    photo_data = await photo.read()
    if not photo_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="照片内容为空",
        )

    return await ai_render_service.restage_photo(
        photo_data=photo_data,
        mode=mode,
        style=style,
        user_id=current_user.id,
        db=db,
    )


@router.get("/capabilities")
async def get_capabilities(
    current_user: User = Depends(get_current_user),
):
    """返回支持的渲染模式与风格列表

    - styles: 推荐风格列表（style 字段允许自由文本，列表仅供参考）
    - restage_modes: 照片重布置模式（必须取自列表）
    - render_types: 渲染类型
    """
    return {
        "styles": SUPPORTED_STYLES,
        "restage_modes": SUPPORTED_RESTAGE_MODES,
        "render_types": ["2d", "3d", "restage"],
        "note": "style 字段允许自由文本，列表仅为推荐项；mode 字段必须取自 restage_modes",
    }

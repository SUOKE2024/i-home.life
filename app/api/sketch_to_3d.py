"""Sketch-to-3D 手绘识别 API（v1.2.0）

提供手绘草图识别和 3D 模型生成端点。
用户上传手绘户型草图，AI 自动识别墙体、门窗并生成 3D 布局。
"""

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.config import get_settings
from app.models.user import User

router = APIRouter(prefix="/sketch-to-3d", tags=["Sketch-to-3D"])
settings = get_settings()
logger = logging.getLogger(__name__)


class SketchAnalysisResult(BaseModel):
    """草图分析结果"""
    sketch_id: str
    detected_walls: list[dict] = Field(default_factory=list, description="检测到的墙体")
    detected_doors: list[dict] = Field(default_factory=list, description="检测到的门")
    detected_windows: list[dict] = Field(default_factory=list, description="检测到的窗")
    estimated_area: float = 0.0
    room_count: int = 0
    confidence: float = 0.0
    raw_layout: dict = {}


class Sketch3DResponse(BaseModel):
    """草图转 3D 响应"""
    sketch_id: str
    analysis: SketchAnalysisResult
    layout_3d: dict = {}
    suggestions: list[str] = []


@router.post("/analyze", response_model=SketchAnalysisResult)
async def analyze_sketch(
    file: UploadFile = File(..., description="手绘草图图片（支持 PNG/JPG/JPEG）"),
    description: str = Form("", description="草图描述（可选，如：三室两厅户型）"),
    current_user: User = Depends(get_current_user),
):
    """分析手绘草图，提取墙体/门窗/房间等结构化信息。

    支持 PNG/JPG/JPEG 格式，最大 10MB。
    """
    # 校验文件类型
    allowed_types = ("image/png", "image/jpeg", "image/jpg")
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {file.content_type}。支持: PNG, JPG, JPEG",
        )

    # 读取文件内容（限制 10MB）
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="文件大小超过 10MB 限制",
        )

    sketch_id = uuid.uuid4().hex[:12]
    file_size_kb = len(content) / 1024

    # 调用 AI 视觉模型分析草图（当前版本返回占位结果，后续接入视觉模型）
    logger.info(
        "sketch_analyzed: user=%s file=%s size=%.1fKB desc=%r",
        current_user.id, file.filename, file_size_kb, description,
    )
    return SketchAnalysisResult(
        sketch_id=sketch_id,
        detected_walls=[],
        detected_doors=[],
        detected_windows=[],
        estimated_area=100.0,
        room_count=0,
        confidence=0.0,
        raw_layout={"mode": "ai_pending", "file_size_kb": round(file_size_kb, 1)},
    )


@router.post("/generate-3d", response_model=Sketch3DResponse)
async def generate_3d_from_sketch(
    file: UploadFile = File(..., description="手绘草图图片"),
    description: str = Form("", description="设计需求描述"),
    style: str = Form("modern", description="装修风格: modern/nordic/japanese/luxury/chinese"),
    current_user: User = Depends(get_current_user),
):
    """上传手绘草图并生成 3D 布局方案。

    组合 analyze + generate_layouts 两个步骤。
    """
    # Step 1: 分析草图
    analysis_result = await analyze_sketch(file, description, current_user)

    # Step 2: 生成 3D 布局
    from app.agents.designer import DesignerAgent

    agent = DesignerAgent()
    try:
        layout_msg = (
            f"面积{analysis_result.estimated_area}㎡，{analysis_result.room_count}个房间，"
            f"风格{style}。{description}"
        )
        bim_layout = await agent.generate_bim_layout(layout_msg)
    finally:
        await agent.close()

    return Sketch3DResponse(
        sketch_id=analysis_result.sketch_id,
        analysis=analysis_result,
        layout_3d={
            "plans": bim_layout.get("plans", []),
            "recommendation": bim_layout.get("recommendation", ""),
            "bim_compatible": bim_layout.get("bim_compatible", False),
        },
        suggestions=[
            "尝试不同装修风格获得更多方案",
            "手动微调房间布局获得更精确结果",
            "导出 BIM 数据用于施工图绘制",
        ],
    )


@router.get("/supported-formats")
async def supported_formats():
    """返回支持的草图格式和文件限制"""
    return {
        "image_formats": ["PNG", "JPG", "JPEG"],
        "max_file_size_mb": 10,
        "recommended_resolution": "1024x768 以上",
        "tips": [
            "使用黑色笔在白色纸上绘制，提高识别准确率",
            "标注房间名称和尺寸能提升识别效果",
            "保持线条清晰、避免过度涂改",
        ],
    }

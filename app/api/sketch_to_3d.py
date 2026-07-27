"""Sketch-to-3D 手绘识别 API（v1.2.0）

提供手绘草图识别和 3D 模型生成端点。
用户上传手绘户型草图，AI 自动识别墙体、门窗并生成 3D 布局。
"""

import base64
import json
import logging
import uuid

import httpx
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

    # ── Feature flag：未启用视觉识别时返回占位结果 ──
    if not settings.sketch_to_3d_vision_enabled:
        logger.info(
            "sketch_analyzed (feature_disabled): user=%s file=%s size=%.1fKB desc=%r",
            current_user.id, file.filename, file_size_kb, description,
        )
        return SketchAnalysisResult(
            sketch_id=sketch_id,
            confidence=0.0,
            raw_layout={"mode": "feature_disabled", "file_size_kb": round(file_size_kb, 1)},
        )

    # ── 按优先级选择视觉模型：DeepSeek → GLM → Qwen ──
    api_key = None
    api_base = None
    model = None
    provider = None

    if settings.deepseek_api_key:
        api_key = settings.deepseek_api_key
        api_base = settings.deepseek_api_base
        model = settings.deepseek_model
        provider = "deepseek"
    elif settings.glm_api_key:
        api_key = settings.glm_api_key
        api_base = settings.glm_api_base
        model = settings.glm_model
        provider = "glm"
    elif settings.qwen_api_key:
        api_key = settings.qwen_api_key
        api_base = settings.qwen_api_base
        model = settings.qwen_model
        provider = "qwen"

    if not api_key:
        logger.warning(
            "sketch_analyzed (no_vision_model): user=%s file=%s size=%.1fKB",
            current_user.id, file.filename, file_size_kb,
        )
        return SketchAnalysisResult(
            sketch_id=sketch_id,
            confidence=0.0,
            raw_layout={"mode": "no_vision_model", "file_size_kb": round(file_size_kb, 1)},
        )

    # ── 图片转 Base64 ──
    image_b64 = base64.b64encode(content).decode("utf-8")
    mime_type = file.content_type or "image/png"

    # ── 构建视觉分析 prompt ──
    prompt = _build_vision_prompt(description)

    # ── 调用视觉模型 ──
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{image_b64}",
                                    },
                                },
                            ],
                        }
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            data = response.json()
            raw_content = data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        logger.error(
            "vision_model_http_error: provider=%s status=%d body=%s",
            provider, e.response.status_code, e.response.text[:500],
        )
        return SketchAnalysisResult(
            sketch_id=sketch_id,
            confidence=0.0,
            raw_layout={
                "mode": "vision_call_failed",
                "error": f"HTTP {e.response.status_code}",
                "file_size_kb": round(file_size_kb, 1),
            },
        )
    except Exception as e:
        logger.error("vision_model_call_failed: provider=%s error=%s", provider, e)
        return SketchAnalysisResult(
            sketch_id=sketch_id,
            confidence=0.0,
            raw_layout={
                "mode": "vision_call_failed",
                "error": str(e),
                "file_size_kb": round(file_size_kb, 1),
            },
        )

    # ── 解析 LLM 返回的 JSON ──
    try:
        parsed = _parse_vision_response(raw_content)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(
            "vision_response_parse_error: provider=%s error=%s raw=%s",
            provider, e, raw_content[:500],
        )
        return SketchAnalysisResult(
            sketch_id=sketch_id,
            confidence=0.0,
            raw_layout={
                "mode": "parse_error",
                "error": str(e),
                "raw_response": raw_content[:500],
                "file_size_kb": round(file_size_kb, 1),
            },
        )

    logger.info(
        "sketch_analyzed: user=%s file=%s size=%.1fKB provider=%s model=%s confidence=%.2f rooms=%d",
        current_user.id, file.filename, file_size_kb, provider, model,
        parsed.get("confidence", 0), parsed.get("room_count", 0),
    )

    return SketchAnalysisResult(
        sketch_id=sketch_id,
        detected_walls=parsed.get("detected_walls", []),
        detected_doors=parsed.get("detected_doors", []),
        detected_windows=parsed.get("detected_windows", []),
        estimated_area=parsed.get("estimated_area", 0.0),
        room_count=parsed.get("room_count", 0),
        confidence=parsed.get("confidence", 0.0),
        raw_layout={
            "mode": "vision_analyzed",
            "provider": provider,
            "model": model,
            "file_size_kb": round(file_size_kb, 1),
        },
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


def _build_vision_prompt(description: str) -> str:
    """构建视觉模型分析 prompt"""
    desc_part = f"用户描述：{description}" if description else "无额外描述"
    return f"""你是一个专业的建筑户型图分析助手。请仔细分析这张手绘户型草图，提取以下结构化信息。

{desc_part}

请以 JSON 格式返回分析结果，格式如下：
```json
{{
  "detected_walls": [
    {{"id": "w1", "start": {{"x": 0, "y": 0}}, "end": {{"x": 100, "y": 0}}, "length_cm": 300, "thickness_cm": 24}}
  ],
  "detected_doors": [
    {{"id": "d1", "position": {{"x": 50, "y": 0}}, "width_cm": 90, "type": "single"}}
  ],
  "detected_windows": [
    {{"id": "win1", "position": {{"x": 30, "y": 100}}, "width_cm": 120, "height_cm": 150}}
  ],
  "estimated_area": 85.5,
  "room_count": 3,
  "confidence": 0.85
}}
```

注意事项：
- 坐标单位为相对比例（0-1000 范围），后续会映射到实际尺寸
- 墙体 thickness_cm 默认 24cm（标准承重墙），轻质隔墙 12cm
- 门 width_cm 默认 90cm，type 可选 "single" 或 "double"
- 窗 width_cm/height_cm 根据草图比例估算
- estimated_area 单位为平方米
- confidence 为识别置信度（0.0-1.0）
- 如果无法识别某个元素，返回空数组

只返回 JSON，不要包含其他文字。"""


def _parse_vision_response(content: str) -> dict:
    """解析视觉模型返回的 JSON，处理 markdown 代码块包裹"""
    text = content.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    return json.loads(text)

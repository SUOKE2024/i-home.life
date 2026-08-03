"""F47 AI 装修问答/案例搜索 API 端点（v1.5.0, PRD v3.1 F47）

端点：
- POST /api/ai-qa/search   知识库问答搜索（带引用来源，未命中诚实降级）
- GET  /api/ai-qa/faq      FAQ 话题列表（知识库 faq 域前 20 条）

所有端点需 PASETO 鉴权。
受 ``settings.ai_qa_search_enabled`` feature flag 控制（默认开启）。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.services import ai_qa_search_service

router = APIRouter(prefix="/ai-qa", tags=["AI 装修问答"])
settings = get_settings()


class AISearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="搜索关键词（不能为空）")


@router.post("/search")
async def search(
    data: AISearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI 装修问答搜索（query 为空返回 422，未命中返回 no_match 诚实降级）。"""
    if not settings.ai_qa_search_enabled:
        raise HTTPException(status_code=404, detail="该功能未启用")
    return await ai_qa_search_service.search(data.query)


@router.get("/faq")
async def faq_topics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FAQ 话题列表（知识库 faq 域前 20 条，含引用来源）。"""
    if not settings.ai_qa_search_enabled:
        raise HTTPException(status_code=404, detail="该功能未启用")
    return ai_qa_search_service.faq_topics()

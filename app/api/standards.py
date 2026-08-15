"""装修行业标准目录 API（P0 标准目录扩展）

端点（只读，需 PASETO 鉴权）：
- GET /api/standards          列出标准目录（可按 domain 过滤）

确定性、只读、零外部依赖。
"""

import logging

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.models.user import User
from app.standards.standards_catalog import get_standards, list_domains

router = APIRouter(prefix="/standards", tags=["标准目录"])
logger = logging.getLogger(__name__)


@router.get("")
async def list_standards(
    domain: str | None = Query(None, description="按领域过滤（如「环保等级」「验收」）"),
    current_user: User = Depends(get_current_user),
):
    """列出装修行业标准目录；domain 为空返回全部。"""
    standards = get_standards(domain)
    logger.info(
        "standards_listed: user=%s domain=%s count=%d",
        current_user.id, domain or "", len(standards),
    )
    return {
        "count": len(standards),
        "domains": list_domains(),
        "standards": standards,
    }

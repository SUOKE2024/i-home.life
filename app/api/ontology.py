"""家装领域本体基座 API（P0 本体/领域知识基座）

端点（只读，需 PASETO 鉴权）：
- GET /api/ontology                  列出可用本体领域
- GET /api/ontology/{domain}         加载指定领域本体
- GET /api/ontology/{domain}/alignments  开放本体对齐映射（Brick/BOT/IFC）

确定性、只读、零外部依赖，无 DB 副作用。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.models.user import User
from app.services.ontology_service import (
    get_ontology_alignments,
    list_ontologies,
    load_ontology,
)

router = APIRouter(prefix="/ontology", tags=["本体基座"])
logger = logging.getLogger(__name__)


@router.get("")
async def list_ontology_domains(current_user: User = Depends(get_current_user)):
    """列出可用本体领域（renovation/agent/material）。"""
    domains = list_ontologies()
    logger.info("ontology_domains_listed: user=%s count=%d", current_user.id, len(domains))
    return {"count": len(domains), "domains": domains}


@router.get("/{domain}")
async def get_ontology(domain: str, current_user: User = Depends(get_current_user)):
    """加载指定领域本体（未知领域 404）。"""
    data = load_ontology(domain)
    if data is None:
        raise HTTPException(status_code=404, detail=f"未知本体领域: {domain}")
    logger.info("ontology_loaded: user=%s domain=%s", current_user.id, domain)
    return data


@router.get("/{domain}/alignments")
async def get_alignments(domain: str, current_user: User = Depends(get_current_user)):
    """返回指定领域的开放本体对齐映射（Brick/BOT/IFC）。"""
    if domain not in list_ontologies():
        raise HTTPException(status_code=404, detail=f"未知本体领域: {domain}")
    alignments = get_ontology_alignments(domain)
    logger.info(
        "ontology_alignments: user=%s domain=%s count=%d",
        current_user.id, domain, len(alignments),
    )
    return {"domain": domain, "count": len(alignments), "alignments": alignments}

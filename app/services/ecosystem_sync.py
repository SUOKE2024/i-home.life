"""跨品牌供应商主数据同步（push 到索克生活 canonical registry）。

未配置 `ECOSYSTEM_SYNC_URL` / `ECOSYSTEM_SYNC_KEY` 时静默跳过；
配置后 best-effort，失败只记日志，不阻断供应商创建/更新/认证主链路。
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_PATH = "/api/v1/ecosystem/suppliers/batch-link"


def _payload(supplier: Any) -> dict:
    return {
        "items": [
            {
                "brand": "ihome",
                "local_id": str(supplier.id),
                "local_name": str(supplier.name or "")[:255],
                "partner_type": "merchant",
                "status": "active" if getattr(supplier, "is_active", True) else "suspended",
                "metadata": {
                    "category": getattr(supplier, "category", ""),
                    "is_verified": bool(getattr(supplier, "is_verified", False)),
                    "source": "i-home.procurement",
                },
            }
        ]
    }


async def push_supplier(supplier: Any) -> bool:
    settings = get_settings()
    base = (settings.ecosystem_sync_url or "").rstrip("/")
    key = settings.ecosystem_sync_key or ""
    if not base or not key:
        logger.debug("ECOSYSTEM_SYNC_URL/KEY 未配置，跳过供应商同步")
        return False
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.post(
                base + _PATH,
                json=_payload(supplier),
                headers={"X-Ecosystem-Sync-Key": key},
            )
        if resp.status_code >= 300:
            logger.warning("供应商生态同步非 2xx: status=%s", resp.status_code)
            return False
        return True
    except Exception as exc:  # noqa: BLE001 - best-effort，不阻断主链路
        logger.warning("供应商生态同步失败（不阻断主链路）: %s", exc)
        return False

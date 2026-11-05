"""跨品牌供应商主数据同步（push 到索克生活 canonical registry）。

设计取舍（2026-11-05 修订）：
- **仍是 best-effort**：同步失败不阻断供应商创建/更新/认证主链路。
- **但不再安静空转**：未配置时每条写日志会刷屏，此前用 `debug` 级别等于隐形；现在
  改为「首次 warning + /health/detail 显式暴露 + 进程内计数」，让「配了但一直失败」
  与「压根没配」在监控上可区分。上一轮生态 SSO 恒 503 就是这类「静默降级」拖了很久
  才被发现，这里不重复同样的错误。
- 只暴露配置**是否存在**与密钥指纹（sha256[:8]，与 PASETO 指纹同一约定），不暴露密钥。
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_PATH = "/api/v1/ecosystem/suppliers/batch-link"

# 进程内统计：单实例视角，重启清零；跨实例汇总交给日志/ARMS，不在这里假装全量。
_STATE: dict[str, Any] = {
    "attempts": 0,
    "ok": 0,
    "failed": 0,
    "skipped_unconfigured": 0,
    "last_ok_at": None,
    "last_fail_at": None,
    "last_error": None,
    "last_local_id": None,
}

# 未配置只告警一次，避免每次供应商写入都刷一条 warning
_warned_unconfigured = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fingerprint(value: str) -> Optional[str]:
    """密钥指纹（sha256[:8]），供运维与生活侧比对是否为同一把 key（不可逆）。"""
    if not value:
        return None
    return hashlib.sha256(value.encode()).hexdigest()[:8]


def _config() -> tuple[str, str]:
    settings = get_settings()
    base = (settings.ecosystem_sync_url or "").strip().rstrip("/")
    key = (settings.ecosystem_sync_key or "").strip()
    return base, key


def sync_status() -> dict:
    """同步通道状态，供 /health/detail 暴露。

    `status` 语义：
    - `unconfigured`：URL 或 KEY 缺一，同步被静默跳过（历史上最容易烂在这里）
    - `idle`：已配置但本次进程尚未推送过
    - `ok`：已配置且最近一次推送成功
    - `degraded`：已配置且最近一次推送失败（错误落在 last_error）
    """
    base, key = _config()
    configured = bool(base and key)
    if not configured:
        status = "unconfigured"
    elif _STATE["last_fail_at"] and (
        not _STATE["last_ok_at"] or _STATE["last_fail_at"] > _STATE["last_ok_at"]
    ):
        status = "degraded"
    elif _STATE["attempts"] == 0:
        status = "idle"
    else:
        status = "ok"
    return {
        "status": status,
        "configured": configured,
        "target": base or None,
        "key_fingerprint": _fingerprint(key),
        "attempts": _STATE["attempts"],
        "ok": _STATE["ok"],
        "failed": _STATE["failed"],
        "skipped_unconfigured": _STATE["skipped_unconfigured"],
        "last_ok_at": _STATE["last_ok_at"],
        "last_fail_at": _STATE["last_fail_at"],
        "last_error": _STATE["last_error"],
        "last_local_id": _STATE["last_local_id"],
    }


def reset_status() -> None:
    """测试用：清空统计。"""
    for k in _STATE:
        _STATE[k] = 0 if isinstance(_STATE[k], int) else None
    global _warned_unconfigured
    _warned_unconfigured = False


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
    global _warned_unconfigured
    base, key = _config()
    local_id = str(getattr(supplier, "id", "") or "")
    _STATE["last_local_id"] = local_id

    if not base or not key:
        _STATE["skipped_unconfigured"] += 1
        if not _warned_unconfigured:
            _warned_unconfigured = True
            logger.warning(
                "ECOSYSTEM_SYNC_URL/KEY 未配置，供应商变更不会同步到索克生活"
                "（已跳过 %d 次，仅首次告警；状态见 /api/health/detail 的 ecosystem_sync）",
                _STATE["skipped_unconfigured"],
            )
        return False

    _STATE["attempts"] += 1
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.post(
                base + _PATH,
                json=_payload(supplier),
                headers={"X-Ecosystem-Sync-Key": key},
            )
        status_code = getattr(resp, "status_code", 0)
        if status_code >= 300:
            _STATE["failed"] += 1
            _STATE["last_fail_at"] = _now()
            _STATE["last_error"] = f"HTTP {status_code}"
            # 403 = 通道 key 不匹配（生活侧 ECOSYSTEM_SYNC_KEY 与本端不一致），
            # 这是配置错而非瞬时故障，单独点明，避免又被当成"偶发失败"忽略。
            if status_code == 403:
                _STATE["last_error"] = "HTTP 403（同步 key 与生活侧不一致或被拒）"
                logger.error(
                    "供应商生态同步被拒 403：请比对两端 ECOSYSTEM_SYNC_KEY 指纹（本端 %s）",
                    _fingerprint(key),
                )
            else:
                logger.warning("供应商生态同步非 2xx: status=%s", status_code)
            return False
        _STATE["ok"] += 1
        _STATE["last_ok_at"] = _now()
        _STATE["last_error"] = None
        return True
    except Exception as exc:  # noqa: BLE001 - best-effort，不阻断主链路
        _STATE["failed"] += 1
        _STATE["last_fail_at"] = _now()
        _STATE["last_error"] = f"{type(exc).__name__}: {exc}"[:200]
        logger.warning("供应商生态同步失败（不阻断主链路）: %s", exc)
        return False

"""可验证支付意图服务 — v1.15.5（2026 智能体支付协议 AP2「可验证意图」对齐）

背景（2026 前沿）：
- Google 将 AP2（Agent Payments Protocol）捐赠 FIDO 联盟，「可验证意图」
  （Verifiable Intent）成为智能体支付信任层核心
- 信通院 2026 智能体十大关键词收录「智能体支付协议」
- 平台自身场景：procurement Agent 代客下单后建议付款——付款意图须由
  服务端签发可验证证明，支付侧验真后才执行（防幻觉下单/金额篡改）

落地（模块化单体最小闭环，不引入外部协议栈）：
- create_payment_intent：对采购订单签发 HMAC-SHA256 意图 token（复用 PASETO
  主密钥），payload = order_id|amount|actor_user_id|expires_at，短时有效
  （payment_intent_ttl_seconds 默认 600s）
- verify_payment_intent：结算/担保支付链校验 token 真实性 + 未过期 +
  字段逐项比对（compare_digest 防时序攻击）

诚实标注（CLAUDE.md 红线）：
- 本服务只做意图签发/验证，不触发任何真实扣款
- escrow 买家付款端点已绑定意图 token（v1.15.8，P2 落地）：携带 token 时强制
  校验真实性/未过期/order/amount/actor 比对（仅验证不扣款，支付闭环仍为 P2 规划）
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time

from app.config import get_settings

logger = logging.getLogger(__name__)


def _sign(payload: str) -> str:
    """HMAC-SHA256 签名（复用 PASETO 主密钥，与微信扫码 state 签名同一模式）。"""
    settings = get_settings()
    key = settings.paseto_secret_key.encode("utf-8")
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_payment_intent(
    order_id: str,
    amount: float,
    actor_user_id: str,
    ttl_seconds: int | None = None,
) -> dict:
    """签发可验证支付意图 token。

    Returns:
        {"token", "order_id", "amount", "expires_at"}（expires_at 为 Unix 秒）
    """
    settings = get_settings()
    ttl = ttl_seconds if ttl_seconds is not None else settings.payment_intent_ttl_seconds
    expires_at = int(time.time()) + int(ttl)
    payload = f"{order_id}|{amount}|{actor_user_id}|{expires_at}"
    token = f"{payload}|{_sign(payload)}"
    return {
        "token": token,
        "order_id": order_id,
        "amount": amount,
        "expires_at": expires_at,
    }


def verify_payment_intent(
    token: str,
    *,
    order_id: str,
    amount: float,
    actor_user_id: str,
) -> dict:
    """校验支付意图 token 真实性。

    Returns:
        {"valid": bool, "reason": str}——reason 仅在 invalid 时有诊断意义
        （malformed / signature / order_mismatch / amount_mismatch /
         actor_mismatch / expired）
    """
    try:
        parts = str(token).split("|")
        if len(parts) != 5:
            return {"valid": False, "reason": "malformed"}
        payload, sig = "|".join(parts[:4]), parts[4]
        if not hmac.compare_digest(_sign(payload), sig):
            return {"valid": False, "reason": "signature"}
        tok_order, tok_amount, tok_user, tok_exp = parts[0], parts[1], parts[2], parts[3]
        if tok_order != order_id:
            return {"valid": False, "reason": "order_mismatch"}
        if float(tok_amount) != float(amount):
            return {"valid": False, "reason": "amount_mismatch"}
        if tok_user != actor_user_id:
            return {"valid": False, "reason": "actor_mismatch"}
        if int(tok_exp) < int(time.time()):
            return {"valid": False, "reason": "expired"}
        return {"valid": True, "reason": "ok"}
    except (ValueError, TypeError, AttributeError) as e:
        logger.warning("verify_payment_intent: 解析失败: %s", e)
        return {"valid": False, "reason": "malformed"}

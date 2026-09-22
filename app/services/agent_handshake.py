"""ATH 可信互联握手凭证服务 — v1.16.x（信通院 ATH 1.0 对齐）

补全 ATH 九步可信握手流程中的身份凭证环节（④⑤⑦）：
- ④ 应用核验智能体身份：verify_agent_identity（查询 AID/ACDL 身份卡，核验已注册）
- ⑦ 握手凭证签发：create_handshake_credential（HMAC-SHA256，复用 PASETO 主密钥）
- ⑤ 智能体核验应用身份：verify_handshake_credential（双向身份验证）

设计（模块化单体最小闭环，复用 agent_payment_intent 的 HMAC 模式）：
- 凭证 payload = app_id|agent_name|actor_user_id|scope|expires_at|sig
- scope 为最小权限声明（如 a2a:task / scene:automation），防越权
- 短时有效（agent_handshake_ttl_seconds 默认 600s），防重放
- **应用注册表**（REGISTERED_APPS）校验 app_id 与 scope：ATH「三方参与」要求
  应用侧身份可核验，禁止调用方自报任意 app_id/scope（v1.17.x 补）

诚实标注（CLAUDE.md 红线）：
- 本服务只做身份凭证签发/校验，不触发任何业务动作
- 独立握手 token 与 PASETO 会话鉴权互补：PASETO 证明「你是谁」，
  握手凭证证明「你获授权与哪个智能体在哪个 scope 交互」（最小权限 + 时效）
- 当前为模块化单体中心化签发，非 ATH「去中心化/分布式认证」的完整实现，
  仅对齐握手凭证语义（诚实标注架构形态）
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time

from app.config import get_settings

logger = logging.getLogger(__name__)


def _sign(payload: str) -> str:
    """HMAC-SHA256 签名（复用 PASETO 主密钥，与 agent_payment_intent 同模式）。"""
    settings = get_settings()
    key = settings.paseto_secret_key.encode("utf-8")
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


# ── 应用注册表（ATH 三方参与：应用侧身份不可自报无名）──
# app_id → 允许的最小权限 scope 集合（精确匹配，越权即拒签）。
# 接入方须在本表单源登记，勿在调用侧自报任意字符串。
REGISTERED_APPS: dict[str, dict] = {
    "flutter": {
        "description": "Flutter 多端（iOS/Android/HarmonyOS）",
        "allowed_scopes": ("a2a:task",),
    },
    "webapp": {
        "description": "WebApp（Vite+React）",
        "allowed_scopes": ("a2a:task",),
    },
    "console": {
        "description": "管理控制台",
        "allowed_scopes": ("a2a:task", "scene:automation", "admin:audit"),
    },
    "suoke_life": {
        "description": "索克生活（跨主体 A2A 入站，见 docs/suoke-a2a-alignment-plan.md）",
        "allowed_scopes": ("a2a:task",),
    },
}


def validate_app(app_id: str, scope: str) -> dict:
    """应用注册表校验（app_id 已登记 + scope 在该应用白名单内）。

    Returns:
        {"valid": bool, "reason": str}——reason 仅在 invalid 时有诊断意义
        （unknown_app / scope_not_allowed）
    """
    app = REGISTERED_APPS.get(str(app_id))
    if app is None:
        return {
            "valid": False,
            "reason": f"unknown_app（未登记的应用标识，已注册：{','.join(sorted(REGISTERED_APPS))}）",
        }
    if str(scope) not in app["allowed_scopes"]:
        return {
            "valid": False,
            "reason": f"scope_not_allowed（{app_id} 可用 scope：{','.join(app['allowed_scopes'])}）",
        }
    return {"valid": True, "reason": "ok"}


def create_handshake_credential(
    app_id: str,
    agent_name: str,
    actor_user_id: str,
    scope: str = "a2a:task",
    ttl_seconds: int | None = None,
) -> dict:
    """签发握手凭证（ATH ⑦ 握手协商签发凭证）。

    Args:
        app_id: 应用/调用方标识（客户端类型，如 flutter / webapp / console）
        agent_name: 目标智能体名
        actor_user_id: 发起交互的用户 ID（用户主权）
        scope: 最小权限声明（如 a2a:task），防越权
        ttl_seconds: 凭证有效期，默认 agent_handshake_ttl_seconds

    Returns:
        {"token", "app_id", "agent_name", "actor_user_id", "scope", "expires_at"}
        （expires_at 为 Unix 秒）

    Raises:
        ValueError: app_id 未登记或 scope 不在该应用白名单内（应用注册表校验）
    """
    settings = get_settings()
    ttl = ttl_seconds if ttl_seconds is not None else settings.agent_handshake_ttl_seconds
    expires_at = int(time.time()) + int(ttl)
    # scope 不允许含分隔符，避免 token 解析歧义
    scope = str(scope).replace("|", "_")
    check = validate_app(app_id, scope)
    if not check["valid"]:
        raise ValueError(check["reason"])
    payload = f"{app_id}|{agent_name}|{actor_user_id}|{scope}|{expires_at}"
    token = f"{payload}|{_sign(payload)}"
    return {
        "token": token,
        "app_id": app_id,
        "agent_name": agent_name,
        "actor_user_id": actor_user_id,
        "scope": scope,
        "expires_at": expires_at,
    }


def verify_handshake_credential(
    token: str,
    *,
    app_id: str,
    agent_name: str,
    actor_user_id: str,
) -> dict:
    """校验握手凭证（ATH ⑤ 智能体核验应用/用户身份）。

    Returns:
        {"valid": bool, "reason": str, "scope": str | None}——
        reason 仅在 invalid 时有诊断意义（malformed / signature /
        app_mismatch / app_unregistered / agent_mismatch / actor_mismatch / expired）
    """
    try:
        parts = str(token).split("|")
        if len(parts) != 6:
            return {"valid": False, "reason": "malformed", "scope": None}
        payload, sig = "|".join(parts[:5]), parts[5]
        if not hmac.compare_digest(_sign(payload), sig):
            return {"valid": False, "reason": "signature", "scope": None}
        tok_app, tok_agent, tok_user, tok_scope, tok_exp = parts[0], parts[1], parts[2], parts[3], parts[4]
        if tok_app != app_id:
            return {"valid": False, "reason": "app_mismatch", "scope": tok_scope}
        if tok_app not in REGISTERED_APPS:
            # 应用注册表：已退登记的 app 其存量凭证一并拒绝（防注册表收紧后被绕过）
            return {"valid": False, "reason": "app_unregistered", "scope": tok_scope}
        if tok_agent != agent_name:
            return {"valid": False, "reason": "agent_mismatch", "scope": tok_scope}
        if tok_user != actor_user_id:
            return {"valid": False, "reason": "actor_mismatch", "scope": tok_scope}
        if int(tok_exp) < int(time.time()):
            return {"valid": False, "reason": "expired", "scope": tok_scope}
        return {"valid": True, "reason": "ok", "scope": tok_scope}
    except (ValueError, TypeError, AttributeError) as e:
        logger.warning("verify_handshake_credential: 解析失败: %s", e)
        return {"valid": False, "reason": "malformed", "scope": None}


def verify_agent_identity(agent_name: str, expected_aid: str | None = None) -> dict:
    """应用核验智能体身份（ATH ④）。

    查询目标智能体的 28 位 AID + ACDL 能力描述，供应用侧核验其身份与能力声明。
    若提供 expected_aid 则逐位比对，不匹配返回 verified=False。

    Returns:
        {"verified": bool, "agent_name": str, "aid": str, "acdl": dict,
         "match": bool | None}——match 仅在提供 expected_aid 时有意义
    """
    from app.services.agent_identity_card import get_agent_identity

    identity = get_agent_identity(agent_name)
    aid = identity["aid"]
    acdl = identity["acdl"]

    if expected_aid is None:
        return {
            "verified": True,
            "agent_name": agent_name,
            "aid": aid,
            "acdl": acdl,
            "match": None,
        }

    match = hmac.compare_digest(aid, expected_aid)
    return {
        "verified": bool(match),
        "agent_name": agent_name,
        "aid": aid,
        "acdl": acdl,
        "match": bool(match),
    }

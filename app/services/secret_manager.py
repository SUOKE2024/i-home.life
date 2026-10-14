"""密钥管理服务（借鉴索克生活 Vault/KMS 凭证管理）

索克生活通过 Vault 管理密钥并暴露 key fingerprint 供运维校验密钥轮换状态。
本模块将该方法论移植到 i-home.life：

1. PASETO key fingerprint：SHA256(key)[:8]，暴露于 /api/health/detail 供运维比对
2. Vault/KMS 集成（可选）：settings.vault_url 配置时从 Vault 拉取密钥，
   未配置时降级到本地 .env（默认行为，不影响现有功能）
3. 密钥轮换校验：fingerprint 变化时记录审计日志

设计原则：
- 永不泄露密钥明文，只暴露 fingerprint
- Vault 不可用时降级到本地配置，不阻断启动
- fingerprint 计算成本极低（SHA256），可高频暴露
"""
from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from typing import Any

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# ── Vault KV 键名常量（与索克生态对齐）──
# 认证改造（v4.public）：签发私钥 / 验签公钥；生态互通：suoke_life 侧公开公钥。
VAULT_KEY_PASETO_PRIVATE = "paseto-private-key"
VAULT_KEY_PASETO_PUBLIC = "paseto-public-key"
# 生态公钥存放在 KV 路径 suoke/ecosystem，字段名 suoke-life-public-paserk（与 suoke_club 一致）。
VAULT_PATH_ECOSYSTEM = "suoke/ecosystem"
VAULT_FIELD_ECOSYSTEM_PUBLIC = "suoke-life-public-paserk"


@lru_cache(maxsize=1)
def get_paseto_key_fingerprint() -> str:
    """计算 PASETO 密钥指纹（SHA256 前 8 位 hex）。

    认证改造（v4.public）后取**验签公钥**的材料字节——它才是决定跨服务验签一致性的密钥；
    未配置/不可用非对称密钥时回退对称 `paseto_secret_key`（legacy）。永不返回密钥明文。

    用于 /api/health/detail 暴露，运维通过比对 fingerprint 确认密钥一致/轮换状态。

    Returns:
        8 字符 hex 指纹，如 "a1b2c3d4"
    """
    material: bytes | None = None
    try:
        # 延迟导入，避免 services → auth 的模块级依赖环
        from app.auth.paseto_handler import _get_verify_key

        raw = getattr(_get_verify_key(), "key", None)
        if isinstance(raw, (bytes, bytearray)) and raw:
            material = bytes(raw)
    except Exception:
        material = None  # 非对称密钥不可用 → 回退 legacy 对称密钥
    if material is None:
        material = settings.paseto_secret_key.encode()
    return hashlib.sha256(material).hexdigest()[:8]


def clear_fingerprint_cache() -> None:
    """清除指纹缓存（密钥轮换后调用）。"""
    get_paseto_key_fingerprint.cache_clear()


class SecretManager:
    """密钥管理器 — Vault/KMS 集成（可选）

    受 settings.secret_manager_enabled feature flag 控制：
    - True + vault_url 配置：从 Vault 拉取密钥
    - True + vault_url 为空：降级到本地 .env（默认）
    - False：不暴露 fingerprint，所有方法返回空
    """

    def __init__(self):
        self._vault_client = None
        self._cached_secrets: dict[str, str] = {}

    @property
    def enabled(self) -> bool:
        return settings.secret_manager_enabled

    @property
    def vault_configured(self) -> bool:
        return bool(settings.vault_url and settings.vault_token)

    async def get_secret(self, key_name: str) -> str | None:
        """获取密钥值。

        优先从 Vault 拉取，Vault 不可用时降级到本地配置。

        Args:
            key_name: 密钥名，如 "paseto_secret_key" / "deepseek_api_key"

        Returns:
            密钥值，未找到返回 None
        """
        if not self.enabled:
            return None

        # 命中缓存
        if key_name in self._cached_secrets:
            return self._cached_secrets[key_name]

        # Vault 集成（可选）
        if self.vault_configured:
            secret = await self._fetch_from_vault(key_name)
            if secret is not None:
                self._cached_secrets[key_name] = secret
                return secret

        # 降级到本地配置
        secret = self._fetch_from_local(key_name)
        if secret is not None:
            self._cached_secrets[key_name] = secret
        return secret

    async def _fetch_from_vault(self, key_name: str) -> str | None:
        """从 Vault/KMS 拉取密钥（简化实现）。"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                # Vault KV v2 风格端点
                url = f"{settings.vault_url}/v1/{settings.vault_namespace}/data/{key_name}"
                resp = await client.get(
                    url,
                    headers={"X-Vault-Token": settings.vault_token},
                )
                if resp.status_code != 200:
                    logger.debug("vault_get %s: status=%s", key_name, resp.status_code)
                    return None
                data = resp.json()
                return data.get("data", {}).get("data", {}).get("value")
        except Exception as e:
            logger.warning("vault_fetch 失败（降级到本地）: %s", e)
            return None

    def _fetch_from_local(self, key_name: str) -> str | None:
        """从本地 settings 降级获取密钥。"""
        return getattr(settings, key_name, None)

    async def get_ecosystem_public_paserk(self) -> str | None:
        """获取索克生活侧公开公钥 PASERK（k4.public.），用于生态 SSO 验签。

        取值顺序：
        1) settings.ecosystem_public_paserk / 环境变量 ECOSYSTEM_PUBLIC_PASERK（公钥可公开）
        2) Vault KV v2 路径 suoke/ecosystem 的字段 suoke-life-public-paserk（与 suoke_club 对齐）

        注意：生态公钥属公开信息，允许 env 直配；私钥 PII 才必须走 Vault。
        """
        import os

        direct = (getattr(settings, "ecosystem_public_paserk", "") or os.getenv("ECOSYSTEM_PUBLIC_PASERK") or "").strip()
        if direct:
            return direct
        if not self.enabled or not self.vault_configured:
            return None
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                url = f"{settings.vault_url}/v1/{settings.vault_namespace}/data/{VAULT_PATH_ECOSYSTEM}"
                resp = await client.get(url, headers={"X-Vault-Token": settings.vault_token})
                if resp.status_code != 200:
                    logger.debug("vault_get %s: status=%s", VAULT_PATH_ECOSYSTEM, resp.status_code)
                    return None
                body = resp.json().get("data", {}).get("data", {})
                value = body.get(VAULT_FIELD_ECOSYSTEM_PUBLIC)
                return value.strip() if isinstance(value, str) and value.strip() else None
        except Exception as e:
            logger.warning("vault_fetch 生态公钥失败: %s", e)
            return None

    def get_health_info(self) -> dict[str, Any]:
        """返回密钥管理健康信息（用于 /api/health/detail）。"""
        if not self.enabled:
            return {"enabled": False}
        return {
            "enabled": True,
            "vault_configured": self.vault_configured,
            "vault_url": settings.vault_url or None,
            "vault_namespace": settings.vault_namespace if self.vault_configured else None,
            "paseto_key_fingerprint": get_paseto_key_fingerprint(),
            "cached_secret_count": len(self._cached_secrets),
        }


# 模块级单例
secret_manager = SecretManager()

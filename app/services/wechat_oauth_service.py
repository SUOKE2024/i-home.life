"""微信开放平台「网站应用」扫码登录服务（OAuth2 授权码流程 / qrconnect）。

链路：
  1. `create_oauth_state` + `build_authorize_url` 生成扫码授权链接（前端整页跳转）
  2. 微信回调携带 code + state → 后端 `verify_oauth_state` 防 CSRF
  3. `exchange_code` 用 code 换 access_token + openid / unionid
  4. `fetch_userinfo` 拉取昵称/头像（snsapi_login scope，尽力而为，失败不影响登录）

安全约束：
  - AppSecret 仅从 env 注入（settings.wechat_app_secret），任何日志/异常均不得携带；
  - state 为 HMAC-SHA256 签名的 nonce+exp（密钥复用 PASETO 主密钥），无状态、
    有有效期，防 CSRF 与重放；
  - 微信侧返回结构不信任：openid 缺失即失败，nickname 清洗后入库。
"""
import base64
import hashlib
import hmac
import logging
import time
import uuid
from urllib.parse import quote

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_AUTHORIZE_URL = "https://open.weixin.qq.com/connect/qrconnect"
_ACCESS_TOKEN_URL = "https://api.weixin.qq.com/sns/oauth2/access_token"
_USERINFO_URL = "https://api.weixin.qq.com/sns/userinfo"


class WeChatOAuthError(Exception):
    """微信 OAuth 调用失败（未配置 / 微信侧错误 / 网络错误）。"""


def _sign_payload(payload: str) -> str:
    """HMAC-SHA256 签名（密钥复用 PASETO 主密钥，不另立密钥）。"""
    key = settings.paseto_secret_key.encode("utf-8")
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_oauth_state() -> str:
    """生成防 CSRF state：base64url(nonce.exp_ts).hmac，有效期 wechat_state_expire_seconds。"""
    nonce = uuid.uuid4().hex
    exp_ts = int(time.time()) + settings.wechat_state_expire_seconds
    payload = f"{nonce}.{exp_ts}"
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).rstrip(b"=").decode("ascii")
    return f"{encoded}.{_sign_payload(payload)}"


def verify_oauth_state(state: str) -> bool:
    """校验 state 签名与有效期。任何格式错误均返回 False（不抛异常细节，防探测）。"""
    try:
        encoded, sig = state.rsplit(".", 1)
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        nonce, exp_ts = payload.split(".", 1)
        if len(nonce) != 32:
            return False
    except Exception:
        return False
    if not hmac.compare_digest(sig, _sign_payload(payload)):
        return False
    return int(exp_ts) >= int(time.time())


def build_authorize_url(state: str) -> str:
    """构造 qrconnect 授权链接（scope=snsapi_login，网站应用扫码）。"""
    redirect = quote(settings.wechat_redirect_uri, safe="")
    return (
        f"{_AUTHORIZE_URL}?appid={settings.wechat_app_id}"
        f"&redirect_uri={redirect}&response_type=code&scope=snsapi_login"
        f"&state={state}#wechat_redirect"
    )


def _require_config() -> tuple[str, str]:
    app_id = settings.wechat_app_id
    app_secret = settings.wechat_app_secret
    if not app_id or not app_secret:
        raise WeChatOAuthError("微信登录未配置 APPID/AppSecret")
    return app_id, app_secret


async def exchange_code(code: str) -> dict:
    """code 换 access_token + openid/unionid。微信侧 errcode 非 0 抛 WeChatOAuthError。"""
    app_id, app_secret = _require_config()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                _ACCESS_TOKEN_URL,
                params={
                    "appid": app_id,
                    "secret": app_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                },
            )
            data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("wechat access_token request failed: %s", type(e).__name__)
        raise WeChatOAuthError("微信授权服务暂不可用，请稍后重试") from e
    if data.get("errcode"):
        # errmsg 来自微信侧，仅截断展示，不记录 AppSecret
        raise WeChatOAuthError(f"微信授权失败({data['errcode']}): {str(data.get('errmsg', ''))[:80]}")
    return data


async def fetch_userinfo(access_token: str, openid: str) -> dict:
    """拉取昵称/头像（best-effort：失败返回空 dict，登录不受影响）。"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                _USERINFO_URL,
                params={"access_token": access_token, "openid": openid, "lang": "zh_CN"},
            )
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        return {}
    if data.get("errcode"):
        return {}
    return data


def sanitize_nickname(nickname: str) -> str:
    """昵称清洗：去控制字符/空白收尾/截断，空值返回空串（调用方回退默认昵称）。"""
    if not nickname:
        return ""
    cleaned = "".join(ch for ch in nickname if ord(ch) >= 32 and ch not in ("\u200b", "\ufeff"))
    return cleaned.strip()[:100]

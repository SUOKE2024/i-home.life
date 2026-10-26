"""微信小程序（索克家居业主端）登录与手机号服务。

链路（2026 现行官方能力，前端不持有 AppSecret）：
  1. 小程序 `wx.login()` 取一次性 code（5 分钟有效）
  2. `code_to_session` 走 jscode2session 换 openid / unionid / session_key
  3. 手机号：`<button open-type="getPhoneNumber">` 取 code → `get_phone_number`
     走 getuserphonenumber 换 purePhoneNumber
     （微信自 2023 起废弃 encryptedData/iv 明文解密链路，现行方案为 code 换号，
     不再需要 session_key 解密，故本服务不下发也不持久化 session_key）

安全约束：
  - AppSecret 仅从 settings 注入，日志与异常信息一律不携带；
  - session_key 属于会话密钥，绝不下发客户端；
  - access_token 进程内缓存并提前 300s 过期，刷取串行化，避免并发打爆每日配额；
  - 微信侧返回结构不信任：openid / 手机号缺失即失败，不做猜测兜底。
"""
import asyncio
import logging
import time

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_JSCODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
# 必须用 stable_token 而非老版 /cgi-bin/token：
# 老接口每次请求都会作废其他实例持有的 token（仅 5 分钟共存期），
# 多 worker / 多实例部署下会互相踢掉对方凭证，形成 40001 刷新风暴。
# stable_token 在 force_refresh=false 时返回同一 token 且不作废存量凭证。
_STABLE_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/stable_token"
_PHONE_NUMBER_URL = "https://api.weixin.qq.com/wxa/business/getuserphonenumber"

# access_token 失效类错误码：命中后强制刷新并重试一次
_TOKEN_INVALID_ERRCODES = {40001, 40014, 42001}

_access_token_cache: dict[str, object] = {"token": "", "expires_at": 0.0}
_access_token_lock = asyncio.Lock()


class WeChatMiniProgramError(Exception):
    """微信小程序接口调用失败（未配置 / 微信侧错误 / 网络错误）。"""


def _require_config() -> tuple[str, str]:
    app_id = settings.miniprogram_app_id
    app_secret = settings.miniprogram_app_secret
    if not app_id or not app_secret:
        raise WeChatMiniProgramError("小程序登录未配置 APPID/AppSecret")
    return app_id, app_secret


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(float(settings.miniprogram_api_timeout_seconds))


async def code_to_session(code: str) -> dict:
    """登录 code 换 openid / unionid。微信侧 errcode 非 0 抛 WeChatMiniProgramError。"""
    app_id, app_secret = _require_config()
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            resp = await client.get(
                _JSCODE2SESSION_URL,
                params={
                    "appid": app_id,
                    "secret": app_secret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                    "lang": "zh_CN",
                },
            )
            data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("miniprogram jscode2session request failed: %s", type(e).__name__)
        raise WeChatMiniProgramError("微信登录服务暂不可用，请稍后重试") from e

    if data.get("errcode"):
        # errmsg 来自微信侧，仅截断展示，不记录 AppSecret
        raise WeChatMiniProgramError(
            f"微信登录失败({data['errcode']}): {str(data.get('errmsg', ''))[:80]}"
        )
    if not data.get("openid"):
        raise WeChatMiniProgramError("微信未返回 openid，登录失败")
    # session_key 不进入返回值，避免误透传到响应体
    return {
        "openid": data["openid"],
        "unionid": data.get("unionid") or None,
    }


async def get_access_token(force_refresh: bool = False) -> str:
    """获取接口调用凭证（进程内缓存 + 提前过期 + 串行刷新）。"""
    if not force_refresh:
        cached = str(_access_token_cache["token"])
        if cached and float(_access_token_cache["expires_at"]) > time.time():
            return cached

    app_id, app_secret = _require_config()
    async with _access_token_lock:
        # 双检：等锁期间可能已被其它协程刷新
        cached = str(_access_token_cache["token"])
        if not force_refresh and cached and float(_access_token_cache["expires_at"]) > time.time():
            return cached

        try:
            async with httpx.AsyncClient(timeout=_timeout()) as client:
                resp = await client.post(
                    _STABLE_TOKEN_URL,
                    json={
                        "grant_type": "client_credential",
                        "appid": app_id,
                        "secret": app_secret,
                        # 仅在凭证被判定失效时强制刷新；常规取用不得作废其他实例的凭证
                        "force_refresh": bool(force_refresh),
                    },
                )
                data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("miniprogram stable_token request failed: %s", type(e).__name__)
            raise WeChatMiniProgramError("微信凭证服务暂不可用，请稍后重试") from e

        if data.get("errcode") or not data.get("access_token"):
            raise WeChatMiniProgramError(
                f"微信凭证获取失败({data.get('errcode')}): {str(data.get('errmsg', ''))[:80]}"
            )

        now = time.time()
        expires_in = int(data.get("expires_in") or 7200)
        _access_token_cache["token"] = data["access_token"]
        # 提前 300s 失效，规避临界期 40001；最短保留 60s 防止异常小值死循环
        _access_token_cache["expires_at"] = now + max(expires_in - 300, 60)
        return str(data["access_token"])


async def get_phone_number(code: str) -> str:
    """手机号快速验证：getPhoneNumber 的 code 换 purePhoneNumber（返回不带区号的号码）。"""
    last_error: WeChatMiniProgramError | None = None
    for attempt in range(2):
        access_token = await get_access_token(force_refresh=attempt > 0)
        try:
            async with httpx.AsyncClient(timeout=_timeout()) as client:
                resp = await client.post(
                    _PHONE_NUMBER_URL,
                    params={"access_token": access_token},
                    json={"code": code},
                )
                data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("miniprogram getuserphonenumber request failed: %s", type(e).__name__)
            raise WeChatMiniProgramError("手机号获取服务暂不可用，请稍后重试") from e

        errcode = int(data.get("errcode") or 0)
        if errcode in _TOKEN_INVALID_ERRCODES and attempt == 0:
            last_error = WeChatMiniProgramError(
                f"微信凭证失效({errcode})，已自动刷新重试"
            )
            continue
        if errcode:
            raise WeChatMiniProgramError(
                f"手机号获取失败({errcode}): {str(data.get('errmsg', ''))[:80]}"
            )

        phone_info = data.get("phone_info") or {}
        phone = phone_info.get("purePhoneNumber") or phone_info.get("phoneNumber")
        if not phone:
            raise WeChatMiniProgramError("微信未返回手机号，请重新授权")
        return str(phone)

    # 仅当两次都命中凭证失效才会到此（理论上不会：第二次是强制刷新后的新凭证）
    raise last_error or WeChatMiniProgramError("手机号获取失败，请重新授权")


def reset_access_token_cache() -> None:
    """清空凭证缓存（测试与密钥轮换使用）。"""
    _access_token_cache["token"] = ""
    _access_token_cache["expires_at"] = 0.0

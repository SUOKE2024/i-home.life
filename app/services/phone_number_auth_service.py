"""阿里云号码认证服务（运营商一键登录）。

覆盖两条链路：
- App 一键登录：客户端 SDK 拿到 access_token → 后端 GetMobile 换手机号。
- H5 一键登录：后端 GetAuthToken 发鉴权 token → 前端 JS SDK 拉起授权页拿 sp_token
  → 后端 GetPhoneWithToken 换手机号。

调用阿里云 OpenAPI（Dypnsapi/2017-05-25，RPC 风格），采用 V3（ACS3-HMAC-SHA256）
自签名，避免引入 alibabacloud_tea_openapi 对 cryptography<49 的硬约束（与项目
webauthn>=49 冲突）。
"""

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_DYPNASPI_VERSION = "2017-05-25"


class PhoneAuthError(Exception):
    """阿里云号码认证调用失败（未配置 / 服务商错误 / 网络错误）。"""


def _percent_encode(value: str) -> str:
    """RFC 3986 编码，保留 A-Za-z0-9-_.~。"""
    return quote(value, safe="-_.~")


def _form_urlencode(params: dict) -> str:
    """按 key 排序构造 application/x-www-form-urlencoded 体（确定性）。"""
    return "&".join(
        f"{_percent_encode(k)}={_percent_encode(str(v))}"
        for k, v in sorted(params.items())
    )


async def _aliyun_rpc_call(action: str, params: dict) -> dict:
    """调用阿里云 RPC OpenAPI（V3 签名），返回 JSON dict。"""
    access_key_id = settings.aliyun_phone_auth_access_key_id
    access_key_secret = settings.aliyun_phone_auth_access_key_secret
    endpoint = settings.aliyun_phone_auth_endpoint
    if not access_key_id or not access_key_secret:
        raise PhoneAuthError("阿里云号码认证服务未配置 AccessKey")

    body = _form_urlencode({k: v for k, v in params.items() if v is not None})
    body_bytes = body.encode("utf-8")
    body_hash = hashlib.sha256(body_bytes).hexdigest()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex

    headers_to_sign = {
        "host": endpoint,
        "content-type": "application/x-www-form-urlencoded;charset=utf-8",
        "x-acs-action": action,
        "x-acs-content-sha256": body_hash,
        "x-acs-date": now,
        "x-acs-signature-nonce": nonce,
        "x-acs-version": _DYPNASPI_VERSION,
    }
    signed_header_names = sorted(headers_to_sign.keys())
    canonical_headers = "".join(
        f"{k}:{headers_to_sign[k].strip()}\n" for k in signed_header_names
    )
    signed_headers = ";".join(signed_header_names)

    canonical_request = "\n".join([
        "POST",
        "/",
        "",
        canonical_headers,
        signed_headers,
        body_hash,
    ])
    hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"ACS3-HMAC-SHA256\n{hashed_canonical_request}"
    signature = hmac.new(
        access_key_secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "host": endpoint,
        "content-type": "application/x-www-form-urlencoded;charset=utf-8",
        "x-acs-action": action,
        "x-acs-content-sha256": body_hash,
        "x-acs-date": now,
        "x-acs-signature-nonce": nonce,
        "x-acs-version": _DYPNASPI_VERSION,
        "Authorization": (
            f"ACS3-HMAC-SHA256 Credential={access_key_id},"
            f"SignedHeaders={signed_headers},Signature={signature}"
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://{endpoint}/",
                headers=headers,
                content=body_bytes,
            )
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning(f"阿里云号码认证调用失败（{action}）: {e}")
        raise PhoneAuthError(f"阿里云号码认证网络错误: {e}") from e

    if data.get("Code") != "OK":
        logger.warning(f"阿里云号码认证返回错误（{action}）: {data}")
        raise PhoneAuthError(data.get("Message") or f"阿里云号码认证失败（{action}）")

    return data


async def get_mobile(access_token: str) -> str:
    """App 一键登录取号（GetMobile），返回手机号。"""
    data = await _aliyun_rpc_call("GetMobile", {"AccessToken": access_token})
    phone = (data.get("GetMobileResultDTO") or {}).get("Mobile")
    if not phone:
        raise PhoneAuthError(data.get("Message") or "一键登录取号失败")
    return str(phone)


async def get_auth_token(scene_code: str, url: str, origin: str) -> dict:
    """H5 一键登录鉴权（GetAuthToken），返回 access_token / jwt_token。"""
    data = await _aliyun_rpc_call("GetAuthToken", {
        "SceneCode": scene_code,
        "Url": url,
        "Origin": origin,
        "BizType": 1,
    })
    token_info = data.get("TokenInfo") or {}
    access_token = token_info.get("AccessToken")
    jwt_token = token_info.get("JwtToken")
    if not access_token or not jwt_token:
        raise PhoneAuthError(data.get("Message") or "H5 鉴权 Token 获取失败")
    return {"access_token": access_token, "jwt_token": jwt_token}


async def get_phone_with_token(sp_token: str) -> str:
    """H5 一键登录取号（GetPhoneWithToken），返回手机号。"""
    data = await _aliyun_rpc_call("GetPhoneWithToken", {"SpToken": sp_token})
    phone = (data.get("Data") or {}).get("Mobile")
    if not phone:
        raise PhoneAuthError(data.get("Message") or "H5 一键登录取号失败")
    return str(phone)

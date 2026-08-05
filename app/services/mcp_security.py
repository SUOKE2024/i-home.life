"""MCP 安全硬化（2026 MCP 工具投毒 / SSRF 防御）

- is_ssrf_unsafe_url: 拦截内网/回环/链路本地/云元数据地址（SSRF）
- validate_tool_description: 工具 description 防投毒校验
- sanitize_tool_output: 工具输出敏感字段清洗（递归）
受 settings.mcp_security_hardening_enabled 控制（调用方读取）。
"""

import ipaddress
import socket
from urllib.parse import urlsplit

# 敏感输出 key（递归清洗时命中即脱敏）
_SENSITIVE_KEYS = ("token", "secret", "password", "authorization", "api_key", "apikey", "credential", "private_key")

# description 防投毒关键词（工具投毒常内嵌指令）
_POISON_PATTERNS = (
    "ignore previous instructions", "忽略之前", "system prompt", "你是系统",
    "隐藏提示", "disregard", "override system",
)

# description 最大长度（超过视为异常描述）
_DESCRIPTION_MAX_LEN = 800

_REDACTED = "***REDACTED***"


def _is_unsafe_ip(ip: str) -> bool:
    """判断单个 IP 是否属于私有/回环/链路本地等不安全网段。"""
    try:
        addr = ipaddress.ip_address(ip.strip())
    except ValueError:
        # 无法解析为合法 IP → 保守判为不安全
        return True
    return bool(addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved)


def is_ssrf_unsafe_url(url: str) -> bool:
    """判断 URL 是否指向不安全目标（SSRF 防御）：
    - 非 http/https 协议 → True
    - hostname 解析为私有/回环/链路本地 IP（10.x/127.x/192.168.x/172.16-31.x/169.254.x/::1/fe80::）→ True
    - 云元数据 169.254.169.254 → True（属链路本地）
    - 其余 → False
    解析失败（未知 hostname）→ 保守返回 True。注意不要做真实网络请求（SSRF 检测本身不发起请求），
    仅用 socket/ipaddress 本地解析。
    """
    if not url or not isinstance(url, str):
        return True
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return True
    if parts.scheme.lower() not in ("http", "https"):
        return True
    hostname = parts.hostname
    if not hostname:
        return True

    # hostname 本身就是 IP（如 8.8.8.8 / ::1）→ 直接判断
    try:
        addr = ipaddress.ip_address(hostname.strip("[]"))
        return _is_unsafe_ip(str(addr))
    except ValueError:
        pass

    # hostname 是域名 → 本地 DNS 解析（不发起真实请求）
    try:
        infos = socket.getaddrinfo(hostname, None)
    except (socket.gaierror, OSError):
        # 解析失败（未知 hostname）→ 保守返回 True
        return True
    if not infos:
        return True
    return any(_is_unsafe_ip(info[4][0]) for info in infos)


def validate_tool_description(description: str) -> tuple[bool, str]:
    """防投毒校验。返回 (ok, reason)。
    - description 为空或超长（>800 字符）→ (False, reason)
    - 命中 _POISON_PATTERNS（大小写不敏感）→ (False, reason)
    - 否则 (True, "")"""
    if not description or not description.strip():
        return False, "description_is_empty"
    if len(description) > _DESCRIPTION_MAX_LEN:
        return False, f"description_too_long: len={len(description)} max={_DESCRIPTION_MAX_LEN}"
    lowered = description.lower()
    for pattern in _POISON_PATTERNS:
        if pattern.lower() in lowered:
            return False, f"description_poison_pattern: {pattern}"
    return True, ""


def sanitize_tool_output(output):
    """递归清洗 dict/list 中 key 含敏感词的字段，值替换为 "***REDACTED***"；
    str/其他类型原样返回。"""
    if isinstance(output, dict):
        cleaned = {}
        for key, value in output.items():
            if any(s in str(key).lower() for s in _SENSITIVE_KEYS):
                cleaned[key] = _REDACTED
            else:
                cleaned[key] = sanitize_tool_output(value)
        return cleaned
    if isinstance(output, list):
        return [sanitize_tool_output(item) for item in output]
    return output


def apply_tool_security(name: str, arguments: dict) -> dict:
    """执行前安全检查（工具名 + 参数）：
    - 参数中所有 URL 字段（key 含 url/uri/endpoint/link 或值以 http 开头）经 is_ssrf_unsafe_url 检查，
      不安全则将该参数字段替换为 {"error": "blocked_by_mcp_security", "reason": "ssrf_unsafe_url"}
    - 返回处理后的 arguments（安全参数原样保留）"""
    cleaned = dict(arguments or {})
    for key, value in list(cleaned.items()):
        key_lower = str(key).lower()
        is_url_field = any(s in key_lower for s in ("url", "uri", "endpoint", "link"))
        is_http_value = isinstance(value, str) and value.lstrip().lower().startswith("http")
        if not (is_url_field or is_http_value):
            continue
        if isinstance(value, str) and is_ssrf_unsafe_url(value):
            cleaned[key] = {"error": "blocked_by_mcp_security", "reason": "ssrf_unsafe_url"}
    return cleaned

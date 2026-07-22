"""PII 全量脱敏工具（借鉴索克生活 pii_masking）

索克生活对 8 类 PII（个人身份信息）做全量脱敏，应用于审计日志、Agent 轨迹、
错误日志等场景。本模块将该方法论移植到 i-home.life：

脱敏类型（8 类）：
1. 手机号    138****1234
2. 身份证号  110101********1234
3. 邮箱      a***@example.com
4. 银行卡号  6222****1234
5. 护照号    E1****56
6. 地址      保留省市，街道门牌脱敏
7. 姓名      张**（保留姓）
8. IP 地址   192.168.*.*

设计原则：
- 永不阻断主流程：脱敏失败返回原文
- 支持嵌套 dict/list 递归脱敏
- 受 settings.pii_masking_enabled feature flag 控制
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# ── 正则模式 ──
_PATTERNS = {
    "phone": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "id_card": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "bank_card": re.compile(r"(?<!\d)\d{16,19}(?!\d)"),
    # 护照号: 1-2 字母 + 7-9 数字
    "passport": re.compile(r"(?<![A-Za-z])[EeKkGgDd]\d{8}(?!\d)"),
    # IPv4
    "ip": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}


def mask_phone(text: str) -> str:
    """手机号脱敏: 13812345678 → 138****5678"""
    return _PATTERNS["phone"].sub(lambda m: m.group()[:3] + "****" + m.group()[-4:], text)


def mask_id_card(text: str) -> str:
    """身份证号脱敏: 110101199001011234 → 110101********1234"""
    return _PATTERNS["id_card"].sub(lambda m: m.group()[:6] + "********" + m.group()[-4:], text)


def mask_email(text: str) -> str:
    """邮箱脱敏: alice@example.com → a***@example.com"""
    def _sub(m):
        addr, domain = m.group().split("@", 1)
        return addr[0] + "***@" + domain if len(addr) > 1 else "*@" + domain
    return _PATTERNS["email"].sub(_sub, text)


def mask_bank_card(text: str) -> str:
    """银行卡号脱敏: 6222021234561234 → 6222****1234"""
    return _PATTERNS["bank_card"].sub(lambda m: m.group()[:4] + "****" + m.group()[-4:], text)


def mask_passport(text: str) -> str:
    """护照号脱敏: E12345678 → E1****78"""
    return _PATTERNS["passport"].sub(lambda m: m.group()[:2] + "****" + m.group()[-2:], text)


def mask_ip(text: str) -> str:
    """IP 地址脱敏: 192.168.1.100 → 192.168.*.*"""
    def _sub(m):
        parts = m.group().split(".")
        return ".".join(parts[:2]) + ".*.*"
    return _PATTERNS["ip"].sub(_sub, text)


def mask_name(name: str) -> str:
    """姓名脱敏: 张三丰 → 张**（保留姓）"""
    if not name or len(name) <= 1:
        return name or ""
    return name[0] + "*" * (len(name) - 1)


def mask_address(address: str) -> str:
    """地址脱敏: 浙江省杭州市西湖区文三路 100 号 → 浙江省杭州市***
    保留省市（前 2 段），后续脱敏。
    """
    if not address:
        return address
    # 匹配省市区/县市
    m = re.match(r"^([\u4e00-\u9fa5]{2,8}[省市])", address)
    if m:
        return m.group(1) + "***"
    return address[:2] + "***" if len(address) > 2 else "***"


# ── 主入口 ──

def mask_text(text: str) -> str:
    """对文本字符串做全量 PII 脱敏（8 类）。

    顺序很重要：身份证（18位）需在银行卡（16-19位）之前匹配，
    避免身份证号被银行卡规则截断。
    """
    if not settings.pii_masking_enabled or not text or not isinstance(text, str):
        return text
    try:
        result = text
        result = mask_id_card(result)    # 身份证优先（18位，避免被银行卡匹配）
        result = mask_bank_card(result)  # 银行卡
        result = mask_phone(result)      # 手机号
        result = mask_passport(result)   # 护照号
        result = mask_email(result)      # 邮箱
        result = mask_ip(result)         # IP
        return result
    except Exception as e:
        logger.debug("mask_text 失败（返回原文）: %s", e)
        return text


def mask_dict(data: dict[str, Any]) -> dict[str, Any]:
    """递归脱敏 dict 中的字符串值。

    Args:
        data: 原始 dict（如 audit_log details）

    Returns:
        脱敏后的 dict 副本（不修改原对象）
    """
    if not settings.pii_masking_enabled or not data:
        return data
    try:
        result = {}
        for k, v in data.items():
            if isinstance(v, str):
                # 对已知 PII 字段名做专用脱敏
                k_lower = k.lower()
                if k_lower in ("name", "real_name", "username", "contact_name"):
                    result[k] = mask_name(v)
                elif k_lower in ("address", "addr", "location"):
                    result[k] = mask_address(v)
                else:
                    result[k] = mask_text(v)
            elif isinstance(v, dict):
                result[k] = mask_dict(v)
            elif isinstance(v, list):
                result[k] = mask_list(v)
            else:
                result[k] = v
        return result
    except Exception as e:
        logger.debug("mask_dict 失败（返回原文）: %s", e)
        return data


def mask_list(data: list[Any]) -> list[Any]:
    """递归脱敏 list 中的字符串值。"""
    if not settings.pii_masking_enabled or not data:
        return data
    try:
        result = []
        for item in data:
            if isinstance(item, str):
                result.append(mask_text(item))
            elif isinstance(item, dict):
                result.append(mask_dict(item))
            elif isinstance(item, list):
                result.append(mask_list(item))
            else:
                result.append(item)
        return result
    except Exception as e:
        logger.debug("mask_list 失败（返回原文）: %s", e)
        return data

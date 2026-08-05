"""GB/Z 185 智能体身份卡（预研：元数据预埋，不硬接外部系统）

- AID：28 位身份码（GB/Z 185.2 思路）：9 位厂商信用代码 + 2 位智能体类型 + 1 位安全分级 + 15 位序列号 + 1 位校验位
- ACDL：GB/Z 185.4 JSON 能力描述（agent_id/name/security_level/capabilities/interface）
受 settings.gbz185_agent_card_enabled 控制。
"""

import hashlib
import re

# 厂商信用代码前缀（模拟，索克家居）
_VENDOR_CODE = "91330000SOKE9"  # 若需 9 位可调整为 "91330000S"，保持总长 28

# 智能体类型编码表（2 位）
AGENT_TYPE_CODES = {
    "designer": "01", "budget": "02", "procurement": "03", "construction": "04",
    "qa_inspector": "05", "settlement": "06", "concierge": "07",
    "growth": "81", "marketing": "82", "competitor_research": "83", "finance_recon": "84",
}

# 安全分级（1 位，参考 GB/Z 185.2：L1-L4）
SECURITY_LEVELS = ("1", "2", "3", "4")

# 默认 ACDL 能力描述（2-4 项中文能力，未显式传入时按 agent 类型取值）
DEFAULT_CAPABILITIES: dict[str, list[str]] = {
    "designer": ["户型方案设计", "空间布局规划", "风格推荐", "动线分析"],
    "budget": ["装修预算估算", "费用明细拆分", "省钱建议"],
    "procurement": ["材料采购建议", "供应商匹配", "采购计划排期"],
    "construction": ["施工计划编排", "进度跟踪", "工种任务发布"],
    "qa_inspector": ["分项验收", "图纸比对", "工艺缺陷检测"],
    "settlement": ["工程结算", "节点放款建议", "结算明细导出"],
    "concierge": ["装修知识问答", "常见问题解答", "人工客服转接"],
    "growth": ["功能使用率周报", "Agent 调用统计", "增长洞察"],
    "marketing": ["营销素材生成", "社媒文案草稿", "活动策划建议"],
    "competitor_research": ["竞品调研简报", "市场趋势分析", "差异化建议"],
    "finance_recon": ["平台收入对账", "资金流水核对", "对账报表"],
    "generic": ["智能体基础问答", "任务编排执行"],
}


def _vendor_code_digits() -> str:
    """取 _VENDOR_CODE 中 9 位数字作为厂商信用代码（截取/填充，保证纯数字）。

    "91330000SOKE9" 过滤非数字后为 "913300009"，恰好 9 位；
    若不足 9 位则右侧补 "0"，超过则截断——保证 AID 前 9 位恒为纯数字。
    """
    digits = re.sub(r"\D", "", _VENDOR_CODE)
    return digits[:9].ljust(9, "0")


def _luhn_check_digit(digits: str) -> str:
    """Luhn 校验位计算（输入不含校验位的数字串，返回 1 位数字）。

    从最右位起隔位乘 2（乘 2 后 >9 减 9），累加所有位数，
    校验位 = (10 - sum % 10) % 10，使完整编码通过 Luhn 校验。
    """
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def generate_aid(agent_name: str, security_level: str = "2") -> str:
    """生成 28 位 AID：
    - 9 位厂商信用代码（截取/填充 _VENDOR_CODE）
    - 2 位智能体类型码（AGENT_TYPE_CODES 映射，未知 agent → "00"）
    - 1 位安全分级（1-4，非法值回退 "2"）
    - 15 位序列号（基于 agent_name 的确定性 hash，如 sha256 hex 截取，保证幂等）
    - 1 位校验位（Luhn 校验：前 27 位数字计算）
    总长必须严格等于 28。
    """
    type_code = AGENT_TYPE_CODES.get(agent_name, "00")
    if security_level not in SECURITY_LEVELS:
        security_level = "2"
    # 确定性序列号：sha256(agent_name) 转 int 后取 15 位，零填充保证恒为 15 位数字
    serial = str(int(hashlib.sha256(agent_name.encode("utf-8")).hexdigest(), 16) % 10**15).zfill(15)
    prefix = _vendor_code_digits() + type_code + security_level + serial
    return prefix + _luhn_check_digit(prefix)


def build_acdl(agent_name: str, capabilities: list[str] | None = None) -> dict:
    """构建 ACDL 能力描述（GB/Z 185.4 JSON）：
    {"schema": "GB-Z-185.4", "acdl_version": "1.0",
     "agent": {"agent_id": <aid>, "name": agent_name, "security_level": "L2",
               "capabilities": capabilities 或默认按 agent 类型给 2-4 项中文能力,
               "interface": {"discovery": "a2a", "transport": ["json-rpc"], "endpoint_hint": "本平台内部"}}}
    """
    aid = generate_aid(agent_name)
    # 安全分级字符位于 AID 第 12 位（9 厂商 + 2 类型 + 1 分级），与身份码保持一致
    level_digit = aid[11]
    if capabilities is None:
        capabilities = list(DEFAULT_CAPABILITIES.get(agent_name, DEFAULT_CAPABILITIES["generic"]))
    return {
        "schema": "GB-Z-185.4",
        "acdl_version": "1.0",
        "agent": {
            "agent_id": aid,
            "name": agent_name,
            "security_level": f"L{level_digit}",
            "capabilities": capabilities,
            "interface": {
                "discovery": "a2a",
                "transport": ["json-rpc"],
                "endpoint_hint": "本平台内部",
            },
        },
    }


def get_agent_identity(agent_name: str, capabilities: list[str] | None = None) -> dict:
    """组装身份卡：{"agent_name": ..., "aid": <28位>, "acdl": {...}}"""
    acdl = build_acdl(agent_name, capabilities)
    return {
        "agent_name": agent_name,
        "aid": acdl["agent"]["agent_id"],
        "acdl": acdl,
    }


def list_supported_agents() -> dict:
    """返回支持身份码的 Agent 列表：{"agents": [{"name": ..., "type_code": ..., "security_level": "2"}], "total": N}"""
    agents = [
        {"name": name, "type_code": code, "security_level": "2"}
        for name, code in AGENT_TYPE_CODES.items()
    ]
    return {"agents": agents, "total": len(agents)}

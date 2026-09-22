"""F41 适老改造补贴资格预检 — 确定性估算（无 LLM、无外部调用）

政策依据（2026-09）：
- 商务部等八部门《促进智能家居消费行动方案》（2026-09-02）：第三条「按照 2026 年
  消费品以旧换新政策部署，支持地方结合实际自主合理确定智能家居产品补贴品类、
  补贴标准」；第四条「发展适老化智能家居」。
- 地方适老化改造补贴细则的公开报道口径：普遍按产品成交价的 15% 补贴并设单件上限，
  补贴目录围绕老年人五大居家刚需场景：防跌倒安全防护 / 居家用火用水安防 /
  家务劳作减负 / 健康应急监护 / 行动康复辅助。

诚实边界（不得突破）：
- 地方补贴目录、比例、单件上限差异较大且动态调整，本服务**不内置任何地方官方目录**，
  默认按公开报道的全国基准口径估算，并在 warnings 中强制标注「未接入地方官方目录」。
- 老年人年龄 / 失能等级 / 困难身份等**个人资格不参与本确定性判定**（地方细则可能另有
  户籍与身份要求），warnings 中强制标注需按当地规定单独核验。
- 输出恒带 is_estimate=True，禁止用于宣称「已获补贴」「已通过核定」。
"""

from app.services.partial_renovation_service import (
    QUICK_INSTALL_PACKAGES,
    get_package_subsidy_line,
)

# ── 补贴品类（政策五大居家刚需场景 + 兜底「其他」）──

SUBSIDY_CATEGORIES: dict[str, str] = {
    "fall_prevention": "防跌倒安全防护",
    "fire_water_safety": "居家用火用水安防",
    "housework_relief": "家务劳作减负",
    "health_emergency": "健康应急监护",
    "mobility_rehab": "行动康复辅助",
    "other": "其他（不在政策五大刚需场景内）",
}

# 可补贴品类（五大刚需场景，不含兜底 other）
_ELIGIBLE_CATEGORIES: tuple[str, ...] = (
    "fall_prevention",
    "fire_water_safety",
    "housework_relief",
    "health_emergency",
    "mobility_rehab",
)

# ── 政策档案（不内置地方细则；max_subsidy_per_unit 为 None 表示地方上限未知，诚实留空）──

SUBSIDY_POLICY_PROFILES: dict[str, dict] = {
    "national_baseline": {
        "name": "全国基准（公开报道口径）",
        "version": "2026-09-national-baseline",
        "subsidy_rate": 0.15,
        "max_subsidy_per_unit": None,
        "eligible_categories": _ELIGIBLE_CATEGORIES,
        "source": (
            "2026 年消费品以旧换新适老化补贴：公开报道口径为普遍按产品成交价 15% 补贴"
            "并设单件上限，具体补贴品类与上限由地方自主确定"
            "（商务部等八部门《促进智能家居消费行动方案》第三条）"
        ),
        "disclaimer": (
            "本结果为估算值，非补贴资格认定。地方补贴目录/比例/单件上限差异较大"
            "（东部地区已纳入毫米波跌倒监测雷达、护理机器人等高阶智能康养装备，"
            "中西部以基础刚需品类为主），实际以当地政策与主管部门核定为准。"
        ),
    },
}


def _validate_items(items: list[dict]) -> None:
    """校验清单行：品类须在目录内、单价非负、数量 ≥ 1。

    Raises:
        ValueError: 清单为空或字段非法（schema 层已拦一道，服务层对内部调用同样兜底）
    """
    if not items:
        raise ValueError("拟购清单不能为空（不得对空清单给出 0 补贴结论）")
    for index, item in enumerate(items):
        category = item.get("category")
        if category not in SUBSIDY_CATEGORIES:
            raise ValueError(
                f"清单第 {index + 1} 项品类非法: {category}，"
                f"可选: {', '.join(SUBSIDY_CATEGORIES.keys())}"
            )
        if not item.get("name"):
            raise ValueError(f"清单第 {index + 1} 项缺少名称")
        if float(item.get("unit_price", 0)) < 0:
            raise ValueError(f"清单第 {index + 1} 项单价不得为负")
        if int(item.get("quantity", 1)) < 1:
            raise ValueError(f"清单第 {index + 1} 项数量须 ≥ 1")


def _estimate_item(item: dict, profile: dict) -> dict:
    """估算单项补贴：可补贴品类按比例计算，超单件上限则截断并标注。"""
    unit_price = float(item["unit_price"])
    quantity = int(item.get("quantity", 1))
    subtotal = round(unit_price * quantity, 2)
    category = item["category"]
    eligible = category in profile["eligible_categories"]

    rate = profile["subsidy_rate"] if eligible else 0.0
    subsidy_unit = round(unit_price * rate, 2)
    subsidy_amount = round(subtotal * rate, 2)
    cap_applied = False

    cap = profile["max_subsidy_per_unit"]
    if eligible and cap is not None:
        capped = round(float(cap) * quantity, 2)
        if subsidy_amount > capped:
            subsidy_amount = capped
            cap_applied = True

    reason = None
    if not eligible:
        reason = f"品类「{SUBSIDY_CATEGORIES[category]}」不在本档案可补贴目录内"

    return {
        "name": item["name"],
        "category": category,
        "category_label": SUBSIDY_CATEGORIES[category],
        "unit_price": unit_price,
        "quantity": quantity,
        "subtotal": subtotal,
        "eligible": eligible,
        "subsidy_rate": rate,
        "subsidy_per_unit": subsidy_unit,
        "subsidy_amount": subsidy_amount,
        "cap_applied": cap_applied,
        "reason": reason,
    }


def _build_warnings(region: str | None, profile: dict, items: list[dict]) -> list[str]:
    """组装诚实标注：地方目录未接入 / 地方上限未知 / 个人资格不判定 / 不可补贴项。"""
    warnings: list[str] = []
    if region:
        warnings.append(
            f"未接入 {region} 官方补贴目录（本平台不内置地方细则），"
            "补贴品类/比例/单件上限以当地政策与主管部门核定为准"
        )
    else:
        warnings.append("未指定地区，按全国基准口径估算，未接入地方补贴目录")

    if profile["max_subsidy_per_unit"] is None:
        warnings.append(
            f"{profile['name']}未设定单件补贴上限，估算未计入地方单件上限，"
            "实际补贴可能低于估算值"
        )

    warnings.append(
        "老年人年龄/失能等级等个人资格不参与本确定性判定"
        "（地方细则可能另有户籍/困难身份要求），个人资格须按当地规定单独核验"
    )

    ineligible = sum(1 for item in items if not item["eligible"])
    if ineligible:
        warnings.append(f"{ineligible} 项不在本档案可补贴目录内，未计入补贴估算")

    return warnings


def precheck_subsidy(
    *,
    items: list[dict] | None = None,
    package_code: str | None = None,
    policy_profile: str = "national_baseline",
    region: str | None = None,
) -> dict:
    """适老改造补贴资格预检（确定性估算，非资格认定）

    Args:
        items: 拟购清单 [{"name", "category", "unit_price", "quantity"}, ...]
        package_code: 标准快装套餐编码（与 items 二选一，取套餐一口价作为清单行）
        policy_profile: 政策档案键，当前仅 national_baseline
        region: 地区（市/省），仅用于输出标注与未来接入地方目录，当前不改变计算结果

    Returns:
        {
            policy_profile, policy_version, region, is_estimate, subsidy_rate,
            max_subsidy_per_unit, source, disclaimer,
            items: [逐项估算结果], total_price, total_subsidy, net_payable, warnings
        }

    Raises:
        ValueError: 政策档案未知 / 清单与套餐均未提供 / 清单非法 / 套餐编码未知
    """
    profile = SUBSIDY_POLICY_PROFILES.get(policy_profile)
    if profile is None:
        raise ValueError(
            f"未知政策档案: {policy_profile}，可选: {', '.join(SUBSIDY_POLICY_PROFILES.keys())}"
        )

    if not items and not package_code:
        raise ValueError("需提供拟购清单 items 或标准套餐 package_code（不得对空输入给出结论）")

    source_items = list(items) if items else [get_package_subsidy_line(package_code)]
    _validate_items(source_items)

    estimated = [_estimate_item(item, profile) for item in source_items]
    total_price = round(sum(item["subtotal"] for item in estimated), 2)
    total_subsidy = round(sum(item["subsidy_amount"] for item in estimated), 2)

    return {
        "policy_profile": policy_profile,
        "policy_version": profile["version"],
        "region": region,
        "is_estimate": True,
        "subsidy_rate": profile["subsidy_rate"],
        "max_subsidy_per_unit": profile["max_subsidy_per_unit"],
        "source": profile["source"],
        "disclaimer": profile["disclaimer"],
        "items": estimated,
        "total_price": total_price,
        "total_subsidy": total_subsidy,
        "net_payable": round(total_price - total_subsidy, 2),
        "warnings": _build_warnings(region, profile, estimated),
    }


def list_policy_profiles() -> list[dict]:
    """可用的补贴政策档案摘要（供前端选择，不含内部实现细节）"""
    return [
        {
            "policy_profile": code,
            "name": profile["name"],
            "version": profile["version"],
            "subsidy_rate": profile["subsidy_rate"],
            "max_subsidy_per_unit": profile["max_subsidy_per_unit"],
            "eligible_categories": list(profile["eligible_categories"]),
            "source": profile["source"],
            "disclaimer": profile["disclaimer"],
        }
        for code, profile in SUBSIDY_POLICY_PROFILES.items()
    ]


__all__ = [
    "SUBSIDY_CATEGORIES",
    "SUBSIDY_POLICY_PROFILES",
    "QUICK_INSTALL_PACKAGES",
    "precheck_subsidy",
    "list_policy_profiles",
]

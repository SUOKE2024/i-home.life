"""装修预算定额库（S5 — 预算定额库）

v1.1.31 FP-6 修复：原 ``budget_service.generate_budget_from_bom`` 直接用
BOMItem.unit_price（采购价）汇总预算，缺乏行业定额基准，无法反映"应花多少"。
现引入按工程类别 × 档次的定额单价表，预算 = BOM 量 × 定额单价。

定额来源：综合《建筑装饰装修工程消耗量定额》及 2026 年华东地区市场均价，
按经济型/舒适型/品质型/豪华型四档分级。仅作预算基准，实际采购价仍由
BOMItem.unit_price 记录，两者差异反映成本控制情况。

受 ``settings.quota_library_enabled`` 控制：
- True：generate_budget_from_bom 用 BOM量 × 定额单价
- False：回退到直接用 BOMItem.total_price（原行为）
"""

# 定额单价表：category_code → {unit, <tier>: 单价}
# 单价单位均为元；unit 为该类工程的标准计量单位
# tier: economy(经济型) / comfort(舒适型) / premium(品质型) / luxury(豪华型)
QUOTA_LIBRARY: dict[str, dict] = {
    "flooring": {
        "unit": "㎡", "economy": 180, "comfort": 320, "premium": 580, "luxury": 980,
        "desc": "地面工程（找平+铺贴/地板）",
    },
    "wall": {
        "unit": "㎡", "economy": 80, "comfort": 150, "premium": 280, "luxury": 480,
        "desc": "墙面工程（基层+腻子+涂料/壁纸）",
    },
    "ceiling": {
        "unit": "㎡", "economy": 120, "comfort": 220, "premium": 380, "luxury": 650,
        "desc": "顶面工程（吊顶+收口）",
    },
    "kitchen_bath": {
        "unit": "㎡", "economy": 600, "comfort": 1100, "premium": 2000, "luxury": 3500,
        "desc": "厨卫工程（防水+贴砖+洁具安装）",
    },
    "doors_windows": {
        "unit": "樘", "economy": 800, "comfort": 1600, "premium": 3000, "luxury": 5800,
        "desc": "门窗工程（含套线/五金）",
    },
    "mep": {
        "unit": "㎡", "economy": 180, "comfort": 280, "premium": 420, "luxury": 650,
        "desc": "水电工程（强电+弱电+给排水，按建筑面积）",
    },
    "custom_furniture": {
        "unit": "㎡", "economy": 600, "comfort": 1100, "premium": 2000, "luxury": 3800,
        "desc": "定制家具（投影面积计价）",
    },
    "soft_decor": {
        "unit": "项", "economy": 8000, "comfort": 18000, "premium": 38000, "luxury": 80000,
        "desc": "软装工程（窗帘/地毯/装饰，按项目计）",
    },
    "appliances": {
        "unit": "项", "economy": 15000, "comfort": 30000, "premium": 60000, "luxury": 150000,
        "desc": "家电设备（厨电+空调+生活电器，按项目计）",
    },
    "other": {
        "unit": "项", "economy": 5000, "comfort": 10000, "premium": 20000, "luxury": 40000,
        "desc": "其他工程（拆除/垃圾清运/成品保护等）",
    },
}

# 合法档次
VALID_TIERS = ("economy", "comfort", "premium", "luxury")


def get_quota_price(category_code: str, tier: str = "comfort") -> tuple[float | None, str]:
    """查询定额单价

    Args:
        category_code: 工程类别码（flooring/wall/ceiling/kitchen_bath/...）
        tier: 档次（economy/comfort/premium/luxury），非法值回退 comfort

    Returns:
        (unit_price, unit)：单价 + 计量单位；类别不存在返回 (None, "项")
    """
    if tier not in VALID_TIERS:
        tier = "comfort"
    entry = QUOTA_LIBRARY.get(category_code) or QUOTA_LIBRARY.get("other")
    if not entry:
        return None, "项"
    return entry.get(tier), entry.get("unit", "项")


def get_quota_entry(category_code: str) -> dict | None:
    """获取整条定额（含全部档次 + desc）"""
    return QUOTA_LIBRARY.get(category_code) or QUOTA_LIBRARY.get("other")


def list_quota_categories() -> list[str]:
    """返回所有定额类别码"""
    return list(QUOTA_LIBRARY.keys())

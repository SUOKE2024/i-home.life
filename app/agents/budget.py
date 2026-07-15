"""预算 Agent — 分项预算、多方案对比、实时追踪、模板库"""

from app.agents.base import BaseAgent


# 装修等级单价（元/㎡）
TIER_PRICES = {
    "economy": (800, 1200),
    "comfort": (1200, 2000),
    "premium": (2000, 3500),
    "luxury": (3500, 6000),
}

# 标准预算分配比例（硬装/定制柜/软装/家电/其他）
BUDGET_RATIOS = {
    "economy": {"hard_fit": 0.50, "custom_cabinet": 0.15, "soft_decor": 0.20, "appliance": 0.10, "other": 0.05},
    "comfort": {"hard_fit": 0.45, "custom_cabinet": 0.18, "soft_decor": 0.22, "appliance": 0.10, "other": 0.05},
    "premium": {"hard_fit": 0.42, "custom_cabinet": 0.20, "soft_decor": 0.23, "appliance": 0.10, "other": 0.05},
    "luxury": {"hard_fit": 0.40, "custom_cabinet": 0.20, "soft_decor": 0.25, "appliance": 0.10, "other": 0.05},
}

# 预算模板库（按户型/风格/档次）
BUDGET_TEMPLATES = {
    "90_economy_modern": {
        "name": "90㎡经济型现代简约",
        "area": 90, "tier": "economy", "style": "modern",
        "total_range": (72000, 108000),
        "lines": [
            {"category": "硬装", "name": "水电改造", "unit_price": 200, "quantity": 90, "unit": "㎡"},
            {"category": "硬装", "name": "墙面涂料", "unit_price": 80, "quantity": 180, "unit": "㎡"},
            {"category": "硬装", "name": "地面瓷砖", "unit_price": 120, "quantity": 90, "unit": "㎡"},
            {"category": "定制柜", "name": "橱柜+衣柜", "unit_price": 12000, "quantity": 1, "unit": "套"},
            {"category": "软装", "name": "窗帘+家具", "unit_price": 15000, "quantity": 1, "unit": "套"},
            {"category": "家电", "name": "基础家电", "unit_price": 8000, "quantity": 1, "unit": "套"},
        ],
    },
    "126_comfort_modern": {
        "name": "126㎡舒适型现代简约",
        "area": 126, "tier": "comfort", "style": "modern",
        "total_range": (151200, 252000),
        "lines": [
            {"category": "硬装", "name": "水电改造", "unit_price": 250, "quantity": 126, "unit": "㎡"},
            {"category": "硬装", "name": "墙面乳胶漆+背景墙", "unit_price": 120, "quantity": 252, "unit": "㎡"},
            {"category": "硬装", "name": "750×1500大板砖", "unit_price": 180, "quantity": 126, "unit": "㎡"},
            {"category": "定制柜", "name": "全屋定制柜体", "unit_price": 28000, "quantity": 1, "unit": "套"},
            {"category": "软装", "name": "家具+窗帘+灯具", "unit_price": 35000, "quantity": 1, "unit": "套"},
            {"category": "家电", "name": "中高端家电套装", "unit_price": 18000, "quantity": 1, "unit": "套"},
        ],
    },
    "160_premium_light_luxury": {
        "name": "160㎡品质型轻奢风",
        "area": 160, "tier": "premium", "style": "light_luxury",
        "total_range": (320000, 560000),
        "lines": [
            {"category": "硬装", "name": "水电改造+智能家居布线", "unit_price": 320, "quantity": 160, "unit": "㎡"},
            {"category": "硬装", "name": "艺术漆+墙板", "unit_price": 200, "quantity": 320, "unit": "㎡"},
            {"category": "硬装", "name": "进口大板砖+人字拼地板", "unit_price": 280, "quantity": 160, "unit": "㎡"},
            {"category": "定制柜", "name": "全屋高端定制", "unit_price": 60000, "quantity": 1, "unit": "套"},
            {"category": "软装", "name": "设计师家具+品牌灯具", "unit_price": 80000, "quantity": 1, "unit": "套"},
            {"category": "家电", "name": "高端家电+智能家居", "unit_price": 40000, "quantity": 1, "unit": "套"},
        ],
    },
}


class BudgetAgent(BaseAgent):
    agent_name = "budget"
    system_prompt = """你是索克家居（i-home.life）AI 预算 Agent。

你的职责：
1. 根据项目面积、装修等级，自动生成分项预算
2. 按类别分解预算（硬装/定制柜/软装/家电/其他）
3. 从 BOM 物料清单自动统计预算
4. 多方案预算对比分析
5. 预算偏差 > 5% 时发出预警

装修等级单价参考（元/㎡）：
- 经济型：800-1200/㎡
- 舒适型：1200-2000/㎡
- 品质型：2000-3500/㎡
- 豪华型：3500+/㎡

预算分配比例参考：
- 硬装（水电、墙面、地面）：40-50%
- 定制柜体：15-20%
- 软装（家具、窗帘、灯具）：20-25%
- 家电设备：10-15%

请用中文回复，专业细致但通俗易懂。"""

    @staticmethod
    def detect_tier(message: str) -> str:
        """从用户消息识别装修等级"""
        if any(kw in message for kw in ["豪华", "高端", "顶配"]):
            return "luxury"
        if any(kw in message for kw in ["品质", "中高端", "轻奢"]):
            return "premium"
        if any(kw in message for kw in ["经济", "简装", "出租"]):
            return "economy"
        return "comfort"

    @staticmethod
    def detect_area(message: str) -> float:
        """从用户消息识别面积"""
        import re
        m = re.search(r"(\d+(?:\.\d+)?)\s*㎡|(\d+(?:\.\d+)?)\s*平方", message)
        if m:
            return float(m.group(1) or m.group(2))
        if "160" in message or "大平层" in message:
            return 160.0
        if "90" in message or "小户型" in message:
            return 90.0
        return 126.0

    def generate_budget_plan(self, message: str) -> dict:
        """生成单套预算方案（业务逻辑，不依赖 LLM）"""
        tier = self.detect_tier(message)
        area = self.detect_area(message)
        low, high = TIER_PRICES[tier]
        ratios = BUDGET_RATIOS[tier]

        mid_price = (low + high) / 2
        total = area * mid_price

        lines = []
        for cat_key, ratio in ratios.items():
            cat_name = {
                "hard_fit": "硬装工程",
                "custom_cabinet": "定制柜体",
                "soft_decor": "软装工程",
                "appliance": "家电设备",
                "other": "其他费用",
            }[cat_key]
            amount = round(total * ratio, 2)
            lines.append({
                "category": cat_name,
                "name": cat_name,
                "estimated_amount": amount,
                "unit": "项",
                "quantity": 1,
                "unit_price": amount,
            })

        return {
            "tier": tier,
            "tier_name": {"economy": "经济型", "comfort": "舒适型", "premium": "品质型", "luxury": "豪华型"}[tier],
            "area": area,
            "unit_price_range": [low, high],
            "total_estimated": round(total, 2),
            "total_range": [round(area * low, 2), round(area * high, 2)],
            "lines": lines,
            "reply": f"已为您生成 {area}㎡ {self._tier_cn(tier)} 预算方案，预估总价 ¥{total:,.0f}（单价 ¥{low}-{high}/㎡）",
        }

    def compare_budget_plans(self, message: str) -> dict:
        """生成多方案预算对比（F11）"""
        area = self.detect_area(message)
        plans = []
        for tier in ["economy", "comfort", "premium"]:
            low, high = TIER_PRICES[tier]
            ratios = BUDGET_RATIOS[tier]
            mid_price = (low + high) / 2
            total = area * mid_price
            breakdown = {cat: round(total * r, 2) for cat, r in ratios.items()}
            plans.append({
                "tier": tier,
                "tier_name": {"economy": "经济型", "comfort": "舒适型", "premium": "品质型", "luxury": "豪华型"}[tier],
                "total_range": [round(area * low, 2), round(area * high, 2)],
                "total_estimated": round(total, 2),
                "breakdown": breakdown,
            })

        # 差异分析
        diff_economy_comfort = plans[1]["total_estimated"] - plans[0]["total_estimated"]
        diff_comfort_premium = plans[2]["total_estimated"] - plans[1]["total_estimated"]

        return {
            "area": area,
            "plans": plans,
            "differences": {
                "economy_to_comfort": round(diff_economy_comfort, 2),
                "comfort_to_premium": round(diff_comfort_premium, 2),
            },
            "recommendation": f"推荐舒适型方案，总价 ¥{plans[1]['total_estimated']:,.0f}，兼顾品质与性价比",
            "reply": (
                f"已生成 {area}㎡ 三档预算对比："
                f"经济型 ¥{plans[0]['total_estimated']:,.0f} / "
                f"舒适型 ¥{plans[1]['total_estimated']:,.0f} / "
                f"品质型 ¥{plans[2]['total_estimated']:,.0f}"
            ),
        }

    def check_budget_variance(self, total_estimated: float, total_actual: float) -> dict:
        """预算偏差检查与预警（F12）"""
        if total_estimated <= 0:
            return {"variance_pct": 0, "status": "ok", "alert": None}

        variance = total_actual - total_estimated
        variance_pct = round(variance / total_estimated * 100, 2)

        if variance_pct > 10:
            status = "critical"
            alert = f"⚠️ 预算超支 {variance_pct}%（超 ¥{variance:,.0f}），建议立即停工复盘"
        elif variance_pct > 5:
            status = "warning"
            alert = f"⚠️ 预算偏差 {variance_pct}%（超 ¥{variance:,.0f}），已触发 5% 预警阈值"
        elif variance_pct < -10:
            status = "saving"
            alert = f"✅ 预算节约 {abs(variance_pct)}%（省 ¥{abs(variance):,.0f}），可考虑升级档次"
        else:
            status = "ok"
            alert = None

        return {
            "total_estimated": total_estimated,
            "total_actual": total_actual,
            "variance": round(variance, 2),
            "variance_pct": variance_pct,
            "status": status,
            "alert": alert,
        }

    def list_templates(self) -> dict:
        """预算模板库（F13）"""
        return {
            "templates": [
                {
                    "code": code,
                    "name": t["name"],
                    "area": t["area"],
                    "tier": t["tier"],
                    "style": t["style"],
                    "total_range": list(t["total_range"]),
                    "line_count": len(t["lines"]),
                }
                for code, t in BUDGET_TEMPLATES.items()
            ],
            "total": len(BUDGET_TEMPLATES),
            "reply": f"共 {len(BUDGET_TEMPLATES)} 套预算模板，覆盖 90-160㎡ 经济/舒适/品质三档",
        }

    def apply_template(self, template_code: str, area: float | None = None) -> dict:
        """应用预算模板（按面积等比缩放）"""
        if template_code not in BUDGET_TEMPLATES:
            return {"error": f"模板 {template_code} 不存在", "available": list(BUDGET_TEMPLATES.keys())}

        tpl = BUDGET_TEMPLATES[template_code]
        scale = (area / tpl["area"]) if area and area > 0 else 1.0

        lines = []
        total = 0.0
        for line in tpl["lines"]:
            qty = round(line["quantity"] * scale, 2)
            amount = round(line["unit_price"] * qty, 2)
            total += amount
            lines.append({
                "category": line["category"],
                "name": line["name"],
                "unit_price": line["unit_price"],
                "quantity": qty,
                "unit": line["unit"],
                "estimated_amount": amount,
            })

        return {
            "template_code": template_code,
            "template_name": tpl["name"],
            "applied_area": area or tpl["area"],
            "scale": round(scale, 3),
            "total_estimated": round(total, 2),
            "lines": lines,
            "reply": f"已应用模板「{tpl['name']}」，按 {area or tpl['area']}㎡ 缩放，总价 ¥{total:,.0f}",
        }

    @staticmethod
    def _tier_cn(tier: str) -> str:
        return {"economy": "经济型", "comfort": "舒适型", "premium": "品质型", "luxury": "豪华型"}[tier]

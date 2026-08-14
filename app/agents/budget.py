"""预算 Agent — 分项预算、多方案对比、实时追踪、模板库"""

import json
import logging

from app.agents.base import BaseAgent
from app.services.agent_tool_registry import tool_registry

logger = logging.getLogger(__name__)


# ── FunctionCall 工具：从 tool_registry 获取 budget 类别工具 schema ──
_BUDGET_TOOL_SCHEMAS = tool_registry.get_openai_schemas_for_category("budget")


# 装修等级单价（元/㎡）
TIER_PRICES = {
    "economy": (800, 1200),
    "comfort": (1200, 2000),
    "premium": (2000, 3500),
    "luxury": (3500, 6000),
}

# 标准预算分配比例（8 类：土建/硬装/软装/厨卫/家具/灯具/电器/智能家居，各档合计 1.0）
BUDGET_RATIOS = {
    "economy": {"structural": 0.10, "hard_fit": 0.35, "soft_decor": 0.18, "kitchen_bath": 0.12,
                "furniture": 0.08, "lighting": 0.05, "appliance": 0.08, "smart_home": 0.04},
    "comfort": {"structural": 0.08, "hard_fit": 0.32, "soft_decor": 0.20, "kitchen_bath": 0.12,
                "furniture": 0.09, "lighting": 0.05, "appliance": 0.09, "smart_home": 0.05},
    "premium": {"structural": 0.06, "hard_fit": 0.30, "soft_decor": 0.20, "kitchen_bath": 0.13,
                "furniture": 0.10, "lighting": 0.06, "appliance": 0.09, "smart_home": 0.06},
    "luxury": {"structural": 0.05, "hard_fit": 0.28, "soft_decor": 0.22, "kitchen_bath": 0.12,
               "furniture": 0.11, "lighting": 0.07, "appliance": 0.08, "smart_home": 0.07},
}

# 旧 5 类比例（向后兼容：F11 多方案对比 breakdown 沿用旧 5 类结构）
BUDGET_RATIOS_5CAT = {
    "economy": {"hard_fit": 0.50, "custom_cabinet": 0.15, "soft_decor": 0.20, "appliance": 0.10, "other": 0.05},
    "comfort": {"hard_fit": 0.45, "custom_cabinet": 0.18, "soft_decor": 0.22, "appliance": 0.10, "other": 0.05},
    "premium": {"hard_fit": 0.42, "custom_cabinet": 0.20, "soft_decor": 0.23, "appliance": 0.10, "other": 0.05},
    "luxury": {"hard_fit": 0.40, "custom_cabinet": 0.20, "soft_decor": 0.25, "appliance": 0.10, "other": 0.05},
}

# 8 类中文名
_CATEGORY_CN = {
    "structural": "土建改造", "hard_fit": "硬装工程", "soft_decor": "软装工程",
    "kitchen_bath": "厨卫工程", "furniture": "家具采购", "lighting": "灯具照明",
    "appliance": "家电设备", "smart_home": "智能家居",
}

# 8 类 → 旧 5 类聚合映射（估算，诚实标注：厨卫柜体与定制家具归入定制柜）
_5CAT_AGGREGATION = {
    "hard_fit": ["structural", "hard_fit"],
    "custom_cabinet": ["kitchen_bath", "furniture"],
    "soft_decor": ["soft_decor", "lighting"],
    "appliance": ["appliance", "smart_home"],
    "other": [],
}

# 三费拆分比例（材料/人工/管理费，估算参考 60%/30%/10%，诚实标注为非精确报价）
COST_SPLIT = {"material": 0.60, "labor": 0.30, "management": 0.10}
COST_SPLIT_NOTE = "材料/人工/管理费按 60%/30%/10% 估算拆分，非精确报价"
RULE_PRICE_SOURCE = "市场价格库（估算）"


def _parse_llm_json(reply) -> dict | None:
    """宽容解析 LLM 回复中的 JSON（支持 ```json 代码块包裹），非法返回 None。"""
    if not isinstance(reply, str):
        return None
    text = reply.strip()
    if text.startswith("```"):
        start = text.find("\n")
        end = text.rfind("```")
        if start != -1 and end > start:
            text = text[start:end].strip()
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


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
    tools = _BUDGET_TOOL_SCHEMAS
    system_prompt = """你是索克家居（i-home.life）AI 预算 Agent。

你的职责：
1. 根据项目面积、装修等级，自动生成分项预算
2. 按 8 类分解预算（土建/硬装/软装/厨卫/家具/灯具/电器/智能家居）
3. 按面积×单价规则估算预算（BOM 明细统计由算量/预算功能完成，对话结果为估算参考）
4. 多方案预算对比分析
5. 预算偏差 > 5% 时发出预警

装修等级单价参考（元/㎡）：
- 经济型：800-1200/㎡
- 舒适型：1200-2000/㎡
- 品质型：2000-3500/㎡
- 豪华型：3500+/㎡

预算分配比例参考（8 类，合计 100%）：
- 土建改造：5-10%
- 硬装工程（水电、墙面、地面）：28-35%
- 软装工程（家具、窗帘、灯具等软装）：18-22%
- 厨卫工程：12-13%
- 家具采购：8-11%
- 灯具照明：5-7%
- 家电设备：8-9%
- 智能家居：4-7%

每项预算可标注材料费（约 60%）/人工费（约 30%）/管理费（约 10%），
价格来源从「供应商报价 / 市场价格库 / 历史项目均价」中诚实标注。

请用中文回复，专业细致但通俗易懂。"""

    # v1.13.x: 稳定人格锚（身份 + 服务承诺 + 沟通风格），与 system_prompt（规则）互补。
    persona = """【人格锚】你是索克家居的预算顾问。
服务承诺：报价透明、来源可追溯，不虚报不漏项，超预算主动预警。
沟通风格：细致但通俗，帮用户看懂每一笔钱花在哪。"""

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
        """生成单套预算方案（8 类拆分 + 三费拆分 + 价格来源；规则路径，诚实标注）"""
        tier = self.detect_tier(message)
        area = self.detect_area(message)
        low, high = TIER_PRICES[tier]
        ratios = BUDGET_RATIOS[tier]

        mid_price = (low + high) / 2
        total = area * mid_price

        lines = []
        breakdown = {}
        for cat_key, ratio in ratios.items():
            cat_name = _CATEGORY_CN[cat_key]
            amount = round(total * ratio, 2)
            breakdown[cat_key] = amount
            lines.append({
                "category": cat_name,
                "name": cat_name,
                "estimated_amount": amount,
                "unit": "项",
                "quantity": 1,
                "unit_price": amount,
                "material_cost": round(amount * COST_SPLIT["material"], 2),
                "labor_cost": round(amount * COST_SPLIT["labor"], 2),
                "management_cost": round(amount * COST_SPLIT["management"], 2),
                "cost_split_note": COST_SPLIT_NOTE,
                "price_source": RULE_PRICE_SOURCE,
            })

        return {
            "tier": tier,
            "tier_name": {"economy": "经济型", "comfort": "舒适型", "premium": "品质型", "luxury": "豪华型"}[tier],
            "area": area,
            "unit_price_range": [low, high],
            "total_estimated": round(total, 2),
            "total_range": [round(area * low, 2), round(area * high, 2)],
            "lines": lines,
            "breakdown": breakdown,
            "legacy_5cat": self._aggregate_5cat(breakdown),
            # 诚实标注：预算由确定性规则引擎生成（TIER_PRICES × 面积 × 比例），未调用 LLM
            "engine": "rule_based",
            "source_note": "规则引擎生成（未调用 LLM）；8 类拆分与三费为估算",
            "reply": f"已为您生成 {area}㎡ {self._tier_cn(tier)} 预算方案，预估总价 ¥{total:,.0f}（单价 ¥{low}-{high}/㎡）",
        }

    @staticmethod
    def _aggregate_5cat(breakdown_8cat: dict) -> dict:
        """将 8 类金额聚合为旧 5 类（估算映射，向后兼容）。"""
        return {
            cat_key: round(sum(breakdown_8cat.get(m, 0.0) for m in members), 2)
            for cat_key, members in _5CAT_AGGREGATION.items()
        }

    def compare_budget_plans(self, message: str) -> dict:
        """生成多方案预算对比（F11，breakdown 沿用旧 5 类结构向后兼容）"""
        area = self.detect_area(message)
        plans = []
        for tier in ["economy", "comfort", "premium"]:
            low, high = TIER_PRICES[tier]
            ratios = BUDGET_RATIOS_5CAT[tier]
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

    async def apply_template(self, template_code: str, area: float | None = None) -> dict:
        """应用预算模板（F13）：优先 LLM 个性化填充，失败回退线性缩放。

        响应标注 filling_source="llm"/"rule" + note，诚实降级不伪装。
        """
        if template_code not in BUDGET_TEMPLATES:
            return {"error": f"模板 {template_code} 不存在", "available": list(BUDGET_TEMPLATES.keys())}

        tpl = BUDGET_TEMPLATES[template_code]
        applied_area = area or tpl["area"]

        # ── LLM 优先：基于户型/风格/档次生成个性化预算行 ──
        llm_lines = await self._try_llm_template_lines(tpl, applied_area)
        if llm_lines is not None:
            total = round(sum(line["estimated_amount"] for line in llm_lines), 2)
            return {
                "template_code": template_code,
                "template_name": tpl["name"],
                "applied_area": applied_area,
                "scale": 1.0,
                "total_estimated": total,
                "lines": llm_lines,
                "filling_source": "llm",
                "note": "预算行由 LLM 基于户型/风格/档次个性化填充（source=llm），未使用线性缩放，请设计师复核",
                "reply": f"已应用模板「{tpl['name']}」，LLM 个性化填充 {applied_area}㎡ 预算，总价 ¥{total:,.0f}",
            }

        # ── 回退：线性缩放（原规则逻辑，诚实标注降级）──
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
            "applied_area": applied_area,
            "scale": round(scale, 3),
            "total_estimated": round(total, 2),
            "lines": lines,
            "filling_source": "rule",
            "note": "LLM 不可用，已降级为线性缩放规则（source=rule）",
            "reply": f"已应用模板「{tpl['name']}」，按 {applied_area}㎡ 缩放，总价 ¥{total:,.0f}",
        }

    async def _try_llm_template_lines(self, tpl: dict, area: float) -> list[dict] | None:
        """调用 LLM 生成个性化预算行（schema 对齐现有 lines）；任何失败返回 None 由调用方回退。

        诚实降级：LLM 无 key 时 _chat 返回 mock（非 JSON）→ 解析失败 → None；
        抛异常 / 返回非 JSON / 结构非法均返回 None，绝不伪装 LLM 能力。
        """
        try:
            user_prompt = (
                f"模板：{tpl['name']}（模板面积 {tpl['area']}㎡，档次 {tpl['tier']}，风格 {tpl['style']}）。\n"
                f"目标面积 {area:.0f}㎡。请为该面积生成 6-10 行个性化预算，"
                "覆盖土建/硬装/软装/厨卫/家具/灯具/电器/智能家居等类别。\n"
                "必须只输出如下 JSON（不要输出任何其他文字）：\n"
                '{"lines": [{"category": "硬装", "name": "水电改造", "unit_price": 250, '
                '"quantity": 120, "unit": "㎡"}]}\n'
                "金额单位：元，estimated_amount 由 unit_price × quantity 计算，不要输出该字段。"
            )
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            reply = await self._chat(messages)
        except Exception as e:
            logger.warning("budget.apply_template: LLM 调用失败，回退线性缩放 (error=%s)", e)
            return None

        parsed = _parse_llm_json(reply)
        raw_lines = parsed.get("lines") if isinstance(parsed, dict) else None
        if not isinstance(raw_lines, list) or not raw_lines:
            logger.warning("budget.apply_template: LLM 返回非 JSON/空 lines，回退线性缩放")
            return None

        lines = []
        for raw in raw_lines[:30]:
            if not isinstance(raw, dict) or not raw.get("name"):
                continue
            try:
                unit_price = float(raw["unit_price"])
                qty = float(raw.get("quantity", 1))
            except (KeyError, TypeError, ValueError):
                continue
            if unit_price <= 0 or qty <= 0:
                continue
            lines.append({
                "category": str(raw.get("category") or "其他"),
                "name": str(raw["name"]),
                "unit_price": unit_price,
                "quantity": qty,
                "unit": str(raw.get("unit") or "项"),
                "estimated_amount": round(unit_price * qty, 2),
            })
        return lines or None

    @staticmethod
    def _tier_cn(tier: str) -> str:
        return {"economy": "经济型", "comfort": "舒适型", "premium": "品质型", "luxury": "豪华型"}[tier]

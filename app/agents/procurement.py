"""采购 Agent — 供应商匹配、询价比价、采购订单生成"""

from app.agents.base import BaseAgent


# 物料品类 → 推荐供应商（mock 数据）
SUPPLIER_RECOMMENDATIONS = {
    "瓷砖": ["东鹏", "马可波罗", "诺贝尔", "蒙娜丽莎"],
    "地板": ["圣象", "大自然", "德尔", "菲林格尔"],
    "橱柜": ["欧派", "索菲亚", "志邦", "金牌"],
    "卫浴": ["科勒", "TOTO", "九牧", "恒洁"],
    "涂料": ["多乐士", "立邦", "芬琳", "都芳"],
    "家电": ["美的", "海尔", "格力", "西门子"],
    "灯具": ["欧普", "雷士", "飞利浦", "松下"],
    "五金": ["汇泰龙", "雅洁", "顶固", "海福乐"],
    "门窗": ["步阳", "王力", "盼盼", "TATA"],
}


class ProcurementAgent(BaseAgent):
    agent_name = "procurement"
    system_prompt = """你是索克家居（i-home.life）AI 采购 Agent。

你的职责：
1. 根据 BOM 物料清单自动匹配供应商
2. 发起询价、收集报价、生成比价报告
3. 推荐最优采购方案（综合价格、交期、品质）
4. 生成采购订单、跟踪物流

采购策略：
- 大宗材料（瓷砖/地板/乳胶漆）批量采购，争取折扣
- 定制类（橱柜/衣柜）提前下单，确认尺寸
- 卫浴/五金 提前确认型号
- 家电 确定品牌后比价下单

请用中文回复，保持专业采购的语气。"""

    @staticmethod
    def detect_material_category(message: str) -> str:
        """识别消息中提到的物料品类"""
        for cat in SUPPLIER_RECOMMENDATIONS.keys():
            if cat in message:
                return cat
        # 别名映射
        alias = {
            "砖": "瓷砖", "地砖": "瓷砖", "墙砖": "瓷砖",
            "木地板": "地板",
            "柜": "橱柜", "衣柜": "橱柜",
            "马桶": "卫浴", "淋浴": "卫浴", "洗手台": "卫浴",
            "漆": "涂料", "乳胶漆": "涂料",
            "空调": "家电", "冰箱": "家电", "洗衣机": "家电",
            "灯": "灯具", "吊灯": "灯具",
            "门": "门窗", "窗": "门窗",
        }
        for kw, cat in alias.items():
            if kw in message:
                return cat
        return ""

    def recommend_suppliers(self, category: str) -> dict:
        """推荐供应商列表（mock）"""
        suppliers = SUPPLIER_RECOMMENDATIONS.get(category, [])
        return {
            "category": category,
            "suppliers": [
                {"name": s, "rating": round(4.5 - i * 0.1, 1), "tier": "认证" if i < 2 else "普通"}
                for i, s in enumerate(suppliers)
            ],
            "reply": f"已为「{category}」品类推荐 {len(suppliers)} 家优质供应商：{'、'.join(suppliers)}",
        }

    def generate_comparison_report(self, quotations: list[dict]) -> dict:
        """根据多份报价生成比价报告（F33）

        quotations 结构：
        [{"supplier_name": "东鹏", "unit_price": 80, "quantity": 100, "delivery_days": 7, "rating": 4.8}, ...]
        """
        if not quotations:
            return {"error": "无报价数据", "reply": "暂无报价可对比"}

        # 计算每份报价的综合得分
        analyzed = []
        prices = []
        for q in quotations:
            total = q.get("unit_price", 0) * q.get("quantity", 1)
            delivery = q.get("delivery_days", 7)
            rating = q.get("rating", 4.0)
            # 综合得分 = 价格分(60%) + 交期分(25%) + 评级分(15%)
            max_total = max(
                qt.get("unit_price", 1) * qt.get("quantity", 1)
                for qt in quotations
            )
            price_score = 100 - (total / max_total * 100) if total > 0 else 50
            delivery_score = max(0, 100 - (delivery - 3) * 10)  # 3天=100分, 每多1天扣10分
            rating_score = (rating / 5.0) * 100
            composite = round(price_score * 0.6 + delivery_score * 0.25 + rating_score * 0.15, 2)

            analyzed.append({
                "supplier_name": q.get("supplier_name", f"供应商{len(analyzed)+1}"),
                "unit_price": q.get("unit_price", 0),
                "quantity": q.get("quantity", 1),
                "total_price": round(total, 2),
                "delivery_days": delivery,
                "rating": rating,
                "price_score": round(price_score, 2),
                "delivery_score": round(delivery_score, 2),
                "rating_score": round(rating_score, 2),
                "composite_score": composite,
            })
            prices.append(total)

        # 按综合得分排序
        analyzed.sort(key=lambda x: x["composite_score"], reverse=True)
        best = analyzed[0]
        lowest = min(prices)
        highest = max(prices)
        price_spread = round(highest - lowest, 2)
        saving_pct = round(price_spread / highest * 100, 2) if highest > 0 else 0

        return {
            "total_quotations": len(analyzed),
            "lowest_price": round(lowest, 2),
            "highest_price": round(highest, 2),
            "price_spread": price_spread,
            "saving_pct_vs_highest": saving_pct,
            "recommended": best,
            "all_quotes": analyzed,
            "reply": (
                f"📊 比价报告：共 {len(analyzed)} 份报价，"
                f"最低 ¥{lowest:,.0f} / 最高 ¥{highest:,.0f}（差价 ¥{price_spread:,.0f}）。"
                f"推荐「{best['supplier_name']}」：综合得分 {best['composite_score']}，"
                f"单价 ¥{best['unit_price']}，{best['delivery_days']}天交期"
            ),
        }

    def generate_purchase_plan(self, bom_items: list[dict]) -> dict:
        """根据 BOM 生成采购计划（按施工阶段分批）

        bom_items 结构：
        [{"name": "瓷砖", "category": "tile", "quantity": 100, "unit": "㎡", "unit_price": 80}, ...]
        """
        # 按物料类别分配到采购阶段
        phase_mapping = {
            "tile": ("phase_1_mep", "水电阶段（开工前）"),
            "flooring": ("phase_2_tile", "泥瓦阶段"),
            "paint": ("phase_3_paint", "油漆阶段"),
            "kitchen": ("phase_4_install", "安装阶段"),
            "bathroom": ("phase_4_install", "安装阶段"),
            "lighting": ("phase_4_install", "安装阶段"),
            "appliance": ("phase_4_install", "安装阶段"),
            "furniture": ("phase_5_final", "完工阶段"),
            "curtain": ("phase_5_final", "完工阶段"),
        }

        phases: dict[str, dict] = {}
        total = 0.0
        for item in bom_items:
            cat = item.get("category", "other")
            phase_key, phase_name = phase_mapping.get(cat, ("phase_4_install", "安装阶段"))
            if phase_key not in phases:
                phases[phase_key] = {"phase_name": phase_name, "items": [], "subtotal": 0.0}
            qty = item.get("quantity", 1)
            price = item.get("unit_price", 0)
            line_total = qty * price
            total += line_total
            phases[phase_key]["items"].append({
                "name": item.get("name", "未命名"),
                "quantity": qty,
                "unit": item.get("unit", "项"),
                "unit_price": price,
                "total": round(line_total, 2),
            })
            phases[phase_key]["subtotal"] = round(phases[phase_key]["subtotal"] + line_total, 2)

        return {
            "phases": list(phases.values()),
            "total_estimated": round(total, 2),
            "reply": f"已生成 {len(bom_items)} 项物料采购计划，分 {len(phases)} 个阶段，预计总金额 ¥{total:,.0f}",
        }

    @staticmethod
    def match_supplier_for_material(material_name: str) -> dict:
        """为单个物料匹配供应商"""
        cat = ""
        for keyword, category in SUPPLIER_RECOMMENDATIONS.items():
            if keyword in material_name:
                cat = keyword
                break
        if not cat:
            return {"material": material_name, "matched": False, "reply": f"未找到「{material_name}」匹配的供应商"}
        return {
            "material": material_name,
            "matched": True,
            "category": cat,
            "suppliers": SUPPLIER_RECOMMENDATIONS[cat][:3],
            "reply": f"已为「{material_name}」匹配 {len(SUPPLIER_RECOMMENDATIONS[cat][:3])} 家供应商",
        }

    # ── 内容发布（扩展 ProcurementAgent） ──

    async def generate_content_publish_reply(self, message: str, user_name: str = "") -> str:
        """辅助供应商在聊天中发布产品/服务"""
        prompt = (
            f"""你是索克家居的内容发布助手。供应商 {user_name} 想要发布产品/服务。

用户消息：{message}

请按以下步骤协助：
1. 如果消息包含产品名称、类别、价格、规格等信息，提取并整理
2. 如果信息不完整，引导供应商补充缺失信息
3. 用 JSON 格式回复：{{"product_info": {{"name": "...", "category": "...", """
            f""""price_range": "...", "description": "...", "tags": [...]}}, """
            f""""missing_fields": [...], "reply": "对供应商的回复"}}

如果用户消息中信息完整，直接在 reply 中生成产品预览卡片格式的回复。
如果信息不完整，在 reply 中友好地询问缺失信息，并在 missing_fields 中列出。"""
        )
        try:
            result = await self.think(prompt)
            return result
        except Exception:
            return (
                f"**产品发布助手**\n\n"
                f"收到您的消息：{message}\n\n"
                "请确认以下信息以便发布产品：\n\n"
                "1. 产品名称\n"
                "2. 产品类别（瓷砖/地板/涂料/橱柜/卫浴/灯具/家电/窗帘/定制家具/其他）\n"
                "3. 价格区间\n"
                "4. 产品描述\n"
                "5. 标签"
            )

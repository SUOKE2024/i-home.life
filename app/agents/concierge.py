"""客服 Agent — 7×24 多模态对话、知识问答、问题升级"""

from app.agents.base import BaseAgent


# FAQ 知识库（常见问题列表）
FAQ_KNOWLEDGE_BASE = [
    {
        "id": "faq_001",
        "question": "装修一般需要多长时间？",
        "keywords": ["工期", "多长时间", "多久", "几天", "装修时间"],
        "answer": "一般家装工期约 45-60 天。其中水电 5-10 天，泥瓦 7-15 天，木工 5-10 天，油漆 7-10 天，安装 5-7 天。具体工期取决于面积、复杂程度和材料到位情况。",
        "category": "construction",
    },
    {
        "id": "faq_002",
        "question": "装修预算大概多少？",
        "keywords": ["预算", "多少钱", "费用", "价格", "花费", "造价"],
        "answer": "装修预算按档次参考：经济型 800-1200 元/㎡，舒适型 1200-2000 元/㎡，品质型 2000-3500 元/㎡，豪华型 3500 元/㎡以上。100㎡ 舒适型装修约 12-20 万元。",
        "category": "budget",
    },
    {
        "id": "faq_003",
        "question": "水电改造需要注意什么？",
        "keywords": ["水电", "水管", "电线", "电路", "管线"],
        "answer": (
            "水电改造注意：1) 水管打压测试 0.8MPa 保压 30 分钟不掉压；"
            "2) 强弱电间距 ≥ 500mm 避免干扰；3) 线管横平竖直，无三管交叉；"
            "4) 开关插座位置符合图纸，偏差 ≤ 5mm；5) 水电完工验收合格后方可封槽。"
        ),
        "category": "construction",
    },
    {
        "id": "faq_004",
        "question": "防水怎么做才算合格？",
        "keywords": ["防水", "闭水", "蓄水", "渗漏"],
        "answer": (
            "防水合格标准：1) 卫生间墙面防水高度 ≥ 1.8m，厨房 ≥ 0.3m；"
            "2) 闭水试验蓄水 48 小时无渗漏；3) 防水层涂刷至少 2-3 遍，厚度 ≥ 1.5mm；"
            "4) 阴阳角、管根处需做附加层处理。"
        ),
        "category": "construction",
    },
    {
        "id": "faq_005",
        "question": "瓷砖空鼓率标准是多少？",
        "keywords": ["空鼓", "瓷砖", "空鼓率"],
        "answer": "瓷砖空鼓率标准：单砖空鼓面积 < 5%，整体空鼓率 < 3%。空鼓率超标需拆除重新铺贴。验收时用空鼓锤逐块敲击检查，空音即为空鼓。",
        "category": "qa",
    },
    {
        "id": "faq_006",
        "question": "装修材料什么时候采购？",
        "keywords": ["采购", "材料", "物料", "买材料", "什么时候买"],
        "answer": "材料采购按施工阶段分批进行：1) 开工前：水电材料、防水材料；2) 水电后：瓷砖、地板、门窗；3) 泥瓦后：定制柜体（需复尺）；4) 油漆后：卫浴洁具、灯具、家电、家具。避免过早采购占用资金和仓储。",
        "category": "procurement",
    },
    {
        "id": "faq_007",
        "question": "装修保修期多久？",
        "keywords": ["保修", "保修期", "质保", "售后"],
        "answer": "装修保修期：1) 基础装修（水电、防水等隐蔽工程）保修 5 年；2) 表面工程（墙面、吊顶等）保修 2 年；3) 主材按厂家保修政策执行。保修期内非人为损坏免费维修。",
        "category": "settlement",
    },
    {
        "id": "faq_008",
        "question": "装修风格有哪些选择？",
        "keywords": ["风格", "装修风格", "设计风格", "现代简约", "北欧"],
        "answer": (
            "主流装修风格：1) 现代简约：简洁线条、中性色调，适合小户型；"
            "2) 北欧风：温暖木材、柔和色彩，性价比高；3) 日式侘寂：原木、白墙、留白艺术；"
            "4) 轻奢风：金属点缀、大理石、深色系；5) 新中式：传统元素与现代结合。"
            "建议根据户型和个人喜好选择。"
        ),
        "category": "design",
    },
    {
        "id": "faq_009",
        "question": "装修验收有哪些标准？",
        "keywords": ["验收", "验收标准", "竣工验收"],
        "answer": (
            "装修验收依据国标：1) GB 50210-2018 建筑装饰装修工程质量验收标准；"
            "2) GB 50327-2017 住宅装饰装修工程施工规范；"
            "3) GB 50300-2013 建筑工程施工质量验收统一标准。"
            "分项验收包含水电、泥瓦、木工、油漆、安装五个阶段，合格率 ≥ 85% 方为合格。"
        ),
        "category": "qa",
    },
    {
        "id": "faq_010",
        "question": "结算付款方式是怎样的？",
        "keywords": ["结算", "付款", "尾款", "结账", "付款方式"],
        "answer": "结算按里程碑分期付款：1) 交房节点 30%；2) 水电验收 20%；3) 泥瓦验收 25%；4) 竣工验收 20%；5) 保修期满 5%。建议每阶段验收合格后再付款，保留尾款作为质量保障。",
        "category": "settlement",
    },
]


# 咨询类型
INQUIRY_TYPES = [
    {"code": "design", "name": "设计咨询", "keywords": ["设计", "布局", "风格", "户型", "方案"]},
    {"code": "budget", "name": "预算咨询", "keywords": ["预算", "价格", "费用", "成本", "报价"]},
    {"code": "procurement", "name": "采购咨询", "keywords": ["采购", "材料", "物料", "建材", "供应商"]},
    {"code": "construction", "name": "施工咨询", "keywords": ["施工", "进度", "工期", "阶段", "工序"]},
    {"code": "settlement", "name": "结算咨询", "keywords": ["结算", "付款", "尾款", "账单"]},
    {"code": "complaint", "name": "投诉", "keywords": ["投诉", "不满", "差评", "举报", "态度"]},
    {"code": "after_sale", "name": "售后", "keywords": ["售后", "保修", "维修", "漏水", "开裂", "故障"]},
    {"code": "other", "name": "其他", "keywords": []},
]


# 升级到人工的规则
ESCALATION_RULES = [
    {
        "code": "complaint",
        "name": "用户投诉",
        "trigger_keywords": ["投诉", "举报", "态度恶劣", "差评", "欺骗", "欺诈"],
        "urgency": "high",
        "need_human": True,
        "reason": "投诉类问题需人工介入处理，安抚用户情绪并协调解决方案",
    },
    {
        "code": "after_sale_urgent",
        "name": "紧急售后",
        "trigger_keywords": ["紧急", "漏水", "着火", "漏电", "燃气", "中毒", "坍塌"],
        "urgency": "critical",
        "need_human": True,
        "reason": "涉及安全隐患的紧急售后问题需立即转人工处理",
    },
    {
        "code": "legal_dispute",
        "name": "法律纠纷",
        "trigger_keywords": ["律师", "法院", "起诉", "合同纠纷", "法律", "维权"],
        "urgency": "high",
        "need_human": True,
        "reason": "法律纠纷类问题需转法务或高级客服处理",
    },
    {
        "code": "refund",
        "name": "退款请求",
        "trigger_keywords": ["退款", "退钱", "退定金", "退货"],
        "urgency": "medium",
        "need_human": True,
        "reason": "退款涉及财务流程，需人工审核处理",
    },
    {
        "code": "complex_budget",
        "name": "复杂预算问题",
        "trigger_keywords": ["明细对不上", "账目不清", "多收费", "乱收费"],
        "urgency": "medium",
        "need_human": True,
        "reason": "预算争议需人工核实明细后回复",
    },
    {
        "code": "negative_emotion",
        "name": "负面情绪",
        "trigger_keywords": ["失望", "后悔", "气愤", "愤怒", "无语", "骗子"],
        "urgency": "high",
        "need_human": True,
        "reason": "用户情绪激动，需人工安抚并跟进处理",
    },
]


# 多模态输入类型
INPUT_MODALITIES = ["text", "voice", "image"]

# 情绪感知回复策略
EMOTION_RESPONSE_STRATEGIES = {
    "anxious": {
        "prefix": "我理解您现在可能有些着急，请放心，我马上帮您处理。",
        "tone": "安抚",
        "urgency_boost": True,
    },
    "angry": {
        "prefix": "非常抱歉给您带来了不愉快的体验，我已经记录您的问题，优先为您处理。",
        "tone": "道歉+共情",
        "urgency_boost": True,
        "force_escalation": True,
    },
    "sad": {
        "prefix": "我能感受到您的失落，装修确实是一件费心的事，让我来帮您分担。",
        "tone": "共情+支持",
        "urgency_boost": True,
    },
    "tired": {
        "prefix": "装修确实很辛苦，您辛苦了。让我来为您分担一些吧。",
        "tone": "关怀",
        "urgency_boost": False,
    },
    "excited": {
        "prefix": "太好了！看到您这么开心我也很高兴！",
        "tone": "积极互动",
        "urgency_boost": False,
    },
    "happy": {
        "prefix": "很高兴能帮到您！",
        "tone": "积极互动",
        "urgency_boost": False,
    },
    "hesitant": {
        "prefix": "不着急，您可以慢慢考虑。如果您需要更多信息帮助决策，我随时在这里。",
        "tone": "耐心引导",
        "urgency_boost": False,
    },
}


class ConciergeAgent(BaseAgent):
    agent_name = "concierge"
    system_prompt = """你是索克家居（i-home.life）AI 客服 Agent。

你的职责：
1. 7×24 小时多模态对话（支持文本、语音、图片输入）
2. 知识问答（装修规范、国标、产品目录、常见问题）
3. 复杂问题升级到人工客服
4. 感知用户情绪，动态调整回复语气和策略

情绪感知与共情回复：
- 检测到用户焦虑/着急 → 安抚语气 + 快速响应 + 优先处理
- 检测到用户愤怒/不满 → 先道歉共情 + 立即升级人工
- 检测到用户疲惫/低落 → 柔和语调 + 给予支持和鼓励
- 检测到用户开心/满意 → 积极互动 + 表达感谢
- 中性情绪 → 保持专业亲和的客服语调

服务准则：
- 友善、专业、耐心，始终以用户满意为目标
- 知识库覆盖装修规范（GB 50210/50327/50300）、产品目录、施工流程
- 涉及投诉、退款、法律纠纷、安全隐患等复杂问题，主动升级人工
- 回答准确清晰，不确定时诚实告知并转人工

升级规则：
- 用户投诉/举报 → 转人工（高优先级）
- 安全隐患（漏水/漏电/燃气）→ 立即转人工（紧急）
- 法律纠纷/合同争议 → 转法务
- 退款请求 → 转财务人工审核
- 预算账目争议 → 转人工核实

请用中文回复，语气亲切专业，根据用户情绪调整回复风格，给出明确的解答或引导。"""

    def answer_faq(self, question: str) -> dict:
        """FAQ 知识问答（基于预置知识库匹配）

        Args:
            question: 用户提问

        Returns:
            匹配到的 FAQ 答案，含匹配度评分
        """
        matched_faqs = []

        for faq in FAQ_KNOWLEDGE_BASE:
            score = self._calculate_match_score(question, faq)
            # 仅保留匹配度 ≥ 0.1 的结果，过滤字符偶然重叠（如"是什么"等通用字符）
            if score >= 0.1:
                matched_faqs.append({
                    "id": faq["id"],
                    "question": faq["question"],
                    "answer": faq["answer"],
                    "category": faq["category"],
                    "match_score": score,
                })

        # 按匹配度排序
        matched_faqs.sort(key=lambda x: x["match_score"], reverse=True)

        if not matched_faqs:
            return {
                "found": False,
                "question": question,
                "answer": "抱歉，知识库中暂未找到匹配的答案。您可以换一种方式提问，或转人工客服获取帮助。",
                "matched_faqs": [],
                "reply": "抱歉，暂未找到相关答案，建议您转接人工客服获取帮助。",
                "need_human": True,
            }

        best_match = matched_faqs[0]
        return {
            "found": True,
            "question": question,
            "answer": best_match["answer"],
            "category": best_match["category"],
            "best_match_question": best_match["question"],
            "match_score": best_match["match_score"],
            "matched_faqs": matched_faqs[:3],
            "reply": best_match["answer"],
            "need_human": False,
        }

    def classify_inquiry(self, message: str) -> dict:
        """分类用户咨询（类型 + 紧急度 + 是否需人工）

        Args:
            message: 用户消息

        Returns:
            分类结果，含类型、紧急度、是否需人工升级
        """
        # 1. 识别咨询类型
        inquiry_type = "other"
        type_name = "其他"
        type_scores = {}
        for itype in INQUIRY_TYPES:
            score = sum(1 for kw in itype["keywords"] if kw in message)
            type_scores[itype["code"]] = score
            if score > 0 and score >= type_scores.get(inquiry_type, 0):
                inquiry_type = itype["code"]
                type_name = itype["name"]

        # 2. 检查升级规则
        escalation = None
        for rule in ESCALATION_RULES:
            if any(kw in message for kw in rule["trigger_keywords"]):
                escalation = rule
                break

        need_human = False
        urgency = "low"
        escalate_reason = ""

        if escalation:
            need_human = escalation["need_human"]
            urgency = escalation["urgency"]
            escalate_reason = escalation["reason"]
        else:
            # 无明确升级规则时，根据咨询类型设定默认紧急度
            urgency_map = {
                "complaint": "high",
                "after_sale": "medium",
                "settlement": "medium",
            }
            urgency = urgency_map.get(inquiry_type, "low")

        # 3. 生成建议
        suggestions = self._generate_suggestions(inquiry_type, need_human)

        return {
            "inquiry_type": inquiry_type,
            "type_name": type_name,
            "urgency": urgency,
            "need_human": need_human,
            "escalate_reason": escalate_reason,
            "escalation_rule": escalation["code"] if escalation else None,
            "suggestions": suggestions,
            "reply": (
                f"咨询分类：{type_name}（紧急度：{urgency}）"
                + (f"，建议转人工处理（原因：{escalate_reason}）" if need_human else "，可由 AI 自动回复")
            ),
        }

    async def generate_response(self, user_message: str, context: str = "") -> str:
        """生成客服回复（调用 think）

        Args:
            user_message: 用户消息
            context: 对话上下文（可选）

        Returns:
            客服回复文本
        """
        try:
            return await self.think(user_message, context)
        except Exception:
            # LLM 不可用时，使用 FAQ 知识库兜底
            faq_result = self.answer_faq(user_message)
            if faq_result["found"]:
                return faq_result["answer"]
            return (
                "您好，我是索克家居 AI 客服。您的问题我已记录，"
                "稍后将由人工客服为您解答。您也可以拨打客服热线 400-xxx-xxxx。"
            )

    def generate_emotion_aware_reply(
        self, user_message: str, emotion: dict | None = None
    ) -> dict:
        """生成情绪感知增强回复

        Args:
            user_message: 用户消息
            emotion: 情绪检测结果 {"label": "anxious", "confidence": 0.8}

        Returns:
            {"reply": str, "emotion_label": str, "force_escalation": bool, "urgency_boost": bool}
        """
        # 情绪标签中文映射
        _emotion_names = {
            "anxious": "焦虑", "excited": "兴奋", "tired": "疲惫", "calm": "平静",
            "angry": "愤怒", "sad": "难过", "happy": "开心", "hesitant": "犹豫",
            "confident": "自信", "neutral": "中性",
        }

        emotion_label = emotion.get("label", "neutral") if emotion else "neutral"
        strategy = EMOTION_RESPONSE_STRATEGIES.get(emotion_label, {})

        # 基础回复
        faq_result = self.answer_faq(user_message)
        if faq_result["found"]:
            base_reply = faq_result["answer"]
        else:
            classify = self.classify_inquiry(user_message)
            if classify["need_human"]:
                base_reply = "您好，您的问题需要人工客服协助处理，正在为您转接人工客服，请稍候。"
            else:
                base_reply = "您好，我是索克家居 AI 客服。您的问题我已收到，请告诉我更多细节，我来帮您解答。"

        # 根据情绪添加前缀
        prefix = strategy.get("prefix", "")
        if prefix:
            base_reply = f"{prefix}\n\n{base_reply}"

        return {
            "reply": base_reply,
            "emotion_label": emotion_label,
            "emotion_name": _emotion_names.get(emotion_label, emotion_label),
            "tone": strategy.get("tone", "专业亲和"),
            "force_escalation": strategy.get("force_escalation", False),
            "urgency_boost": strategy.get("urgency_boost", False),
        }

    @staticmethod
    def detect_concierge_intent(message: str) -> str:
        """识别客服相关子意图"""
        if any(kw in message for kw in ["FAQ", "常见问题", "怎么", "什么是", "如何", "为什么"]):
            return "faq"
        if any(kw in message for kw in ["投诉", "举报", "差评", "不满"]):
            return "complaint"
        if any(kw in message for kw in ["售后", "保修", "维修", "漏水", "故障"]):
            return "after_sale"
        if any(kw in message for kw in ["退款", "退钱", "退货"]):
            return "refund"
        if any(kw in message for kw in ["帮助", "咨询", "客服", "人工", "转人工"]):
            return "help"
        if any(kw in message for kw in ["你好", "在吗", "请问", "hi", "hello"]):
            return "greeting"
        return "general"

    def _calculate_match_score(self, question: str, faq: dict) -> float:
        """计算问题与 FAQ 的匹配度评分

        Args:
            question: 用户问题
            faq: FAQ 条目

        Returns:
            匹配评分（0-1）
        """
        score = 0.0
        # 关键词匹配
        matched_keywords = sum(1 for kw in faq["keywords"] if kw in question)
        if matched_keywords > 0:
            score += matched_keywords / len(faq["keywords"]) * 0.7

        # 问题文本相似度（简单包含匹配）
        faq_question = faq["question"]
        common_chars = sum(1 for char in question if char in faq_question and char.strip())
        if common_chars > 0:
            score += min(common_chars / max(len(faq_question), 1) * 0.3, 0.3)

        return round(min(score, 1.0), 2)

    def _generate_suggestions(self, inquiry_type: str, need_human: bool) -> list[str]:
        """根据咨询类型生成建议"""
        if need_human:
            return ["转接人工客服", "留下联系方式", "查看处理进度"]

        suggestions_map = {
            "design": ["查看设计方案", "预约设计师", "查看案例"],
            "budget": ["获取预算明细", "调整预算方案", "导出预算报表"],
            "procurement": ["查看材料清单", "对比供应商", "发起采购"],
            "construction": ["查看施工进度", "查看质检报告", "预约验收"],
            "settlement": ["查看结算单", "确认付款", "导出对账单"],
            "after_sale": ["提交报修", "查看保修政策", "预约维修"],
            "complaint": ["转接人工客服", "提交投诉记录"],
            "other": ["查看常见问题", "转接人工客服"],
        }
        return suggestions_map.get(inquiry_type, suggestions_map["other"])


# ── 模块级函数 ──


def search_knowledge_base(keyword: str, category: str | None = None) -> dict:
    """搜索知识库

    Args:
        keyword: 搜索关键词
        category: 限定类别（可选）

    Returns:
        匹配的 FAQ 列表
    """
    results = []
    for faq in FAQ_KNOWLEDGE_BASE:
        if category and faq["category"] != category:
            continue
        # 关键词匹配
        if keyword in faq["question"] or keyword in faq["answer"] or any(keyword in kw for kw in faq["keywords"]):
            results.append({
                "id": faq["id"],
                "question": faq["question"],
                "answer": faq["answer"],
                "category": faq["category"],
            })

    return {
        "keyword": keyword,
        "category": category,
        "total": len(results),
        "results": results,
        "reply": f"搜索「{keyword}」找到 {len(results)} 条相关结果" if results else f"搜索「{keyword}」未找到相关结果",
    }


def list_faq_by_category(category: str) -> dict:
    """按类别列出 FAQ

    Args:
        category: 类别代码（design/budget/procurement/construction/settlement/qa）

    Returns:
        该类别的 FAQ 列表
    """
    faqs = [faq for faq in FAQ_KNOWLEDGE_BASE if faq["category"] == category]
    return {
        "category": category,
        "total": len(faqs),
        "faqs": [{"id": f["id"], "question": f["question"], "answer": f["answer"]} for f in faqs],
        "reply": f"「{category}」类别下共 {len(faqs)} 条 FAQ",
    }


def check_escalation(message: str) -> dict:
    """检查消息是否需要升级人工

    Args:
        message: 用户消息

    Returns:
        升级判定结果
    """
    for rule in ESCALATION_RULES:
        if any(kw in message for kw in rule["trigger_keywords"]):
            return {
                "need_human": rule["need_human"],
                "escalation_rule": rule["code"],
                "rule_name": rule["name"],
                "urgency": rule["urgency"],
                "reason": rule["reason"],
                "triggered_keywords": [kw for kw in rule["trigger_keywords"] if kw in message],
                "reply": f"检测到升级规则「{rule['name']}」，建议转人工处理（紧急度：{rule['urgency']}）",
            }

    return {
        "need_human": False,
        "escalation_rule": None,
        "urgency": "low",
        "reply": "未触发升级规则，可由 AI 自动回复",
    }


def get_all_faq_categories() -> dict:
    """获取所有 FAQ 类别统计"""
    category_stats = {}
    for faq in FAQ_KNOWLEDGE_BASE:
        cat = faq["category"]
        category_stats[cat] = category_stats.get(cat, 0) + 1

    return {
        "categories": [{"code": k, "count": v} for k, v in sorted(category_stats.items())],
        "total_faqs": len(FAQ_KNOWLEDGE_BASE),
        "reply": f"知识库共 {len(FAQ_KNOWLEDGE_BASE)} 条 FAQ，覆盖 {len(category_stats)} 个类别",
    }

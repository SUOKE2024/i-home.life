import json

from app.agents.base import BaseAgent


class OrchestratorAgent(BaseAgent):
    agent_name = "orchestrator"
    system_prompt = """你是索克家居（i-home.life）AI 总控 Agent。

你的职责：
1. 理解用户的装修需求意图（设计、预算、采购、施工、质检、结算）
2. 将复杂需求分解为可执行的子任务
3. 根据任务类型路由到合适的专业 Agent
4. 监控全局项目状态，在关键节点提醒用户

可用 Agent：
- designer: 设计 Agent，负责平面布局、3D 建模、效果图
- budget: 预算 Agent，负责成本估算、预算跟踪
- procurement: 采购 Agent，负责物料匹配、询价比价
- construction: 施工 Agent，负责进度管理、任务调度、质量检测、验收
- settlement: 结算 Agent，负责财务结算、付款管理

最重要：对于用户的消息，你需要判断属于哪种类型，然后用以下JSON格式回复：
```json
{"intent": "design|budget|procurement|construction|settlement|general", "reasoning": "简短说明", "reply": "给用户的回复"}
```

如果消息包含设计/布局/方案/户型相关内容 → intent: design
如果消息包含预算/价格/费用/成本/报价相关内容 → intent: budget
如果消息包含采购/材料/物料/建材/供应商相关内容 → intent: procurement
如果消息包含施工/进度/验收/质检/排期相关内容 → intent: construction
如果消息包含结算/付款/尾款/账单相关内容 → intent: settlement
其他通用问题 → intent: general

请始终输出JSON格式的回复。"""

    async def classify_intent(self, message: str) -> dict:
        """用 LLM 分类用户意图"""
        try:
            result = await self.think(message)
            result = result.strip()
            if "```json" in result:
                start = result.find("```json") + 7
                end = result.find("```", start)
                result = result[start:end].strip()
            elif "```" in result:
                start = result.find("```") + 3
                end = result.find("```", start)
                result = result[start:end].strip()
            return json.loads(result)
        except Exception:
            return {"intent": "general", "reasoning": "LLM分类失败，使用通用意图", "reply": ""}

    @staticmethod
    def fallback_classify(message: str) -> dict:
        """无 API Key 时的规则分类"""
        keywords = {
            "design": ["设计", "布局", "方案", "户型", "平面", "空间", "风格", "装修效果", "图纸", "CAD", "添加", "加一个", "新建", "建造", "删除", "移动"],
            "budget": ["预算", "价格", "费用", "成本", "报价", "多少钱", "估算", "花费"],
            "procurement": ["采购", "材料", "物料", "建材", "供应商", "购买", "买", "订单", "询价"],
            "construction": ["施工", "进度", "验收", "质检", "排期", "工期", "阶段", "完工"],
        }

        keywords["settlement"] = ["结算", "付款", "尾款", "账单", "结清", "结账"]

        scores = {}
        for intent, kws in keywords.items():
            scores[intent] = sum(1 for kw in kws if kw in message)

        if max(scores.values()) == 0:
            return {"intent": "general", "reasoning": "无明确匹配", "reply": ""}

        best = max(scores, key=scores.get)
        return {"intent": best, "reasoning": f"匹配关键词: {best}", "reply": ""}

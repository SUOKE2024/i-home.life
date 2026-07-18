import json
import logging

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    agent_name = "orchestrator"
    system_prompt = (
        """你是索克家居（i-home.life）AI 总控 Agent。

你的职责：
1. 理解用户的装修需求意图（设计、预算、采购、施工、质检、结算、客服）
2. 将复杂需求分解为可执行的子任务
3. 根据任务类型路由到合适的专业 Agent
4. 监控全局项目状态，在关键节点提醒用户

可用 Agent：
- designer: 设计 Agent，负责平面布局、3D 建模、效果图
- budget: 预算 Agent，负责成本估算、预算跟踪
- procurement: 采购 Agent，负责物料匹配、询价比价、内容发布
- construction: 施工 Agent，负责进度管理、任务调度、工人匹配（含木工、水电安装工、窗帘安装工等工种调度）
- qa_inspector: 质检 Agent，负责质量检测、验收报告、缺陷识别、图纸比对
- settlement: 结算 Agent，负责财务结算、付款管理
- concierge: 客服 Agent，负责 7×24 知识问答、咨询接待、问题升级
- content_publisher: 内容发布 Agent，辅助供应商在聊天中发布产品/服务

最重要：对于用户的消息，你需要判断属于哪种类型，然后用以下JSON格式回复：
```json
{
  "intent": "design|budget|procurement|construction|qa_inspector|settlement|concierge|content_publish|general",
  "reasoning": "简短说明",
  "reply": "给用户的回复"
}
```

如果消息包含设计/布局/方案/户型相关内容 → intent: design
如果消息包含预算/价格/费用/成本/报价相关内容 → intent: budget
如果消息包含采购/材料/物料/建材/供应商相关内容 → intent: procurement
如果消息包含施工/进度/排期/工期/阶段/完工/木工/水电安装工/水电工/窗帘安装工/工人/招工/派工相关内容 → intent: construction
如果消息包含质检/验收/缺陷/整改/返工/空鼓/裂缝/渗漏相关内容 → intent: qa_inspector
如果消息包含结算/付款/尾款/账单相关内容 → intent: settlement
如果消息包含咨询/帮助/投诉/售后/FAQ/常见问题相关内容 → intent: concierge
如果消息包含发布/上架/产品/商品/服务/推广相关内容 → intent: content_publish
其他通用问题 → intent: general

请始终输出JSON格式的回复。"""
    )

    async def classify_intent(self, message: str) -> dict:
        """用 LLM 分类用户意图

        LLM 调用失败时打印 warning 日志（避免静默降级），并回退到 fallback_classify
        规则分类，使意图路由至少与 /voice/process 行为一致。
        """
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
        except Exception as e:
            logger.warning(
                "classify_intent_llm_failed: msg=%r provider=%s error=%s; "
                "fallback to rule-based classify",
                message[:80], self.provider, e,
            )
            fallback = self.fallback_classify(message)
            fallback["reasoning"] = f"LLM分类失败({e})，使用规则分类"
            return fallback

    @staticmethod
    def fallback_classify(message: str) -> dict:
        """无 API Key 时的规则分类"""
        keywords = {
            "design": [
                "设计", "布局", "方案", "户型", "平面", "空间", "风格",
                "装修效果", "图纸", "CAD", "添加", "加一个",
                "新建", "建造", "删除", "移动",
            ],
            "budget": ["预算", "价格", "费用", "成本", "报价", "多少钱", "估算", "花费"],
            "procurement": ["采购", "材料", "物料", "建材", "供应商", "购买", "买", "订单", "询价"],
            "construction": ["施工", "进度", "排期", "工期", "阶段", "完工", "招工", "找人", "派工", "发布任务", "安排工人", "要一个",
                             "木工", "水电", "窗帘安装", "安装工", "电工", "水工"],
            "qa_inspector": ["质检", "验收", "缺陷", "整改", "返工", "空鼓", "裂缝", "渗漏", "色差", "平整度", "工艺缺陷", "验收报告"],
            "concierge": ["咨询", "帮助", "投诉", "售后", "FAQ", "常见问题", "客服", "转人工", "保修", "报修", "退款"],
            "content_publish": ["发布", "上架", "产品", "商品", "推广", "上新", "介绍产品", "发布产品",
                                "修改产品", "更新产品", "下架产品", "我的产品", "库存", "售罄", "缺货",
                                "改价格", "改描述", "编辑产品", "管理产品", "产品列表", "我的商品"],
            "admin": ["用户管理", "角色管理", "权限管理", "平台统计", "平台数据", "管理员", "禁用用户",
                      "启用用户", "审核认证", "系统管理", "设为管理员", "修改角色", "用户列表",
                      "全部项目", "所有用户"],
        }

        keywords["settlement"] = ["结算", "付款", "尾款", "账单", "结清", "结账"]

        scores = {}
        for intent, kws in keywords.items():
            scores[intent] = sum(1 for kw in kws if kw in message)

        if max(scores.values()) == 0:
            return {"intent": "general", "reasoning": "无明确匹配", "reply": ""}

        best = max(scores, key=scores.get)
        return {"intent": best, "reasoning": f"匹配关键词: {best}", "reply": ""}

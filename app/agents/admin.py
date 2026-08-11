"""管理 Agent — 处理管理员意图，执行平台管理操作"""

import logging

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class AdminAgent(BaseAgent):
    """平台管理 Agent — 用户管理、角色权限、平台统计。

    支持 FunctionCall 工具调用，自动识别管理意图并执行对应操作。
    v1.13.0（审计修复）：tools 从 tool_registry 拉取（category=admin），
    与内置工具统一契约（required 显式声明 + use-example 描述），
    避免内联 schema 与 registry 双源不一致（原内联工具若被 think_with_tools
    路径选中会返回「工具不存在」——广告了不可执行的工具，违反诚实降级）。
    """

    agent_name = "admin"
    cost_tier = "economy"  # 平台统计/管理低价值意图：优先低成本供应商
    system_prompt = """你是索克家居平台的管理 Agent（⚙️）。你可以执行以下管理操作：

1. **用户管理** — 列出用户、修改用户角色、启用/禁用用户
2. **权限管理** — 查看角色权限、修改角色权限
3. **平台统计** — 查看平台数据（项目数、用户数、材料数等）
4. **身份认证审核** — 查看待审核的实名认证申请

当用户请求管理操作时，你需要：
- 确认操作意图（列出/修改/查看）
- 如果需要修改，先向用户确认
- 执行后给出清晰的反馈

请用中文回复，语气专业但不生硬。回复格式为 Markdown。"""

    # v1.13.0：工具 schema 统一从 registry 拉取（单源契约）
    @property
    def tools(self) -> list[dict]:
        from app.services.agent_tool_registry import tool_registry
        return tool_registry.get_admin_openai_schemas()

    def classify_intent(self, message: str) -> dict:
        """基于关键词的意图分类（mock 模式兜底）"""
        lower = message.lower()
        if any(kw in lower for kw in ["用户", "角色", "权限", "管理员", "禁用", "启用"]):
            intent = "user_manage"
        elif any(kw in lower for kw in ["统计", "数据", "概况", "平台"]):
            intent = "platform_stats"
        elif any(kw in lower for kw in ["认证", "实名", "审核"]):
            intent = "identity_review"
        else:
            intent = "general"
        return {"intent": intent, "confidence": 0.9}

    async def handle_admin_request(self, message: str, user_name: str) -> str:
        """处理管理请求 — 意图分类 + 自然语言回复"""
        classification = self.classify_intent(message)
        intent = classification["intent"]

        if intent == "user_manage":
            return self._mock_user_manage_reply(message, user_name)
        elif intent == "platform_stats":
            return self._mock_platform_stats_reply()
        elif intent == "identity_review":
            return self._mock_identity_review_reply()
        else:
            return self._mock_general_reply()

    def _mock_user_manage_reply(self, message: str, user_name: str) -> str:
        lower = message.lower()
        if "角色" in lower or "改成" in lower or "设为" in lower or "提升" in lower:
            return (
                "⚙️ **角色修改确认**\n\n"
                f"管理员 {user_name}，我理解您想要修改用户角色。\n\n"
                "请确认以下信息：\n"
                "- 目标用户的手机号或 ID\n"
                "- 要设置的新角色（homeowner / designer / contractor / supplier / admin）\n\n"
                "示例：`把用户 13800138000 的角色改为 designer`\n\n"
                "⚠️ 请通过管理 API 直接操作，或提供完整信息后我为您执行。"
            )
        elif "禁用" in lower or "启用" in lower:
            return (
                "⚙️ **用户状态管理**\n\n"
                "请提供：\n"
                "- 用户手机号或 ID\n"
                "- 操作类型（启用/禁用）\n\n"
                "示例：`禁用用户 13800138000`"
            )
        elif "列表" in lower or "查看" in lower or "所有" in lower:
            return (
                "⚙️ **用户列表查询**\n\n"
                "我可以为您列出用户。支持以下筛选条件：\n"
                "- 角色：homeowner / designer / contractor / supplier / admin\n"
                "- 状态：已激活 / 已禁用\n\n"
                "请问需要按什么条件筛选？"
            )
        return (
            "⚙️ **用户管理**\n\n"
            "我可以帮您：\n"
            "- 查看用户列表（支持按角色/状态筛选）\n"
            "- 修改用户角色\n"
            "- 启用/禁用用户账户\n\n"
            "请告诉我具体操作内容。"
        )

    def _mock_platform_stats_reply(self) -> str:
        return (
            "⚙️ **平台统计**\n\n"
            "请通过管理 API `/api/admin/stats` 获取实时数据。\n\n"
            "统计维度包括：\n"
            "- 总项目数 / 活跃项目数\n"
            "- 总用户数 / 本周新增用户\n"
            "- 待审核认证数\n"
            "- 材料 SKU 数 / 供应商数\n\n"
            "需要我帮您查询当前数据吗？"
        )

    def _mock_identity_review_reply(self) -> str:
        return (
            "⚙️ **实名认证审核**\n\n"
            "您可以查看待审核的实名认证申请，并通过 `/api/identity/{id}/review` 进行审核。\n\n"
            "操作：\n"
            "- 查看待审核列表：`GET /api/identity/pending`\n"
            "- 审核通过/拒绝：`POST /api/identity/{id}/review`\n\n"
            "需要我列出当前待审核的申请吗？"
        )

    def _mock_general_reply(self) -> str:
        return (
            "⚙️ **管理 Agent 功能列表**\n\n"
            "我可以帮您执行以下管理操作：\n\n"
            "**用户管理**\n"
            "- 查看用户列表 `查看所有设计师`\n"
            "- 修改角色 `把用户 xxx 设为 admin`\n"
            "- 启用/禁用用户\n\n"
            "**平台概况**\n"
            "- 查看平台统计数据\n\n"
            "**权限管理**\n"
            "- 查看角色权限\n"
            "- 修改角色权限\n\n"
            "请告诉我您的具体需求。"
        )

"""内容发布 Agent — 辅助供应商在聊天中发布产品/服务，管理产品信息"""

import logging
import re

from app.agents.base import BaseAgent
from app.agents.procurement import (
    PRODUCT_CATEGORY_MAP,
    PRODUCT_UNIT_MAP,
)

logger = logging.getLogger(__name__)


class ContentPublisherAgent(BaseAgent):
    """内容发布 Agent — 产品上架、编辑、下架、文案生成。

    从 ProcurementAgent 中独立出来，专门处理供应商角色的产品管理需求。
    支持 FunctionCall 工具调用和 mock 模式规则匹配。
    """

    agent_name = "content_publisher"
    system_prompt = """你是索克家居（i-home.life）AI 内容发布 Agent（🛒）。

你的职责：
1. 协助供应商在聊天中发布产品/服务信息
2. 提取产品信息（名称、类别、价格、规格、描述、标签）
3. 生成产品文案和预览卡片
4. 管理产品状态（草稿/已发布/已下架/售罄）
5. 引导供应商补全缺失的产品信息

产品类别：
- 瓷砖、地板、涂料、橱柜、卫浴、灯具、家电、窗帘、定制家具、服务

回复格式：
- 信息完整时：输出产品预览卡片（Markdown 表格 + 描述）
- 信息不完整时：友好引导供应商补充缺失字段，列出需要确认的项
- 产品管理操作：给出明确的操作指引

请用中文回复，语气专业、高效。"""

    # ── 意图分类 ──

    @staticmethod
    def classify_intent(message: str) -> str:
        """识别产品管理意图"""
        lower = message.lower()
        if any(kw in lower for kw in ["下架", "归档", "删除产品"]):
            return "archive_product"
        if any(kw in lower for kw in ["修改", "更新", "改价格", "改描述", "编辑"]):
            return "update_product"
        if any(kw in lower for kw in ["列表", "产品列表", "我的商品"]):
            return "list_my_products"
        if any(kw in lower for kw in ["发布到", "上架到", "推送到项目", "发布产品"]):
            return "publish_product"
        if any(kw in lower for kw in ["库存", "售罄", "缺货", "有货", "补货"]):
            return "update_stock"
        # 默认：新建产品
        return "create_product"

    # ── 产品信息提取 ──

    @staticmethod
    def extract_product_info(message: str) -> dict:  # noqa: C901
        """从自然语言中提取产品信息"""
        info: dict = {
            "name": "",
            "category": "",
            "price_min": None,
            "price_max": None,
            "unit": "",
            "description": "",
            "tags": [],
            "stock_status": "in_stock",
        }

        # 提取分类
        for kw, cat in PRODUCT_CATEGORY_MAP.items():
            if kw in message:
                info["category"] = cat
                info["unit"] = PRODUCT_UNIT_MAP.get(cat, "")
                break

        # 提取价格：匹配 "XX元"、"XX 元"、"¥XX" 等模式
        price_patterns = [
            r'(\d+\.?\d*)\s*元?\s*[-~到]\s*(\d+\.?\d*)\s*元?',
            r'¥\s*(\d+\.?\d*)\s*[-~到]\s*¥?\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*元\s*/\s*[每]?\s*(\S+)',
            r'(\d+\.?\d*)\s*元',
        ]
        for pattern in price_patterns:
            m = re.search(pattern, message)
            if m:
                groups = m.groups()
                if len(groups) == 3 and groups[2]:
                    # 单价模式
                    info["price_min"] = float(groups[0])
                    info["price_max"] = float(groups[0])
                    if not info["unit"]:
                        info["unit"] = groups[2]
                elif len(groups) >= 2:
                    # 价格区间 OR 单价+单位模式
                    try:
                        # 尝试解析第二个组为数字（价格区间）
                        info["price_min"] = float(groups[0])
                        info["price_max"] = float(groups[1])
                    except ValueError:
                        # 第二个组不是数字 → 单价模式
                        info["price_min"] = float(groups[0])
                        info["price_max"] = float(groups[0])
                        if not info["unit"]:
                            info["unit"] = groups[1]
                elif len(groups) == 1:
                    info["price_min"] = float(groups[0])
                    info["price_max"] = float(groups[0])
                break

        # 提取标签：匹配 #xxx 格式
        tag_matches = re.findall(r'#(\S+)', message)
        if tag_matches:
            info["tags"] = tag_matches[:5]

        # 提取产品名称
        if info["category"]:
            for kw_cn, cat_code in PRODUCT_CATEGORY_MAP.items():
                if cat_code == info["category"] and kw_cn in message:
                    idx = message.index(kw_cn)
                    prefix = message[:idx].strip().rstrip("，。！？；：、")
                    name_prefix = prefix[-20:] if len(prefix) > 20 else prefix
                    info["name"] = (name_prefix.strip() + kw_cn).strip()
                    break
            if not info["name"]:
                info["name"] = f"{info['category']}产品"

        if not info["name"]:
            info["name"] = message[:30].strip()

        # 提取描述
        if info["name"] and info["name"] in message:
            remaining = message[message.index(info["name"]) + len(info["name"]):]
            remaining = re.sub(r'\d+\.?\d*\s*元[^\s，。]*', '', remaining)
            remaining = re.sub(r'#\S+', '', remaining)
            desc = remaining.strip().lstrip("，。！？；：、").strip()
            if desc and len(desc) > 3:
                info["description"] = desc[:200]

        return info

    # ── Mock 模式处理 ──

    def handle_product_request(self, message: str, user_name: str) -> str:
        """处理产品管理请求（mock 模式）"""
        intent = self.classify_intent(message)

        if intent == "create_product":
            info = self.extract_product_info(message)
            if info["name"] and info["category"]:
                price_str = info['price_min'] or '—'
                if info.get('price_max') and info['price_max'] != info['price_min']:
                    price_str = f"{info['price_min']}-{info['price_max']} {info['unit'] or ''}"
                elif info['unit']:
                    price_str = f"{info['price_min']} 元/{info['unit']}" if info['price_min'] else '—'
                return (
                    "🛒 **产品信息已识别**\n\n"
                    f"| 字段 | 值 |\n"
                    f"|------|----|\n"
                    f"| 名称 | {info['name']} |\n"
                    f"| 分类 | {info['category']} |\n"
                    f"| 价格 | {price_str} |\n"
                    f"| 标签 | {', '.join(info['tags']) if info['tags'] else '—'} |\n"
                    f"| 描述 | {info['description'][:60] or '—'} |\n\n"
                    f"请在管理面板确认并发布。\n"
                    f"或说「发布产品」以通过 API 创建。"
                )
            else:
                return (
                    "🛒 **产品发布助手**\n\n"
                    "请提供以下信息：\n\n"
                    "1. **产品名称和规格**：如「800×800灰色防滑地砖」\n"
                    "2. **类别**：瓷砖/地板/橱柜/涂料/灯具/家电/窗帘/定制家具/服务\n"
                    "3. **价格**：如「58元/㎡」或「50-80元/㎡」\n"
                    "4. **标签**：#防滑 #灰色 #客厅\n"
                    "5. **描述**：材质、产地、卖点等（可选）\n\n"
                    "示例：`上架 800×800 灰色防滑地砖，佛山产，58元/㎡ #防滑 #灰色`"
                )

        elif intent == "list_my_products":
            return (
                "🛒 **我的产品**\n\n"
                "请通过 API 获取您的产品列表：\n"
                "`GET /api/products/mine`\n\n"
                "支持按状态筛选：`?status=draft` 或 `?status=published`"
            )

        elif intent == "update_product":
            return (
                "🛒 **产品更新**\n\n"
                "请提供：\n"
                "- 产品 ID 或名称\n"
                "- 要修改的字段（价格/描述/标签/库存）\n\n"
                "示例：`把产品 #abc123 的价格改成 68 元`"
            )

        elif intent == "archive_product":
            return (
                "🛒 **产品下架**\n\n"
                "请提供要下架的产品 ID 或名称。\n\n"
                "示例：`下架产品 #abc123`"
            )

        elif intent == "publish_product":
            return (
                "🛒 **产品发布**\n\n"
                "请提供产品 ID 和目标项目 ID，\n"
                "我将通过 WebSocket 推送产品卡片到项目聊天室。\n\n"
                "示例：`发布产品 #abc123 到项目 #xyz789`"
            )

        elif intent == "update_stock":
            return (
                "🛒 **库存更新**\n\n"
                "支持状态：in_stock（有货）/ pre_order（预售）/ out_of_stock（售罄）\n\n"
                "示例：`产品 #abc123 已售罄`"
            )

        return (
            "🛒 **产品管理**\n\n"
            "我可以帮您：\n"
            "- 创建新产品\n"
            "- 查看产品列表\n"
            "- 修改产品信息（价格/描述/标签）\n"
            "- 发布产品到项目聊天室\n"
            "- 下架/归档产品\n\n"
            "请告诉我具体操作。"
        )

    # ── LLM 模式：内容发布引导 ──

    async def generate_content_publish_reply(self, message: str, user_name: str = "") -> str:
        """LLM 模式：辅助供应商在聊天中发布产品/服务"""
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

"""Agent 工具注册表 —— FunctionCall / MCP 工具集

提供 Agent 的工具注册、发现和执行能力：
- 内置工具集（预算查询、设计布局、物料搜索、施工进度、质检报告等）
- MCP 工具服务器集成
- FunctionCall 协议适配
"""

import asyncio
import logging
from typing import Any, Callable, Coroutine

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


# ── 工具定义 ──

class AgentTool:
    """Agent 可调用的工具"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable[..., Coroutine[Any, Any, Any]] | Callable[..., Any],
        category: str = "general",
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler
        self.category = category

    def to_openai_schema(self) -> dict:
        """转换为 OpenAI FunctionCall 兼容的 schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": list(self.parameters.keys()),
                },
            },
        }

    def to_qwen_schema(self) -> dict:
        """转换为 Qwen-Audio FunctionCall 兼容的 schema"""
        return self.to_openai_schema()

    async def execute(self, **kwargs) -> Any:
        """执行工具调用"""
        try:
            if asyncio.iscoroutinefunction(self.handler):
                return await self.handler(**kwargs)
            return self.handler(**kwargs)
        except Exception as e:
            logger.error(f"tool_execution_error: tool={self.name}, error={e}")
            return {"error": str(e)}


# ── 内置工具实现 ──

async def _tool_get_budget(project_id: str = "", area: float = 0, style: str = "") -> dict:
    """查询装修预算"""
    if not area:
        area = 100
    tiers = {
        "economy": {"label": "经济型", "range": (800, 1200), "total": area * 1000},
        "comfort": {"label": "舒适型", "range": (1200, 2000), "total": area * 1600},
        "quality": {"label": "品质型", "range": (2000, 3500), "total": area * 2750},
        "luxury": {"label": "豪华型", "range": (3500, 9999), "total": area * 5000},
    }

    breakdown = {
        "hard_decoration": {"label": "硬装（水电+墙面+地面）", "ratio": 0.42},
        "custom_furniture": {"label": "定制柜体", "ratio": 0.18},
        "soft_furnishing": {"label": "软装+家电", "ratio": 0.30},
        "management": {"label": "管理费+其他", "ratio": 0.10},
    }

    result = {
        "area": area,
        "style": style or "现代简约",
        "tiers": {},
    }
    for key, tier in tiers.items():
        result["tiers"][key] = {
            "label": tier["label"],
            "price_per_sqm": f"{tier['range'][0]}-{tier['range'][1]}元/㎡",
            "total_estimate": round(tier["total"]),
            "breakdown": {
                v["label"]: round(tier["total"] * v["ratio"])
                for v in breakdown.values()
            },
        }

    return result


async def _tool_get_design_layout(area: float = 100, style: str = "modern", rooms: str = "") -> dict:
    """获取装修设计方案"""
    layouts = {
        "modern": {"name": "现代简约", "colors": ["白色", "灰色", "原木色"], "features": ["开放式厨房", "无主灯设计"]},
        "nordic": {"name": "北欧风", "colors": ["米白", "浅灰", "莫兰迪蓝"], "features": ["原木地板", "简约线条"]},
        "japanese": {"name": "日式侘寂", "colors": ["原木色", "奶油白", "灰绿"], "features": ["榻榻米", "障子门"]},
        "luxury": {"name": "轻奢风", "colors": ["深灰", "金色点缀", "大理石纹"], "features": ["金属线条", "水晶吊灯"]},
        "chinese": {"name": "新中式", "colors": ["胡桃木", "朱红", "水墨黑"], "features": ["中式格栅", "回字纹"]},
    }

    style_info = layouts.get(style, layouts["modern"])
    room_list = [r.strip() for r in rooms.split(",") if r.strip()] if rooms else ["客厅", "卧室", "厨房", "卫生间"]

    return {
        "area": area,
        "style": style_info["name"],
        "color_palette": style_info["colors"],
        "design_features": style_info["features"],
        "rooms": room_list,
        "estimated_duration_days": 45,
    }


async def _tool_search_materials(category: str = "", keyword: str = "", budget_range: str = "") -> dict:
    """搜索装修物料"""
    material_db = {
        "瓷砖": [
            {"name": "东鹏灰色防滑地砖", "size": "800×800mm", "price": "68-88元/㎡", "rating": 4.8},
            {"name": "马可波罗大理石纹", "size": "600×1200mm", "price": "120-160元/㎡", "rating": 4.7},
            {"name": "诺贝尔白色亮面砖", "size": "800×800mm", "price": "55-75元/㎡", "rating": 4.5},
        ],
        "地板": [
            {"name": "圣象强化复合地板", "thickness": "12mm", "price": "120-180元/㎡", "rating": 4.6},
            {"name": "大自然实木复合", "thickness": "15mm", "price": "280-350元/㎡", "rating": 4.8},
        ],
        "涂料": [
            {"name": "立邦净味全效", "type": "乳胶漆", "price": "25-35元/㎡", "rating": 4.7},
            {"name": "多乐士森呼吸", "type": "乳胶漆", "price": "30-40元/㎡", "rating": 4.6},
        ],
    }

    results = []
    for mat_category, items in material_db.items():
        if category and category not in mat_category:
            continue
        for item in items:
            if keyword and keyword not in item["name"] and keyword not in mat_category:
                continue
            results.append({"category": mat_category, **item})

    return {
        "keyword": keyword,
        "category": category,
        "total": len(results),
        "results": results[:5],
    }


async def _tool_get_progress(project_id: str = "") -> dict:
    """查询施工进度"""
    phases = [
        {"name": "准备阶段", "progress": 100, "days": "1-3天"},
        {"name": "拆改阶段", "progress": 100, "days": "4-8天"},
        {"name": "水电阶段", "progress": 85, "days": "9-18天"},
        {"name": "泥瓦阶段", "progress": 40, "days": "19-32天"},
        {"name": "木工阶段", "progress": 0, "days": "26-35天"},
        {"name": "油漆阶段", "progress": 0, "days": "33-40天"},
        {"name": "安装阶段", "progress": 0, "days": "40-43天"},
        {"name": "验收阶段", "progress": 0, "days": "44-45天"},
    ]

    total = sum(p["progress"] for p in phases) / len(phases)
    return {
        "project_id": project_id or "current",
        "overall_progress": round(total, 1),
        "phases": phases,
        "estimated_remaining_days": 18,
    }


async def _tool_run_qa_inspection(project_id: str = "", phase: str = "", categories: str = "") -> dict:
    """执行质检"""
    inspection_items = [
        {"name": "水管打压测试", "standard": "0.8MPa/30min不掉压", "status": "pass"},
        {"name": "电路绝缘测试", "standard": "≥0.5MΩ", "status": "pass"},
        {"name": "防水闭水试验", "standard": "48h无渗漏", "status": "pass"},
        {"name": "瓷砖空鼓检测", "standard": "空鼓率<5%", "status": "pass"},
        {"name": "墙面平整度", "standard": "2m靠尺≤3mm", "status": "pass"},
        {"name": "阴阳角方正", "standard": "偏差≤3mm", "status": "warning"},
    ]

    cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else []
    if cat_list:
        inspection_items = [
            i for i in inspection_items
            if any(c in i["name"] for c in cat_list)
        ]

    passed = sum(1 for i in inspection_items if i["status"] == "pass")
    total = len(inspection_items)

    return {
        "project_id": project_id or "current",
        "phase": phase or "all",
        "total_items": total,
        "passed": passed,
        "pass_rate": round(passed / max(total, 1) * 100, 1),
        "items": inspection_items,
        "conclusion": "合格" if passed / max(total, 1) >= 0.85 else "需整改",
    }


# ── 工具注册表 ──

BUILTIN_TOOLS: list[AgentTool] = [
    AgentTool(
        name="get_budget",
        description="查询装修预算。根据面积和风格返回经济型/舒适型/品质型/豪华型四档预算估算，包含硬装、定制柜体、软装、管理费的详细分项。",
        parameters={
            "area": {"type": "number", "description": "房屋面积（平方米）"},
            "style": {"type": "string", "description": "装修风格：modern/nordic/japanese/luxury/chinese"},
            "project_id": {"type": "string", "description": "项目ID（可选）"},
        },
        handler=_tool_get_budget,
        category="budget",
    ),
    AgentTool(
        name="get_design_layout",
        description="获取装修设计方案。根据面积和风格返回配色方案、设计特点、房间规划和预估工期。",
        parameters={
            "area": {"type": "number", "description": "房屋面积（平方米）"},
            "style": {"type": "string", "description": "装修风格：modern/nordic/japanese/luxury/chinese"},
            "rooms": {"type": "string", "description": "房间列表，逗号分隔（如：客厅,卧室,厨房）"},
        },
        handler=_tool_get_design_layout,
        category="design",
    ),
    AgentTool(
        name="search_materials",
        description="搜索装修物料。按类别和关键词搜索瓷砖、地板、涂料等材料，返回价格、规格和评分。",
        parameters={
            "category": {"type": "string", "description": "物料类别：瓷砖/地板/涂料"},
            "keyword": {"type": "string", "description": "搜索关键词"},
            "budget_range": {"type": "string", "description": "预算范围（可选）"},
        },
        handler=_tool_search_materials,
        category="procurement",
    ),
    AgentTool(
        name="get_construction_progress",
        description="查询施工进度。返回项目整体进度、各阶段完成情况和预估剩余天数。",
        parameters={
            "project_id": {"type": "string", "description": "项目ID"},
        },
        handler=_tool_get_progress,
        category="construction",
    ),
    AgentTool(
        name="run_qa_inspection",
        description="执行质量检测。对指定阶段进行质检，返回各检测项的状态和合格率。",
        parameters={
            "project_id": {"type": "string", "description": "项目ID"},
            "phase": {"type": "string", "description": "检测阶段：waterproof/electric/tile/paint"},
            "categories": {"type": "string", "description": "检测类别，逗号分隔"},
        },
        handler=_tool_run_qa_inspection,
        category="qa",
    ),
]


class ToolRegistry:
    """工具注册表（单例）"""

    _instance = None
    _tools: dict[str, AgentTool] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_builtin_tools()
        return cls._instance

    def _init_builtin_tools(self):
        for tool in BUILTIN_TOOLS:
            self.register(tool)

    def register(self, tool: AgentTool):
        self._tools[tool.name] = tool
        logger.debug(f"tool_registered: {tool.name} [{tool.category}]")

    def get(self, name: str) -> AgentTool | None:
        return self._tools.get(name)

    def list_tools(self, category: str | None = None) -> list[AgentTool]:
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def get_openai_schemas(self) -> list[dict]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def get_openai_schemas_for_category(self, category: str) -> list[dict]:
        """获取指定类别的工具 OpenAI schemas"""
        return [t.to_openai_schema() for t in self.list_tools(category)]

    def get_qwen_schemas(self) -> list[dict]:
        return [t.to_qwen_schema() for t in self._tools.values()]

    async def execute(self, name: str, arguments: dict) -> Any:
        tool = self.get(name)
        if not tool:
            return {"error": f"工具不存在: {name}"}
        logger.info(f"tool_execute: {name}, args={arguments}")
        return await tool.execute(**arguments)

    @property
    def tool_count(self) -> int:
        return len(self._tools)


tool_registry = ToolRegistry()

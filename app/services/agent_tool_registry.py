"""Agent 工具注册表 —— FunctionCall / MCP 工具集

提供 Agent 的工具注册、发现和执行能力：
- 内置工具集（预算查询、设计布局、物料搜索、施工进度、质检报告等）
- MCP 工具服务器集成
- FunctionCall 协议适配

v1.1.31 FP-1 修复：原 5 个内置工具 handler 返回硬编码假数据（"真实协议 +
假数据" 伪专业模式）。现由 ``settings.tool_real_data_enabled`` 控制：
- True（默认）+ 传入 db session：查真实 DB，查无记录或异常时回退样例
- False：回滚到硬编码样例（紧急回滚用）

隐式上下文参数 ``_db`` / ``_project_id`` 由 ``ToolRegistry.execute`` 注入，
不暴露在 OpenAI schema 中（下划线前缀避免与 LLM 提供的 ``project_id`` 冲突）。
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
        """执行工具调用

        v1.1.31: 透传 ``_db`` / ``_project_id`` 隐式上下文参数给 handler。
        这两个参数不暴露在 schema 中，由 ToolRegistry.execute 注入。
        """
        try:
            if asyncio.iscoroutinefunction(self.handler):
                return await self.handler(**kwargs)
            return self.handler(**kwargs)
        except Exception as e:
            logger.error(f"tool_execution_error: tool={self.name}, error={e}")
            return {"error": str(e)}


# ── 内置工具实现 ──
#
# 设计约定（v1.1.31 FP-1）：
# - 每个 handler 接收 ``_db=None, _project_id=""`` 隐式参数（由 ToolRegistry 注入）
# - 当 ``settings.tool_real_data_enabled and _db is not None`` 时查真实 DB
# - 查询命中：返回 ``source="db"`` 的真实结果
# - 查无记录 / 异常 / flag 关闭：回退到原硬编码样例，``source`` 标记为 ``*_fallback``
# - ``effective_pid = project_id or _project_id``：LLM 提供的 project_id 优先，
#   否则用对话上下文的 _project_id

# 施工阶段中文映射（DB phase → 中文名）
_PHASE_CN = {
    "preparation": "准备阶段", "demolition": "拆改阶段",
    "water_electricity": "水电阶段", "electrical": "电气阶段",
    "waterproof": "防水阶段", "masonry": "泥瓦阶段",
    "mep": "机电阶段", "carpentry": "木工阶段",
    "painting": "油漆阶段", "installation": "安装阶段",
    "completion": "竣工阶段", "inspection": "验收阶段",
}

# QualityIssue.status → 质检项状态映射
_QA_STATUS_MAP = {
    "open": "fail",         # 待处理 = 不合格
    "in_progress": "warning",  # 整改中 = 警告
    "resolved": "pass",     # 已整改 = 合格
    "verified": "pass",     # 已验收 = 合格
    "closed": "pass",       # 已关闭 = 合格
}


async def _tool_get_budget(
    project_id: str = "", area: float = 0, style: str = "",
    _db=None, _project_id: str = "",
) -> dict:
    """查询装修预算"""
    effective_pid = project_id or _project_id

    # v1.1.31 FP-1: 真实 DB 查询
    if settings.tool_real_data_enabled and _db is not None and effective_pid:
        try:
            from sqlalchemy import select
            from app.models.budget import Budget, BudgetLine
            stmt = (
                select(Budget, BudgetLine)
                .join(BudgetLine, BudgetLine.budget_id == Budget.id, isouter=True)
                .where(Budget.project_id == effective_pid, Budget.deleted_at.is_(None))
            )
            result = await _db.execute(stmt)
            rows = result.all()
            if rows and rows[0][0] is not None:
                budget = rows[0][0]
                lines = [r[1] for r in rows if r[1] is not None]
                by_category: dict[str, float] = {}
                for line in lines:
                    by_category[line.category] = by_category.get(line.category, 0.0) + line.estimated_amount
                return {
                    "source": "db",
                    "project_id": effective_pid,
                    "area": area or 0,
                    "style": style or "",
                    "total_estimated": round(budget.total_estimated, 2),
                    "total_actual": round(budget.total_actual, 2),
                    "status": budget.status,
                    "line_count": len(lines),
                    "breakdown_by_category": {k: round(v, 2) for k, v in by_category.items()},
                    "lines": [
                        {
                            "category": l.category, "name": l.name,
                            "estimated": round(l.estimated_amount, 2),
                            "quantity": l.quantity, "unit": l.unit,
                            "unit_price": round(l.unit_price, 2),
                        } for l in lines[:20]
                    ],
                }
            logger.debug("_tool_get_budget: 项目 %s 无预算记录，回退估算", effective_pid)
        except Exception as e:
            logger.warning("_tool_get_budget: DB 查询失败，回退估算: %s", e)

    # 回退：基于面积的行业估算样例（source 标记，便于区分）
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
        "source": "estimated_fallback",
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


async def _tool_get_design_layout(
    area: float = 100, style: str = "modern", rooms: str = "",
    _db=None, _project_id: str = "",
) -> dict:
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

    # v1.1.31 FP-1: 风格调色板是合法设计目录数据；真实化的是项目房间列表
    # Room 通过 floor_id → Floor.project_id 关联项目（Room 无直接 project_id）
    real_rooms: list[dict] = []
    source = "catalog"
    if settings.tool_real_data_enabled and _db is not None and _project_id:
        try:
            from sqlalchemy import select
            from app.models.project import Room, Floor
            stmt = (
                select(Room)
                .join(Floor, Floor.id == Room.floor_id)
                .where(Floor.project_id == _project_id)
            )
            result = await _db.execute(stmt)
            rooms_db = result.scalars().all()
            if rooms_db:
                real_rooms = [
                    {"name": r.name, "area": r.area, "room_type": r.room_type}
                    for r in rooms_db
                ]
                room_list = [r.name for r in rooms_db]
                source = "db"
        except Exception as e:
            logger.warning("_tool_get_design_layout: 房间 DB 查询失败，回退默认房间列表: %s", e)

    return {
        "source": source,
        "area": area,
        "style": style_info["name"],
        "color_palette": style_info["colors"],
        "design_features": style_info["features"],
        "rooms": room_list,
        "real_rooms": real_rooms,
        "estimated_duration_days": 45,
    }


async def _tool_search_materials(
    category: str = "", keyword: str = "", budget_range: str = "",
    _db=None, _project_id: str = "",
) -> dict:
    """搜索装修物料"""
    # v1.1.31 FP-1: 真实 DB 查询 Material 表
    if settings.tool_real_data_enabled and _db is not None:
        try:
            from sqlalchemy import select, or_
            from app.models.material import Material, MaterialCategory
            stmt = (
                select(Material, MaterialCategory.name.label("category_name"))
                .join(MaterialCategory, MaterialCategory.id == Material.category_id, isouter=True)
                .where(Material.is_active.is_(True), Material.deleted_at.is_(None))
            )
            if category:
                stmt = stmt.where(MaterialCategory.name.like(f"%{category}%"))
            if keyword:
                stmt = stmt.where(or_(
                    Material.name.like(f"%{keyword}%"),
                    Material.brand.like(f"%{keyword}%"),
                    Material.sku.like(f"%{keyword}%"),
                ))
            stmt = stmt.limit(20)
            result = await _db.execute(stmt)
            rows = result.all()
            if rows:
                results = []
                for mat, cat_name in rows:
                    results.append({
                        "category": cat_name or "",
                        "name": mat.name,
                        "brand": mat.brand or "",
                        "spec": mat.spec or "",
                        "sku": mat.sku,
                        "unit": mat.unit,
                        "unit_price": round(mat.unit_price, 2),
                        "price": f"{mat.unit_price}元/{mat.unit}",
                    })
                return {
                    "source": "db",
                    "keyword": keyword,
                    "category": category,
                    "total": len(results),
                    "results": results[:5],
                }
            logger.debug("_tool_search_materials: DB 无匹配物料，回退样例库")
        except Exception as e:
            logger.warning("_tool_search_materials: DB 查询失败，回退样例库: %s", e)

    # 回退：行业样例库（source 标记）
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
        "source": "sample_fallback",
        "keyword": keyword,
        "category": category,
        "total": len(results),
        "results": results[:5],
    }


async def _tool_get_progress(
    project_id: str = "", _db=None, _project_id: str = "",
) -> dict:
    """查询施工进度"""
    effective_pid = project_id or _project_id

    # v1.1.31 FP-1: 真实 DB 查询 ConstructionTask 按 phase 聚合
    if settings.tool_real_data_enabled and _db is not None and effective_pid:
        try:
            from sqlalchemy import select, func
            from app.models.construction import ConstructionTask
            stmt = (
                select(
                    ConstructionTask.phase,
                    ConstructionTask.status,
                    func.count().label("cnt"),
                )
                .where(
                    ConstructionTask.project_id == effective_pid,
                    ConstructionTask.deleted_at.is_(None),
                )
                .group_by(ConstructionTask.phase, ConstructionTask.status)
            )
            result = await _db.execute(stmt)
            rows = result.all()
            if rows:
                phase_stats: dict[str, dict] = {}
                for phase, status, cnt in rows:
                    if phase not in phase_stats:
                        phase_stats[phase] = {"total": 0, "completed": 0, "in_progress": 0, "pending": 0}
                    phase_stats[phase]["total"] += cnt
                    if status == "completed":
                        phase_stats[phase]["completed"] += cnt
                    elif status == "in_progress":
                        phase_stats[phase]["in_progress"] += cnt
                    else:
                        phase_stats[phase]["pending"] += cnt

                phases = []
                total_weighted = 0.0
                total_tasks = 0
                # 按 CONSTRUCTION_PHASES 顺序输出
                phase_order = [
                    "preparation", "demolition", "water_electricity", "electrical",
                    "waterproof", "masonry", "mep", "carpentry",
                    "painting", "installation", "completion", "inspection",
                ]
                for phase in phase_order:
                    if phase not in phase_stats:
                        continue
                    stats = phase_stats[phase]
                    if stats["total"] == 0:
                        continue
                    progress = round(
                        (stats["completed"] + 0.5 * stats["in_progress"]) / stats["total"] * 100, 1
                    )
                    phases.append({
                        "name": _PHASE_CN.get(phase, phase),
                        "phase_code": phase,
                        "progress": progress,
                        "tasks_total": stats["total"],
                        "tasks_completed": stats["completed"],
                        "tasks_in_progress": stats["in_progress"],
                    })
                    total_weighted += progress * stats["total"]
                    total_tasks += stats["total"]

                overall = round(total_weighted / max(total_tasks, 1), 1) if total_tasks else 0
                return {
                    "source": "db",
                    "project_id": effective_pid,
                    "overall_progress": overall,
                    "phases": phases,
                    "total_tasks": total_tasks,
                }
            logger.debug("_tool_get_progress: 项目 %s 无施工任务，回退样例", effective_pid)
        except Exception as e:
            logger.warning("_tool_get_progress: DB 查询失败，回退样例: %s", e)

    # 回退：硬编码样例（source 标记）
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
        "source": "sample_fallback",
        "project_id": effective_pid or "current",
        "overall_progress": round(total, 1),
        "phases": phases,
        "estimated_remaining_days": 18,
    }


async def _tool_run_qa_inspection(
    project_id: str = "", phase: str = "", categories: str = "",
    _db=None, _project_id: str = "",
) -> dict:
    """执行质检"""
    effective_pid = project_id or _project_id

    # v1.1.31 FP-1: 真实 DB 查询 QualityIssue
    if settings.tool_real_data_enabled and _db is not None and effective_pid:
        try:
            from sqlalchemy import select
            from app.models.quality import QualityIssue
            stmt = select(QualityIssue).where(QualityIssue.project_id == effective_pid)
            if phase:
                stmt = stmt.where(QualityIssue.phase == phase)
            result = await _db.execute(stmt)
            issues = result.scalars().all()
            if issues:
                items = []
                for iss in issues:
                    item_status = _QA_STATUS_MAP.get(iss.status, "warning")
                    items.append({
                        "name": iss.category,
                        "standard": iss.standard or "",
                        "status": item_status,
                        "severity": iss.severity,
                        "issue_status": iss.status,
                        "description": iss.description,
                        "location": iss.location or "",
                    })
                # categories 过滤
                cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else []
                if cat_list:
                    items = [i for i in items if any(c in i["name"] for c in cat_list)]
                passed = sum(1 for i in items if i["status"] == "pass")
                total = len(items)
                return {
                    "source": "db",
                    "project_id": effective_pid,
                    "phase": phase or "all",
                    "total_items": total,
                    "passed": passed,
                    "pass_rate": round(passed / max(total, 1) * 100, 1),
                    "items": items,
                    "conclusion": "合格" if passed / max(total, 1) >= 0.85 else "需整改",
                }
            logger.debug("_tool_run_qa_inspection: 项目 %s 无质量问题记录，回退样例", effective_pid)
        except Exception as e:
            logger.warning("_tool_run_qa_inspection: DB 查询失败，回退样例: %s", e)

    # 回退：硬编码样例（source 标记）
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
        "source": "sample_fallback",
        "project_id": effective_pid or "current",
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

    async def execute(
        self, name: str, arguments: dict,
        _db=None, _project_id: str = "",
    ) -> Any:
        """执行工具调用

        v1.1.31 FP-1: 注入隐式上下文参数 ``_db`` / ``_project_id``。
        这两个参数不暴露在 OpenAI schema 中（下划线前缀避免与 LLM 提供的
        ``project_id`` 参数冲突），仅用于 handler 内部查真实 DB。
        当 ``_db is None`` 时不注入，handler 走默认回退逻辑。
        """
        tool = self.get(name)
        if not tool:
            return {"error": f"工具不存在: {name}"}
        logger.info(f"tool_execute: {name}, args={arguments}")
        inject: dict = {}
        if _db is not None:
            inject["_db"] = _db
        if _project_id:
            inject["_project_id"] = _project_id
        return await tool.execute(**arguments, **inject)

    @property
    def tool_count(self) -> int:
        return len(self._tools)


tool_registry = ToolRegistry()

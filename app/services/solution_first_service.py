"""F45 方案前置决策服务层 — 3 套布局方案 + 预算区间估算 + 入口状态

生成路径（诚实降级链）：
1. LLM 优先：复用 BaseAgent._chat()（多 LLM fallback 链）生成 3 套布局 + 预算区间
   （source="llm"）；LLM 无 key（返回 mock）/抛异常/返回非 JSON/结构非法时回退。
2. 规则兜底：source="rule_based" 并标注「LLM 不可用已降级」，禁止伪装 LLM 能力。
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.models.floorplan import FloorPlan
from app.models.project import Project

logger = logging.getLogger(__name__)

# 业务时区（平台业务时区为北京时间，对齐 agent_context_service._DEFAULT_TZ）
_BJ_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")

SOURCE = "rule_based"
SOURCE_NOTE = "布局与预算由内置规则引擎生成（source=rule_based），可接入 LLM 升级生成更个性化方案"
SOURCE_NOTE_LLM = "布局与预算由 LLM 基于户型/风格生成（source=llm），签约前请由设计师复核"
SOURCE_NOTE_FALLBACK = "LLM 不可用，已降级为规则引擎生成（source=rule_based）"

# 预算档次：单价区间（元/㎡）— 2026 市场行情参考（诚实标注：非精确报价）
BUDGET_LEVELS: list[dict[str, Any]] = [
    {"level": "economic", "per_sqm_lower": 1200, "per_sqm_upper": 1800},
    {"level": "comfort", "per_sqm_lower": 1800, "per_sqm_upper": 2600},
    {"level": "quality", "per_sqm_lower": 2600, "per_sqm_upper": 4000},
]

# 布局方案（A/B/C）静态要点定义 — 3-5 条/方案
_LAYOUT_PLANS: list[dict[str, Any]] = [
    {
        "plan_no": "A",
        "name": "经典分区布局",
        "summary": "动静分区，客厅/餐厅等动区与卧室/书房等静区独立成区，私密性与隔音最好。",
        "layout_points": [
            "动静分区：客厅/餐厅等动区集中布置，卧室/书房等静区独立成区",
            "以玄关/过道为动静缓冲带，减少动区对静区的干扰",
            "保留传统独立房间格局，隔墙完整、空间边界清晰",
        ],
        "pros": [
            "空间边界清晰，动静互不干扰",
            "隔音与私密性最好，适合多代同堂",
            "施工成熟、造价可控，拆改风险低",
        ],
        "cons": [
            "空间通透性一般，采光差时更显局促",
            "墙体较多，实际得房率偏低",
        ],
    },
    {
        "plan_no": "B",
        "name": "开放融合布局",
        "summary": "LDK 一体化，客厅+餐厅+厨房打通形成大开间；拆墙前必须做 HC-001 承重校验。",
        "layout_points": [
            "LDK 一体化：客厅(Living)+餐厅(Dining)+厨房(Kitchen)打通",
            "拆除客厅与厨房/餐厅之间非承重隔墙，形成大开间",
            "拆墙前必须完成 HC-001 承重结构校验，承重墙严禁拆除",
            "用吧台/岛台或玻璃隔断软性分区，保留功能边界",
        ],
        "pros": [
            "空间通透显大，采光通风显著提升",
            "动线流畅，适合年轻家庭与社交场景",
            "减少墙体，空间利用率与得房率提高",
        ],
        "cons": [
            "开放式厨房油烟扩散，需配置大吸力烟机",
            "隔音与私密性下降",
            "拆改增加结构安全审查成本",
        ],
    },
    {
        "plan_no": "C",
        "name": "高效收纳布局",
        "summary": "通过整面墙柜体与零碎空间利用最大化收纳体量，长期居住不显杂乱。",
        "layout_points": [
            "玄关/客厅/卧室设置整面墙收纳柜体，提升收纳体量",
            "利用过道/飘窗/楼梯下等零碎空间做定制收纳",
            "柜体遵循「上轻下重」原则，常用物品置于黄金收纳区(650-1850mm)",
            "预留 10%-15% 弹性收纳余量，应对家庭物品增长",
        ],
        "pros": [
            "收纳容量最大化，长期居住不显杂乱",
            "柜体与墙面一体化，视觉整洁统一",
            "小户型空间利用率收益最大",
        ],
        "cons": [
            "定制柜体造价较高、工期较长",
            "柜体过多压缩活动空间与通透感",
            "需关注板材环保等级（ENF/E0 级）",
        ],
    },
]

BUDGET_NOTE = "区间估值为行业行情参考，非精确报价（source: rule_based）"

# ── F45 多风格目录（2026 主流装修风格，诚实标注：非精确报价） ──
STYLE_CATALOG: list[dict[str, Any]] = [
    {"key": "modern", "name": "现代简约", "desc": "线条利落、低饱和中性色，强调收纳与秩序感"},
    {"key": "new_chinese", "name": "新中式", "desc": "传统元素现代化，木质+留白，沉稳雅致"},
    {"key": "nordic", "name": "北欧风", "desc": "浅木色+白墙，自然光感强，温馨舒适"},
    {"key": "luxury", "name": "轻奢风", "desc": "金属/石材点缀，精致质感，低调奢华"},
    {"key": "industrial", "name": "工业风", "desc": "裸露结构/水泥肌理，个性硬朗"},
    {"key": "log", "name": "原木风", "desc": "大面积原木+暖色，自然治愈，日式氛围"},
]


def list_styles() -> list[dict[str, Any]]:
    """返回可用装修风格目录。"""
    return [dict(style) for style in STYLE_CATALOG]


def _resolve_style(style: str | None) -> dict[str, Any]:
    """解析风格 key；未知/空回退现代简约（诚实标注）。"""
    if not style:
        return STYLE_CATALOG[0]
    for s in STYLE_CATALOG:
        if s["key"] == style:
            return s
    return STYLE_CATALOG[0]


def _parse_floorplan_data(data: str) -> dict[str, Any] | None:
    """解析 floorplan.data JSON 字符串，解析失败或非对象返回 None。"""
    if not data:
        return None
    try:
        parsed = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_room_names(floorplan_data: dict[str, Any] | None) -> list[str]:
    """从户型数据中提取房间名称列表（容忍缺失/脏数据）。"""
    if not floorplan_data:
        return []
    rooms = floorplan_data.get("rooms", [])
    if not isinstance(rooms, list):
        return []
    names: list[str] = []
    for room in rooms:
        if isinstance(room, dict) and room.get("name"):
            names.append(str(room["name"]))
    return names


class SolutionFirstAgent(BaseAgent):
    """方案前置决策 Agent — 复用 BaseAgent._chat() 的多 LLM fallback 链。

    LLM 无 key 时 _chat 返回 mock（非 JSON），由 _parse_llm_json 解析失败触发降级，
    不预检 key，保证「配置检测」与诚实降级自然衔接。
    """

    agent_name = "solution_first"
    system_prompt = (
        "你是索克家居（i-home.life）AI 装修方案设计 Agent。"
        "请根据户型总面积与房间列表生成 3 套差异化布局方案（例如动静分区、LDK 一体化、高效收纳等），"
        "并为每套方案给出预算区间。"
        "必须只输出一个合法 JSON 对象（不要输出 markdown、注释或任何其他文字）。"
    )


_LLM_OUTPUT_SCHEMA = (
    '{"layouts": [{"layout_name": "方案名", "description": "一句话描述", '
    '"rooms": ["房间名"], "layout_points": ["要点"], "pros": ["优点"], "cons": ["缺点"], '
    '"budget_range": {"lower": 整数, "upper": 整数, "level": "comfort"}}], '
    '"budget_range": {"lower": 整数, "upper": 整数, "level": "comfort"}}'
)


def _parse_llm_json(reply: Any) -> dict | None:
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


def _normalize_llm_budget(raw: Any, total_area: float) -> dict[str, Any]:
    """归一化 LLM 预算区间；缺失/非法时用规则区间兜底并诚实标注。"""
    levels = budget_range_for(total_area)["levels"]
    if isinstance(raw, dict):
        try:
            lower = float(raw["lower"])
            upper = float(raw["upper"])
            if 0 < lower < upper and total_area > 0:
                level = str(raw.get("level") or "comfort")
                return {
                    "level": level,
                    "lower": int(lower),
                    "upper": int(upper),
                    "per_sqm_lower": round(lower / total_area, 2),
                    "per_sqm_upper": round(upper / total_area, 2),
                    "levels": levels,
                    "note": "主推区间由 LLM 基于户型/风格生成（source=llm），三档明细为行业行情参考（非精确报价）",
                }
        except (KeyError, TypeError, ValueError):
            pass
    rule = budget_range_for(total_area)
    rule["note"] = "预算区间由规则引擎兜底生成（source=rule_based，LLM 未返回合法区间）"
    return rule


def _normalize_llm_package(parsed: dict, total_area: float) -> dict[str, Any] | None:
    """将 LLM 输出归一化为 {layouts, budget_range}，结构非法返回 None（触发回退）。"""
    raw_layouts = parsed.get("layouts")
    if not isinstance(raw_layouts, list) or not raw_layouts:
        return None
    layouts = []
    for idx, raw in enumerate(raw_layouts[:3]):
        if not isinstance(raw, dict):
            return None
        name = raw.get("layout_name") or raw.get("name")
        if not name:
            return None
        layouts.append({
            "plan_no": str(raw.get("plan_no") or "ABC"[idx]),
            "name": str(name),
            "summary": str(raw.get("description") or raw.get("summary") or ""),
            "layout_points": list(raw.get("layout_points") or []),
            "pros": list(raw.get("pros") or []),
            "cons": list(raw.get("cons") or []),
            "rooms": list(raw.get("rooms") or []),
            "budget_range": raw.get("budget_range"),
            "source": "llm",
            "source_note": SOURCE_NOTE_LLM,
        })
    return {"layouts": layouts, "budget_range": _normalize_llm_budget(parsed.get("budget_range"), total_area)}


async def _llm_generate_package(
    floorplan_data: dict[str, Any] | None,
    total_area: float,
    style: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """调用 LLM 生成 3 套布局 + 预算区间；任何失败返回 None（调用方回退 rule_based）。

    诚实降级：LLM 无 key 时 _chat 返回 mock（非 JSON）→ 解析失败 → None；
    抛异常 / 返回非 JSON / 结构非法均返回 None，绝不伪装 LLM 能力。
    """
    agent = SolutionFirstAgent()
    try:
        rooms = _extract_room_names(floorplan_data)
        room_desc = "、".join(rooms) if rooms else "（未提供房间明细）"
        style_hint = f"偏好风格：{style['name']}（{style['desc']}）。" if style else ""
        user_prompt = (
            f"项目总面积 {total_area:.0f}㎡，房间：{room_desc}。\n"
            f"{style_hint}"
            "请生成 3 套装修布局方案。必须只输出如下 JSON（不要输出任何其他文字）：\n"
            f"{_LLM_OUTPUT_SCHEMA}"
        )
        messages = [
            {"role": "system", "content": SolutionFirstAgent.system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        reply = await agent._chat(messages)
        parsed = _parse_llm_json(reply)
        if not parsed:
            logger.warning("solution_first: LLM 返回非 JSON，降级 rule_based")
            return None
        return _normalize_llm_package(parsed, total_area)
    except Exception as e:
        logger.warning("solution_first: LLM 调用失败，降级 rule_based (error=%s)", e)
        return None
    finally:
        await agent.close()


async def _resolve_package(
    floorplan_data: dict[str, Any] | None,
    total_area: float,
    style: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], str, str]:
    """LLM 优先、规则兜底的包解析：返回 (layouts, budget_range, source, source_note)。"""
    llm_pkg = await _llm_generate_package(floorplan_data, total_area, style)
    if llm_pkg:
        return llm_pkg["layouts"], llm_pkg["budget_range"], "llm", SOURCE_NOTE_LLM
    layouts = generate_layouts(floorplan_data, total_area, style)
    budget_range = budget_range_for(total_area)
    return layouts, budget_range, "rule_based", SOURCE_NOTE_FALLBACK


def generate_layouts(
    floorplan_data: dict[str, Any] | None,
    total_area: float,
    style: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """生成 3 套布局方案（纯规则，source=rule_based）。

    Args:
        floorplan_data: 解析后的户型数据（可能含 rooms 数组），None 则用 total_area 兜底
        total_area: 项目总面积（m²）
        style: 偏好风格（可选，仅用于 source_note 标注，不影响布局结构）
    """
    room_names = _extract_room_names(floorplan_data)
    style_hint = f"，风格偏好：{style['name']}" if style else ""
    if not room_names:
        area_hint = f"（户型数据缺失，按总面积 {total_area:.0f}㎡ 通用规则生成{style_hint}）"
    else:
        area_hint = f"（户型含 {len(room_names)} 个房间，按空间结构规则生成{style_hint}）"

    plans = []
    for plan in _LAYOUT_PLANS:
        plans.append({
            "plan_no": plan["plan_no"],
            "name": plan["name"],
            "summary": plan["summary"],
            "layout_points": list(plan["layout_points"]),
            "pros": list(plan["pros"]),
            "cons": list(plan["cons"]),
            "source": SOURCE,
            "source_note": SOURCE_NOTE + area_hint,
        })
    return plans


def budget_range_for(total_area: float) -> dict[str, Any]:
    """按户型面积估算三档预算区间（纯规则，行业行情参考，非精确报价）。

    Args:
        total_area: 项目总面积（m²）

    Returns:
        {lower, upper, level, per_sqm_lower, per_sqm_upper, levels, note}
        lower/upper 为舒适档（comfort）主推区间，levels 含三档明细。
    """
    if total_area <= 0:
        total_area = 100.0

    levels = []
    for level in BUDGET_LEVELS:
        levels.append({
            "level": level["level"],
            "per_sqm_lower": level["per_sqm_lower"],
            "per_sqm_upper": level["per_sqm_upper"],
            "lower": int(level["per_sqm_lower"] * total_area),
            "upper": int(level["per_sqm_upper"] * total_area),
        })

    comfort = next(item for item in levels if item["level"] == "comfort")
    return {
        "level": comfort["level"],
        "lower": comfort["lower"],
        "upper": comfort["upper"],
        "per_sqm_lower": comfort["per_sqm_lower"],
        "per_sqm_upper": comfort["per_sqm_upper"],
        "levels": levels,
        "note": BUDGET_NOTE,
    }


async def _get_active_floorplan(db: AsyncSession, project_id: str) -> FloorPlan | None:
    """获取项目 active 户型方案（按 created_at 倒序取最新一条）。"""
    result = await db.execute(
        select(FloorPlan)
        .where(FloorPlan.project_id == project_id, FloorPlan.is_active.is_(True))
        .order_by(FloorPlan.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _resolve_total_area(project: Project, floorplan: FloorPlan | None) -> float:
    """优先取户型面积，否则回退项目 total_area（0 时用 100㎡ 兜底）。"""
    total_area = float(project.total_area or 0.0)
    if floorplan and floorplan.total_area and floorplan.total_area > 0:
        total_area = float(floorplan.total_area)
    return total_area


async def generate_package(
    db: AsyncSession,
    project_id: str,
    style: str | None = None,
) -> dict[str, Any]:
    """生成方案前置决策包：3 套布局 + 预算区间 + 推荐建议。

    Args:
        db: 数据库会话
        project_id: 项目 ID（API 层已校验存在性与访问权限）
        style: 偏好风格 key（可选，见 STYLE_CATALOG）

    Returns:
        {project_id, project_name, plan_count, layouts, budget_range,
         recommendations, source, source_note, generated_at}
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"项目不存在: {project_id}")

    floorplan = await _get_active_floorplan(db, project_id)
    floorplan_data = _parse_floorplan_data(floorplan.data) if floorplan else None
    total_area = _resolve_total_area(project, floorplan)
    style_info = _resolve_style(style)

    # LLM 优先（source="llm"，含风格），失败/无 key/解析失败回退规则（source="rule_based"）
    layouts, budget_range, source, source_note = await _resolve_package(
        floorplan_data, total_area, style_info,
    )

    recommendations = [
        "先确定预算档位：8-12 万升级化装修是 2026 市场主力档，可按面积档位上下浮动"
        f"（当前项目约 {int(budget_range['lower'])}-{int(budget_range['upper'])} 元，source: {source}）",
        f"建议先明确需求优先级（动线/收纳/通透），再选择方案 A/B/C 或组合（source: {source}）",
        f"若选择方案 B 开放融合布局，拆墙前必须完成 HC-001 承重结构校验（source: {source}）",
    ]

    return {
        "project_id": project_id,
        "project_name": project.name,
        "style": style_info,
        "plan_count": len(layouts),
        "layouts": layouts,
        "budget_range": budget_range,
        "recommendations": recommendations,
        "source": source,
        "source_note": source_note,
        "generated_at": datetime.now(_BJ_TZ).isoformat(),
    }


# ── F45 多轮对话：方案 refine 深化 ──

_REFINE_SCHEMA = (
    '{"refined_layout": {"layout_name": "方案名", "description": "一句话描述", '
    '"layout_points": ["要点"], "pros": ["优点"], "cons": ["缺点"]}}'
)


async def _llm_refine_layout(
    plan_name: str,
    feedback: str,
    style: dict[str, Any] | None,
    total_area: float,
) -> dict[str, Any] | None:
    """调用 LLM 依据用户反馈深化方案；任何失败返回 None（调用方回退 rule_based）。"""
    agent = SolutionFirstAgent()
    try:
        style_hint = f"偏好风格：{style['name']}（{style['desc']}）。" if style else ""
        user_prompt = (
            f"针对已有方案「{plan_name}」（总面积 {total_area:.0f}㎡），"
            f"用户反馈：{feedback}。{style_hint}"
            "请给出深化后的单一方案。必须只输出如下 JSON（不要输出任何其他文字）：\n"
            f"{_REFINE_SCHEMA}"
        )
        messages = [
            {"role": "system", "content": SolutionFirstAgent.system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        reply = await agent._chat(messages)
        parsed = _parse_llm_json(reply)
        if not parsed:
            logger.warning("solution_first.refine: LLM 返回非 JSON，降级 rule_based")
            return None
        raw = parsed.get("refined_layout")
        if not isinstance(raw, dict) or not raw.get("layout_name"):
            return None
        return {
            "plan_no": "R",
            "name": str(raw["layout_name"]),
            "summary": str(raw.get("description") or ""),
            "layout_points": list(raw.get("layout_points") or []),
            "pros": list(raw.get("pros") or []),
            "cons": list(raw.get("cons") or []),
            "feedback": feedback,
            "source": "llm",
            "source_note": SOURCE_NOTE_LLM,
        }
    except Exception as e:
        logger.warning("solution_first.refine: LLM 调用失败，降级 rule_based (error=%s)", e)
        return None
    finally:
        await agent.close()


def _rule_refine_layout(plan_name: str, feedback: str) -> dict[str, Any]:
    """规则兜底：基于反馈生成深化建议（诚实标注 rule_based，不伪装 LLM）。"""
    return {
        "plan_no": "R",
        "name": f"{plan_name}（深化）",
        "summary": f"基于反馈「{feedback}」的深化方案",
        "layout_points": [
            "优先落实反馈中明确的空间诉求（如动线/收纳/交互）",
            "保持原方案结构与预算基调，仅做局部微调",
            "建议下一步由设计师结合现场复核深化",
        ],
        "pros": ["延续原方案可行性，改动可控"],
        "cons": ["规则引擎生成，未充分体现个性化偏好"],
        "feedback": feedback,
        "source": "rule_based",
        "source_note": SOURCE_NOTE_FALLBACK,
    }


async def refine_layout(
    db: AsyncSession,
    project_id: str,
    plan_no: str,
    feedback: str,
    style: str | None = None,
) -> dict[str, Any]:
    """多轮对话：依据用户反馈深化指定方案（LLM 优先，规则兜底）。

    Args:
        db: 数据库会话
        project_id: 项目 ID（API 层已校验存在性与访问权限）
        plan_no: 方案编号（A/B/C 或实际方案名）
        feedback: 用户反馈/偏好
        style: 偏好风格 key（可选）

    Returns:
        {project_id, plan_no, refined_layout, source, generated_at}
    """
    if not feedback or not feedback.strip():
        raise ValueError("feedback 不能为空")
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"项目不存在: {project_id}")

    floorplan = await _get_active_floorplan(db, project_id)
    total_area = _resolve_total_area(project, floorplan)
    style_info = _resolve_style(style)

    plan_name = plan_no.strip()
    refined = await _llm_refine_layout(plan_name, feedback.strip(), style_info, total_area)
    if not refined:
        refined = _rule_refine_layout(plan_name, feedback.strip())

    return {
        "project_id": project_id,
        "plan_no": plan_no,
        "refined_layout": refined,
        "source": refined["source"],
        "source_note": refined["source_note"],
        "generated_at": datetime.now(_BJ_TZ).isoformat(),
    }


async def get_entry(db: AsyncSession, project_id: str) -> dict[str, Any]:
    """查询项目方案前置决策入口状态。

    Args:
        db: 数据库会话
        project_id: 项目 ID（API 层已校验存在性与访问权限）

    Returns:
        {project_id, has_floorplan, total_area, plan_available, note}
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise ValueError(f"项目不存在: {project_id}")

    floorplan = await _get_active_floorplan(db, project_id)
    total_area = _resolve_total_area(project, floorplan)

    return {
        "project_id": project_id,
        "has_floorplan": floorplan is not None,
        "total_area": total_area,
        "plan_available": True,
        "note": "方案由内置规则引擎生成（source: rule_based），可接入 LLM 升级",
    }

"""工具选择准确率评估（v1.13.0，对齐 2026 生产级 Agent Eval 的 Tool-Selection Accuracy）

2026 Agent 评估指南（AI VOID 12-metric framework / MLflow 2026）：
- Tool-Selection Accuracy: 模型是否在正确场景选择正确的工具
- 每个失败模式 ≥50 评估用例，否则 pass rate 在分布漂移下失真
- 用确定性基线（关键词分类）建立"最低可接受线"，LLM 分类必须显著高于它才有价值

本模块提供：
- TOOL_SELECTION_DATASET: ≥50 条「用户查询 → 期望工具 + 关键参数」用例，
  覆盖 11 个用户内置工具 × normal/boundary/confusable/negative 四类失败模式
- classify_tool_by_keywords(query): 确定性关键词分类器（诚实标注：基线，非 LLM）
- evaluate_tool_selection(cases): 对给定分类器计算准确率 + 混淆矩阵
- get_tool_accuracy_report(): 生成可序列化报告（供 ihome_eval / CI 复用）

设计原则：
- 确定性、零 LLM 依赖（测试稳定）；LLM 分类的抽样评估由 eval 报告 notes 标注
- 用例用中文（对齐真实用户话语），failure_mode 显式标注供失败归因
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolSelectionCase:
    """单条工具选择评估用例"""

    query: str                    # 用户查询原文
    expected_tool: str            # 期望选中的工具名
    expected_params: dict = field(default_factory=dict)  # 期望关键参数（含校验类型）
    failure_mode: str = "normal"  # normal | boundary | confusable | negative
    note: str = ""                # 补充说明


# ════════════════════════════════════════════════════════════════
# 评估数据集（≥50 用例，覆盖 11 个用户内置工具）
# ════════════════════════════════════════════════════════════════

TOOL_SELECTION_DATASET: list[ToolSelectionCase] = [
    # ── get_budget（预算）──────────────────────────────────────────
    ToolSelectionCase("100平简约风装修预算多少", "get_budget", {"area": 100, "style": "modern"}, "normal", "面积+风格"),
    ToolSelectionCase("帮我估算下120平房子的装修费用", "get_budget", {"area": 120}, "normal", "仅面积"),
    ToolSelectionCase("90平轻奢装修大概花多少钱", "get_budget", {"area": 90, "style": "luxury"}, "normal"),
    ToolSelectionCase("装修预算明细能查吗", "get_budget", {}, "boundary", "无面积信息，仍应选预算工具"),
    ToolSelectionCase("160平的别墅装修要多少钱", "get_budget", {"area": 160}, "normal"),
    ToolSelectionCase("预算超支了怎么办", "get_budget", {}, "confusable", "预算类意图"),
    # ── get_design_layout（设计布局）────────────────────────────────
    ToolSelectionCase("120平三室两厅北欧风设计一下", "get_design_layout", {"area": 120, "style": "nordic"}, "normal"),
    ToolSelectionCase("帮我出个新中式的客厅布局", "get_design_layout", {"style": "chinese"}, "normal"),
    ToolSelectionCase("80平两居室怎么布置好", "get_design_layout", {"area": 80}, "normal"),
    ToolSelectionCase("日式风格装修方案看看", "get_design_layout", {"style": "japanese"}, "normal"),
    ToolSelectionCase("现代简约的卧室设计图", "get_design_layout", {"style": "modern"}, "normal"),
    ToolSelectionCase("厨房要不要做成开放式的", "get_design_layout", {}, "confusable", "设计讨论类"),
    # ── search_materials（物料搜索）─────────────────────────────────
    ToolSelectionCase("有没有便宜的瓷砖推荐", "search_materials", {"category": "瓷砖"}, "normal"),
    ToolSelectionCase("立邦乳胶漆什么价格", "search_materials", {"keyword": "立邦"}, "normal"),
    ToolSelectionCase("实木地板和复合地板区别和价格", "search_materials", {"category": "地板"}, "normal"),
    ToolSelectionCase("防水涂料哪个牌子好", "search_materials", {"category": "涂料"}, "normal"),
    ToolSelectionCase("找一款性价比高的马桶", "search_materials", {"keyword": "马桶"}, "normal"),
    ToolSelectionCase("材料清单帮我看看", "search_materials", {}, "boundary", "无类别信息"),
    # ── get_construction_progress（施工进度）────────────────────────
    ToolSelectionCase("我家装修进行到哪一步了", "get_construction_progress", {}, "normal", "需 project_id 注入"),
    ToolSelectionCase("水电阶段完成了没有", "get_construction_progress", {}, "normal"),
    ToolSelectionCase("施工进度到哪了能看看吗", "get_construction_progress", {}, "normal"),
    ToolSelectionCase("帮我查一下项目进度", "get_construction_progress", {}, "normal"),
    ToolSelectionCase("工期会不会延期", "get_construction_progress", {}, "confusable", "进度预测"),
    # ── run_qa_inspection（质检）────────────────────────────────────
    ToolSelectionCase("水电验收结果怎么样", "run_qa_inspection", {"phase": "water_electricity"}, "normal"),
    ToolSelectionCase("防水闭水试验做了吗", "run_qa_inspection", {}, "normal"),
    ToolSelectionCase("瓷砖空鼓检查情况", "run_qa_inspection", {}, "normal"),
    ToolSelectionCase("质检报告帮我查一下", "run_qa_inspection", {}, "normal"),
    ToolSelectionCase("最近有没有质量隐患", "run_qa_inspection", {}, "normal"),
    ToolSelectionCase("油漆阶段质量怎么样", "run_qa_inspection", {"phase": "paint"}, "normal"),
    # ── search_poi（周边 POI）──────────────────────────────────────
    ToolSelectionCase("附近哪里有建材市场", "search_poi", {"keywords": "建材市场"}, "normal"),
    ToolSelectionCase("我家周边有五金店吗", "search_poi", {"keywords": "五金"}, "normal"),
    ToolSelectionCase("附近的小区楼盘有哪些", "search_poi", {"keywords": "小区"}, "normal"),
    ToolSelectionCase("哪里有家电卖场", "search_poi", {"keywords": "家电卖场"}, "normal"),
    ToolSelectionCase("周边建材城在哪", "search_poi", {"keywords": "建材"}, "normal"),
    ToolSelectionCase("帮我找找附近的瓷砖店", "search_poi", {"keywords": "瓷砖"}, "normal"),
    # ── launch_agent_task（后台任务编排）────────────────────────────
    ToolSelectionCase("顺便帮我做一份100平的预算", "launch_agent_task", {"command": "做一份100平的预算"}, "normal", "顺便=后台任务"),
    ToolSelectionCase("同时查一下施工进度和预算", "launch_agent_task", {}, "normal", "同时=并行编排"),
    ToolSelectionCase("把设计师的方案整理成文档", "launch_agent_task", {}, "boundary"),
    # ── get_voice_tasks（任务查询）──────────────────────────────────
    ToolSelectionCase("刚才那个预算任务做完了吗", "get_voice_tasks", {}, "normal"),
    ToolSelectionCase("我的任务列表有哪些", "get_voice_tasks", {}, "normal"),
    ToolSelectionCase("任务进度怎么样了", "get_voice_tasks", {}, "normal"),
    # ── cancel_agent_task（取消任务）────────────────────────────────
    ToolSelectionCase("取消1号任务吧", "cancel_agent_task", {}, "normal"),
    ToolSelectionCase("那个任务别做了", "cancel_agent_task", {}, "normal"),
    ToolSelectionCase("帮我取消刚才的任务", "cancel_agent_task", {}, "normal"),
    # ── generate_design_proposals（多方案生成）──────────────────────
    ToolSelectionCase("帮我设计一个现代风格的厨房", "generate_design_proposals", {"requirement": "现代风格厨房"}, "normal"),
    ToolSelectionCase("客厅设计几套方案给我选", "generate_design_proposals", {}, "normal"),
    ToolSelectionCase("卫生间干湿分离怎么设计", "generate_design_proposals", {}, "normal"),
    ToolSelectionCase("给我两个卧室装修方案", "generate_design_proposals", {}, "normal"),
    # ── update_design_proposal（方案修订）───────────────────────────
    ToolSelectionCase("方案B加个中岛", "update_design_proposal", {"proposal_id": "B", "change": "加中岛"}, "normal"),
    ToolSelectionCase("方案A改成开放式厨房", "update_design_proposal", {"proposal_id": "A", "change": "开放式厨房"}, "normal"),
    ToolSelectionCase("第三个方案卧室放大点", "update_design_proposal", {"proposal_id": "C"}, "normal"),
    ToolSelectionCase("把方案B的颜色换成浅色", "update_design_proposal", {"proposal_id": "B"}, "normal"),
    # ── 混淆/负面用例（不应误选工具）───────────────────────────────
    ToolSelectionCase("你好，在吗", "get_voice_tasks", {}, "negative", "闲聊，不应选工具"),
    ToolSelectionCase("谢谢你的帮助", "get_voice_tasks", {}, "negative", "致谢，不应选工具"),
    ToolSelectionCase("我家的户型图在哪个菜单里找", "get_design_layout", {}, "confusable", "导航类问题，非设计需求"),
    ToolSelectionCase("油漆多少钱一桶", "search_materials", {"keyword": "油漆"}, "normal", "价格=物料搜索"),
]


# ════════════════════════════════════════════════════════════════
# 确定性关键词分类器（诚实标注：基线，非 LLM）
# ════════════════════════════════════════════════════════════════

# 工具 → 触发关键词（按优先级排序，先命中先返回）
_TOOL_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("cancel_agent_task", ("取消", "别做", "停掉", "终止任务")),
    ("update_design_proposal", ("方案A", "方案B", "方案C", "方案", "改成", "加个", "改颜色")),
    ("generate_design_proposals", ("设计一下", "几套方案", "帮我设计", "方案给我", "怎么设计", "怎么布置", "装修方案")),
    ("get_voice_tasks", ("任务", "进度怎么样", "做完了吗", "任务列表")),
    ("launch_agent_task", ("顺便", "同时", "帮我做一份", "整理成文档")),
    ("search_poi", ("附近", "周边", "哪里有", "在哪", "找找", "建材市场", "五金店", "家电卖场")),
    ("run_qa_inspection", ("验收", "闭水试验", "空鼓", "质检", "质量隐患", "检查情况")),
    ("get_construction_progress", ("进度", "到哪一步", "进行到", "延期", "工期")),
    ("search_materials", ("瓷砖", "乳胶漆", "地板", "涂料", "马桶", "油漆", "价格", "多少钱", "物料", "材料")),
    ("get_budget", ("预算", "装修费用", "花多少钱", "多少钱", "费用")),
    ("get_design_layout", ("设计", "布局", "布置", "风格")),
]


def classify_tool_by_keywords(query: str) -> str | None:
    """确定性关键词分类器（诚实标注：基线工具选择，非 LLM）。

    返回选中的工具名；无法归类返回 None（表示"不调用工具"，LLM 直接回复）。
    """
    q = (query or "").lower()
    for tool, keywords in _TOOL_KEYWORDS:
        if any(kw in q for kw in keywords):
            return tool
    return None


# ════════════════════════════════════════════════════════════════
# 评估执行
# ════════════════════════════════════════════════════════════════


def evaluate_tool_selection(
    cases: list[ToolSelectionCase] | None = None,
    classifier=None,
) -> dict:
    """对给定分类器评估工具选择准确率。

    Args:
        cases: 评估用例（默认 TOOL_SELECTION_DATASET）
        classifier: 分类函数 f(query) -> tool_name|None（默认 classify_tool_by_keywords）

    Returns:
        {"sample_size", "accuracy", "per_tool": {tool: {correct, total, accuracy}},
         "confusion": [{query, expected, predicted, failure_mode}], ...}
    """
    cases = cases or TOOL_SELECTION_DATASET
    classifier = classifier or classify_tool_by_keywords
    total = len(cases)
    correct = 0
    per_tool: dict[str, dict] = {}
    confusion: list[dict] = []
    by_mode: dict[str, dict] = {}

    for case in cases:
        predicted = classifier(case.query)
        is_correct = predicted == case.expected_tool
        if is_correct:
            correct += 1
        per_tool.setdefault(case.expected_tool, {"correct": 0, "total": 0})
        per_tool[case.expected_tool]["total"] += 1
        if is_correct:
            per_tool[case.expected_tool]["correct"] += 1
        by_mode.setdefault(case.failure_mode, {"correct": 0, "total": 0})
        by_mode[case.failure_mode]["total"] += 1
        if is_correct:
            by_mode[case.failure_mode]["correct"] += 1
        if not is_correct:
            confusion.append({
                "query": case.query,
                "expected": case.expected_tool,
                "predicted": predicted,
                "failure_mode": case.failure_mode,
            })

    return {
        "sample_size": total,
        "correct": correct,
        "accuracy": round(correct / total * 100, 2),
        "per_tool": {
            tool: {
                "correct": v["correct"],
                "total": v["total"],
                "accuracy": round(v["correct"] / v["total"] * 100, 2),
            } for tool, v in per_tool.items()
        },
        "per_failure_mode": {
            mode: {
                "correct": v["correct"],
                "total": v["total"],
                "accuracy": round(v["correct"] / v["total"] * 100, 2),
            } for mode, v in by_mode.items()
        },
        "confusion": confusion,
    }


def get_tool_accuracy_report(classifier=None) -> dict:
    """生成工具选择准确率报告（供 ihome_eval TOOL_CALL_ACCURACY 维度 / CI 复用）。

    返回报告 + 数据集规模 + 版本标注。零 LLM 依赖（确定性，诚实标注为基线）。
    """
    result = evaluate_tool_selection(classifier=classifier)
    return {
        "report_type": "tool_selection_accuracy",
        "baseline": "keyword_classifier" if classifier is None else "custom",
        "dataset": "TOOL_SELECTION_DATASET",
        "dataset_size": len(TOOL_SELECTION_DATASET),
        "metrics": {
            "accuracy": result["accuracy"],
            "sample_size": result["sample_size"],
        },
        "per_tool": result["per_tool"],
        "per_failure_mode": result["per_failure_mode"],
        "confusion": result["confusion"],
        "notes": [
            "确定性关键词基线（非 LLM），用于建立工具选择最低可接受线",
            "LLM 分类的抽样评估需在 notes 中诚实标注（本项目 LLM 分类经 think_with_tools 采样）",
        ],
    }

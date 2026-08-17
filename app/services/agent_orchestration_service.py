"""多智能体协作编排服务（v1.12.x，对齐 2026 hub-spoke / pipeline 编排范式）

2026 前沿参照（multi-agent orchestration production 2026）：
- Orchestrator-Worker（hub-spoke）：Orchestrator 解析目标 → 分解子任务 →
  派发专用 Worker → 聚合结果
- 循环检测：任务图 DAG 校验，拒绝产生环的派发（can_dispatch 范式）
- 结构化 Agent 消息：子 Agent 输出作为 JSON 数据聚合（AgentTaskResult），
  不直接拼接为未转义 prompt 再注入其它 Agent（防 prompt injection at seams）

设计约束：
- 受 settings.agent_orchestration_pipeline_enabled 门控，关闭则编排降级为
  单意图分类（与原 classify_intent 行为一致）
- LLM 分解失败（无 key / 非 JSON / 结构非法）诚实降级为规则分解（单任务），
  绝不伪装 LLM 能力
- 子任务执行复用 harness.run：自动获得轨迹落库（workflow_id 传播，
  见 harness._persist_trace）+ 自进化 Case 提取
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field

from app.config import get_settings
from app.metrics import agent_orchestration_task_total

logger = logging.getLogger(__name__)

# ── 结构化 Agent 间消息（2026 前沿：结构化输出而非自由文本）──


@dataclass
class AgentTask:
    """编排子任务（结构化 Agent 间消息）"""

    task_id: str
    agent_name: str
    description: str
    dependencies: list[str] = field(default_factory=list)  # 前置 task_id 列表
    status: str = "pending"  # pending / running / success / failed / skipped
    result: str = ""
    error: str = ""


@dataclass
class AgentTaskResult:
    """子任务执行结果（结构化消息，供聚合/审计）"""

    task_id: str
    agent_id: str
    status: str
    result: str
    confidence: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "result": self.result,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


# ── Agent 注册表（编排可派发的执行型 Agent 子集）──


def _agent_registry() -> dict[str, type]:
    """惰性构建 agent_name → class 注册表（延迟 import 防循环依赖）。

    v1.13.x 逐项审计：补齐 files/products/identity/notifications/ifc_export
    5 个专用 Agent（此前这些意图在编排中收敛到 concierge 客服）。
    """
    from app.agents import (  # noqa: F401
        DesignerAgent, BudgetAgent, ProcurementAgent, ConstructionAgent,
        QAInspectorAgent, SettlementAgent, ConciergeAgent,
        KitchenAgent, BathroomAgent, MepAgent, ApplianceAgent,
        FurnitureAgent, DoorWindowAgent, TakeoffAgent,
        FilesAgent, ProductsAgent, IdentityAgent, NotificationsAgent,
        IfcExportAgent,
    )
    return {
        "designer": DesignerAgent,
        "budget": BudgetAgent,
        "procurement": ProcurementAgent,
        "construction": ConstructionAgent,
        "qa_inspector": QAInspectorAgent,
        "settlement": SettlementAgent,
        "concierge": ConciergeAgent,
        "kitchen": KitchenAgent,
        "bathroom": BathroomAgent,
        "mep": MepAgent,
        "appliance": ApplianceAgent,
        "furniture": FurnitureAgent,
        "door_window": DoorWindowAgent,
        "takeoff": TakeoffAgent,
        "files": FilesAgent,
        "products": ProductsAgent,
        "identity": IdentityAgent,
        "notifications": NotificationsAgent,
        "ifc_export": IfcExportAgent,
    }


# ── JSON 解析 ──


def _parse_llm_json(reply) -> dict | None:
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


# ── 任务分解 ──

# orchestrator 意图名 → 编排 Agent 名（两者命名体系不同：intent 用 design，
# Agent 用 designer；未映射意图收敛到 concierge 客服）
_INTENT_TO_AGENT = {
    "design": "designer",
    "budget": "budget",
    "procurement": "procurement",
    "construction": "construction",
    "qa_inspector": "qa_inspector",
    "settlement": "settlement",
    "concierge": "concierge",
    "content_publish": "concierge",
    "kitchen": "kitchen",
    "bathroom": "bathroom",
    "mep": "mep",
    "appliance": "appliance",
    "furniture": "furniture",
    "door_window": "door_window",
    "takeoff": "takeoff",
    "files": "files",
    "products": "products",
    "identity": "identity",
    "notifications": "notifications",
    "ifc_export": "ifc_export",
}


# 主链路 canonical 顺序 + 链式表述领域关键词（v1.15.x）
_CHAIN_ORDER = ["designer", "budget", "procurement", "construction", "qa_inspector", "settlement"]
_CHAIN_CONNECTORS = ("先", "然后", "接着", "随后", "最后", "之后", "再")
_CHAIN_DOMAIN_KEYWORDS = {
    "designer": ["设计", "布局", "方案", "户型", "风格", "空间规划"],
    "budget": ["预算", "报价", "费用", "成本", "多少钱", "价格"],
    "procurement": ["采购", "材料", "物料", "建材", "清单", "供应商"],
    "construction": ["施工", "排期", "工期", "进度", "安排施工"],
    "qa_inspector": ["质检", "验收", "缺陷", "整改"],
    "settlement": ["结算", "付款", "尾款", "账单"],
}


def _has_chain_connector(message: str) -> bool:
    """检测链式表述（先/再/然后/最后等连接词）。"""
    return any(c in message for c in _CHAIN_CONNECTORS)


def _rule_decompose(message: str) -> list[AgentTask]:
    """规则分解兜底：默认按 orchestrator 关键词分类为单任务（与原路由行为一致）。

    v1.15.x 走查修复：含「先…再…然后…最后…」等多阶段链式表述且命中 ≥2 个
    主链路领域关键词时，按 canonical 顺序（designer→budget→procurement→
    construction→qa_inspector→settlement）生成依赖链任务，避免真实 LLM 分解
    失败/DAG 校验失败时整段需求塌缩成单任务。
    """
    if _has_chain_connector(message):
        hit = [
            agent for agent, kws in _CHAIN_DOMAIN_KEYWORDS.items()
            if any(k in message for k in kws)
        ]
        if len(hit) >= 2:
            tasks = []
            for agent_name in _CHAIN_ORDER:
                if agent_name not in hit:
                    continue
                tasks.append(AgentTask(
                    task_id=str(uuid.uuid4())[:12],
                    agent_name=agent_name,
                    description=message,
                    dependencies=[tasks[-1].task_id] if tasks else [],
                ))
            logger.info(
                "orchestration._rule_decompose: 链式分解 agent_chain=%s",
                [t.agent_name for t in tasks],
            )
            return tasks

    from app.agents.orchestrator import OrchestratorAgent
    cls = OrchestratorAgent.fallback_classify(message)
    intent = cls["intent"]
    registry = _agent_registry()
    agent_name = _INTENT_TO_AGENT.get(intent, "concierge")
    if agent_name not in registry:
        agent_name = "concierge"  # 无法映射的意图交给客服 Agent
    return [AgentTask(
        task_id=str(uuid.uuid4())[:12],
        agent_name=agent_name,
        description=message,
    )]


def _resolve_dependencies(tasks: list[AgentTask]) -> None:
    """v1.15.x 走查修复：重映射 LLM 分解产生的依赖引用。

    LLM 无法预知 uuid task_id，常按序号（task_1）或 agent 名引用依赖 →
    validate_dag 恒失败整体降级为单任务。此处按「task_N 序号 / agent 名 /
    已有 id」三档解析；无法解析的依赖丢弃（防环/悬空）。
    """
    id_set = {t.task_id for t in tasks}
    by_index: dict[str, str] = {}
    by_agent: dict[str, str] = {}
    for idx, t in enumerate(tasks, start=1):
        by_index[str(idx)] = t.task_id
        by_index[f"task_{idx}"] = t.task_id
        by_agent.setdefault(t.agent_name, t.task_id)
    for t in tasks:
        resolved: list[str] = []
        for dep in t.dependencies:
            target = None
            if dep in id_set:
                target = dep
            elif dep in by_index:
                target = by_index[dep]
            elif dep in by_agent and by_agent[dep] != t.task_id:
                target = by_agent[dep]
            if target is None:
                logger.warning(
                    "orchestration._resolve_dependencies: 丢弃无法解析的依赖 task=%s dep=%r",
                    t.task_id, dep,
                )
                continue
            if target not in resolved:
                resolved.append(target)
        t.dependencies = resolved


async def decompose_request(
    message: str, db=None, user_id: str = "", project_id: str = "",
    user_context: str = "",
) -> list[AgentTask]:
    """用户需求 → 结构化子任务列表。

    LLM 优先（返回 JSON 数组），任何失败诚实降级为规则单任务分解。
    v1.10.x 全链路记忆：user_context（时间/空间感知 + 长期记忆注入块）
    随需求注入分解 prompt，使编排器感知用户偏好/当前时间位置。
    """
    settings = get_settings()
    if settings.agent_orchestration_pipeline_enabled:
        try:
            tasks = await _llm_decompose(message, db, user_id, project_id, user_context)
            if tasks:
                logger.info(
                    "orchestration.decompose: LLM 分解成功 task_count=%d user_id=%s",
                    len(tasks), user_id or "",
                )
                return tasks
        except Exception as e:
            logger.warning("orchestration.decompose: LLM 分解失败，降级规则分解: %s", e)
    return _rule_decompose(message)


async def _llm_decompose(
    message: str, db=None, user_id: str = "", project_id: str = "",
    user_context: str = "",
) -> list[AgentTask] | None:
    """LLM 分解：将复杂需求拆为多 Agent 子任务（JSON 结构输出）。

    要求输出形如：
    {"tasks": [{"agent": "designer", "task": "……", "depends_on": []}]}
    非法/空返回 None 由调用方降级。分解 prompt 不含用户 PII 明文扩散。
    """
    from app.agents.orchestrator import OrchestratorAgent
    agent = OrchestratorAgent()
    try:
        user_ctx_block = (
            f"\n用户上下文（偏好/时间/位置，供理解需求）：\n{user_context}"
            if user_context else ""
        )
        prompt = (
            "你是装修项目总控。请把以下用户需求拆解为可并行/串行执行的子任务，"
            "每个子任务指派给最合适的专业 Agent。\n"
            f"用户需求：{message}\n"
            f"{user_ctx_block}\n"
            "可选 Agent 及职责：\n"
            "- designer: 设计/布局/方案\n- budget: 预算/报价\n- procurement: 采购/物料\n"
            "- construction: 施工/进度\n- qa_inspector: 质检/验收\n- settlement: 结算/付款\n"
            "- kitchen: 厨房设计\n- bathroom: 卫浴设计\n- mep: 水电暖通\n"
            "- appliance: 家电\n- furniture: 家具\n- door_window: 门窗防水\n"
            "- takeoff: 工程量计算\n- soft_furnishing: 软装\n- hard_decoration: 硬装\n"
            "- concierge: 通用客服\n"
            "必须只输出如下 JSON（不要输出任何其他文字）：\n"
            '{"tasks": [{"agent": "designer", "task": "子任务描述", "depends_on": ["前置task_id"]}]}\n'
            "注意：depends_on 引用前置任务时用序号（如 [\"task_1\"]，从 1 开始按输出顺序编号）"
            "或前置任务的 agent 名；无依赖填空数组；任务数 1-4 个，不要过度拆分。"
        )
        messages = [
            {"role": "system", "content": agent.system_prompt},
            {"role": "user", "content": prompt},
        ]
        # v1.13.3（全链路闭环补齐，断点 I）：_llm_decompose 此前绕过 think
        # 直连 _chat，签名收 db/user_id/project_id 却未用于注入。此处复用
        # _inject_evolution_context（Case + Skill 注入），使任务分解同样享有
        # 自进化经验；不做 Case 沉淀——子任务执行已由 harness 统一沉淀（避免重复）。
        if db is not None and user_id:
            await agent._inject_evolution_context(
                messages, message, user_id, db, project_id,
            )
        reply = await agent._chat(messages)
    except Exception as e:
        logger.warning("orchestration._llm_decompose: 调用失败: %s", e)
        return None
    finally:
        await agent.close()

    parsed = _parse_llm_json(reply)
    raw_tasks = parsed.get("tasks") if isinstance(parsed, dict) else None
    if not isinstance(raw_tasks, list) or not raw_tasks:
        logger.warning("orchestration._llm_decompose: 非 JSON/空 tasks，降级规则分解")
        return None

    registry = _agent_registry()
    tasks: list[AgentTask] = []
    for raw in raw_tasks[:4]:
        if not isinstance(raw, dict) or not raw.get("task"):
            continue
        agent_name = str(raw.get("agent") or "concierge").strip().lower()
        if agent_name not in registry:
            agent_name = "concierge"  # 未知 Agent 收敛到客服
        deps = raw.get("depends_on") or []
        deps = [str(d) for d in deps if isinstance(d, (str, int))]
        tasks.append(AgentTask(
            task_id=str(uuid.uuid4())[:12],
            agent_name=agent_name,
            description=str(raw["task"]),
            dependencies=deps,
        ))

    # v1.15.x 走查修复：依赖引用重映射（task_N 序号 / agent 名 / 已有 id 三档），
    # 无法解析的依赖丢弃——防 validate_dag 恒失败整体降级为单任务。
    _resolve_dependencies(tasks)
    return tasks or None


# ── DAG 校验 + 循环检测（2026 前沿：can_dispatch 范式）──


def validate_dag(tasks: list[AgentTask]) -> tuple[bool, str]:
    """校验任务依赖图：重复 ID / 悬空依赖 / 环。

    Returns:
        (ok, error_msg)；ok=False 时 error_msg 给出原因，供调用方回退单任务。
    """
    ids = [t.task_id for t in tasks]
    if len(ids) != len(set(ids)):
        return False, "任务 ID 重复"
    id_set = set(ids)
    for t in tasks:
        for dep in t.dependencies:
            if dep not in id_set:
                return False, f"任务 {t.task_id} 依赖不存在的任务 {dep}"

    # Kahn 拓扑排序检测环
    indegree = {t.task_id: 0 for t in tasks}
    children: dict[str, list[str]] = {t.task_id: [] for t in tasks}
    for t in tasks:
        for dep in t.dependencies:
            if t.task_id in children[dep]:  # 重复依赖去重
                continue
            indegree[t.task_id] += 1
            children[dep].append(t.task_id)
    queue = [tid for tid, deg in indegree.items() if deg == 0]
    visited = 0
    while queue:
        cur = queue.pop(0)
        visited += 1
        for child in children.get(cur, []):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(tasks):
        return False, "任务依赖存在环（循环派发）"
    return True, ""


def topological_order(tasks: list[AgentTask]) -> list[AgentTask] | None:
    """按依赖返回拓扑序执行列表；存在环返回 None（调用方应先 validate_dag）。"""
    ok, _ = validate_dag(tasks)
    if not ok:
        return None
    by_id = {t.task_id: t for t in tasks}
    indegree = {t.task_id: 0 for t in tasks}
    children: dict[str, list[str]] = {t.task_id: [] for t in tasks}
    for t in tasks:
        for dep in t.dependencies:
            if t.task_id in children[dep]:
                continue
            indegree[t.task_id] += 1
            children[dep].append(t.task_id)
    queue = [t.task_id for t in tasks if indegree[t.task_id] == 0]
    order: list[AgentTask] = []
    while queue:
        cur = queue.pop(0)
        order.append(by_id[cur])
        for child in children[cur]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    return order if len(order) == len(tasks) else None


# ── 工作流执行 ──


async def run_workflow(
    tasks: list[AgentTask],
    db=None, user_id: str = "", project_id: str = "", workflow_id: str = "",
) -> list[AgentTaskResult]:
    """按拓扑序执行子任务（复用 harness.run → 轨迹落库 + Case 提取闭环）。

    前置任务失败 → 依赖它的任务标记 skipped（不级联执行）。
    """
    registry = _agent_registry()
    from app.agents.harness import get_harness
    harness = get_harness()

    order = topological_order(tasks)
    if order is None:
        # DAG 非法（理论上 decompose 已规避）→ 退化为顺序单任务执行
        order = tasks

    results: list[AgentTaskResult] = []
    status_by_id = {t.task_id: t.status for t in tasks}

    for task in order:
        # 前置任务失败/跳过 → 本任务跳过
        deps_failed = any(
            status_by_id.get(dep, "failed") in ("failed", "skipped")
            for dep in task.dependencies
        )
        if deps_failed:
            task.status = "skipped"
            status_by_id[task.task_id] = "skipped"
            agent_orchestration_task_total.labels(agent=task.agent_name, status="skipped").inc()
            results.append(AgentTaskResult(
                task_id=task.task_id, agent_id=task.agent_name,
                status="skipped", result="", reasoning="前置任务未成功，已跳过",
            ))
            continue

        agent_cls = registry.get(task.agent_name)
        if agent_cls is None:
            task.status = "failed"
            status_by_id[task.task_id] = "failed"
            agent_orchestration_task_total.labels(agent=task.agent_name, status="failed").inc()
            results.append(AgentTaskResult(
                task_id=task.task_id, agent_id=task.agent_name,
                status="failed", result="", reasoning=f"Agent {task.agent_name} 未注册",
            ))
            continue

        task.status = "running"
        status_by_id[task.task_id] = "running"
        agent = agent_cls()
        _t0 = time.monotonic()
        logger.info(
            "orchestration.task_start: workflow_id=%s task_id=%s agent=%s deps=%s",
            workflow_id, task.task_id, task.agent_name, task.dependencies,
        )
        try:
            reply = await harness.run(
                agent,
                task.description,
                db=db, user_id=user_id, project_id=project_id,
                workflow_id=workflow_id,
            )
            reply_text = (reply.get("reply") or "").strip()
            if reply.get("fallback") or not reply_text:
                task.status = "failed"
                task.error = "Agent 执行降级/无回复"
            else:
                task.status = "success"
                task.result = reply_text
        except Exception as e:
            logger.warning("orchestration.workflow: %s 任务失败: %s", task.agent_name, e)
            task.status = "failed"
            task.error = str(e)
        finally:
            await agent.close()
        status_by_id[task.task_id] = task.status
        logger.info(
            "orchestration.task_end: workflow_id=%s task_id=%s agent=%s status=%s "
            "duration_ms=%.1f error=%s",
            workflow_id, task.task_id, task.agent_name, task.status,
            (time.monotonic() - _t0) * 1000, task.error[:200] if task.error else "",
        )
        agent_orchestration_task_total.labels(
            agent=task.agent_name, status=task.status,
        ).inc()

        results.append(AgentTaskResult(
            task_id=task.task_id,
            agent_id=task.agent_name,
            status=task.status,
            result=task.result,
            confidence=1.0 if task.status == "success" else 0.0,
            reasoning=task.error or ("规则引擎/harness 执行" if task.status != "success" else ""),
        ))

    return results


def aggregate_results(results: list[AgentTaskResult]) -> dict:
    """聚合子任务结果为面向用户的结构化输出（诚实标注每项来源）。"""
    success = [r for r in results if r.status == "success"]
    failed = [r for r in results if r.status == "failed"]
    skipped = [r for r in results if r.status == "skipped"]

    sections = []
    for r in success:
        sections.append(f"【{r.agent_id}】\n{r.result}")
    for r in failed:
        sections.append(f"【{r.agent_id}】（执行失败）\n{r.reasoning or '服务不可用，请重试'}")
    for r in skipped:
        sections.append(f"【{r.agent_id}】（已跳过，因前置任务未成功）")

    summary = f"已完成 {len(success)}/{len(results)} 项子任务"
    if failed:
        summary += f"，{len(failed)} 项失败"
    if skipped:
        summary += f"，{len(skipped)} 项跳过"

    return {
        "summary": summary,
        "results": [r.to_dict() for r in results],
        "success_count": len(success),
        "failed_count": len(failed),
        "skipped_count": len(skipped),
        "reply": "\n\n".join(sections) if sections else summary,
        "engine": "orchestration_pipeline",
    }

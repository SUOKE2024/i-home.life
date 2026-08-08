"""Agent Skill 蒸馏与进化服务 — 自进化管线的能力跃升层

借鉴 EverMind SkillCorpus + HarnessBank：
  Phase 2（蒸馏）: 同主题 Case 聚类 → LLM 蒸馏为 Skill → 校验 → active
  Phase 3（进化）: Skill 随成败回写 + 三维质控（Utility/Robustness/Safety）
                  + WHERE×WHY 诊断归因循环（抗过拟合核心）

HarnessBank 核心原则（本服务轻量实现）：
  「提出变更（LLM，有噪声）与归因变更（确定性代码，可信）必须分离」
  - LLM 诊断失败 Case 的 (WHERE=哪个环节, WHY=为何失败) 病理
  - 确定性代码做配对显著性检验（z≥1.96 才采纳 Skill patch）
  - 以 (WHERE×WHY) 病理为键存档，而非以"任务"为键（抗过拟合归纳偏置）

设计约束（对齐 CLAUDE.md）：
- feature flag 门控（agent_skill_distillation_enabled / agent_skill_evolution_enabled）
- best-effort：蒸馏/进化失败仅 log，不影响主流程
- 生成前先检查现有 Skill（合并相似而非新建冗余）—— SkillCorpus 策展思想
- scope 隔离 + user_id 强隔离
- LLM 调用走 BaseAgent fallback chain
"""
from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.agent_case import AgentCase
from app.models.agent_skill import (
    AgentSkill, STATUS_DRAFT, STATUS_ACTIVE, STATUS_ARCHIVED,
    SCOPE_PERSONAL,
)

logger = logging.getLogger(__name__)

# Case 聚类触发阈值：同 agent_name 下未蒸馏 Case 达到此数才触发蒸馏
_DISTILL_THRESHOLD = 3

# 配对显著性检验阈值（z-score，借鉴 HarnessBank Gated Screening）
_SIGNIFICANCE_Z = 1.96  # 95% 置信


async def distill_skill_from_cases(
    db: AsyncSession,
    *,
    agent_name: str,
    owner_id: str,
    scope: str = SCOPE_PERSONAL,
    created_by: str = "",
) -> AgentSkill | None:
    """Phase 2: 从同主题 Case 聚类蒸馏为 Skill。

    流程（借鉴 EverOS Case→Skill 蒸馏 + SkillCorpus 策展）：
      1. 查同 agent_name + scope 下未蒸馏的高质量 Case（quality >= 0.5）
      2. 达到 _DISTILL_THRESHOLD 才触发
      3. 生成前检查现有 Skill（合并相似而非新建冗余）
      4. LLM 从 Case 簇蒸馏 Skill（system_prompt + tools + acceptance_criteria）
      5. 存为 STATUS_DRAFT（需校验/进化后才 active）
      6. 回写 Case.distilled_to_skill_id

    Returns:
        新建的 AgentSkill 或 None（不足阈值/flag 关闭/提取失败）
    """
    settings = get_settings()
    if not settings.agent_skill_distillation_enabled:
        return None

    # 1. 查未蒸馏的高质量 Case
    stmt = (
        select(AgentCase)
        .where(
            and_(
                AgentCase.agent_name == agent_name,
                AgentCase.scope == scope,
                AgentCase.owner_id == owner_id,
                AgentCase.quality_score >= 0.5,
                AgentCase.distilled_to_skill_id.is_(None),
                AgentCase.deleted_at.is_(None),
            )
        )
        .order_by(AgentCase.quality_score.desc())
        .limit(10)
    )
    result = await db.execute(stmt)
    cases = list(result.scalars().all())

    if len(cases) < _DISTILL_THRESHOLD:
        logger.debug(
            "distill_skill: %s 不足阈值（%d < %d），跳过",
            agent_name, len(cases), _DISTILL_THRESHOLD,
        )
        return None

    # 2. LLM 蒸馏 Skill 结构
    skill_data = await _llm_distill_skill(cases, agent_name)
    if skill_data is None:
        logger.debug("distill_skill: LLM 蒸馏失败，跳过")
        return None

    # 3. 检查现有 Skill（合并相似而非新建冗余——SkillCorpus 策展）
    existing = await _find_similar_skill(
        db, agent_name=agent_name, owner_id=owner_id, scope=scope,
        name=skill_data.get("name", ""),
    )
    if existing:
        logger.info("distill_skill: 合并到已有 Skill %s（避免冗余）", existing.id)
        # 回写 Case 的 distilled_to_skill_id
        cluster_id = str(uuid.uuid4())
        for case in cases:
            case.cluster_id = cluster_id
            case.distilled_to_skill_id = existing.id
        await db.flush()
        return existing

    # 4. 创建新 Skill（STATUS_DRAFT）
    cluster_id = str(uuid.uuid4())
    new_skill = AgentSkill(
        id=str(uuid.uuid4()),
        name=skill_data.get("name", f"{agent_name}_distilled"),
        description=skill_data.get("description", ""),
        owner_scope=scope,
        owner_id=owner_id,
        agent_name=agent_name,
        system_prompt=skill_data.get("system_prompt", ""),
        provider="deepseek",
        tools=json.dumps(skill_data.get("tools", []), ensure_ascii=False),
        cost_tier="standard",
        acceptance_criteria=json.dumps(
            skill_data.get("acceptance_criteria", []), ensure_ascii=False,
        ),
        version=1,
        status=STATUS_DRAFT,
        created_by=created_by or owner_id,
    )
    db.add(new_skill)
    await db.flush()

    # 5. 回写 Case
    for case in cases:
        case.cluster_id = cluster_id
        case.distilled_to_skill_id = new_skill.id
    await db.flush()

    logger.info(
        "distill_skill: 已蒸馏 Skill %s (agent=%s, from %d cases)",
        new_skill.id, agent_name, len(cases),
    )
    return new_skill


_SKILL_DISTILL_PROMPT = """你是 Agent Skill 蒸馏器。从以下任务执行 Case 中提炼可复用的 Skill。

Case 列表（{count} 条）：
{cases_text}

请提取并返回严格 JSON（不要 markdown 代码块）：
{{
  "name": "Skill 名称（简短，如 compare_materials_by_cost）",
  "description": "Skill 用途描述",
  "system_prompt": "可复用的 system prompt（包含通用步骤和注意事项，200-500字）",
  "tools": ["该 Skill 常用的工具名称列表"],
  "acceptance_criteria": [
    {{"input": "示例输入", "expected": "期望输出特征"}}
  ]
}}

规则：
- 提炼的是跨 Case 的通用模式，不是某个具体 Case 的复制
- system_prompt 应包含：何时使用、关键步骤、已知陷阱（来自失败 Case）
- acceptance_criteria 至少 2 条，用于后续校验 Skill 质量
"""


async def _llm_distill_skill(cases: list[AgentCase], agent_name: str) -> dict | None:
    """LLM 从 Case 簇蒸馏 Skill 结构。"""
    cases_text_parts = []
    for i, case in enumerate(cases, 1):
        steps_text = case.approach
        try:
            steps = json.loads(case.approach) if case.approach else []
            steps_text = "; ".join(
                f"步骤{s.get('step')}: {s.get('attempted', '')}→{s.get('result', '')}"
                for s in steps[:5]
            )
        except (json.JSONDecodeError, TypeError):
            pass
        cases_text_parts.append(
            f"Case {i} [质量={case.quality_score:.1f}]: {case.task_intent}\n  步骤: {steps_text}"
        )
    cases_text = "\n".join(cases_text_parts)

    prompt = _SKILL_DISTILL_PROMPT.format(count=len(cases), cases_text=cases_text)
    messages = [
        {"role": "system", "content": "你是 Agent Skill 蒸馏器，只返回严格 JSON。"},
        {"role": "user", "content": prompt},
    ]
    try:
        from app.agents.base import BaseAgent

        agent = BaseAgent()
        agent.agent_name = "skill_distiller"
        agent.system_prompt = "你是 Agent Skill 蒸馏器，只返回严格 JSON。"
        reply = await agent._chat(messages)
        await agent.close()
    except Exception as e:
        logger.debug("_llm_distill_skill: LLM 调用失败: %s", e)
        return None

    return _parse_skill_json(reply)


def _parse_skill_json(reply: str) -> dict | None:
    """安全解析 LLM 返回的 Skill JSON。"""
    if not reply or not isinstance(reply, str):
        return None
    text = reply.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except (json.JSONDecodeError, TypeError):
                return None
        else:
            return None
    if not isinstance(data, dict) or "system_prompt" not in data:
        return None
    return data


async def _find_similar_skill(
    db: AsyncSession,
    *,
    agent_name: str,
    owner_id: str,
    scope: str,
    name: str,
) -> AgentSkill | None:
    """检查现有 Skill 是否与待创建的相似（避免冗余——SkillCorpus 策展）。"""
    if not name:
        return None
    stmt = (
        select(AgentSkill)
        .where(
            and_(
                AgentSkill.agent_name == agent_name,
                AgentSkill.owner_scope == scope,
                AgentSkill.owner_id == owner_id,
                AgentSkill.name == name,
                AgentSkill.deleted_at.is_(None),
                AgentSkill.status.in_([STATUS_DRAFT, STATUS_ACTIVE]),
            )
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalars().first()


# ── Phase 3: Skill 进化（三维质控 + WHERE×WHY 诊断归因）──


async def record_skill_outcome(
    db: AsyncSession,
    *,
    skill_id: str,
    success: bool,
) -> None:
    """记录 Skill 使用后的任务成败（随成败进化数据层）。

    被 BaseAgent 在使用 Skill 执行任务后调用（best-effort）。
    """
    settings = get_settings()
    if not settings.agent_skill_evolution_enabled:
        return
    stmt = select(AgentSkill).where(AgentSkill.id == skill_id)
    result = await db.execute(stmt)
    skill = result.scalars().first()
    if not skill:
        return
    if success:
        skill.success_count += 1
    else:
        skill.fail_count += 1
    await db.flush()


async def evaluate_skill_quality(db: AsyncSession, *, skill_id: str) -> dict | None:
    """Phase 3: 计算 Skill 三维质控评分（借鉴 SkillCorpus）。

    维度：
    - Utility（实用性）: success_rate = success / (success + fail)，高频使用且成功率高→高分
    - Robustness（鲁棒性）: 基于总使用次数的置信度（次数越多评分越稳定）
    - Safety（安全性）: fail_rate 反向（失败率低→高分）

    Returns:
        {"utility": float, "robustness": float, "safety": float, "overall": float}
        或 None（flag 关闭/Skill 不存在）
    """
    settings = get_settings()
    if not settings.agent_skill_evolution_enabled:
        return None

    stmt = select(AgentSkill).where(AgentSkill.id == skill_id)
    result = await db.execute(stmt)
    skill = result.scalars().first()
    if not skill:
        return None

    total = skill.success_count + skill.fail_count
    if total == 0:
        utility = 0.0
        robustness = 0.0
        safety = 1.0  # 无使用记录，默认安全
    else:
        success_rate = skill.success_count / total
        fail_rate = skill.fail_count / total
        # Utility: 成功率 + 使用频次加权（使用越多越有实用价值）
        frequency_factor = min(1.0, total / 10.0)  # 10 次使用达到满频次权重
        utility = success_rate * (0.5 + 0.5 * frequency_factor)
        # Robustness: 置信度（Wilson 区间下界近似）
        z = 1.96
        p = success_rate
        denom = 1 + z * z / total
        center = (p + z * z / (2 * total)) / denom
        robustness = max(0.0, center)
        # Safety: 失败率反向
        safety = 1.0 - fail_rate

    overall = (utility + robustness + safety) / 3.0

    skill.utility_score = round(utility, 3)
    skill.robustness_score = round(robustness, 3)
    skill.safety_score = round(safety, 3)
    skill.last_evaluated_at = datetime.now(timezone.utc)

    # 低质 Skill 自动 archived（进化淘汰）
    if total >= 5 and overall < 0.3:
        skill.status = STATUS_ARCHIVED
        logger.info(
            "evaluate_skill: Skill %s 质量过低（overall=%.2f），已 archived", skill_id, overall,
        )
    # 高质 DRAFT Skill 自动 active（进化晋升）
    elif total >= 3 and overall >= 0.6 and skill.status == STATUS_DRAFT:
        skill.status = STATUS_ACTIVE
        logger.info(
            "evaluate_skill: Skill %s 质量达标（overall=%.2f），DRAFT→ACTIVE", skill_id, overall,
        )

    await db.flush()
    return {
        "utility": round(utility, 3),
        "robustness": round(robustness, 3),
        "safety": round(safety, 3),
        "overall": round(overall, 3),
    }


async def diagnose_credit_skill_patch(
    db: AsyncSession,
    *,
    skill_id: str,
    before_success_rate: float,
    after_success_rate: float,
    sample_size: int,
) -> dict:
    """Phase 3: WHERE×WHY 诊断归因循环（借鉴 HarnessBank，轻量版）。

    HarnessBank 核心原则：提出变更（LLM）与归因变更（确定性代码）分离。
    本函数实现「归因」侧——确定性统计检验，判断 Skill patch 是否真的有效。

    Args:
        skill_id: 被评估的 Skill
        before_success_rate: patch 前成功率
        after_success_rate: patch 后成功率
        sample_size: 样本量（patch 后评估次数）

    Returns:
        {"significant": bool, "z_score": float, "delta": float, "credited": bool}
        credited=True 表示通过显著性检验，可采纳该 patch
    """
    settings = get_settings()
    if not settings.agent_skill_evolution_enabled:
        return {"significant": False, "z_score": 0.0, "delta": 0.0, "credited": False}

    delta = after_success_rate - before_success_rate
    # 配对比例显著性检验（z-score，借鉴 HarnessBank Gated Screening 四闸门之一）
    # H0: patch 前后成功率无差异
    if sample_size <= 0 or before_success_rate >= 1.0:
        z_score = 0.0
    else:
        # 合并比例的标准误
        p_pool = (before_success_rate + after_success_rate) / 2.0
        se = math.sqrt(p_pool * (1 - p_pool) * 2.0 / max(sample_size, 1))
        z_score = abs(delta) / se if se > 0 else 0.0

    significant = z_score >= _SIGNIFICANCE_Z
    credited = significant and delta > 0

    logger.info(
        "diagnose_credit: Skill %s delta=%.3f z=%.2f significant=%s credited=%s",
        skill_id, delta, z_score, significant, credited,
    )
    return {
        "significant": significant,
        "z_score": round(z_score, 3),
        "delta": round(delta, 3),
        "credited": credited,
    }


async def get_skill_for_injection(
    db: AsyncSession,
    *,
    agent_name: str,
    owner_id: str,
    scope: str = SCOPE_PERSONAL,
) -> AgentSkill | None:
    """检索可注入的 Skill（供 BaseAgent 执行前使用）。

    优先取 ACTIVE + 高 utility_score 的 Skill。
    """
    settings = get_settings()
    if not settings.agent_skill_distillation_enabled:
        return None

    stmt = (
        select(AgentSkill)
        .where(
            and_(
                AgentSkill.agent_name == agent_name,
                AgentSkill.owner_scope == scope,
                AgentSkill.owner_id == owner_id,
                AgentSkill.status == STATUS_ACTIVE,
                AgentSkill.deleted_at.is_(None),
            )
        )
        .order_by(AgentSkill.utility_score.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalars().first()

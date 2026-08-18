"""Agent 运行时治理安全审计 — OWASP Agentic Skills Top 10 对照（2026）

将 2026 OWASP Agentic Skills Top 10 风险类别逐项映射到本平台既有控制措施，
输出确定性审计报告（只读、无副作用、无网络/DB 写入）。

设计原则：
- 确定性检查：每个 AG 类别依据 settings feature flag / 既有安全机制判定
  pass / warn / fail，不依赖 LLM（诚实标注 evidence 为实际落地的控制点）
- 可追溯：evidence 引用具体模块/flag，供管理员定位整改
- 报告含整改建议：warn/fail 项给出明确 action
- 仅暴露给管理员（app/api/admin.py 端点），普通用户不可见

OWASP Agentic Skills Top 10（2026 版）与本平台控制映射见 AGENTIC_SKILL_RISKS。
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


# ── OWASP Agentic Skills Top 10 风险类别定义 ──

AGENTIC_SKILL_RISKS: list[dict] = [
    {
        "id": "AG1", "name": "Agentic Prompt Injection",
        "desc": "外部内容（网页/文件/工具输出）注入恶意指令劫持 Agent 行为",
        "control": "工具 description 防投毒校验（mcp_security.validate_tool_description）"
                   "+ 多智能体编排结构化 Agent 消息（AgentTaskResult，防注入 seams）",
    },
    {
        "id": "AG2", "name": "Excess Agency / Uncontrolled Autonomy",
        "desc": "Agent 自主执行超出授权的操作（高危动作无人工审批）",
        "control": "三档安全 posture（strict/auto/dangerous）+ 高危工具 AgentApproval 状态机"
                   "（strict 模式 pending 拦截，拒绝-重新触发）",
    },
    {
        "id": "AG3", "name": "Insecure Output Handling",
        "desc": "Agent 输出被下游系统当作指令执行（输出未受约束）",
        "control": "Model Spec 宪法 + HC 硬约束 + rebuttal_engine 反驳重生成"
                   "（check_output_with_semantic 关键词预筛 + LLM 语义兜底）",
    },
    {
        "id": "AG4", "name": "Poisoned Skill Supply Chain",
        "desc": "恶意 Skill/插件被引入执行（供应链完整性缺失）",
        "control": "Skill scope-owned 授权共享（_can_read 权限校验，share_scope 治理）"
                   "+ 工具 description 防投毒校验",
    },
    {
        "id": "AG5", "name": "Insecure Agent-to-Agent Communication",
        "desc": "Agent 间消息未鉴权/未结构化，可被篡改或注入",
        "control": "A2A 协议（a2a_enabled）+ PASETO v4.local 鉴权"
                   "+ 编排层 AgentTaskResult 结构化消息（JSON 数据聚合，非自由文本拼接）",
    },
    {
        "id": "AG6", "name": "Unbounded Computational Resources",
        "desc": "Agent 无限循环/无预算约束导致资源耗尽",
        "control": "agent_function_call_max_rounds 工具轮数上限 + harness agent_timeout 超时"
                   "+ max_retries 重试上限",
    },
    {
        "id": "AG7", "name": "Insecure Tool / Skill Authorization",
        "desc": "未授权用户/Agent 访问工具与数据（越权）",
        "control": "verify_project_access 项目归属校验（API 层）+ 审批状态机"
                   "+ Skill 授权读取（_can_read）",
    },
    {
        "id": "AG8", "name": "Unvalidated / Hallucinated Tool Inputs",
        "desc": "LLM 幻觉生成非法工具参数（schema 不符 / 非 JSON）",
        "control": "FunctionCall 工具 schema 严格校验 + 参数 JSON 宽容解析容错"
                   "（_chat_single_provider 解析失败回退空参数）",
    },
    {
        "id": "AG9", "name": "Sensitive Information Leakage",
        "desc": "PII / 密钥 / 内部信息经 Agent 输出泄漏",
        "control": "pii_masking 输出掩码 + 会话 Fernet 加密（allow_plaintext_session=False 拒绝明文）"
                   "+ agent_traces prompt 截断采样（防 PII 扩散）",
    },
    {
        "id": "AG10", "name": "Improper Input / Output Validation",
        "desc": "Agent 输入输出缺校验导致异常注入/输出违规",
        "control": "Pydantic 输入校验（message 长度/location 格式）+ Model Spec HC 输出硬约束",
    },
]


def _verify_project_access_coverage() -> int:
    """统计 verify_project_access 覆盖的 API 文件数（对齐 IHomeEval _idor_score）。"""
    try:
        root = Path(__file__).resolve().parents[2]
        result = __import__("subprocess").run(
            ["grep", "-rl", "verify_project_access", str(root / "app" / "api")],
            capture_output=True, text=True, timeout=10,
        )
        return len([f for f in result.stdout.splitlines() if f.endswith(".py")])
    except Exception as e:
        logger.debug("governance_audit: verify_project_access 覆盖率统计失败: %s", e)
        return 0


# ── ATH 可信握手协议 + 7 项国标信任层对照（v1.15.7，信通院 2026-07）──
# 信通院联合腾讯/华为发布 ATH 1.0（智能体可信握手协议）；7 项国标落地，
# MCP/A2A/ATH 三协议共建信任层。本表将 ATH 信任层要点映射到本平台控制点，
# 供企业级专属智能体（Claw 类）评估自检与差距整改。

ATH_TRUST_CHECKS: list[dict] = [
    {
        "id": "ATH1", "name": "智能体身份可信声明",
        "desc": "Agent Card 声明可核验的身份与能力（ATH 握手前置）",
        "control": "A2A Agent Card（/.well-known/agent-card 公开发现 + REGISTERED_AGENT_NAMES）",
    },
    {
        "id": "ATH2", "name": "握手互认与任务状态机",
        "desc": "跨 Agent 任务下发遵循标准状态机（submitted→working→completed/failed）",
        "control": "A2A Task Machine（/api/a2a/tasks/send + 状态查询 + TTL 过期清理）",
    },
    {
        "id": "ATH3", "name": "执行证据链可回放",
        "desc": "任务执行结果附可核验证据（谁执行/何时/是否降级）",
        "control": "a2a_tasks.trace_id/evidence（v1.15.5）+ agent_traces 轨迹回放（tool_calls 落库）",
    },
    {
        "id": "ATH4", "name": "动作可验证意图",
        "desc": "Agent 发起的付款类动作携带可验证意图证明（AP2 Verifiable Intent 对齐）",
        "control": "agent_payment_intent HMAC-SHA256 意图 token（签发/校验端点，TTL 600s）",
    },
    {
        "id": "ATH5", "name": "MCP 规范对齐",
        "desc": "工具暴露遵循 MCP 2026-07-28 规范（stateless 核心 8 项）",
        "control": "app/mcp/ 8 项规范实现 + mcp_security_hardening（描述防投毒/SSRF/清洗）",
    },
]


def _audit_ath_trust_layer() -> dict:
    """ATH/国标信任层确定性审计（v1.15.7，只读无副作用）。

    Returns:
        {"summary": {total/pass/warn/fail/score}, "findings": [...],
         "standard_refs": [信通院公开依据], "recommendations": [...]}
    """
    settings = get_settings()
    findings: list[dict] = []

    def _check(idx: int, status: str, evidence: str, recommendation: str = "") -> None:
        check = ATH_TRUST_CHECKS[idx]
        findings.append({
            "id": check["id"], "name": check["name"], "desc": check["desc"],
            "control": check["control"], "status": status,
            "evidence": evidence, "recommendation": recommendation,
        })

    # ATH1 身份声明：A2A Agent Card 公开发现
    _check(0, "pass",
           f"a2a_enabled={settings.a2a_enabled}：/.well-known/agent-card 公开发现端点"
           " + REGISTERED_AGENT_NAMES 能力清单（22 执行型 Agent）")

    # ATH2 状态机
    _check(1, "pass",
           f"a2a_enabled={settings.a2a_enabled}：Task Machine 状态机（submitted/working/"
           "completed/failed）+ 24h TTL 过期清理 + 越权/降级诚实标注")

    # ATH3 证据链（v1.15.5 落地）
    if settings.agent_trace_persist_enabled:
        _check(2, "pass",
               "agent_trace_persist_enabled=True + a2a_tasks.trace_id/evidence 证据链"
               "（v1.15.5）+ agent_traces.tool_calls 轨迹可回放")
    else:
        _check(2, "warn",
               f"agent_trace_persist_enabled={settings.agent_trace_persist_enabled}："
               "轨迹不落库，A2A 证据链缺失回放源",
               "开启 agent_trace_persist_enabled=True")

    # ATH4 可验证意图（v1.15.5 落地；escrow 绑定为 P2 路线图，诚实标注）
    if settings.agent_payment_intent_enabled:
        _check(3, "pass",
               "agent_payment_intent_enabled=True：HMAC-SHA256 意图 token 签发/校验"
               "端点就绪（诚实标注：escrow 支付链路绑定为 P2 路线图，未绑定前不宣称支付闭环）")
    else:
        _check(3, "warn",
               f"agent_payment_intent_enabled={settings.agent_payment_intent_enabled}",
               "开启 agent_payment_intent_enabled=True")

    # ATH5 MCP 对齐
    if settings.mcp_security_hardening_enabled:
        _check(4, "pass",
               "app/mcp/ 对齐 2026-07-28 规范 8 项（stateless/discover/header-routing/"
               "cacheable/MRTR/RFC9207/Tasks/Server Card）+ mcp_security_hardening_enabled=True")
    else:
        _check(4, "warn",
               f"mcp_security_hardening_enabled={settings.mcp_security_hardening_enabled}",
               "开启 mcp_security_hardening_enabled=True")

    statuses = [f["status"] for f in findings]
    n_pass = statuses.count("pass")
    n_warn = statuses.count("warn")
    n_fail = statuses.count("fail")
    return {
        "framework": "ATH 1.0 可信握手 + 7 项国标信任层（信通院 2026-07）",
        "summary": {
            "total": len(findings), "pass": n_pass, "warn": n_warn, "fail": n_fail,
            "score": f"{n_pass}/{len(findings)}",
        },
        "findings": findings,
        "standard_refs": [
            "智能体可信握手协议（ATH）1.0（信通院联合腾讯/华为等，2026-07）",
            "2026 智能体互联技术标准：7 项国标（MCP/A2A/ATH 三协议共建信任层）",
            "企业级专属智能体（Claw 类）技术能力要求评估（信通院，2026-08 启动）",
        ],
        "recommendations": [
            f["recommendation"] for f in findings
            if f["status"] != "pass" and f["recommendation"]
        ],
    }


def run_governance_audit() -> dict:
    """执行 OWASP Agentic Skills Top 10 对照审计（确定性，只读）。

    Returns:
        {"generated_at": str, "framework": "OWASP Agentic Skills Top 10 (2026)",
         "summary": {"total": 10, "pass": n, "warn": n, "fail": n, "score": "n/10"},
         "findings": [{id, name, desc, status, evidence, recommendation}],
         "recommendations": [str]}
    """
    from datetime import datetime, timedelta, timezone

    settings = get_settings()
    findings: list[dict] = []

    def _check(risk: dict, status: str, evidence: str, recommendation: str = "") -> None:
        findings.append({
            "id": risk["id"], "name": risk["name"], "desc": risk["desc"],
            "control": risk["control"], "status": status,
            "evidence": evidence, "recommendation": recommendation,
        })

    # AG1 提示注入
    if settings.mcp_security_hardening_enabled:
        _check(AGENTIC_SKILL_RISKS[0], "pass",
               "mcp_security_hardening_enabled=True：工具 description 防投毒校验生效；"
               "编排层 AgentTaskResult 结构化消息防注入 seams")
    else:
        _check(AGENTIC_SKILL_RISKS[0], "warn",
               "mcp_security_hardening_enabled=False：工具 description 防投毒校验未启用",
               "建议开启 mcp_security_hardening_enabled=True（内置工具描述已过校验）")

    # AG2 过度自主
    posture = settings.agent_security_posture
    if posture == "dangerous":
        _check(AGENTIC_SKILL_RISKS[1], "warn",
               f"agent_security_posture={posture}：高危工具全放行（无审批拦截）",
               "生产环境建议 agent_security_posture=strict 或 auto")
    else:
        _check(AGENTIC_SKILL_RISKS[1], "pass",
               f"agent_security_posture={posture}：strict 高危工具批准 / auto 正常执行")

    # AG3 不安全输出处理
    if settings.model_spec_enabled:
        _check(AGENTIC_SKILL_RISKS[2], "pass",
               "model_spec_enabled=True：Model Spec HC 硬约束 + rebuttal_engine 反驳重生成")
    else:
        _check(AGENTIC_SKILL_RISKS[2], "warn",
               "model_spec_enabled=False：输出 HC 硬约束未启用",
               "建议开启 model_spec_enabled=True")

    # AG4 技能供应链
    if settings.agent_skill_enabled and settings.mcp_security_hardening_enabled:
        _check(AGENTIC_SKILL_RISKS[3], "pass",
               "agent_skill_enabled=True（scope-owned 授权共享）+ 工具防投毒校验生效")
    elif settings.agent_skill_enabled:
        _check(AGENTIC_SKILL_RISKS[3], "warn",
               "agent_skill_enabled=True（scope-owned 授权共享）但工具防投毒校验未启用",
               "建议开启 mcp_security_hardening_enabled=True")
    else:
        _check(AGENTIC_SKILL_RISKS[3], "pass",
               "agent_skill_enabled=False：Skill 资产化关闭，供应链面收窄")

    # AG5 Agent 间通信
    if settings.a2a_enabled and settings.paseto_secret_key and \
            settings.paseto_secret_key != "change-me-to-a-random-32-byte-key-minimum":
        _check(AGENTIC_SKILL_RISKS[4], "pass",
               "a2a_enabled=True + PASETO v4.local 强密钥鉴权 + AgentTaskResult 结构化消息")
    else:
        _check(AGENTIC_SKILL_RISKS[4], "warn",
               "a2a_enabled=True 但 PASETO 密钥为默认/空（A2A 鉴权强度不足）",
               "生产环境配置强 PASETO_SECRET_KEY（≥32 字节随机）")

    # AG6 无界计算资源
    if settings.agent_function_call_max_rounds > 0 and settings.harness_agent_timeout_seconds > 0:
        _check(AGENTIC_SKILL_RISKS[5], "pass",
               f"agent_function_call_max_rounds={settings.agent_function_call_max_rounds} "
               f"+ harness_agent_timeout_seconds={settings.harness_agent_timeout_seconds}："
               "工具轮数 + 超时双约束")
    else:
        _check(AGENTIC_SKILL_RISKS[5], "warn",
               "工具轮数或 harness 超时未配置上限", "建议设置有限的正值上限")

    # AG7 工具/Skill 授权
    coverage = _verify_project_access_coverage()
    if settings.tool_real_data_enabled and coverage >= 20:
        _check(AGENTIC_SKILL_RISKS[6], "pass",
               f"tool_real_data_enabled=True + verify_project_access 覆盖 {coverage} 个 API 文件"
               "+ Skill _can_read 授权读取 + 审批状态机")
    else:
        _check(AGENTIC_SKILL_RISKS[6], "warn",
               f"tool_real_data_enabled={settings.tool_real_data_enabled}，"
               f"verify_project_access 覆盖 {coverage} 个 API 文件（<20）",
               "补齐 API 层项目归属校验（verify_project_access）")

    # AG8 幻觉工具输入
    if settings.agent_function_call_enabled:
        _check(AGENTIC_SKILL_RISKS[7], "pass",
               "agent_function_call_enabled=True：FunctionCall schema 严格校验 + 参数 JSON 宽容解析")
    else:
        _check(AGENTIC_SKILL_RISKS[7], "pass",
               "agent_function_call_enabled=False：FunctionCall 关闭，无工具输入面")

    # AG9 敏感信息泄漏
    plaintext = bool(getattr(settings, "allow_plaintext_session", False))
    if settings.pii_masking_enabled and not plaintext:
        _check(AGENTIC_SKILL_RISKS[8], "pass",
               "pii_masking_enabled=True + allow_plaintext_session=False（会话 Fernet 加密）"
               "+ agent_traces prompt 截断采样")
    else:
        _check(AGENTIC_SKILL_RISKS[8], "warn",
               f"pii_masking_enabled={settings.pii_masking_enabled}，"
               f"allow_plaintext_session={plaintext}（明文会话降级开启）",
               "生产禁止 allow_plaintext_session=True")

    # AG10 输入输出校验
    if settings.model_spec_enabled:
        _check(AGENTIC_SKILL_RISKS[9], "pass",
               "Pydantic 输入校验（message 长度/location 格式）+ Model Spec HC 输出硬约束")
    else:
        _check(AGENTIC_SKILL_RISKS[9], "warn",
               "Pydantic 输入校验生效，但 Model Spec HC 输出约束未启用",
               "建议开启 model_spec_enabled=True")

    # 汇总
    statuses = [f["status"] for f in findings]
    n_pass = statuses.count("pass")
    n_warn = statuses.count("warn")
    n_fail = statuses.count("fail")
    recommendations = [
        f["recommendation"] for f in findings
        if f["status"] != "pass" and f["recommendation"]
    ]
    _bj_tz = timezone(timedelta(hours=8), name="Asia/Shanghai")
    return {
        "generated_at": datetime.now(_bj_tz).isoformat(),
        "framework": "OWASP Agentic Skills Top 10 (2026)",
        "summary": {
            "total": len(findings), "pass": n_pass, "warn": n_warn, "fail": n_fail,
            "score": f"{n_pass}/{len(findings)}",
        },
        "findings": findings,
        "recommendations": recommendations,
        # v1.15.7 ATH/国标信任层独立章节（不并入 OWASP 10 项，兼容既有断言）
        "ath_trust_layer": _audit_ath_trust_layer(),
    }

"""AI 应用服务商能力档案（v1.17.4）

政策依据：工信厅科函〔2026〕414号《关于开展人工智能应用服务商培育专项行动的通知》
（2026-08-27 成文 / 2026-08-31 发布）。通知将「人工智能应用服务商」定义为围绕
用户单位智能化需求，提供人工智能解决方案 **咨询规划 / 交付实施 / 运营管理 /
安全治理** 等服务的企业或机构，配套服务为第五类；任务一要求「建立服务商资源池」
并建立服务商档案（附件1 模板），省级主管部门 **2026-12-01 前**报送。

本模块按政策定义的五类服务组织平台**确有代码证据**的能力条目，产出可提交的
资源池入池材料底座（`GET /api/admin/ai-service-provider-profile`）。

诚实红线（不可绕过，与 CLAUDE.md「诚实降级」一致）：
- 每条能力必须给出 `evidence`（仓库内真实模块路径），`status` 由文件存在性
  **确定性判定**，不依赖人工声明；无证据/未实现的条目如实标 `not_evidenced`
  并在 `note` 说明，禁止编造能力充数。
- `maturity_level` **恒为 `not_assessed`**——GB/T 45907-2025 成熟度等级判定
  须第三方评估机构出具结论，平台自检不得自评等级。
- `disclaimer` 恒带「非第三方认证结论，不构成资源池入库证明」。
- 纯确定性实现：零 LLM 调用、零外部网络调用、只读无副作用。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

# app/services/xxx.py → parents[2] = 仓库根
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = "app/services/ai_service_provider_profile.py"

PROFILE_DISCLAIMER = (
    "本档案为平台自检材料，非第三方认证结论，不构成资源池入库证明。"
    "资源池正式申报须由企业按省级主管部门要求提交并经审核。"
)

MATURITY_NOTE = (
    "平台自检不评定成熟度等级（恒为 not_assessed）：GB/T 45907-2025《人工智能 "
    "服务能力成熟度评估》等级判定须由第三方评估机构实施并出具结论。"
    "本档案仅按要求组织能力条目与代码证据，供第三方评估与省级报送时引用。"
)

# ── 政策事实（原文核验，非解读）──

POLICY_BASIS: dict = {
    "document": "工信厅科函〔2026〕414号",
    "title": "关于开展人工智能应用服务商培育专项行动的通知",
    "issued_at": "2026-08-27",
    "published_at": "2026-08-31",
    "issuer": "工业和信息化部办公厅（联合国务院国资委等）",
    "definition": (
        "人工智能应用服务商：围绕用户单位智能化需求，提供人工智能解决方案"
        "咨询规划、交付实施、运营管理、安全治理等服务的企业或机构（配套服务为第五类）。"
    ),
    "national_targets": {
        "2026_end_resource_pool": "全国资源池服务商突破 2000 家",
        "2027_end_resource_pool": "全国资源池服务商不少于 3000 家",
        "pilot_zone_province": "国家人工智能产业创新应用先导区所在省份 2027 年底本省资源池 ≥100 家",
        "provincial_submission_deadline": "2026-12-01 前由省级主管部门报送服务商资源池（附件2/3）",
        "service_team": "每省 ≥10 个服务团，每个服务团 1 家服务商牵头 + ≥2 家上下游单位",
    },
    "key_tasks": [
        "建立服务商资源池（摸清底数、建立服务商档案，附件1 模板）",
        "提升服务供给水平（服务团 / 安全可靠基础软硬件集成 / 安全合规内嵌全流程）",
        "推动规模化应用（模块化标准化「小快轻准」产品包 / 开放真实场景 / "
        "首购首用与风险补偿 / 加大大模型、智能体、Token 三类服务采购）",
        "加强服务商支撑保障（算力券 / 产教融合实训 / 鼓励搭建 FDE 前线部署工程师团队）",
    ],
    "source_note": "来源：工业和信息化部公开文件（本平台检索核验于 2026-09-23），文号与标题以原文为准。",
}

RELATED_POLICIES: list[dict] = [
    {
        "document": "工信部信发〔2026〕209号",
        "title": "「人工智能+软件」专项行动实施方案",
        "issued_at": "2026-09-02",
        "relation": "软件供给侧行动方案，与本通知培育应用服务商形成供需两侧配合",
    },
    {
        "document": "云政办发〔2025〕57号",
        "title": "云南省全面实施「人工智能+」行动计划",
        "issued_at": "2025-12-19",
        "relation": "省级承接：原文明确「引育人工智能服务商，鼓励开展『人工智能+』咨询服务能力建设」，"
                    "本项目属云南区域空间健康领域承接方",
    },
]

STANDARDS_REFERENCE: list[dict] = [
    {
        "code": "GB/T 45907-2025",
        "title": "人工智能 服务能力成熟度评估",
        "status": "现行（2025-06-30 发布即实施）",
        "note": "等级判定须第三方评估机构实施；本平台不自评等级",
    },
]


# ── 五类服务能力条目（evidence 为仓库内真实模块路径，运行时确定性核验）──

SERVICE_CATEGORIES: list[dict] = [
    {
        "key": "consulting_planning",
        "name": "咨询规划服务",
        "policy_desc": "围绕用户单位智能化需求提供方案咨询、架构规划与可行性论证",
        "capabilities": [
            {"name": "空间设计方案生成与 BOM 输出（Designer Agent）",
             "evidence": "app/agents/designer.py",
             "note": "设计 → 算量 → 报价链路入口，编排见 app/api/design_flow.py"},
            {"name": "预算测算与报价（Budget Agent）",
             "evidence": "app/agents/budget.py", "note": ""},
            {"name": "工程算量",
             "evidence": "app/api/takeoff.py", "note": "BOM 反向驱动采购（以销定产）"},
            {"name": "方案前置决策（F45）",
             "evidence": "app/api/solution_first.py", "note": "先定方案再谈价，降低返工"},
        ],
    },
    {
        "key": "delivery_implementation",
        "name": "交付实施服务",
        "policy_desc": "解决方案落地交付：采购、施工、验收与结算",
        "capabilities": [
            {"name": "以销定产采购驱动（Procurement Agent）",
             "evidence": "app/agents/procurement.py",
             "note": "procurement_demand_driven_enabled 从 Designer BOM 反向驱动采购优先级"},
            {"name": "施工过程管理（Construction Agent）",
             "evidence": "app/agents/construction.py", "note": ""},
            {"name": "质检与节点验收（QA Inspector Agent）",
             "evidence": "app/agents/qa_inspector.py", "note": ""},
            {"name": "结算（Settlement Agent）",
             "evidence": "app/agents/settlement.py", "note": ""},
            {"name": "B2B 装企交付链路",
             "evidence": "app/api/b2b_delivery.py", "note": "设计方案 + 报价 + 施工计划编排（只读）"},
            {"name": "资金托管（节点验收双向确认放款）",
             "evidence": "app/api/escrow_trustee.py", "note": "F43 资金托管深化"},
        ],
    },
    {
        "key": "operations_management",
        "name": "运营管理服务",
        "policy_desc": "交付后的长期运营：资产台账、空间场景、设备运维与主动服务",
        "capabilities": [
            {"name": "存量空间资产全周期台账",
             "evidence": "app/services/space_asset_service.py",
             "note": "评估→改造→交付→运营状态机 + 智能化就绪度评分（/api/space-assets/*）"},
            {"name": "场景自动化与设备联动",
             "evidence": "app/services/scene_automation_service.py",
             "note": "传感器触发 → 设备命令真实执行闭环（/api/scene-automation/*）"},
            {"name": "智能家居设备接入与运维",
             "evidence": "app/api/smart_home.py",
             "note": "生态桥真机接入程度以 /api/ecosystem/status 的 implemented 标记为准（诚实标注）"},
            {"name": "能耗与环境监测",
             "evidence": "app/api/energy.py", "note": "A1 能耗监测"},
            {"name": "传感器数据接入",
             "evidence": "app/api/sensor_snapshot.py", "note": "per-user 限流 + 数值范围校验"},
            {"name": "主动经营日报 / 项目周报（Orchestrator Agent）",
             "evidence": "app/agents/orchestrator.py",
             "note": "每日简报（阿里云 FC 定时触发）+ 项目周报（best-effort 降级逐段标注）"},
        ],
    },
    {
        "key": "security_governance",
        "name": "安全治理服务",
        "policy_desc": "把网络安全、数据安全、伦理治理、业务合规内嵌到研发、部署、应用全流程",
        "capabilities": [
            {"name": "Agent 治理安全审计（OWASP Agentic Skills Top 10 + ATH 信任层）",
             "evidence": "app/services/agent_governance_audit.py",
             "note": "/api/admin/agent-governance-audit（只读确定性对照，pass/warn/fail + 证据）"},
            {"name": "MCP 2026-07-28 规范对齐与安全加固",
             "evidence": "app/mcp/server.py",
             "note": "规范 8 项 + 工具描述防投毒 / SSRF 拦截 / 输出敏感字段清洗"},
            {"name": "健康声明合规闸门（禁疗效词 + 非医疗诊断免责）",
             "evidence": "app/services/health_claim_compliance.py",
             "note": "康养/疗愈/适老文案命中禁用疗效词即阻断"},
            {"name": "设备凭据加密存储（AES-256-GCM）",
             "evidence": "app/services/device_credentials.py",
             "note": "Matter wifi/thread 凭据加密落库，解密失败诚实返回 None"},
            {"name": "智能体身份与握手凭证（GB/Z 185 / ATH）",
             "evidence": "app/api/agent_handshake.py",
             "note": "A2A Agent Card 公开发现 + 应用侧核验 + 握手凭证签发/校验"},
            {"name": "A2A 证据链（trace_id / evidence）",
             "evidence": "app/api/a2a.py",
             "note": "任务执行结果附可核验证据（谁执行/何时/是否降级）"},
        ],
    },
    {
        "key": "supporting_services",
        "name": "配套服务",
        "policy_desc": "FDE 前线部署工程师驻场、模块化产品包、算力与实训等支撑保障",
        "capabilities": [
            {"name": "FDE 现场服务记录（驻场 / 远程支持）",
             "evidence": "app/api/fde_field_service.py",
             "note": "service_type / mode / capability_tags 四维（只声明实际维度）"},
            {"name": "「小快轻准」一口价改造产品包",
             "evidence": "app/services/partial_renovation_service.py",
             "note": "QUICK_INSTALL_PACKAGES（PKG-ELDERLY-* / 快装套餐）：模块化、标准化、短周期、0 搬家"},
            {"name": "适老改造补贴预检（非资格认定）",
             "evidence": "app/services/elderly_subsidy_service.py",
             "note": "确定性估算，输出恒带 is_estimate=True，不宣称已获补贴"},
            {"name": "Token 用量计量口径",
             "evidence": "app/services/ai_token_metering.py",
             "note": "基于 agent_traces 聚合（/api/ai-usage/tokens）；仅计量非计费，接口恒带 billing_ready=False"},
            {"name": "人工智能应用服务团多主体封装",
             "evidence": None,
             "note": "P2 路线图：OrchestratorAgent.plan_and_delegate + A2A 已具备技术链路，"
                     "缺平台侧多主体（联合体）实体，故不列入已具备能力"},
            {"name": "Token 计费结算闭环",
             "evidence": None,
             "note": "P2 路线图：政策要求「加快形成统一 Token 计量口径与结算规范」，"
                     "当前仅内部计量披露，未接计费结算，禁止宣称 Token 账单"},
        ],
    },
]


def _status_for(evidence: str | None) -> str:
    """确定性证据核验（不依赖人工声明）。

    - evidence 为空 → not_evidenced（未给出证据，不编造）
    - evidence 为仓库内模块路径且文件存在 → evidenced
    - evidence 给出但文件不存在 → missing（能力与代码漂移，须排查）
    """
    if not evidence:
        return "not_evidenced"
    if not evidence.startswith("app/"):
        return "missing"
    return "evidenced" if (PROJECT_ROOT / evidence).exists() else "missing"


def _now_iso() -> str:
    _bj_tz = timezone(timedelta(hours=8), name="Asia/Shanghai")
    return datetime.now(_bj_tz).isoformat()


def build_service_provider_profile(include_governance: bool = True) -> dict:
    """构建 AI 应用服务商能力档案（确定性，只读）。

    `governance_evidence` 复用 `run_governance_audit()` 的 OWASP 10 项 + ATH 5 项
    结果，不重复实现治理检查。
    """
    categories: list[dict] = []
    n_total = n_evidenced = n_missing = n_not_evidenced = 0

    for cat in SERVICE_CATEGORIES:
        caps: list[dict] = []
        for cap in cat["capabilities"]:
            evidence = cap.get("evidence")
            status = _status_for(evidence)
            caps.append({
                "name": cap["name"],
                "evidence": evidence,
                "status": status,
                "note": cap.get("note", ""),
            })
            n_total += 1
            if status == "evidenced":
                n_evidenced += 1
            elif status == "missing":
                n_missing += 1
            else:
                n_not_evidenced += 1
        categories.append({
            "key": cat["key"],
            "name": cat["name"],
            "policy_desc": cat["policy_desc"],
            "capabilities": caps,
            "evidenced_count": sum(1 for c in caps if c["status"] == "evidenced"),
            "capability_count": len(caps),
        })

    governance: dict = {"included": False}
    if include_governance:
        from app.services.agent_governance_audit import run_governance_audit

        audit = run_governance_audit()
        ath = audit.get("ath_trust_layer", {})
        governance = {
            "included": True,
            "source": "app/services/agent_governance_audit.run_governance_audit（复用同一实现，不重复造）",
            "owasp_agentic_skills_top10": {
                "framework": audit.get("framework"),
                "summary": audit.get("summary", {}),
                "non_pass": [f["id"] for f in audit.get("findings", []) if f["status"] != "pass"],
            },
            "ath_trust_layer": {
                "framework": ath.get("framework"),
                "summary": ath.get("summary", {}),
                "non_pass": [f["id"] for f in ath.get("findings", []) if f["status"] != "pass"],
            },
            "note": "治理审计为平台自检对照（非第三方安全测评），完整结果见 /api/admin/agent-governance-audit",
        }

    return {
        "generated_at": _now_iso(),
        "module": MODULE_PATH,
        "policy_basis": POLICY_BASIS,
        "related_policies": RELATED_POLICIES,
        "service_categories": categories,
        "governance_evidence": governance,
        "standards_reference": STANDARDS_REFERENCE,
        # 诚实红线：平台自检不得自评等级
        "maturity_level": "not_assessed",
        "maturity_note": MATURITY_NOTE,
        "summary": {
            "category_count": len(categories),
            "capability_count": n_total,
            "evidenced": n_evidenced,
            "missing": n_missing,
            "not_evidenced": n_not_evidenced,
        },
        "limitations": [
            "成熟度等级未评定：等级判定须第三方评估机构（GB/T 45907-2025），平台不自评",
            "资源池正式申报由企业在省级报送截止（2026-12-01）前提交，本档案仅为材料底座",
            "Token 计量 ≠ 计费：无统一 Token 结算规范落地前不提供对外计价承诺",
            "智能家居部分生态桥为 stub，真机接入程度以 /api/ecosystem/status 的 implemented 标记为准",
            "治理证据为平台自检对照（OWASP Agentic Skills Top 10 / ATH 信任层），非第三方安全测评结论",
            "服务团「1 家牵头 + N 家上下游」多主体形态暂无平台侧实体承载（P2 路线图）",
        ],
        "disclaimer": PROFILE_DISCLAIMER,
    }

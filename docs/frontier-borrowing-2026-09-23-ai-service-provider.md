# AI 应用服务商培育政策评估与落地（v1.17.4）

> 评估日期：2026-09-23 · 触发：工信部《关于开展人工智能应用服务商培育专项行动的通知》
> **落地状态（2026-09-23 更新）：P0/P1/P2 三项全量落地（v1.17.4）**，第五节 L1–L6 保持诚实遗留。
> 回归测试：`tests/test_ai_service_provider.py`（34 用例）
> 落地实现：`app/services/ai_service_provider_profile.py`（P0）·
> `app/services/ai_token_metering.py` + `app/api/ai_usage.py`（P1）·
> `app/models/fde_field_service.py` + `app/services/fde_field_service.py` + `app/api/fde_field_service.py`（P2）
> 政策出处：
> - 工信厅科函〔2026〕414号《关于开展人工智能应用服务商培育专项行动的通知》（成文 2026-08-27，发布 2026-08-31）
> - 工信部信发〔2026〕209号《"人工智能+软件"专项行动实施方案》（2026-09-02）
> - 云政办发〔2025〕57号《云南省全面实施"人工智能+"行动计划》（2025-12-19）
> - GB/T 45907-2025《人工智能 服务能力成熟度评估》（2025-06-30 发布即实施，现行）

---

## 一、政策事实（原文核验，非解读）

### 1.1 核心定义与目标

**人工智能应用服务商**（通知原文定义）：围绕用户单位智能化需求，提供人工智能解决方案**咨询规划、交付实施、运营管理、安全治理**等服务的企业或机构。配套服务为第五类。

| 指标 | 数值 |
|------|------|
| 2026 年底全国资源池服务商 | 突破 2000 家 |
| 2027 年底全国资源池服务商 | 不少于 3000 家 |
| 下辖国家人工智能产业创新应用先导区的省份 | 2027 年底本省资源池 ≥100 家 |
| 省级报送截止 | **2026-12-01** 前报送资源池（附件2/3） |
| 服务团报送 | 每省 ≥10 个，每个服务团 **1 家服务商牵头 + ≥2 家上下游单位** |

### 1.2 四项重点任务

1. **建立服务商资源池**——摸清底数，建立服务商档案（附件1模板），工信部依据**相关标准**汇总全国资源池。
2. **提升服务供给水平**——组建"人工智能应用服务团"；鼓励**安全可靠操作系统/数据库/推理芯片**集成应用能力；把网络安全、数据安全、伦理治理、业务合规**内嵌到研发、部署、应用全流程**（变被动应对为主动防控）。
3. **推动规模化应用**——封装**模块化、标准化解决方案产品包**（"小快轻准"）；组织开放真实场景；探索**首购首用、风险补偿**模式，加大**大模型、智能体、Token** 三类服务采购力度。
4. **加强服务商支撑保障**——对接国家算力网络枢纽/算力互联互通节点，用好**算力券**；产教融合实训基地；鼓励服务商搭建**前线部署工程师（FDE）团队**，扎根用户现场。

### 1.3 Token 的制度含义（关键）

通知将**大模型、智能体、Token** 三者并列纳入服务采购对象，构建"能力—应用—计量"三位一体采购图谱：
- 大模型 = 基础能力供给
- 智能体 = 面向场景的自主决策执行系统
- **Token = 用模用智的计量与计价载体**，要求**可量化、可核算、可审计**，支撑"从一次性交付转向持续计量、按量结算"（人民邮电报解读：加快形成统一 Token 计量口径与结算是扩大采购规模的前提）。

### 1.4 FDE 与标准

- 通知原文仅表述"鼓励服务商搭建前线部署工程师（FDE）团队，扎根用户现场，保障场景落地"；**FDE 纳入 MIIT/TC1 标准体系**出自金元证券研报（券商观点，非通知原文）。
- 标准侧：**GB/T 45907-2025《人工智能 服务能力成熟度评估》已现行**（TC28 归口，TC28/SC42 执行）。人民邮电报报道工信部正通过 TC28/SC42 与 MIIT/TC1 组织编制"人工智能应用服务商总体要求、成熟度评估"标准。

### 1.5 省级承接（云南）

云政办发〔2025〕57号原文已明确："依托'人工智能+'创新平台，构建'模型开发—测试验证—产业化应用'全链条服务体系。**引育人工智能服务商，鼓励开展'人工智能+'咨询服务能力建设**。"省级目标：30 个以上典型应用场景、30 个以上高质量数据集、10 个以上"人工智能+"创新平台、5 个以上行业垂类大模型。

---

## 二、核心判断：本项目即政策定义的"人工智能应用服务商"

项目对外定位「**空间健康资产运营商**」（存量康养/疗愈/旅居/文旅/适老空间的 AI 智能化改造 + 长期运营），其能力结构与通知定义的**四类服务逐项对应**。这不是新增叙事，而是国家口径对既有定位的背书；同时省级文件已把"引育人工智能服务商"写入行动计划。

| 政策服务类别 | 项目现有能力（代码证据） | 对应关系 |
|---|---|---|
| 咨询规划服务 | designer / budget Agent；BOM → 算量 → 报价链路 | 完全具备 |
| 交付实施服务 | procurement / construction / qa_inspector / settlement Agent；`delivery_orders` / `escrow_payments` | 完全具备 |
| 运营管理服务 | `space_asset_service` 全周期台账（评估→改造→交付→运营）+ 场景自动化 + 设备运维 | 完全具备 |
| 安全治理服务 | `agent_governance_audit`（OWASP Agentic Skills Top 10 + ATH 信任层 5 项）、`health_claim_compliance`、设备凭据 AES-256-GCM | **能力具备，缺档案出口** |
| 配套服务 | FDE 驻场（改造交付天然驻场） | **能力具备，缺登记** |

---

## 三、缺口分析（仅列真实缺失，不虚增）

| # | 缺口 | 现状证据 | 政策依据 |
|---|------|---------|---------|
| G1 | **服务商能力档案无出口** | `run_governance_audit` 已产出 OWASP 10 + ATH 5 审计结果，但仅供内部管理端点调用，未按"四类服务"组织成可对外提交的档案 | 任务一（资源池）+ GB/T 45907-2025 |
| G2 | **Token 计量口径缺位** | `agent_traces` 已有 `prompt_tokens/completion_tokens/total_tokens` 与 `user_id`/`project_id`，但仅服务内部成本追踪，**无 per-project/per-user 用量聚合与对外计量口径** | 任务三（Token 采购标的，可量化/可核算/可审计） |
| G3 | **FDE 现场服务无登记** | `space_assets` 是资产台账（状态机维度），无"谁在现场、做了什么、耗时多少、解决与否"的服务记录 | 任务四（FDE 扎根用户现场） |

**已具备、无需新建**：`QUICK_INSTALL_PACKAGES`（PKG-ELDERLY-* 等一口价干法套餐）即政策所指"小快轻准"产品包原形；`OrchestratorAgent.plan_and_delegate` + A2A 证据链可承载"1 家牵头 + N 家上下游"服务团形态。

---

## 四、落地设计

三个独立 feature flag 灰度，全部**确定性实现、零 LLM 成本**，关闭即回退诚实降级。

### P0 服务商能力档案（`ai_service_provider_profile_enabled`，默认 True）

- 模块：`app/services/ai_service_provider_profile.py`
- 端点：`GET /api/admin/ai-service-provider-profile`（平台管理员；flag 关闭 503）
- 输出结构：
  - `policy_basis`：政策文号与名称（工信厅科函〔2026〕414号）
  - `service_categories`：5 类（咨询规划/交付实施/运营管理/安全治理/配套服务），每类挂 `capabilities[{name, evidence, status}]`，`evidence` 指向真实代码模块/端点而非文案
  - `governance_evidence`：复用 `run_governance_audit()` → OWASP 10 项 + ATH 5 项结果（不重复实现）
  - `standards_reference`：引用 GB/T 45907-2025 编号与名称
  - `maturity_level`：**恒为 `not_assessed`** —— 国标等级判定需第三方评估，平台自检不得自评等级
  - `disclaimer`：恒带「本档案为平台自检材料，非第三方认证结论，不构成资源池入库证明」

**诚实红线**：档案只声明平台**确有代码证据**的能力，`evidence` 为模块路径/端点；无法给出证据的条目标 `not_evidenced`，不编造。

### P1 Token 计量口径（`ai_token_metering_enabled`，默认 True）

- 模块：`app/services/ai_token_metering.py`
- 端点：
  - `GET /api/ai-usage/tokens`——当前用户 Token 用量（`project_id` 可选，传则走 `verify_project_access` 项目归属校验）
  - `GET /api/admin/ai-usage/tokens`——平台级汇总（admin）
- 数据源：`agent_traces` 聚合（`prompt_tokens` / `completion_tokens` / `total_tokens` / 执行次数），按 `agent_name` / `model` / `provider` 分组，支持时间窗
- 输出恒带：`metering_only=True`、`billing_ready=False`、`billing_note`「仅计量口径，未接入计费结算闭环」
- `agent_trace_persist_enabled=False` 时如实标注 `data_source_available=False`（不返回 0 伪装成无用量）

**诚实红线**：计量 ≠ 计费。`agent_traces` 是按采样率落库的可观测数据，**不是完整计费账本**；接口必须显式声明该局限，禁止对外宣称"Token 账单"。

### P2 FDE 现场服务记录（`fde_field_service_enabled`，默认 True）

- 模型：`app/models/fde_field_service.py`（表 `fde_field_visits`）+ alembic 迁移 `l4d5e6f7a8b9`
- 端点：`POST/GET/GET{id}/PATCH/DELETE /api/fde-field-visits`（owner 归属隔离 + admin）
  + `GET /api/fde-field-visits/enums`
- 字段要点：
  - `service_type` ∈ `installation / commissioning / training / maintenance / safety_walkthrough / consulting`
  - `mode` ∈ `on_site / remote_support`（对齐政策"现场驻守 + 远程专家支持"）
  - `capability_tags`（JSON）：政策 FDE 四维能力——`business`（懂业务）/ `model`（通模型）/ `security`（知安全）/ `delivery`（能交付），**只声明实际具备的维度，不硬凑四维**（与 `elderly_design` 同纪律）
  - `duration_hours` / `findings` / `resolved` / `space_asset_id` / `project_id`
  - 补充字段（支撑 G3「谁在现场」与按时间检索）：`title` / `engineer_name` / `service_date`
- 归属与越权：`owner_id` 隔离；带 `project_id` 时走 `verify_project_access`

---

## 五、诚实遗留（P2 路线图，本版本不落地）

| # | 项 | 现状 |
|---|----|------|
| L1 | 资源池正式申报 | P0 档案提供材料底座；实际申报由团队在 2026-12-01 前向省工信厅提交 |
| L2 | 成熟度等级自评 | 需第三方评估机构，平台只引用标准编号不自评等级 |
| L3 | Token 计费结算闭环 | 依赖统一 Token 计量口径与结算规范落地（政策要求"加快形成"），当前仅计量 |
| L4 | "人工智能应用服务团"多主体封装 | 现有 `OrchestratorAgent` + A2A 可承载，但需平台侧多主体实体（L3 同类：无 Team/联合体实体） |
| L5 | 算力券 / 首购首用申报 | 属地区政策对接事务，无代码需求 |
| L6 | 出海服务体系 | 省级文件有南亚东南亚出海导向，本版本不涉及 |

---

## 六、风险提示

1. **入池材料必须真实**——工信部"依据相关标准形成全国资源池"，虚构能力会在实地指导/跟踪评估环节暴露；本项目诚实降级红线在此处是资产。
2. **Token 口径尚无国标**——政策要求"加快形成统一 Token 计量口径与结算规范"，当前无统一口径，故本项目只做内部计量披露，不做对外计价承诺。
3. **先导区省份 100 家硬指标**与云南是否在先导区名单无关——云南省级行动计划已独立把"引育人工智能服务商"列为任务，承接路径不依赖先导区身份。
# 索克家居 · 前沿研究 2026 第二轮（i-home.life v1.8.1）

> 日期：2026-08-05
> 目的：承接《2026-08-04 前沿研究》（第一轮），基于 2026-08 最新行业动态 + 项目 v1.8.1 实际落地状态，输出新一轮可落地前沿方向与参赛材料衔接建议。
> 依据：本仓库代码实测（app/ 目录统计）+ 2026-08 公开行业动态（MCP 官方博客、AAIF、GB/Z 185 首批身份码发放、浙江"智安工兵"、DeepSeek V4-Flash、Qwen3.8、东易日盛 AI 3.0、贝壳 AI 全家桶、Matter 1.6、等保数据安全新规等）+ 上一轮《2026-08-04 前沿研究》衔接。
> 对齐红线：不引入 K8s/Helm（阿里云 FC）；鉴权 PASETO（禁 JWT）；诚实降级不可移除；新 API 补测试。

---

## 一、结论先行（TL;DR）

1. **协议层领先叙事继续成立并加码**：MCP 2026-07-28 史上最大重构（去 Session/stateless、MRTR、W3C Trace、OAuth2.1、Server Cards）正是索克已全部落地的 8 项；本轮新增 **MCPA 官方认证（2026-07-10，首个 MCP 官方认证）** 与 **GB/Z 185 首批智能体身份码发放（2026-07-21，200+ 企业申领）** 两个"标准对齐"确定性证据点。
2. **质检真实 CV/VLM 的落地路径本轮已成熟**：第一轮列为 P0 的"质检真实 CV"仍未启用（`real_cv_quality_enabled=False`），但行业已给出可抄作业的落地架构——浙江"智安工兵"91% 准确率全省 2390 工地 + "边缘小模型定位 → 云端 VLM 判定 → 人工复核闭环"（Qwen3-VL-8B QLoRA 24GB 即可微调）。这是复赛最值得补的硬能力，且已具备零样本/低成本路径。
3. **新增两个低成本高合规价值的确定性窗口**：
   - **AI 生成内容标识**：《人工智能生成合成内容标识办法》2025-09-01 已施行 + 2026-04"清朗·整治 AI 应用乱象"专项行动 + 欧盟 AI Act 透明度条款 2026-08-02 生效——索克 AI 渲染/报告/效果图输出管道需补显式+隐式标识。
   - **等保数据安全 + AI 安全扩展要求**：GA/T 2380-2026（2026-06-01 实施，数据安全独立专项域）、《智能体规范应用与创新发展实施意见》（2026-05-08 三部门）——AI 资产清单（AI-BOM）、模型调用日志留存 ≥6 个月。
4. **LLM 链性价比窗口**：DeepSeek V4-Flash-0731（2026-07-31）以 $0.28/M 输出价把 Agent 场景性价比拉到"斩杀线"，索克 `deepseek → qwen → glm → doubao` fallback 链应评估升级，回归 pytest 1872 基线即可。
5. **2026 下半年最大风险面是 MCP/Agent 安全**：Invariant 工具投毒、PraisonAI CVE-2026-44336（RCE）、CowAgent 攻击链（prompt injection → MCP config → RCE）、Pynt 审计"10 个串联 MCP 服务器利用概率 92%"——索克 MCP 需落实"意图-执行分离 + 工具输出清洗 + 权限最小化"。

---

## 二、项目技术前沿盘点（i-home.life v1.8.1 实测，2026-08-05）

> 全部来自本仓库代码实测，非声明。

### 2.1 规模实测

| 指标 | 实测值 | 证据 |
|---|---|---|
| 版本 | **v1.8.1** | [app/config.py](file:///Users/netsong/Developer/i-home.life/app/config.py) `app_version` |
| API 路由模块 | **75 个** | `app/api/` 全量 include_router |
| ORM 模型 | **121 个** | [app/models/__init__.py](file:///Users/netsong/Developer/i-home.life/app/models/__init__.py) |
| Agent | **26 领域**（22 执行型 + 4 商业运营）+ Orchestrator + Harness | `app/agents/`（growth/marketing/competitor_research/finance_recon 为本轮新增） |
| Service 模块 | **97 个** | `app/services/` |
| MCP | 自研纯 Python + **Enterprise 扩展**（audit/SSO/gateway）+ Tasks 扩展 + MRTR | [app/mcp/](file:///Users/netsong/Developer/i-home.life/app/mcp/) |
| LLM fallback 链 | 4 家 deepseek→qwen→glm→doubao | `app/agents/base.py` |
| pytest 基线 | 1872 passed（collect 1877 = +2 skipped +3 xfailed） | 全量跑通 |

### 2.2 自上一轮（08-04）以来新落地的前沿点

| 新落地能力 | 说明 | 对齐的行业前沿 |
|---|---|---|
| **MCP Enterprise 扩展**（[enterprise.py](file:///Users/netsong/Developer/i-home.life/app/mcp/extensions/enterprise.py)） | `enterprise/status` 能力声明（审计 HMAC/SSO WebAuthn/网关 stateless）+ `enterprise/audit` 只读审计轨迹查询 | MCP 2026 Roadmap Enterprise Readiness（审计/SSO/网关） |
| **商业运营 Agent ×4** | growth（基于 `agent_feedbacks` 诚实标注）/marketing/competitor_research/finance_recon（基于内部支付/托管表），各自 flag 灰度默认 False | 东易日盛"十大 AI 智能体 + 中央厨房"、义乌"AI 嵌入生意每一环" |
| **主动 Orchestrator 每日简报** | `OrchestratorAgent.generate_daily_briefing` 聚合 growth + finance，阿里云 FC 定时触发 `/api/admin/daily-briefing` | 无 K8s/Cron 约束下的 Serverless 定时编排 |
| **以销定产** | `procurement_demand_driven_enabled` 开启后 `drive_procurement_from_bom` 从设计 BOM 反向驱动采购优先级（紧急/常规/可缓） | 义乌"以销定产"模式 |
| **PASETO 撤销列表 Redis 化** | `paseto_revocation_redis_enabled` flag（默认 False 内存 dict，True 用 Redis 共享撤销列表，不可用 best-effort 降级） | 多 worker 无状态扩展必需；PASETO v4 生态活跃（paseto-kit 2026 新库） |

### 2.3 已知"名实差距"（诚实边界，复赛/评审易攻击点）

| 能力 | 现状 | 前端 flag | 本轮行业对照（已成熟） |
|---|---|---|---|
| 质检缺陷识别 | **mock CV**（真实 CV 未启用） | `real_cv_quality_enabled=False` | 浙江"智安工兵"91%、ConstructView 91.4%、moondream 92.3%、陌讯钢筋 92.4% |
| 生态桥接（米家/鸿蒙） | 状态报告 + 501 诚实，未真实联动 | F46 | Matter 1.6（NFC 配网）落地；GB/T 46456 已实施、强制国标 2028 |
| VR 渲染 / AI 渲染 | mock 降级 / L1-L2 降级 | `ai_render_contract_strict=True` | 3DGS（PlanarGS/LighthouseGS）+ GHPT 可重光照已可达；商汤 U1.5 原生 4K |
| IFC 导出 | 依赖 ifcopenshell | — | 如实披露 |

---

## 三、2026-08 行业前沿（本轮新调研，相对 08-04 增量）

### 3.1 Agent 基础设施（协议层持续加码 + 安全事件爆发）

**MCP 生态数据与认证**：
- 2026-07-28 第五版规范正式发布（第一轮已述），本轮确认生态数据：Tier 1 SDK 月下载近 5 亿次、TS/Python SDK 各自累计破 10 亿；官方博客口径公共服务器 22,000 个；另一口径 2026-04 公开 MCP 服务器超 14,000 个。
- **MCPA 认证**（2026-07-10，AAIF）：首个官方 MCP 认证（120 分钟线上监考、两年有效、五大考试域含安全与治理）——标准从"协议"走向"人才认证"，索克若参赛可主张"自研零 SDK 且 8 项规范全实现，优于认证级基线"。
- AWS Bedrock AgentCore Gateway 当天支持新规范（UpdateGateway 向后兼容）；Solo.io agentgateway（Rust）2026-06-04 加入 AAIF 成第 4 个托管项目。

**A2A / AP2**：
- **A2A v1.2** 为当前稳定版：新增 gRPC 支持 + Signed Agent Cards 域名验证（JWS 签名绑定发布者域名，`/.well-known/agent.json` 发布）——被业界视为"解除企业采购信任障碍"的关键变更。
- **AP2 v0.2**（2026-04-28）新增 Human Not Present + Verifiable Intent，**已捐赠 FIDO Alliance** 治理；60+ 支付伙伴。索克结算/采购 Agent 可借鉴 Intent/Cart/Payment Mandate 授权链思路（用户授权 + 金额上限 + 可验证）。

**国标与治理双轨**：
- **GB/Z 185-2026《人工智能 智能体互联》七项子标准**（2026-05-22 发布、06-26 发布会）：185.2 身份码为 28 位 AID 编码（厂商信用代码/智能体类型/安全分级/序列号/校验位）、185.4 ACDL JSON 能力描述、185.6 默认 gRPC+Protobuf、185.7 工具调用五重安全机制（注册/校验/拦截/日志/熔断）。**2026-07-21 中关村应用推进会议发放首批智能体身份码，超 200 家企业申领**；规划 2028 年前升级强制国标。
- **WAICO**（2026-07-16 上海成立，29 创始国）+ 网信办《智能体互信互联互操作全球合作倡议》（10 大方向）；与美方 Pax Silica（35 国）并行。
- **IETF**：AIPF 框架草案（2026-06-23，Nokia+中国移动+阿里云，识别六大缺口 + Intent-Execution Separation 安全要求）；draft-rosenberg-agentproto-usecases（2026-07-04）；OAuth 2.1 draft-15（2026-03-02，PKCE 全强制/隐式流移除/RTR）。

**可观测性标准化**：
- **OTel GenAI 语义约定 2026-06 正式稳定**（首个厂商中立 LLM/Agent 遥测标准，System/Model/Agent 三层 span + `gen_ai.*` 属性 + W3C Trace 跨 Agent 传播 + MCP 埋点 schema）；ATSC（OTEP 4959，21 种 agent span kinds 含 `agent.handoff`）仍 proposed。阿里云 LoongSuite 基于 OTel 出 Agent 可观测规范。

**MCP/Agent 安全（2026 下半年头号风险）**：
- Invariant Labs 工具投毒：恶意 `description` 内嵌指令、`list_changed` rug pull、跨服务器 shadowing（7 个主流客户端中 Cursor 全中）。
- **PraisonAI CVE-2026-44336**（Critical）：`tools/call` 路径穿越 → Python `.pth` 注入 RCE，无点击即触发。
- **CowAgent 攻击链**（2026-07-17，Critical）：prompt injection → 诱导写恶意 MCP 配置 → 热加载 → STDIO 任意命令 → 环境变量继承窃取全部 API key。
- Pynt 281 个真实 MCP 实现审计：单服务器约 9% 可利用概率，串联 10 个 → 92%。
- 行业共识对策：**Intent-Execution Separation（意图-执行分离）**——把授权约束放确定性代码而非提示词 + 命令白名单 + 工具输出清洗 + 不可篡改审计轨迹。

### 3.2 设计渲染 / 空间智能（承办方与头部玩家动态）

**群核科技（00068.HK）**：
- 股价回调：2026-08-04 收盘 8.675 港元、市值约 149.75 亿港元（峰值曾破 800 亿）；7-31 中金测算有望纳入港股通（8/21 恒指半年度审议）。
- **三篇论文入选 ECCV 2026**（SPEAR 高保真具身仿真、WalkerBench 首个街景交互式空间智能评测基准——最强模型完成率仅 24.5%、Syn-GRPO）；**SIGGRAPH 2026** DiT 可控纹理平铺（保真偏好 +42%、空间可控首选率 91%）；与阿里云联合发布 AnalyticDB 具身多模数据平台 V2.0。
- 产品线：LuxReal/酷家乐 AI 视频创作 Agent（基于 3D，时空一致性，计划年内发布）；Aholo 开放平台。

**竞品/大厂（对索克差异化最关键）**：
- **东易日盛"晶鲤焕新家"（2026-05-20）+ 家装 AI 3.0**：十大 AI 智能体（营销/咨询/设计/报价/DIM+/施工/供应商/门店/结算/平台）+ "AI 中台中央厨房 + 城市服务商 + 社区店"铁三角，目标砍掉传统装企约 40% 费用率中的人力损耗——**与索克 22 执行型 Agent 分工高度同构，是最直接的竞品对照**。
- **贝壳"AI 全家桶"（2026-05 智博会）**：自研 MR 看房 3DGS 渲染管线 + **行业首款 AI 可穿戴智能验收设备 + 数显化验收工具** + 智慧工地可视化（AI 识别 + 360° 全景）；资金存管"节点验收、双向确认、银行拨付"（60/35/5 分批放款，竣工 7 日解冻率 99%、存管用户占比 93%）。
- **金螳螂**：Q2 新签订单 59.34 亿（+25.9%）；"四维履约雷达系统"（资金/物料/人力/信息流）Q2 工期履约率 99.2%。
- **飞流AI（金牌家居）**："深化设计 Pro"一键生成施工图包，200+ 工长内测 **94% 认为可直接施工交底**——直接对标索克"AI 生成图可施工"叙事。
- **京东自营装修 App**（2026 上线，JoyAI + 直管 5200 产业工人，目标三年 GMV 300 亿）；天猫设计家（2026-05，开放 AI 设计/工艺标准/供应链能力包，不参与施工）；支付宝家装宝（节点验收、分段放款）。

**渲染/空间技术前沿**：
- 3DGS 成为室内重建事实标准：PlanarGS（NeurIPS'25，室内 PSNR>38dB）、LighthouseGS（WACV'26，手机全景式拍摄）、GaussianRoom（无纹理室内）；**GHPT（CVPR'26）3DGS 可重光照实时**（RTX 4080 级）；InteriorGS（群核开源全球首个大规模室内 3DGS 数据集）。
- 可控生成：RelaCtrl（DiT 相关性引导，仅 15% 参数达同级可控性能）；**商汤 SenseNova U1.5-Lite（2026-08-03 开源）8B 原生 4K 直出 + 指哪儿改哪儿**——国内开源模型已把分辨率与可控编辑拉高。
- 空间语言/世界模型：SpatialLM 1.5（对话式端到端空间语言）、**Kairos-HomeWorld（ACE Robotics，2026-07-22）全球首个全屋交互 3D 世界模型 + 开源 30 万中国真实户型 + 5000 可交互模拟环境**、NVIDIA Cosmos 3、World Labs Marble、Google Genie 3。

**AI 质检/工地监理（第一轮 P0 的行业证据已规模化）**：
- 浙江"智安工兵"：YOLO 快筛 + 真知大模型精析，覆盖 4 阶段 27 种隐患，**识别准确率 91%**，全省 11 设区市 2390 工地连通，单项目隐患日均 35→3 个、发现-处置 28h→2.5h，闭环"智能预警—分发告警—处置消警（安全员复核 + AI 认证双重验证）"，探索与安责险衔接。
- ConstructView（2026-05）：Gemini 2.5 Flash 多模态里程碑核验，AI 与专家一致率 **91.4%**；moondream 建筑缺陷检测（裂缝/空鼓）**92.3%**；陌讯多模态钢筋计数 mAP 92.4% 边缘部署（Jetson NX，单帧 32ms）。

**全屋智能/互联互通**：
- **Matter 1.6**（2026-06）：NFC 一碰配网（未通电可配对）、多管理员跨生态共享、状态可视化。
- 中国 **GB/T 46456《智能家居互联互通》已 2026-02-01 实施**；工信部 2026 年第五批强制国标计划把互联互通第 1-4 部分列为**强制性标准（18 个月周期）**，预计 2026 发布、2027 准备、**2028 强制执行**；2026-07-21 上海专项组会议进入实质编制。
- OneConnect 智家标准（2026-03 AWE）：整合鸿蒙 OS + 星闪，原生支持 AI Agent，12 大类设备。

### 3.3 大模型与企业级 AI（fallback 链性价比与工程化）

- **DeepSeek V4-Flash-0731**（2026-07-31）：纯后训练升级，Terminal Bench 2.1 61.8→82.7、DeepSWE 7.3→54.4，Agent/编码追平 Opus 4.8 级，价格 **$0.14/$0.28 每百万 token**（缓存命中低至 $0.0028）——Agent 场景性价比"斩杀线"。
- **Qwen3.8-Max**（2026-08-03）：2.4 万亿总参/95B 激活，百万级上下文 + 原生多模态，自动化编程测试无人工干预连续运行 16 天；同批发布"千问办公"（三合一 + 内置 AI 操作审计日志，**每句生成内容可溯源**——审计成为企业级标配的信号）。
- **GLM-5.2**（6 月全量开放）：744B/40B 激活、Agentic Coding 专项，适配 7 大国产芯片平台。
- 框架格局：AutoGen 转维护模式、统一为 Microsoft Agent Framework；LangGraph 1.0（月下载 3800 万）；CrewAI 首个支持 A2A；OpenAI Agents SDK v0.19.2。
- 评估范式：**BenchJack 事件（2026-04）**证明 Agent 基准可被攻击式刷分（SWE-bench Verified 退役），"过程验证而非分数崇拜"；**Agent-as-a-Judge**（阿里 AgentLoop）与人类专家一致性 65%→90%、成本 1/30；`pass^k` 一致性指标。
- RAG 演进：固定 GraphRAG 弱于 Agentic RAG 于事实细节问题（+0.576 relevancy）；Agent 记忆（episodic/semantic）+ **SSGM 框架**处理记忆漂移/投毒/稳定性坍塌（冲突检测门控 + 高价值变更人工复核）。

### 3.4 合规与安全（本轮新增的确定性政策窗口）

- **AI 生成内容标识**：《人工智能生成合成内容标识办法》2025-09-01 施行（显式 + 隐式双标识），2026-04 起"清朗"专项行动 4 个月；欧盟 AI Act 透明度条款 **2026-08-02** 生效（违规最高罚 1500 万欧元）。
- **《人工智能拟人化互动服务管理暂行办法》2026-07-15 施行**（涉及 AI 数字人/拟人化顾问须合规自查）。
- **等保三轨时代**：GA/T 2380-2026《等保数据安全基本要求》2026-06-01 实施（数据安全独立专项域、三级以上强制国密、全量审计、"321 备份"、10 万人以上泄露须立即上报最高罚 1000 万）；**AI 系统纳入等保对象**（AI-BOM 资产识别、模型调用日志 ≥6 个月、输出敏感数据过滤）；新《网络安全法》2026-01-01 施行首次写入 AI 条款；关基保护明确 AI 智能体入关键资产清单（高危操作双人复核/自动拦截）。
- **PASETO 生态**：paseto-kit（2026 新库，JS/TS 全运行时）支持 v4/v3 + 完整 PASERK（wrapping/seal/key IDs）——索克 PASETO v4.local 红线符合 2026 主流方向。

---

## 四、项目可引入的前沿技术方向（第二轮落地建议）

> 按确定性窗口 × 业务价值 × 与现有架构契合度排序。均为"可落地、不依赖外部 key 或已具备支撑"的高价值项；跨轮未落地项保留并给出本轮更具体的路径。

| 优先级 | 方向 | 落地动作 | 依据（本轮证据） |
|---|---|---|---|
| **P0** | **质检真实 CV/VLM 接入**（上轮 P0 未落地，本轮路径成熟） | 复用 `qa_inspector` + 多模态 LLM 链；按"边缘小模型定位 ROI + VLM 云端判定 + 结构化 JSON + 人工复核闭环"实现，沿用诚实降级链（VLM 不可用 → 明确占位） | 浙江"智安工兵"91% / ConstructView 91.4% / moondream 92.3%；Qwen3-VL-8B QLoRA 24GB 即可；与 F48 AI 工地监理天然合流 |
| **P0** | **AI 生成内容标识合规**（本轮新增确定性窗口） | AI 渲染/效果图/质检报告/预算说明输出管道补显式提示 + 文件元数据隐式标识（水印字段预埋） | 《标识办法》2025-09-01 施行 + "清朗"专项 + 欧盟 AI Act 2026-08-02 生效 |
| **高** | **MCP 安全硬化**（工具投毒防御） | 工具 description 变更签名/审查、命令白名单、内网/云元数据地址拦截、环境变量隔离、工具输出清洗；**意图-执行分离**：预算上限等授权约束放确定性代码（PASETO/flag 机制）而非提示词 | PraisonAI CVE-2026-44336 / CowAgent / Invariant 投毒 / Pynt 92% 链式概率 |
| **高** | **OTel GenAI SemConv 埋点对齐**（上轮 P0 W3C Trace 延伸） | AgentTrace `_meta` 写 `traceparent/tracestate/baggage`，span 按 `gen_ai.system/model/agent/tool` + `usage.input_tokens` 标注，宣称对齐 SEP-414 + GenAI SemConv | OTel GenAI SemConv 2026-06 正式稳定；ATSC 提案含 `agent.handoff`；阿里千问办公"每句可溯源"成标配 |
| **高** | **LLM 链模型升级**（成本红利） | 评估 DeepSeek V4-Flash-0731 作为 fallback 链主力（性价比斩杀线 $0.28/M），Qwen 系列用于长上下文/多模态设计理解；升级后回归 pytest 1872 基线 | V4-Flash-0731 Terminal Bench 82.7 / 价格 $0.14/$0.28；Qwen3.8-Max 百万上下文 + 原生多模态 |
| **高** | **GB/Z 185 身份码/ACDL 对齐预研** | 预研 28 位 AID + ACDL JSON 能力描述映射（只做设计文档 + 元数据预埋，不硬接）；作为政企/供应链互认接入点叙事 | 2026-07-21 首批身份码发放、200+ 企业申领；185.7 工具五重安全机制与索克 MCP 审计天然对齐 |
| **中** | **结算/采购 Agent 借鉴 AP2 授权链** | escrow 资金托管 + 分段放款（对齐贝壳 60/35/5 节点验收）基础上，补"用户授权 + 金额上限 + 可验证"的 Mandate 思路设计 | AP2 v0.2 捐赠 FIDO Alliance；贝壳/支付宝节点验收放款成行业标准闭环 |
| **中** | **Agent-as-a-Judge 评估升级** | IHomeEval 10 维 + DSPy 离线评估升级为"轨迹级 + 结果级"双层（工具选择/错误恢复/计划连贯六维度），防质量退化 | BenchJack 基准信任危机；AgentLoop 一致性 65%→90%、成本 1/30 |
| **中** | **Matter/GB-T 46456 兼容矩阵** | 智能家居方案/交付 Agent 预置 Matter + OneConnect + GB/T 46456 协议合规校验规则（可编程校验 = 差异化） | Matter 1.6 NFC 配网；强制国标 2028 执行；IDC 2026 出货 3 亿台 |
| **中** | **商业运营 Agent 记忆防漂移** | growth/finance_recon 的 agent_memory 加"冲突检测门控 + 高价值变更人工复核"（SSGM 框架思路） | Agent 记忆 2026 最热主题；记忆漂移/投毒/稳定性坍塌三类风险 |

> 上轮"承办方渲染正面回避"结论维持：不堆渲染能力，主打"AI 生成图可施工 + 全流程多 Agent 协同 + 诚实降级 + 开放协议"；飞流 AI"94% 可直接施工"与索克叙事同向，需在方案中正面回应差异（索克是端到端交付闭环而非单点施工图工具）。

---

## 五、参赛材料衔接建议（初赛方案 V3.2 → 第二轮前沿增量）

1. **补两个确定性标准证据**：GB/Z 185 首批智能体身份码发放（2026-07-21，200+ 企业）+ MCPA 官方认证启动（2026-07-10）——强化"索克协议层 8 项全实现 = 超越认证级基线"叙事。
2. **补 AI 生成内容标识合规点**：方案合规章节加一条"AI 生成内容显式+隐式标识对齐《标识办法》"，并如实说明当前渲染 L1/L2 降级路径下标识策略。
3. **补质检真实 CV 的"规划中 + 路径"表述**：第一轮已提示如实标注为规划中能力；本轮可进一步写"已选型 VLM 方案（边缘定位 + 云端判定），复赛前按 4 级诚实降级链启用"——从"没有"变成"有明确落地路径"。
4. **补安全叙事**：MCP 安全硬化（意图-执行分离、工具投毒防御、审计轨迹）作为"AI 智能装修平台安全纵深"新章节素材（PASETO + WebAuthn + HMAC 审计 + 本轮 MCP 硬化）。
5. **竞品矩阵更新**：补东易日盛"十大 AI 智能体"（与索克 22 Agent 同构对照）、贝壳 AI 可穿戴验收 + 节点放款、金螳螂四维履约雷达、飞流 AI"94% 可直接施工"、京东自营装修（300 亿 GMV）、天猫设计家。
6. **诚实边界保持**：质检 mock CV、生态桥接 stub、AI 渲染 L1/L2 降级、VR mock 均如实披露；商业运营 Agent 数据源诚实标注（`agent_feedbacks`/内部表）已是差异化亮点，可展开。

---

## 六、参考来源

**Agent 基础设施**
- MCP 官方博客《The 2026-07-28 Specification》https://blog.modelcontextprotocol.io/posts/2026-07-28/；AWS Blog（AgentCore Gateway 支持）
- AAIF《Introducing the MCPA Certification》https://aaif.io/blog/introducing-the-mcpa-the-first-official-certification-for-the-model-context-protocol/
- A2A Complete Guide for 2026（Rapid Claw）；AP2 官方站 https://a2aprotocol.ai/ap2-protocol；Agent Patterns Catalog（Signed Agent Card）
- GB/Z 185-2026 七项标准（中国标准在线服务网 / 百度百科 / 2026-07-21 首批身份码发放报道）
- IETF：draft-zahed-agent-comm-framework-00（AIPF）、draft-rosenberg-agentproto-usecases-00、draft-ietf-oauth-v2-1-15
- OTel GenAI SemConv 稳定化（BusinessTechNavigator 2026-06）；OTEP 4959 ATSC；阿里云 LoongSuite
- MCP 安全：Invariant Labs 工具投毒（Kayssel）、PraisonAI CVE-2026-44336（GitHub Advisory）、CowAgent Issue #2968、Pynt 281 实现审计（ssojet）、Confused Deputy（Cyber0946）

**设计渲染 / 空间智能 / 家装**
- 网易《酷家乐 AI+大家居产品升级发布会》（2026-07-13）；新浪财经 00068.HK 行情（2026-08-04）；搜狐/央广网 ECCV 2026 三篇论文（2026-07-01）；DoNews 群核×阿里云 AnalyticDB（2026-07-20）；中国日报网 SIGGRAPH 2026（2026-07-27）
- 新浪家居《东易日盛晶鲤焕新家》（2026-05-21）；搜狐《金螳螂 2026 Q2 订单》（2026-07-30）；36氪《贝壳 AI 全家桶》（2026-05-29）；DoNews《京东阿里蚂蚁加码家装》（2026-06-21）
- PlanarGS（NeurIPS'25）、LighthouseGS（WACV'26）、GaussianRoom、GHPT（CVPR'26）、RelaCtrl；凤凰科技《商汤 U1.5 开源》（2026-08-03）
- SpatialLM 1.5 / SpatialGen；ACE Robotics Kairos-HomeWorld（2026-07-22 GlobeNewswire）；NVIDIA Cosmos 3
- 浙江省住建厅《智安工兵》（2026-06-11）；JETIR ConstructView（2026-05）；CSDN moondream / 陌讯钢筋计数（2026-07-31）
- Matter 1.6（CSDN 2026-06）；工信部 2026 第五批强制国标计划（2026-03）；IT之家《互联互通标准实质编制》（2026-07-30）；OneConnect（移动通信网 2026-03-20）

**大模型 / 企业级 AI / 合规**
- DeepSeek V4-Flash-0731（datanorth 2026-08-04 / 今日头条分析）；Doubao-Seed 2.1（2026-06-23）；Qwen3.8-Max + 千问办公（2026-08-03）；GLM-5.2
- GAIA Leaderboard（2026-05）；BenchJack（Berkeley RDI）；阿里云 AgentLoop（Agent-as-a-Judge）；OpenAI Agents SDK v0.19.2
- 《人工智能生成合成内容标识办法》（中国政府网）；人民邮电报 AI 内容治理（2026-07-03）；欧盟 AI Act 透明度条款生效（2026-08-02）
- GA/T 2380-2026《等保数据安全基本要求》（2026-06-01）；CSDN《AI 系统也要过等保了》（2026-07-17）；新《网络安全法》
- paseto-kit（npmjs，2026）；OAuth 2.1（WorkOS 迁移指南）
- i-home.life 代码实测（app/ 目录统计，v1.8.1）；上一轮《2026-08-04 前沿研究》与《2026-08-03 行业与竞品调研报告》

# 索克家居 · 前沿研究 2026（i-home.life v1.8.0）

> 日期：2026-08-04
> 目的：系统盘点 i-home.life 现有技术栈中的前沿点，调研 2026 年设计渲染 + AI 家居赛道与 Agent 基础设施的最新行业前沿，输出可落地的前沿技术引入建议与参赛材料衔接建议。
> 依据：本仓库代码实测（app/ 目录统计）+ 2026 公开行业活动与协议换代（广州建博会 2026-07、MCP 2026-07-28 重构、A2A 一周年、GB/Z 185-2026 等）+ 上一轮《2026-08-03 行业与竞品调研报告》衔接。

---

## 一、结论先行（TL;DR）

1. **索克协议层已经领先行业**：2026-07-28 MCP 史上最大重构（去 Session/stateless 化、MRTR、W3C Trace）正是索克**已全部落地**的 8 项规范——行业刚从"有状态 Session"转向索克早已实现的架构，这是最有说服力的差异化叙事。
2. **承办方（群核/酷家乐）2026-07-09 已发布"AI+设计/AI+渲染/AI+旧改局改"三大升级 + 空间智能飞轮**（SpatialLM/SpatialGEN + AHOLO 实景重建 + 3D 高斯渲染 + 图生空间）。索克应回避"堆渲染能力"正面竞争，强化"全流程多 Agent 协同 + 诚实降级 + 开放协议"的差异化。
3. **最大可落地的"名实差距"仍是质检 mock CV**（`real_cv_quality_enabled=False`）：行业已规模化落地（浙江"智安工兵"91% 准确率、中建八局搭贝），且 MCP 2026-07-28 重构后 W3C Trace 语义与索克 AgentTrace 天然对齐，是复赛最值得补的硬能力。
4. **新增确定性政策窗口**：GB/Z 185-2026《智能体互联互通》国标 + 工信部《智能家居互联互通》强制国标（2028 执行）+ WAICO 初签——索克应把"标准对齐"作为持续叙事主线。

---

## 二、项目技术前沿盘点（i-home.life v1.8.0 实测）

> 以下全部来自本仓库代码实测（`app/` 目录统计），非声明。

### 2.1 规模实测

| 指标 | 实测值 | 证据 |
|---|---|---|
| 版本 | **v1.8.0** | `app/config.py` `app_version` |
| API 路由 | **630+ 条 / 70 模块** | `app/api/` 全量 include_router |
| ORM 模型 | **118 个** | `app/models/__init__.py` |
| Agent 模块 | **24 个**（BaseAgent/Harness + Orchestrator + 22 领域） | `app/agents/` |
| Service 模块 | **82 个** | `app/services/` |
| MCP 工具 | **11 个**（flag 关闭时 8 个） | `app/services/agent_tool_registry.py` |
| 意图契约 | **39 个**（CI 强制校验） | `config/intent_contract.json` |
| 硬约束 | **9 HC + 3 SC** | `config/ihome_model_spec.json` |
| LLM fallback 链 | **4 家** deepseek→qwen→glm→doubao | `app/agents/base.py` |
| 事件总线 | **11 类业务事件** | `app/services/event_bus.py` |

### 2.2 已具备的前沿点（相对 2026 行业）

| 前沿点 | 索克实现 | 2026 行业对照 |
|---|---|---|
| **MCP 2026-07-28 规范 8 项全实现** | 自研纯 Python、零 SDK：stateless / discover / header-routing / cacheable / MRTR / RFC9207+CIMD / Tasks / Server Card | 行业 2026-07-28 才从"有状态 Session"转向 stateless，索克**架构领先** |
| **A2A v1.0 双协议** | agent-card + tasks/send + 任务状态机；AP2 思路复用结算 | A2A v1.0 2026-03 发布、150+ 组织、一周年 |
| **对齐 AG-UI 卡片流协议**（代号 A2UI） | 自研 SSE 四事件 + 8 类卡片双端渲染（Flutter+React） | AG-UI 2026-03 Oracle+CopilotKit+Google 三方对齐 |
| **空间智能三能力** | 空间感知（AR 4 级降级 + RMS 精度）/ 空间推理（DesignerAgent 动线 + 承重红线）/ 空间交互（模型即图纸 + IFC4 导出） | 白皮书 2026-04 定义空间智能三能力，仅个别产品完整实现 |
| **多模态输入** | AR 量房、DXF 导入、草图转 3D、拍照识别、Qwen-Audio 真双工语音、传感器融合 | 行业主流"上传户型图"单点 |
| **诚实降级契约** | AI 渲染 L0-L3（`ai_render_contract_strict=True` → 503 诚实报错）+ 响应体 `source` 全量标注 | 竞品 AI 生成"不可施工图"是行业死穴 |
| **数据飞轮对标 AgentLoop** | AgentTrace + IHomeEval 10 维 + DSPy 离线评估 + AgentFeedback→L4 偏好学习 | 赛题基础设施 AgentLoop 数据飞轮 |
| **安全合规纵深** | PASETO v4.local（禁 JWT）+ WebAuthn/FIDO2 + HMAC 审计 + 缓存 user_id 隔离 + RBAC + IDOR 403 | 2026 智能体安全（零信任/审计）成为标准要求 |

### 2.3 已知"名实差距"（诚实边界，复赛/评审易攻击点）

| 能力 | 现状 | 前端 flag |
|---|---|---|
| 质检缺陷识别 | **mock CV**（真实 CV 未启用） | `real_cv_quality_enabled=False` |
| 生态桥接（米家/鸿蒙） | 状态报告 + 501 诚实，未真实联动 | F46 |
| VR 渲染 | mock 降级 | — |
| AI 渲染 | L1/L2 降级路径 | `ai_render_contract_strict=True` |

---

## 三、2026 行业前沿（最新调研，2026-08 视角）

### 3.1 设计渲染 / 空间智能赛道（承办方群核/酷家乐最新）

**群核科技（酷家乐）2026-07-09 广州建博会「AI+大家居产品升级」发布会**（继 2026-03 定制展全链路方案首发后迭代）：
- **AI+设计**：AI 智能设计平台升级——零基础 10 分钟上手、3 分钟出全案；布局模型 6 月底起厨房/卧室/卫生间陆续升级；**AI 轻户改**（现场快速调整户型、一键更新翻新方案）已上线；**AI 互动设计**（语音 + 可控标签自然语言输入）。
- **AI+渲染（AI 美化）**：一键质感增强、3 秒出图、实时美化、内置多套时间模板一键切换、自动全图风格迁移。
- **AI+旧改/局改**：以 **AHOLO 空间重建平台**为核心（3D 高斯渲染 + 点云实例分割、厘米级实景还原、混合渲染、旧房拆改模拟、房屋数字档案 / 隐蔽工程三维存档）；**图生空间**（上传单图/全景秒级生成精准空间模型 + AI 一键清空旧装修 + 链通 AI 智能设计）。
- **空间智能飞轮**：三层架构（空间编辑工具层 → 海量空间数据层 → 空间大模型层），沉淀 **5 亿+ 3D 场景、4.8 亿+ 3D 模型**，训练 **SpatialLM 空间语言模型 / SpatialGEN 空间生成模型**，具备空间理解、户型生成、智能布局、实景重建。
- **2026-04-17 港股上市（00068.HK）**，注册用户 2500 万、设计师 800 万、服务 2 万家品牌企业；**开源 AholoViewer 3D 高斯浏览器**；与影石创新战略合作空间重建。

**对索克的启示**：
- 承办方已把"渲染/布局/旧改"做到极致，且打通**方案内商品一键下单**商业闭环。索克**不应在渲染/布局维度正面拼**，应主打"AI 生成图可施工 + 全流程多 Agent 协同 + 诚实降级 + 开放协议"。
- 酷家乐"图生空间/旧改数字档案/隐蔽工程存档"与索克 F49 局改快装、F48 施工可视化方向可对标，但索克差异化在**端到端业务闭环**而非单点工具。

### 3.2 Agent 基础设施前沿（协议换代周）

**MCP 2026-07-28 史上最大重构（"Kubernetes 时刻" / 协议层地缘基础设施化）**：
- **去 Session（stateless）**：SEP-2575/2567 移除 `initialize`/`initialized` 握手与 `Mcp-Session-Id`，改 `server/discover` RPC；Serverless 可跑 MCP 服务端。**索克已实现（无握手、无 Mcp-Session-Id、round-robin）**。
- **MRTR 替代回调**：`InputRequiredResult` 终止当前请求，客户端重发独立请求。**索克已实现（asyncio.Future 多轮往返）**。
- **W3C Trace Context 标准化（SEP-414）**：`traceparent/tracestate/baggage` 嵌入 `_meta`，与 OpenTelemetry 统一；旧 Logging 废弃。**索克 AgentTrace + OTel 天然对齐，可宣称"开箱即用"**。
- **OAuth 2.1 硬化**：强制 `iss` 校验（RFC 9207）、凭据绑定颁发者。**索克已实现（RFC9207 + CIMD）**。
- **Server Cards**：`/.well-known` 标准化元数据。**索克已实现（GET /.well-known/mcp）**。
- 生态数字：**9,700 万月 SDK 下载、22,000 个公共服务器、78% 企业采用率、190 成员组织治理**。

**A2A 一周年（2026-04-09）**：150+ 组织、22,000+ GitHub Star、5 种 SDK、Linux Foundation 托管；v1.0 含 Signed Agent Cards + 多租户 + **AP2 支付协议**（60+ 组织，agent-driven transactions）。索克 A2A v1.0 在线 + AP2 思路复用结算。

**MCP+A2A 融合草案（2026-06-25，Linux Foundation AAIF）**：分层架构（A2A 横向协调 + MCP 纵向连接），"不是合并，是确认分工"。索克双协议同平台落地。

**MCP 2026 Roadmap（2026-03-05 发布）四大优先**：
1. Transport Evolution（stateless 会话、水平扩缩容、Server Cards）
2. Agent Communication（Tasks 原语补 retry/expiry 语义，异步可靠）
3. Governance（贡献者阶梯 + 委托模型）
4. **Enterprise Readiness：审计轨迹、SSO 集成、网关模式（gateway patterns）**——以轻量扩展形式输出

→ **对索克**：MCP Roadmap 的 Enterprise Readiness（审计/SSO/gateway）与索克 HMAC 审计 + RBAC + secret_manager 高度契合，可把"审计/SSO/网关"作为 MCP 扩展的落地亮点。

**新增标准与治理**：
- **GB/Z 185-2026《智能体互联互通》国家标准**（2026-07 发布）——国内 Agent 互联互通标准化走向落地。
- **WAICO 创始文件**（29 国上海签署）——国际 Agent 合作治理框架。
- **IETF 维也纳投票**：Agent 协议纳入正式标准化轨道。
- 三横一纵格局固化：MCP（Agent↔Tool 纵向手）+ A2A（Agent↔Agent 横向同事）+ Llama Stack（独立轨道）；四大商业面（Copilot Agent / Agentforce / SAP Joule / ServiceNow）未默认采纳任一开放协议——**"工具清单才是被锁定的资产"**，索克以开放协议 + 工具一层抽象对准。

### 3.3 与索克的战略对应

| 2026 前沿 | 索克现状 | 可宣称的差异化 |
|---|---|---|
| MCP stateless 重构（2026-07-28） | ✅ 已实现 8 项 | **架构领先**：行业刚转向，索克已落地 |
| W3C Trace（SEP-414） | ✅ OTel Span + AgentTrace | 观测与标准对齐，宣称"开箱踩线" |
| Enterprise Readiness（审计/SSO/gateway） | ✅ HMAC 审计 + RBAC + secret_manager | 可做 MCP 企业级扩展叙事 |
| A2A + AP2 支付 | ✅ A2A v1.0 + AP2 结算复用 | 跨 Agent 委托 + 支付闭环 |
| 承办方 AI 渲染/旧改 | ⚠️ 渲染弱于酷家乐 | 回避正面拼，主打"可施工 + 全流程 + 诚实" |
| 质检真实 CV | ⚠️ mock CV | 复赛最值得补的硬能力 |

---

## 四、项目可引入的前沿技术方向（落地建议）

> 按确定性窗口 × 业务价值 × 与现有架构契合度排序。均为"可落地、不依赖外部 key 或已具备支撑"的高价值项。

| 优先级 | 方向 | 落地动作 | 依据 |
|---|---|---|---|
| **P0** | **质检真实 CV 接入**（`real_cv_quality_enabled` 默认 False 已预埋） | 复用多模态视觉 LLM 链（DeepSeek→GLM→Qwen），已有 F38 基础；行业已验证（浙江"智安工兵"91% 准确率 / 中建八局搭贝） | 最大名实差距；复赛评审易攻击点；行业规模化落地标杆 |
| **P0** | **W3C Trace 语义对齐** | 把 `traceparent/tracestate/baggage` 写入 AgentTrace `_meta`，宣称与 MCP SEP-414 + OTel 对齐 | MCP 2026-07-28 标准化；索克观测栈已就绪 |
| **高** | **MCP Enterprise Adapter 扩展** | 以 MCP 扩展形式暴露审计/SSO/gateway 模式，对齐 MCP 2026 Roadmap Enterprise Readiness | 2026 Roadmap 明确方向；索克已有 HMAC/RBAC/secret_manager |
| **高** | **F50 材料溯源（一板一码）+ HENF** | 板材产地/批次/物流可查 + HENF 等级字段预埋（GB18580-2025 强制 + HENF 新标准） | 环保从板材到过程成标配；酷家乐/头部企业已做 |
| **高** | **F48 施工可视化 + AI 工地监理** | 工地直播/影像存档 + AI 巡检（闭水试验监测/违规抓拍）+ 时间戳影像日志 | 托管式整装透明化成信任基础设施；浙江全省推行 |
| **中** | **F49 局改快装产品化** | 48h 厨卫换新 / 7 天墙面焕新标准化套餐 + 干法施工 + 0 搬家 | 局改独立赛道 30%+ 增速；京东/索菲亚/金牌全线下场 |
| **中** | **F46 落地 1 个真实生态桥接（优先米家）** | 其余保持 stub 诚实标注；预适配 L1-L5 智能等级评价 | 互联互通强制国标 2026 发布/2028 执行；2026 全屋智能元年 |
| **中** | **F45 方案前置决策 LLM 真 AI 深化** | 已有 SolutionFirstAgent（source="llm"，失败降级 rule_based）；补多风格/多轮对话 | 飞流AI 自然语言+空间模型抢跑；已有基础 |
| **中** | **F7 BOM 版本管理与差异标注 + 接入几何算量** | BOM 升级对齐酷家乐"算量 2.0 报价清单" | 设计-落地脱节痛点；酷家乐已接算量 2.0 |

> 对齐既有红线：不引入 K8s/Helm（保持阿里云 FC）；鉴权保持 PASETO（禁 JWT）；诚实降级不可移除；所有新 API 补 `tests/test_*.py`。

---

## 五、参赛材料衔接建议（goai-agent-infra 初赛方案 V3.1 → 前沿增量）

1. **把"协议层领先"作为最强叙事**：MCP 2026-07-28 重构论证点（去 Session/stateless、MRTR、W3C Trace、OAuth2.1）正是索克已落地的 8 项——一句话讲清"行业刚转向的架构，索克已实现"。
2. **补 W3C Trace 对齐**：方案 §2.8 数据飞轮补一句"对齐 MCP SEP-414 W3C Trace + OpenTelemetry，AgentTrace 开箱踩线标准"。
3. **补 MCP Enterprise Readiness**：方案第六部分 2026 技术对齐表增一行"Enterprise Readiness（审计/SSO/gateway）→ 索克 HMAC+RBAC+secret_manager 天然对齐，可做 MCP 企业级扩展"。
4. **补新标准证据**：GB/Z 185-2026《智能体互联互通》国标 + WAICO 创始文件 + MCP 2026 Roadmap，强化"标准对齐"叙事主线。
5. **承办方竞品更新**：竞品矩阵补酷家乐 2026-07-09"AI+设计/AI+渲染/AI+旧改局改"三大升级 + 空间智能飞轮（SpatialLM/SpatialGEN + AHOLO + 3D 高斯）+ 港股上市（00068.HK）——同时明确索克回避渲染正面竞争、主打"可施工 + 全流程 + 诚实"。
6. **质检真实 CV 定位**：如实标注为"规划中能力"而非"已实现"（`real_cv_quality_enabled=False`），避免评审把名实差距当攻击点；若复赛前启用，则同步更新方案与 PPT。
7. **诚实边界保持**：质检 mock CV、VR mock、AI 渲染 L1/L2 降级、生态桥接 stub、IFC 依赖 ifcopenshell 均如实披露，不夸大。

---

## 六、参考来源

- 群核科技（酷家乐）「AI+大家居产品升级专场」发布会（2026-07-09 广州建博会）；AholoViewer 开源；与影石创新空间重建战略合作
- 群核科技港股上市（00068.HK，2026-04-17）；企查查企业信息（2026-08-04）
- MCP 2026-07-28 史上最大重构分析（去 Session SEP-2575/2567、MRTR、W3C Trace SEP-414、OAuth2.1 硬化、Server Cards）；MCP 2026 Roadmap（2026-03-05）
- A2A v1.0（2026-03）与一周年（2026-04-09，150+ 组织、22k+ stars、5 种 SDK、AP2 支付协议）
- MCP+A2A 融合草案（2026-06-25，Linux Foundation AAIF）
- GB/Z 185-2026《智能体互联互通》国标；WAICO 创始文件（29 国上海签署）；IETF 维也纳 Agent 协议标准化投票
- i-home.life 代码实测（app/ 目录统计，v1.8.0）；上一轮《2026-08-03 行业与竞品调研报告》

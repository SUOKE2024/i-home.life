# 索克家居 · 前沿研究 2026 第三轮（本体/领域开源资产 + 代码结构优化 + 论文修订）

> 日期：2026-08-15
> 目的：承接《2026-08-04/08-05 前沿研究》第一、二轮，聚焦「本体（Ontology）/领域开源知识（论文）、数据、标准、GitHub 开源库」的系统盘点，并据此输出**代码结构优化方案**与**论文修订建议**。
> 交付方式：**方案先行**（本文件为评审稿，代码落地待评审确认后再实施）。
> 真实性约定：标注「✅ 已联网核实」的资产为本次经 WebSearch 核实的真实开源项目/论文/数据集；标注「📦 仓库口径」的为沿用本项目既有前沿研究文档的 2026 口径；未标记者为公认成熟开源资产（2025 年前即存在）。
> 对齐红线：不引入 K8s/Helm（阿里云 FC）；鉴权 PASETO（禁 JWT）；诚实降级不可移除；新 API 补测试；代码改动可回溯到本方案。

---

## 一、结论先行（TL;DR）

1. **索克最缺的不是「多一个 Agent」，而是一层可检索、可对齐的「本体/领域知识基座」**。当前 `app/standards/` 只有定额库与验收清单，空间语义（`spatial_semantics_service`）是规则派生的、未对齐开放本体（Brick/BOT/IFC）。引入开放本体语义映射，能让索克的空间底座从「自定义 JSON」升级为「可对齐开源标准的空间知识图谱」。
2. **IFC/BIM 开源栈成熟且与索克现有 IFC 导出天然同源**：`ifcopenshell`（LGPL）+ `Bonsai`（原 BlenderBIM）+ `bSDD/IDS/BCF` 已形成完整 openBIM 生态。索克当前 IFC 导出依赖 ifcopenshell，可进一步对齐 `bSDD`（buildingSMART Data Dictionary）做「构件语义字典」，对齐 `IDS`（Information Delivery Specification）做「交付物校验规则」。
3. **空间/3D 数据集可低成本反哺索克设计与空间语义**：`3D-FRONT`（阿里，18,797 房间/7,302 家具，学术免费）、`SpatialLM-Dataset`（群核，12,328 场景/54,778 房间/59 语义类，**CC-BY-NC-4.0 非商用**）可作空间推理/布局评测金标；但**商用许可红线必须守住**（CC-BY-NC 不能进生产数据管线）。
4. **多智能体/自进化方向**：索克自建的「Harness + 自进化三层 + 编排」在架构上已对齐 2026 主流（AutoGen/LangGraph/CrewAI/MetaGPT），**无需引入外部框架**；应把精力放在「经验注入的结构化/预算控制、轨迹可回放、Agent-as-a-Judge `pass^k`、记忆冲突门控」这些与索克既有代码契合的**增量打磨**上。
5. **论文修订重点**：把「本体/领域知识基座 + 开源资产对齐」作为新的差异化维度写入论文（第 3 章架构 + 第 2 章相关工作 + 参考文献），并把此前 `128/105/2391` 等口径统一为实测值（`140 ORM / 111 Service / 2417 pytest`）。

---

## 二、本体/领域开源资产目录（论文 / 数据 / 标准 / GitHub 库）

> 每条资产标注：名称 · 类型 · 许可证 · GitHub/论文 · 与索克映射。

### 2.1 空间 / 3D / 家装数据集

| 资产 | 类型 | 许可证 | 规模 | 与索克映射 |
|---|---|---|---|---|
| **3D-FRONT** ✅ 已联网核实 | 室内场景数据集 | 学术免费（商用需确认） | 18,797 房间 / 7,302 家具（配套 3D-FUTURE） | 空间布局/风格评测金标；设计域「布局合理性」回归基准 |
| **SpatialLM-Dataset** ✅ 已联网核实 | 室内点云+结构化布局 | **CC-BY-NC-4.0（非商用）** | 12,328 场景 / 54,778 房间 / 59 语义类 | 对标 `spatial_semantics_service` 的语义标注评测；**仅限评测/研究，不进生产管线** |
| SUN RGB-D | RGB-D 室内场景 | 学术 | 10,335 RGB-D 帧 | 空间感知/物体识别参考 |
| ScanNet / Matterport3D | 真实扫描 3D | 学术（受限） | 1,513 场景 / 2,056 场景 | AR 量房/重建参考 |
| Structured3D / OpenRooms | 结构化户型/重光照 | 学术 | 大型 | 户型解析/渲染光照参考 |
| Habitat (AI Habitat) | 具身仿真平台 | MIT | — | 空间推理/导航仿真参考 |

**索克落地建议**：不直接入库商用受限数据；仅把 3D-FRONT 作为「设计布局合理性」离线评测金标（本地下载、评测脚本），SpatialLM-Dataset 仅作语义对齐的**研究对照**，并在文档/许可中如实标注 CC-BY-NC 边界。

### 2.2 空间理解 / 世界模型（论文 + 模型）

| 资产 | 类型 | 许可证 | GitHub / 论文 | 与索克映射 |
|---|---|---|---|---|
| **SpatialLM / SpatialLM1.1** ✅ 已联网核实 | 空间语言模型 | 开源（Apache-2.0） | github.com/manycore-research/SpatialLM；arXiv:2506.07491（NeurIPS 2025） | 视频/点云 → 结构化布局（墙门窗+物体框）；对齐索克「AR 量房 → 空间语义」链路 |
| SpatialGEN | 空间生成模型 | 开源 | 群核科技 | 户型生成/布局生成参考 |
| Kairos-HomeWorld 📦 仓库口径 | 全屋交互 3D 世界模型 | 开源 | ACE Robotics（2026-07） | 对标「户型→可执行空间」理念，索克以确定性规则兜底 |
| MASt3R-SLAM | 点云重建 | 开源 | — | SpatialLM 上游，索克 AR 测量可选增强 |

**索克落地建议**：SpatialLM 作为「AR 量房后结构化布局」的**可选外部增强器**（feature flag 门控 + 诚实降级），输出映射到现有 `floorplan.data` SSOT 与 `spatial_semantics_service` 的 schema；不默认启用（体积/算力/许可）。

### 2.3 BIM / IFC 开源库

| 资产 | 类型 | 许可证 | GitHub | 与索克映射 |
|---|---|---|---|---|
| **IfcOpenShell** ✅ 已联网核实 | IFC 库+几何引擎 | LGPL | github.com/IfcOpenShell/IfcOpenShell | 索克 IFC 导出已依赖；可增强为「IFC 校验 + bSDD + IDS」 |
| **Bonsai（原 BlenderBIM）** ✅ 已联网核实 | openBIM 建模工具 | 开源 | bonsaibim.org / github.com/IfcOpenShell/IfcOpenShell | 前端 BIM 建模参考（非后端集成） |
| IfcConvert / IfcClash / IfcDiff / Ifc4D / Ifc5D | IFC 工具链 | LGPL | IfcOpenShell 生态 | 索克 IFC 导出可补「IfcDiff 模型对比、Ifc5D 成本」 |
| xBIM | .NET IFC 库 | 开源 | github.com/xBimTeam | 参考（后端为 Python，不直接引入） |
| Speckle | AEC 数据流平台 | Apache-2.0 | github.com/specklesystems/speckle-sharp | 多端 BIM 数据同步参考 |
| BHoM | 建筑对象模型 | 开源 | github.com/BHoM | 建筑领域对象模型参考 |

**索克落地建议**：保持 Python 后端，围绕 IfcOpenShell 做「IFC 导出增强 + 校验 + bSDD 构件字典对齐」，不引入 .NET(xBIM)/Blender(Bonsai) 依赖。

### 2.4 建筑 / 家装本体（Ontology）

| 资产 | 类型 | 许可证 | GitHub / 标准 | 与索克映射 |
|---|---|---|---|---|
| **Brick Schema** ✅ 已联网核实 | 建筑元数据本体（RDF） | BSD-3-Clause | github.com/BrickSchema/Brick | 对齐 `smart_home`/传感器/设备语义；可作「设备-点位-关系」本体 |
| **BOT（Building Topology Ontology）** ✅ 已联网核实 | 建筑拓扑本体 | 开源（W3C LBD） | w3c-lbd-cg.github.io/bot | 对齐 `spatial_semantics_service` 的房间/楼层/zone 拓扑 |
| **SAREF** ✅ 已联网核实 | 智能家电本体 | 开源（ETSI） | SAREF ontology | 对齐家电/智能家居设备语义 |
| **RealEstateCore (REC)** ✅ 已联网核实 | 地产/建筑数字孪生本体 | 开源 | github.com/RealEstateCore/rec | 对齐「楼盘/楼栋/单元/户型」地产层级 |
| ifcOWL | IFC 的 OWL 本体 | 开源 | buildingSMART | IFC→RDF 语义桥，可作「构件语义」对齐 |
| Project Haystack | 建筑标签系统 | 开源 | project-haystack.org | 设备标签参考（Brick 更正式，优先 Brick） |

**索克落地建议**：新增 `app/ontology/` 模块，输出「家装领域本体」JSON（房间/空间/构件/材质/工序/设备/关系），**以 Brick/BOT/IFC 的术语与关系为对齐锚点**，同时保留索克自有术语（如「施工阶段」「质检项」）作为扩展。这是本轮最高价值、最低风险、零外部运行时依赖的代码优化。

### 2.5 多智能体 / 自进化框架

| 资产 | 类型 | 许可证 | GitHub | 与索克映射 |
|---|---|---|---|---|
| AutoGen / Microsoft Agent Framework | 多智能体框架 | MIT | microsoft/autogen | 编排范式参考（索克已有自研编排，不引入） |
| LangGraph | 图式 Agent 编排 | MIT | langchain-ai/langgraph | DAG 状态机参考（索克已有 `validate_dag`/拓扑执行） |
| CrewAI | 角色式多智能体 | MIT | crewAIInc/crewAI | Worker 分工参考 |
| MetaGPT | SOP 多智能体 | MIT | geekan/MetaGPT | 家装 SOP 参考 |
| OpenAI Agents SDK | Agent 框架 | MIT | openai/openai-agents-python | 工具/委派范式参考 |
| MemGPT / Letta | 记忆分层框架 | Apache-2.0 | letta-ai/letta | 5-tier 记忆参考（索克已有） |
| Voyager | 技能库自进化 | MIT | MineDojo/Voyager | 技能库参考（索克已有 P1 Skill 蒸馏/进化） |
| Reflexion | 语言反馈自进化 | MIT | noahshinn/reflexion | 反驳重生成参考（索克已有 rebuttal_engine） |

**索克落地建议**：**不引入外部框架**（模块化单体红线 + 已有同构能力），仅吸收其「结构化上下文、经验注入预算、轨迹回放、`pass^k` 一致性、记忆冲突门控」等可增量落地的工程细节（见 §3.4）。

### 2.6 标准（家装 / 建材 / 施工 / 环保 / BIM / 智能家居）

| 标准 | 领域 | 状态 | 与索克映射 |
|---|---|---|---|
| **IFC（ISO 16739）** ✅ | BIM 数据交换 | 现行 | 索克 IFC 导出对齐 |
| **COBie** | 运维信息交付 | 现行 | 交付物信息参考 |
| **bSDD / IDS / BCF** ✅ | buildingSMART 字典/规范/协作 | 现行 | 构件字典、交付校验、协作议题对齐 |
| **GB 55000 系列（2021 全文强制）** | 建筑/市政通用规范 | 现行强制 | 设计安全红线（承重/逃生/水电） |
| GB/T 50353 | 建筑面积计算规范 | 现行 | 面积/算量对齐 |
| GB/T 50327 | 住宅装饰装修施工规范 | 现行 | 施工工序/工艺对齐 |
| GB 50210 | 建筑装饰装修质量验收标准 | 现行 | 质检/验收清单对齐 |
| GB 18580（2017/2025 演进）| 人造板甲醛释放限量 | 现行 | 环保材料等级（ENF/E0）对齐 |
| GB 18583/18584/18585 | 胶粘剂/涂料/壁纸有害物限量 | 现行 | 材料环保约束 HC-003 对齐 |
| GB/T 46456 📦 | 智能家居互联互通 | 2026-02 实施 | 智能家居协议合规矩阵 |
| GB/Z 185-2026 📦 | 智能体互联互通 | 2026 发布 | Agent 身份码/ACDL 对齐 |
| Matter（CSA）| 智能家居协议 | 现行 | Matter 设备桥接对齐 |

**索克落地建议**：`app/standards/` 增加结构化的**标准目录**（编号/名称/领域/关键约束/适用 Agent），供 Model Spec HC 硬约束、质检验收清单、定额库、环保等级校验统一引用，实现「标准 → 规则 → 代码」可追溯（见 §3.2）。

---

## 三、代码结构优化方案（四方向，方案先行）

> 每个方向给出：现状 → 差距 → 落地动作 → 目标文件 → 优先级 → 验证方式。

### 3.1 本体/领域知识基座（方向 A，最高价值）

- **现状**：`spatial_semantics_service` 用规则从 `floorplan.data` 派生房间语义/邻接图；`app/standards/` 有定额库 + 验收清单；无统一「家装领域本体」，语义是自定义 JSON，未对齐开放本体。
- **差距**：语义无法与 Brick/BOT/IFC 对齐，跨系统互操作弱；Agent 能力描述分散在各 `agent_name`/`system_prompt`。
- **落地动作**：
  1. 新增 `app/ontology/` 包，输出三个确定性 JSON 本体（零外部运行时依赖）：
     - `renovation_ontology.json`：空间（room/zone/floor/site）+ 构件（wall/door/window/furniture/fixture）+ 关系（adjacent/contains/opens_to）
     - `agent_ontology.json`：25 Agent + 1 Orchestrator 的「能力/工具/审批边界/输入输出」结构化描述（对齐 GB/Z 185 ACDL 思路）
     - `material_ontology.json`：材质/环保等级/工艺（对齐 GB 18580 ENF/E0、HC-003）
  2. 新增 `app/services/ontology_service.py`：加载 + 检索 + 对齐映射（Brick/BOT/IFC 术语 → 索克术语），供 `spatial_semantics_service`、`agent_identity_card`、`agent_governance_audit`、RAG 引用。
  3. 端点：`GET /api/ontology/{domain}`（只读，供控制台/论文引用）。
- **优先级**：P0（零外部依赖、可立即落地、论文差异化最大）。
- **验证**：pytest 补 `tests/test_ontology.py`（本体 JSON 可解析 + 术语对齐表完整 + 25 Agent 全覆盖）。

### 3.2 标准目录扩展（方向 B）

- **现状**：标准散落在 `config/ihome_model_spec.json`（9 HC + 3 SC）、`app/standards/acceptance_checklists.py`（6 阶段）、`app/standards/quota_library.py`（9 类 × 4 档），无统一目录。
- **差距**：标准 → 规则 → 代码不可追溯，新增标准（如 HENF、GB/T 46456）需改多处。
- **落地动作**：
  1. 新增 `app/standards/standards_catalog.py`：结构化标准目录（编号/名称/领域/关键约束/适用 Agent/来源），覆盖 §2.6 清单。
  2. 复用：`ihome_model_spec.json` 的 HC 约束引用目录条目；验收清单/定额库/环保等级标注出处。
  3. 端点：`GET /api/standards`（只读，供控制台「标准对齐」页 + 论文）。
- **优先级**：P0（确定性、低风险、直接支撑「标准对齐」叙事）。
- **验证**：pytest `tests/test_standards_catalog.py`（目录完整 + 与 HC/验收清单/定额库交叉引用一致）。

### 3.3 开放数据与库对齐（方向 C）

- **现状**：IFC 导出依赖 ifcopenshell；空间语义为规则派生；无外部空间/3D 数据接入。
- **差距**：空间语义缺少开源金标评测；IFC 导出缺少校验/字典/交付规范对齐；开放数据集（3D-FRONT/SpatialLM-Dataset）未利用。
- **落地动作**（**仅方案，商用许可红线**）：
  1. **IFC 增强**：`ifc_export_service` 增补 `IfcDiff`（模型对比）、`bSDD` 构件字典对齐、`IDS` 交付校验规则（可选 feature flag，ifcopenshell 已支持）。
  2. **空间语义金标评测**：新增 `scripts/eval_spatial_semantics.py`，用 3D-FRONT 布局 + SpatialLM-Dataset 语义标注（**本地研究用，CC-BY-NC 不入生产**）评估 `spatial_semantics_service` 的房间语义/邻接图准确率。
  3. **SpatialLM 可选增强**：`spatial_perception_enabled` 下新增「AR 量房 → SpatialLM 结构化布局 → floorplan.data SSOT」外部增强器（flag 门控 + 诚实降级到现有规则派生）。
- **优先级**：P1（IFC 增强可立即；SpatialLM 需评估算力/许可，复赛前评估）。
- **验证**：`tests/test_ifc_export.py` 扩展；金标评测脚本产报告（诚实标注许可边界）。

### 3.4 多智能体/自进化增强（方向 D）

- **现状**：Harness + 自进化三层（Case/Skill 蒸馏/进化 + z≥1.96 归因）+ hub-spoke 编排已齐；`context_injection_budget`、轨迹回放、`pass^k`、记忆冲突门控已部分落地（v1.13.x）。
- **差距**：与 2026 前沿相比，可补的增量点集中在「经验质量」而非「框架」。
- **落地动作**（增量打磨，不重写）：
  1. **经验注入结构化**：`build_case_context` 已按预算裁剪，补「案例→技能」的显式溯源（注入块标注 `case_id/skill_id`，供 trace 回放与评测归因）。
  2. **轨迹回放深化**：`agent_traces.tool_calls` 已落库，补 `GET /api/agents/traces/{trace_id}/replay` 端点（只读，重建 messages 序列）。
  3. **Agent-as-a-Judge 对齐**：`llm_judge_enabled` 下补 `pass^k`（k=3）一致性 + `evaluate_judge_alignment` 人类金标校准（已在 v1.13.6 预埋，补测试与报告接线）。
  4. **记忆冲突门控**：`memory_conflict_gate_enabled` 已落地，补 growth/finance 商业运营 Agent 的冲突检测接线验证。
- **优先级**：P1（均为既有代码的增量，不引入外部依赖）。
- **验证**：pytest 扩展 `tests/test_agent_skill_evolution.py` / `test_ihome_eval.py` / `test_agent_memory.py`。

---

## 四、论文修订建议（章节级）

> 目标：把「本体/领域知识基座 + 开源资产对齐」写成新的差异化维度，并统一实测数字。

| 章节 | 修订动作 |
|---|---|
| 摘要/Abstract | 补一句贡献：「提出家装领域本体基座（对齐 Brick/BOT/IFC）与标准目录，支撑空间语义与治理审计的开源标准对齐」；测试基线统一 `2417` |
| §1.3 贡献 | 新增贡献 6：本体/领域知识基座 + 标准目录 + 开源资产对齐 |
| §2 相关工作 | 补 `SpatialLM`（arXiv:2506.07491）、`3D-FRONT`（arXiv:2011.09127）、`Brick Schema`、`IfcOpenShell`、`AutoGen/LangGraph/CrewAI/MetaGPT` 等真实文献 |
| §3 系统架构 | 增补「本体/标准层」：`app/ontology/` + `app/standards/` 在图与分层中体现 |
| §7 可观测/评估 | 补「空间语义金标评测（3D-FRONT/SpatialLM-Dataset，CC-BY-NC 研究边界）」 |
| §10 评估结果 | 数字统一：`140 ORM / 111 Service / 2417 pytest`；补「开源资产对齐表」 |
| 参考文献 | 新增真实可核查条目：SpatialLM、3D-FRONT、Brick、IfcOpenShell、AutoGen、LangGraph、MetaGPT、Voyager、Reflexion、ISO 16739、GB 55000/GB 18580 等 |

**诚实边界保持**：明确标注「SpatialLM-Dataset 为 CC-BY-NC-4.0 仅研究对照、不商用」「质检 mock CV/VR mock/AI 渲染 L1-L2 如实披露」，与既有论文一致。

---

## 五、落地顺序与风险

| 阶段 | 内容 | 风险 |
|---|---|---|
| **P0（本轮可立即）** | 3.1 本体基座 + 3.2 标准目录（零外部依赖）+ 论文数字统一 | 低：确定性 JSON + 只读端点，不碰主流程 |
| **P1（复赛前）** | 3.3 IFC 增强（IfcDiff/bSDD/IDS）+ 3.4 自进化增量（溯源/回放/pass^k） | 中：ifcopenshell 已支持；需补测试防回归 |
| **P2（评估后）** | SpatialLM 外部增强器 + 空间语义金标评测 | 高：算力/许可（CC-BY-NC）/模型体积，须 feature flag + 诚实降级 |

**红线**：所有改动 feature flag 门控可回滚；新 API 补 `tests/test_*.py`；不引入 K8s/微服务/外部记忆服务；商用受限数据（CC-BY-NC）不进入生产数据管线；全量 pytest 基线（2417 passed）不得回退。

---

## 六、参考来源

**本次经联网核实（WebSearch，2026-08-15）**
- SpatialLM / SpatialLM1.1：github.com/manycore-research/SpatialLM；arXiv:2506.07491（NeurIPS 2025）；HuggingFace manycore-research/SpatialLM1.1-Qwen-0.5B
- SpatialLM-Dataset：12,328 场景 / 54,778 房间 / 59 语义类，CC-BY-NC-4.0（Voxel51 Dataset Card）
- 3D-FRONT：arXiv:2011.09127（阿里巴巴，ICCV 2021），18,797 房间 / 7,302 家具（3D-FUTURE）
- IfcOpenShell + Bonsai（原 BlenderBIM）：docs.ifcopenshell.org / bonsaibim.org（LGPL，支持 IFC2X3/IFC4/IFC4.3 + bSDD/IDS/BCF）
- Brick Schema：github.com/BrickSchema/Brick（BSD-3）；BOT（w3c-lbd-cg.github.io/bot）；SAREF；RealEstateCore

**仓库口径（沿用 2026-08-04/08-05 前沿研究）**
- MCP 2026-07-28 规范 8 项 + W3C Trace(SEP-414) + Enterprise；A2A v1.0 + AP2；AG-UI；GB/Z 185-2026；GB/T 46456；DeepSeek V4-Flash-0731；Qwen3.8-Max；Kairos-HomeWorld；AgentLoop 数据飞轮

**公认成熟开源资产（2025 前即存在）**
- AutoGen / LangGraph / CrewAI / MetaGPT / OpenAI Agents SDK / MemGPT(Letta) / Voyager / Reflexion
- ISO 16739(IFC) / COBie / bSDD / IDS / BCF / GB 55000 系列 / GB/T 50353 / GB/T 50327 / GB 50210 / GB 18580 / GB 18583-18585 / Matter
- i-home.life 代码实测（v1.14.0：140 ORM / 76 路由模块 / 111 Service / 25 Agent+1 Orchestrator / 2417 pytest 基线）

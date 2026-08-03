# 索克家居 · 需求-实现验证报告（v1.5.0 · F1-F47 全量复核）

> 日期：2026-08-03（首轮 F1-F40 / v1.4.0）→ 2026-08-03 复核（F1-F47 / v1.5.0）
> 验证基准：PRD v3.1（`goai-agent-infra/house-design-platform-prd.html`）F1-F47 功能需求 + CLAUDE.md 架构红线
> 方法：对 `app/api`、`app/agents`、`app/services`、`app/models`、`flutter_app/lib`、`console-src/src` 真实代码逐项核验（纯静态审计 + 全量测试实测，未改动任何文件）
> 本轮新增：F1-F40 全部重新逐项核验（更细粒度：子功能级）+ F41-F47 落地质量核验 + 全量 pytest 实测（1713 passed）

## 一、结论速览

- **F1-F47 实现率：22 项已实现 / 25 项部分实现 / 0 项未实现 / 0 项纯 stub**，无完全缺失的功能模块。
- **与上轮（F1-F40：30 已实现 / 10 部分实现）的差异来自核验粒度升级**：本轮对每项做子功能级核查，11 项原「已实现」因发现子功能缺口降为「部分实现」（F3 楼层叠加 / F4 剖面图与导出 / F10 八类拆分与价格来源 / F11 豪华档与 React UI / F13 AI 自动填充 / F25 柜体格局 / F26 3D 模型 seed 全空 / F28 通道宽度检查 / F33 模拟报价缺 source 标注 / F36 入驻审核 / F39 Agent 评估与合同附项）；F5 由「部分实现」升为「已实现」（真实渲染后端可配置调用）。
- **F41-F47 落地质量：结构完整、诚实标注到位，但 5/7 项存在「声明/深度」缺口**（详见 §2.4）。
- **全量测试实测：1713 passed / 2 skipped / 3 xfailed**（916s），与 CLAUDE.md 基线一致，无回退。
- **发现 1 处🔴红线问题**：`knowledge/loader.py:189` 伪向量 RAG（`[0.0]*128`）——v1.1.31 FP-3 同类问题在 `agentic_rag.py` 已修复但 `knowledge/loader.py` 漏网（详见 §三）。
- README 声称的 57 测试 / 4 ORM 模型 / 7 flag 全部属实，无夸大。

## 二、F1-F47 核验表

图例：✅ 已实现 / 🟡 部分实现 / ❌ 未实现 / ⬜ 占位 stub

### 2.1 F1-F15（测量/设计/物料/土建/预算/结算/支付）

| # | 功能 | 状态 | 后端证据 | 前端证据 | 缺口/诚实降级 | 测试 |
|---|---|---|---|---|---|---|
| F1 | AR 空间测量 | ✅ | surveys.py 14 端点 + ar_scan_service 降级链（LiDAR→VisualSLAM→摄影测量→手动）+ iOS ARScanPlugin | ar_scan_page.dart + web/ar-measurement.html | 墙面特征"AI 检测"为规则启发式（`detected_by="ai_default"` 标注）；USDZ 解析失败降级硬编码户型（带 parse_warnings） | test_ar_scan/test_surveys |
| F2 | 2D CAD 精确绘图 | ✅ | cad_import.py DXF 真实解析（ezdxf）+ DWG 转换 | web/studio.html Canvas 引擎（正交/捕捉/图层/块）+ cad_page.dart + stylus_adapter | 自绘引擎非专业 CAD 内核；缺样条 | test_cad_import |
| F3 | 3D 建模与可视化 | 🟡 | 无后端 3D API（前端即时拉伸） | studio.html generate3DFrom2D + 3d-viewer.html | **楼层叠加未实现**（仅单楼层）；门窗洞口无持久化模型 | visual 批次 |
| F4 | 平立剖面自动生成 | 🟡 | construction_drawing.py 3 端点（floor-plan/elevation/all）+ SVG 服务 | studio.html 平立剖视图 | **剖面图无后端端点**；**DXF/DWG/PDF 导出未实现**（仅 SVG） | test_construction_drawing* |
| F5 | 效果图渲染 | ✅ | ai_render.py 4 端点 + L0-L3 四级降级链 + 真实后端 httpx 调用 | AIRenderPage.tsx + ai_image_page.dart | 未配置后端→mock 诚实标注（`render_backend="mock"`）；restage 待适配器补 base64 | test_ai_render（24 契约用例） |
| F6 | BOM 自动生成 | 🟡 | materials.py generate_bom + material_service 面积×标准用量经验法 | MaterialsPage.tsx + materials_page.dart | **仍为经验法，未接入几何算量**（F9 的 quantity_takeoff_service 已具备可挂接） | test_materials |
| F7 | BOM 导出与管理 | 🟡 | export Excel（openpyxl 真实）+ summary + auto-match | MaterialsPage.tsx + materials_page.dart | **无版本管理/差异标注**（BOMItem 无 version 字段） | test_materials |
| F8 | 土建结构 | ✅ | structural.py 40+ 端点 + structural_service（GB 50009 荷载/GB 50096 开间进深合规） | StructuralPage.tsx + structural_page.dart + web/structure.html | — | test_structural |
| F9 | 工程量计算 | ✅ | takeoff.py + quantity_takeoff_service（v1.2.0 已从 floorplan 几何派生，GB/T 50854） | TakeoffPage.tsx + takeoff_page.dart | 合规标注诚实声明最终结算须套国标复核 | test_takeoff |
| F10 | AI 分项预算 | 🟡 | budgets.py generate-plan + agents/budget.py 规则引擎 | budget_page.dart + BudgetPage.tsx（仅查看） | **PRD 8 类拆分实为 5 类**；每项"材料费+人工费+管理费+价格来源"标注缺失；"AI"为纯规则无 `source` 标注 | test_budgets* |
| F11 | 多方案预算对比 | 🟡 | compare-plans 3 档 + differences + 推荐 | budget_page.dart Tab2 | 缺"豪华"档（PRD 经济/舒适/豪华）；**React 无对比 UI** | test_budgets_and_agents |
| F12 | 实时预算追踪 | 🟡 | variance-check（>5% warning/>10% critical）+ dashboard 汇总 | DashboardPage.tsx | **采购订单→预算科目自动扣减未实现**（procurement/change_orders 无 budget 关联代码）；手动触发非自动 | test_procurement/test_dashboard |
| F13 | 预算模板库 | 🟡 | templates + apply（3 套硬编码模板线性缩放） | budget_page.dart Tab3 | **"AI 自动填充"未实现**；React 无模板 UI | test_budgets_and_agents |
| F14 | AI 自动结算 | ✅ | settlements.py 13 端点 + agents/settlement.py 5 里程碑 + 6 类异常检测 | SettlementPage.tsx + settlement_page.dart | auto-settlement 需客户端传金额（未自动聚合）；规则引擎非 LLM | test_settlements |
| F15 | 支付管理 | ✅ | payments.py 11 端点（分阶段节点/电子发票 INV-/归档）+ payment_service 状态机 | EscrowPage.tsx + timeline_page.dart | 发票为平台自编号记录（未对接税局系统）；担保支付独立 escrow | test_payments/test_escrow_trustee |

### 2.2 F16-F30（厨卫/电器/硬装/软装/家具/灯具）

| # | 功能 | 状态 | 后端证据 | 前端证据 | 缺口/诚实降级 | 测试 |
|---|---|---|---|---|---|---|
| F16 | 厨房设计器 | ✅ | kitchen.py 10 端点 + kitchen_service（I/L/U/中岛、黄金三角 3.6-6.6m、燃气/排烟校验） | KitchenPage.tsx + kitchen_page.dart | 布局生成器内置品牌模板（属设计器预设） | test_kitchen |
| F17 | 卫生间设计器 | ✅ | bathroom.py 10 端点（干湿分离/地漏坡度 1-2%/防水校验/通风） | BathroomPage.tsx + bathroom_page.dart | waterproof_strict_check=False 回滚硬编码 passed（flag 控制，默认 strict） | test_bathroom |
| F18 | 厨卫水电 | ✅ | kitchen_bath_mep.py 11 端点（给排水/回路/等电位 GB50096/燃气预留） | kitchen_bath_mep_page.dart；**React 无页面** | React 控制台缺 F18 页面 | test_kitchen_bath_mep |
| F19 | 电器品类库 | 🟡 | appliance.py 11 端点 + appliance_service 多维筛选/能效/安装要求 | AppliancePage.tsx + appliance_page.dart | **无 3D 模型字段/资产（PRD 要求每款含 3D 模型）**——已知缺口未修复 | test_appliance |
| F20 | 电器点位规划 | ✅ | 点位 CRUD + load-calc + cabinet-match + embedding-plan（空调孔 φ65/电视墙 φ50） | AppliancePage.tsx + appliance_page.dart | — | test_appliance |
| F21 | 硬装 | ✅ | hard_decoration.py 14 端点（瓷砖排版 5 式/涂料用量/吊顶灯位/防滑 DIN51130） | HardDecorationPage.tsx + hard_decoration_page.dart | 涂料色卡无专门端点（仅用量+颜色字段） | test_harddecoration |
| F22 | 水电隐蔽工程 | ✅ | mep.py 4 端点 + mep_service（房型点位标准/GB50096/负荷平衡/排水坡度） | MepPage.tsx + mep_page.dart | 纯计算无 ORM；等电位默认假定合规（建议型输出） | test_mep |
| F23 | 门窗/防水 | ✅ | door_window_waterproof.py 12 端点（门窗选型/防水面积/规范校验） | DoorWindowPage.tsx + door_window_waterproof_page.dart | — | test_door_window_waterproof |
| F24 | 软装搭配 | 🟡 | soft_furnishing.py 13 端点（ai-match/60-30-10 配色/预算） | SoftFurnishingPage.tsx + soft_furnishing_page.dart | **AR 挂画试挂未实现**（挂画仅为 item_type）——已知缺口未修复 | test_soft_furnishing |
| F25 | 收纳系统 | 🟡 | storage 4 端点（人均 200L + 容量计算） | SoftFurnishing 集成 | 柜体内部格局较浅（仅格数+容量，无层板/抽屉/挂杆明细） | test_soft_furnishing |
| F26 | 家具品类库 | 🟡 | furniture_catalog.py 8 端点 + 1:1 摆放坐标计算 | FurniturePage.tsx + furniture_catalog_page.dart | **model_3d_url 字段存在但 seed 数据全 NULL**；AR 摆放=数学坐标计算非真实 AR | test_furniture_catalog |
| F27 | 定制家具设计器 | ✅ | custom_furniture.py 12 端点（7 类参数化/板材展开/五金/BOM 拆单/报价） | CustomFurniturePage.tsx + custom_furniture_page.dart | — | test_custom_furniture |
| F28 | 智能布局推荐 | 🟡 | agents/designer.py analyze_circulation（三动线 + Liang-Barsky 穿越检测） | DesignPage.tsx + design_proposal_page.dart | **通道宽度检查未实现**（仅动线长度/穿越） | test_vertical_designers |
| F29 | 灯光设计 | ✅ | lighting.py 9 端点 + lighting_service（照度 Lux/色温/GB50034 眩光 UGR/均匀度） | LightingPage.tsx + lighting_page.dart | 灯光层次（环境/任务/氛围）未显式建模为层类型 | test_lighting |
| F30 | 无主灯设计 | ✅ | design_none_main_light（筒灯网格+射灯+灯带，CAD 坐标） | LightingPage.tsx + lighting_page.dart | 磁吸轨道灯未显式建模 | test_lighting |

### 2.3 F31-F40（智能家居/采购/服务商/施工）

| # | 功能 | 状态 | 后端证据 | 前端证据 | 缺口/诚实降级 | 测试 |
|---|---|---|---|---|---|---|
| F31 | 智能家居方案 | ✅ | smart_home.py 17 端点（点位/布线/协议/Matter placement）+ GB 50311 合规 | SmartHomePage.tsx + smart_home_page.dart | Matter commission 走 stub→501 诚实报错 | test_smart_home* |
| F32 | 场景编辑 | 🟡 | scene_automation.py 19 端点 + **v1.5.0 新增** ecosystem.py 状态报告 | ScenePage.tsx + EcosystemPage.tsx（新） | **生态桥接仍 stub**（5 桥接 32 处 NotImplementedError）；v1.5.0 状态报告+501 诚实补齐标注机制 | test_scene_automation/test_ecosystem_bridge |
| F33 | AI 比价采购 | 🟡 | procurement.py 20 + procurement_enhanced.py 24 端点（评分 价格60%+交期25%+评级15%） | ProcurementPage.tsx + procurement_enhanced_page.dart | **模拟市场报价仅代码注释标注，响应体无 source=mock 字段** | test_procurement* |
| F34 | 下单与物流 | ✅ | 订单 CRUD + escrow 8 + logistics 5 + samples 3 | DeliveryPage.tsx + EscrowPage.tsx | 旧 tracking 端点模拟轨迹仅 docstring 标注（响应体无 source） | test_b2b_delivery |
| F35 | 服务商匹配 | 🟡 | workers.py 6 端点 + worker_service 六类多维评分 | worker_page.dart；**React 无 WorkersPage** | **投标/电子签/评价全缺**——已知缺口未修复 | test_workers |
| F36 | 工程队匹配 | 🟡 | crews.py 7 端点 + crew_service 六维评分 | CrewsPage.tsx + crew_page.dart | **无入驻审核流程**（create 直落库默认 available）；模型缺执照/保险字段 | test_crews |
| F37 | AI 进度管理 | ✅ | construction.py ~44 端点（Gantt/WBS/依赖/关键路径/预警/里程碑）+ 推送任务卡到聊天室 | ConstructionPage.tsx + construction_page.dart + gantt_chart.dart | 照片质检 mock CV 三重标注（source/engine/is_placeholder） | test_construction* |
| F38 | AI 质量管理 | 🟡 | quality 端点内嵌 construction.py ~12 端点 + quality_service（验收清单/整改闭环状态机真实） | QualityPage.tsx + quality_report_page.dart | **缺陷识别仍为 mock CV**（hash 模拟，`engine="mock_cv_engine"` 三重标注）——已知缺口未修复 | test_qa_inspector_concierge |
| F39 | 变更管理 | 🟡 | change_orders.py 6 端点 + 真实状态机（pending→reviewing→approved/rejected） | ChangeOrdersPage.tsx + change_orders_page.dart | **review 为人工录入未调设计/预算 Agent**；无合同附项表 | test_change_orders |
| F40 | 三方协作 | 🟡 | chat.py 6 端点 + chat_service + 四角色鉴权 | chat_page.dart；console 仅 Workbench 无 IM 群页 | **Agent 未作为群成员进 IM 房间**，响应走独立 /agents/chat——已知缺口未修复 | test_chat/test_agents* |

### 2.4 F41-F47（v1.5.0 新增 · 落地质量核验）

| # | 功能 | 状态 | 后端证据 | 业务规则深度 | flag | 前端 | 测试 |
|---|---|---|---|---|---|---|---|
| F41 | 适老改造 | 🟡 | elderly_adaptation.py 7 端点 | **GB 50763-2012 真实规则**（门宽≥800/走廊≥900/高差≤15mm，80/60 阈值）；score 空不伪造结论 | elderly_adaptation_enabled | ElderlyAdaptationPage.tsx + elderly_adaptation_page.dart | test_elderly_adaptation（10） |
| F42 | 局部焕新 | ✅ | partial_renovation.py 5 端点 | 5 种 scope × 3 档模板 + 阶段化任务 + 干扰最小化方案（噪音/降尘/隔离） | partial_renovation_enabled | PartialRenovationPage.tsx + partial_renovation_page.dart | test_partial_renovation（8） |
| F43 | 资金托管深化 | ✅ | escrow_trustee.py 8 端点 | **真实状态机**（active→双向确认→release_requested→released）+ 放款前置校验 + 利息归属业主 | escrow_trustee_enabled | EscrowPage.tsx + escrow_trustee_page.dart | test_escrow_trustee（12，含状态机/越权） |
| F44 | 环保材料标签 | 🟡 | eco_materials.py 6 端点 | ENF>E0>E1（GB/T 39600-2021）真实校验 + HC-003 合规报告 + 替代推荐 | eco_material_label_enabled | EcoMaterialsPage.tsx + eco_materials_page.dart | test_eco_materials（10） |
| F45 | 方案前置决策 | 🟡 | solution_first.py 2 端点 | **静态模板规则**（3 套布局写死）+ 面积×单价区间，`source=rule_based` 诚实标注（明确可接 LLM） | solution_first_enabled | SolutionFirstPage.tsx + solution_first_page.dart | test_solution_first（8） |
| F46 | 生态桥接优先级 | 🟡 | ecosystem.py 2 端点 + ecosystem_bridge_status.py | 4 生态注册表（米家 p1/鸿蒙 p2/HomeKit p3/涂鸦 p4）+ 环境变量检测 + requires_api_key 诚实报告 | ecosystem_bridge_priority_enabled | EcosystemPage.tsx + ecosystem_page.dart | test_ecosystem_bridge（4） |
| F47 | AI 装修问答 | 🟡 | ai_qa.py 2 端点 + knowledge/loader.py | 关键词优先/向量降级 + citation 引用 + no_match 不编造；**知识库仅落地 4/8 域** | ai_qa_search_enabled | AIQAPage.tsx + ai_qa_page.dart | test_ai_qa_search（5） |

**F41-F47 缺口明细**：
- **F41**：HC-006 逃生通道仅 docstring 声明（无代码）；无入户门宽/逃生窗/禁止封闭走廊专项检查。
- **F44**：PRD「AI 选材强制提示环保等级」未落地——ai_render/material 链路无 eco_grade 引用，仅独立 /validate 端点 + 前端表单。
- **F45**：「AI 先出 3 套方案」实为静态模板规则（诚实标注）；「业主端首屏入口」仅侧边栏/详情页，非首屏突出位。
- **F46**：**核心要求「优先落地 1-2 个主流生态真实联动」未完成**——米家/鸿蒙桥接仍 NotImplementedError（诚实 501 + 状态报告，功能处于"规划+诚实标注"而非"部分落地"）。
- **F47**：知识库 4/8 域（eco_ratings/safety/design_rules/cost_reference 缺失）；「真实案例库」未落地；**问答链路未接入 AgenticRAG**（走 knowledge/loader 关键词路径）。

## 三、🔴 红线问题（诚实降级违反）

| # | 位置 | 问题 | 判定 |
|---|---|---|---|
| 1 | `knowledge/loader.py:189` | **`vector_search` 使用 `[0.0]*128` 占位向量做 Qdrant 语义检索（伪 RAG）**。v1.1.31 FP-3 已修复 `agentic_rag.py` 同类问题（改真实 embedding + 失败降级关键词），但 `knowledge/loader.py` 是漏网修复——一旦 `vector_db_url` 配置即返回"看似语义检索"的伪结果。当前默认空串使生产走关键词降级，风险暂未暴露 | **🔴 违反「禁止硬编码假数据伪装真实能力」红线**（建议 P0 修复，对齐 agentic_rag 的 `embed_query` 路径） |

**名实差距（非伪装但需标注）**：
- `agents/budget.py`/`agents/settlement.py` 以"AI Agent"名义但为 100% 确定性规则，**响应体无 `engine="rule_based"` 标注**——建议补齐诚实标注。
- `app/api/procurement.py` 模拟物流轨迹、`procurement_enhanced_service.py` 模拟市场报价、`agents/procurement.py` 模板推荐供应商——**仅代码注释/docstring 标注，响应体无 `source="mock"` 字段**，前端无法程序化识别（历史教训 v1.1.31 同类形态）。

## 四、诚实降级/stub 全量清单（更新）

| # | 降级点 | 文件 | 性质 |
|---|---|---|---|
| 1 | 生态桥接 stub（5 桥接 32 处） | ecosystem_bridge.py | HomeKit/米家/鸿蒙/涂鸦/Matter `NotImplementedError("TODO: need API key")`，端点 501 + v1.5.0 状态报告诚实标注 |
| 2 | 质检缺陷识别 mock CV | agents/qa_inspector.py | hash 模拟，`engine="mock_cv_engine"` + is_placeholder 三重标注 |
| 3 | VR 渲染 mock | vr_panorama_service.py | `source="mock_fallback"` |
| 4 | AI 渲染降级链 | ai_render_service.py | L0-L3；未配置后端→L2 占位 + `render_backend="mock"`；strict+require_real→503 |
| 5 | AR 模型解析降级 | ar_scan_service.py | USDZ/GLB 解析失败降级硬编码户型（parse_warnings 标注） |
| 6 | IFC 依赖 ifcopenshell | ifc_export_service.py | 可选依赖未装报错；H-IFC viewpoints 占位 |
| 7 | Sketch-3D 无 vision key | sketch_to_3d.py | flag 关闭返回 `mode="no_vision_model"` |
| 8 | 抽象基类 NotImplementedError | identity/webauthn/mcp | 抽象接口（有真实实现），非真 stub |
| 9 | 图像识别降级 | image_recognition_service.py | 无 AI API 时文字推断 |
| 10 | 工具假数据回滚 | agent_tool_registry.py | `tool_real_data_enabled=False` 时回滚样例（source="*_fallback" 标注） |
| 11 | 🔴 伪向量 RAG | knowledge/loader.py | `[0.0]*128` 占位向量（**违反红线，见 §三**） |
| 12 | 其他 mock | push_sender/voice_realtime/ai_image 等 | 测试音频/模板/LLM 无 key 规则降级 |

## 五、规模数据核对（实测 vs 声明 · v1.5.0）

| 指标 | 实测代码 | README 声称 | 结论 |
|---|---|---|---|
| API 模块 | **70** 文件含 `@router` | 70 模块 | ✅ 一致 |
| 端点数 | 630+（含 /health /metrics /docs /ws） | 630+ | ✅ 一致 |
| ORM 模型 | **118**（models/__init__.py `__all__`） | 118 | ✅ 一致 |
| Agent | **22 个具体 Agent**（25 文件含 base/harness） | 22 | ✅ 一致 |
| Service | 89 个 .py 模块文件（含 __init__.py 90） | 82 | 声明偏低（含辅助文件口径差异） |
| MCP 工具 | **11**（BUILTIN_TOOLS） | 11 | ✅ 一致 |
| 意图契约 | **39** 全 validated | 39 | ✅ 一致 |
| 版本号 | **`app_version="1.5.0"`** | v1.5.0 | ✅ 上轮"版本滞后"已修复 |
| F41-F47 flag | **7 个**全部存在默认 True | 7 | ✅ 属实 |

## 六、测试覆盖核验（本轮实测）

- **全量 pytest：1713 passed / 2 skipped / 3 xfailed，耗时 916s（15m16s）**——与 CLAUDE.md 基线 1713 一致，无回退；收集 1718（121 个根目录 test 文件 + 2 e2e）。
- F41-F47 新增 **57 测试**（10+8+12+10+8+4+5）全部为真实 API 集成测试（鉴权/CRUD/状态机/诚实降级路径），README 声称属实。
- 63 个 API 模块均有对应测试文件，无缺测模块；MCP 21 / 缓存隔离 16 / AI 渲染契约 24 / H-IFC 16 专项覆盖与声明一致。
- 【缺口】Flutter 页面测试覆盖 8/45（上轮遗留，本轮未复测）。

## 七、核心缺口（按影响排序 · 更新）

1. **🔴 伪向量 RAG（P0 红线）**：knowledge/loader.py `[0.0]*128`，对齐 agentic_rag 修复。
2. **对外连接三缺口依旧**：生态桥接 stub（F46 米家/鸿蒙真实联动未落地，仅状态报告）、Agent 未进 IM 群（F40）、AI 质检 mock CV（F38）——行业已规模化落地真实 CV（浙江"智安工兵"91% 准确率），索克最大"名实差距"。
3. **F6/F7 BOM**：仍为经验法（几何算量 F9 已具备未接入）+ 无版本管理/差异标注；F12 采购→预算科目自动扣减未打通。
4. **F41-F47 深度缺口**：F41 HC-006 仅注释、F44 AI 选材强制提示未落地、F45 rule_based 非真 AI、F47 知识库 4/8 域 + AgenticRAG 未接入。
5. **资产类缺口**：F35 电子签、F24 AR 挂画试挂、F19/F26 3D 模型资产（全仓无 3D 资产文件，系统性薄弱）。
6. **F3/F4**：楼层叠加、剖面图后端端点 + DXF/DWG/PDF 导出。
7. **名实差距标注**：budget/settlement 规则引擎无 `engine="rule_based"`；procurement 模拟报价/物流轨迹响应体无 `source="mock"`。
8. **React 控制台滞后**：F11 对比/F13 模板/F18 厨卫水电/F35 服务商/F40 IM 群 5 处无页面或页面缺失（Flutter 端已覆盖）。

## 八、核心风险

| 风险 | 等级 | 说明 |
|---|---|---|
| 伪向量 RAG 潜伏 | 🔴 高 | loader.py 配置 vector_db_url 后即返回伪语义结果，与诚实降级红线冲突 |
| 名实差距被评审攻击 | 高 | 飞流AI 3.1（空间模型+拆改规划+全流程交付）、酷家乐算量 2.0、行业真实 AI 质检均已落地，索克 F38/F45/F46 的"AI 名义 vs 规则/mock 实现"差距显著 |
| 响应体缺 source 标注 | 中 | 模拟物流/报价前端无法程序化识别，v1.1.31 教训同类形态 |
| 真实后端依赖不可用 | 中 | AI 渲染/质检 CV/生态桥接真实能力依赖外部 key，默认路径全部诚实降级 |
| Flutter 测试覆盖不足 | 中 | 8/45 页面有测试 |

## 九、关键证据文件

- [knowledge/loader.py](file:///Users/netsong/Developer/i-home.life/knowledge/loader.py#L165-L199)（🔴 伪向量 RAG）
- [ai_render_service.py](file:///Users/netsong/Developer/i-home.life/app/services/ai_render_service.py)（F5 降级链 + 真实后端）
- [ecosystem_bridge.py](file:///Users/netsong/Developer/i-home.life/app/services/ecosystem_bridge.py) + [ecosystem_bridge_status.py](file:///Users/netsong/Developer/i-home.life/app/services/ecosystem_bridge_status.py)（F46 状态报告）
- [qa_inspector.py](file:///Users/netsong/Developer/i-home.life/app/agents/qa_inspector.py)（F38 mock CV）
- [agent_tool_registry.py](file:///Users/netsong/Developer/i-home.life/app/services/agent_tool_registry.py)（11 工具）
- [app/models/__init__.py](file:///Users/netsong/Developer/i-home.life/app/models/__init__.py)（118 模型）
- [app/config.py](file:///Users/netsong/Developer/i-home.life/app/config.py)（`app_version="1.5.0"` + 7 个 F41-F47 flag）
- [quantity_takeoff_service.py](file:///Users/netsong/Developer/i-home.life/app/services/quantity_takeoff_service.py)（F9 几何算量，可挂接 F6 BOM）

## 十、本轮验证结论

- **结构完整性高**：0 项未实现 / 0 项纯 stub，后端 API/Service/ORM 三层与双端页面、测试全部配套；F41-F47 全链路落地（flag + Web/Flutter 页面 + 57 测试 + 4 ORM）。
- **诚实标注意识整体优秀**：绝大多数 mock/占位点均带 source/engine 标注，F41 score 空不伪造、F45 rule_based、F46 requires_api_key、F47 no_match 均为正面范例。
- **需 P0 处置**：loader.py 伪向量红线；需系统性补强：真实 AI 质检 CV、生态真实桥接、BOM 算量贯通、名实差距 source 标注。

## 十一、修复状态（v1.6.0 执行落地，2026-08-03）

基于本报告 §七 核心缺口，v1.6.0 已执行以下修复（详见 `CHANGELOG.md` v1.6.0）：

| 缺口（§七 序号） | 修复状态 | 落地位置 |
|---|---|---|
| 1. 🔴 伪向量 RAG | ✅ 已修复 | knowledge/loader.py → 真实 embedding（embed_query），禁用/失败降级关键词 |
| 7. 名实差距标注（budget/settlement/procurement） | ✅ 已修复 | budget.py/settlement.py 补 `engine="rule_based"`；procurement 补 `data_source="mock"`/`source="mock"`/`source="mock_template"` |
| 4. F41 HC-006 仅注释 | ✅ 已修复 | elderly_adaptation_service.py 新增 `check_escape_route()`（入户门≥800/逃生通道≥900/高差≤15/逃生窗≥600/禁封闭走廊） |
| 4. F44 AI 选材强制提示 | ✅ 已修复 | material_service.py BOM/AI 选材链路接入 `eco_grade`+`eco_notice`（无认证 `unverified` 诚实标注） |
| 4. F47 知识库 4/8 域 | ✅ 已修复 | 新增 eco_ratings/safety/design_rules/cost_reference → 8 域 114 条 |
| 2. F38 mock CV | 🟡 已接入真实 CV 路径 | qa_inspector.py 多模态视觉 LLM（`real_cv_quality_enabled` flag 默认 False），无 key 诚实降级 mock |
| 2. F40 Agent 未进 IM 群 | ✅ 已修复 | chat.py/chat_service.py 房间 Agent 群成员 + 自动回复（真实/规则/降级三档标注 + 系统 Agent 用户） |
| 3. F12 采购→预算联动 | ✅ 已修复 | budget_service.deduct_budget_for_purchase + procurement_service 订单自动扣减 + `GET /budgets/{project_id}/linked-purchases` |
| 3. F7 BOM 版本管理 | ✅ 已修复 | BOMItem.version + `/bom/{project_id}/versions|version|diff` |
| 3. F6 BOM 几何算量 | ✅ 已修复 | generate_bom_for_project 优先 quantity_takeoff_service 几何派生，`quantity_source` 诚实标注 |
| 2. F46 米家/鸿蒙真实联动 | ⬜ 未落地（外部依赖） | 保持 stub + 状态报告 501 诚实标注（需真实 API key，见调研报告 A2 后续项） |

**v1.6.0 工程动作**：轻量 schema 迁移 v7（chat_rooms.agent_members / chat_messages.auto_reply_meta / bom_items.version|quantity_source|fallback_note）+ 新增 ~30 测试 + 版本号全链路 1.5.0 → 1.6.0。

**Wave 2（v1.7.0）追加落地**：F45 方案前置决策 LLM 升级（source=llm/rule_based 诚实降级）、F10 预算 8 类拆分+三费+价格来源（保留 legacy_5cat）、F13 模板 AI 自动填充、F36 工程队入驻审核状态机（未审核不参与匹配）、F39 变更 Agent 自动评估（assessment_source=agent/unavailable）、F28 通道宽度检查、F4 剖面图端点+DXF 导出（PDF 依赖缺失诚实 501）、React 控制台 5 页面补齐（F11/F13/F18/F35/F40）。

**遗留项（v1.7.0 未覆盖，均依赖外部服务/资产，保持诚实 stub）**：F46 真实生态桥接（A2，需米家/鸿蒙 API key）、F35 电子签（A4，需电子签服务）、F24 AR 挂画试挂（A5，需 AR 能力）、F19/F26 3D 模型资产（A6，需 3D 资产）、施工可视化 AI 监理（F48，新需求排期）。

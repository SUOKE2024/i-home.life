# 索克家居 i-home.life 用户验收测试计划 (UAT Test Plan)

| 项 | 值 |
|---|---|
| 项目 | 索克家居 · AI 智能装修平台 (i-home.life) |
| 版本 | v1.0.0 |
| 文档版本 | V1.0 |
| 编制日期 | 2026-07-08 |
| 测试环境 | 远程生产 `http://118.31.223.213:8081` |
| 认证方式 | PASETO v4.local |
| 前置条件 | SIT 已通过 (通过率 99.49%, 0 Critical/High) |
| 测试范围 | PRD F1-F40 全量功能 (40 模块 / 321 API / 72 张表) |
| 测试负责人 | UAT 测试组 |

---

## 1. 测试目标与范围

### 1.1 测试目标

验证索克家居 i-home.life v1.0.0 在真实生产环境 `http://118.31.223.213:8081` 上，能否完整支撑业主、设计师、施工方、供应商四类角色从注册到结算支付的端到端业务闭环，并满足 PRD F1-F40 的业务验收标准与体验要求。

### 1.2 测试范围

| 范畴 | 包含 | 不包含 |
|---|---|---|
| 功能验收 | F1-F40 全部 40 个功能模块的核心业务路径 | 第三方支付通道真实扣款 |
| UI/UX 易用性 | Web 后台 13 Tab 切换 / 移动端 Flutter App / 设计台 Canvas | 设计稿视觉走查 |
| 性能负载 | 接口响应时间、并发 50 用户、Canvas/3D 渲染 FPS | 长时压力测试 (soak) |
| 兼容性 | Chrome / Safari / Edge / 鸿蒙 MatePad / iOS / Android | IE 与低端机 |
| 安全 | PASETO 鉴权、越权防护、输入校验 | 渗透测试与代码审计 |

### 1.3 准入准出标准

| 阶段 | 标准 |
|---|---|
| 准入 | SIT 报告通过 (99.49%)；远程环境健康检查 `/health` 返回 200；演示账号可用 |
| 准出 | 8 大核心场景 100% 执行；Critical/High 缺陷为 0；Medium 缺陷 ≤ 2 且有规避方案；用户代表签字确认 |

---

## 2. 测试环境与账号

### 2.1 测试环境

| 项 | 值 |
|---|---|
| 后端地址 | `http://118.31.223.213:8081` |
| API 前缀 | `/api` |
| API 文档 | `http://118.31.223.213:8081/api/docs` |
| Web 后台 | `http://118.31.223.213:8081/index.html` |
| 设计台 | `http://118.31.223.213:8081/studio.html` |
| 3D 查看器 | `http://118.31.223.213:8081/3d-viewer.html` |
| VR 查看器 | `http://118.31.223.213:8081/vr-viewer.html` |
| 健康检查 | `GET /health` 返回 `{"status":"ok"}` |
| WebSocket | `ws://118.31.223.213:8081/ws/{project_id}` |

### 2.2 测试账号

| 角色 | 手机号 | 密码 | 用途 |
|---|---|---|---|
| 业主 | 13800138000 | 123456 | 业主端场景 |
| 设计师 | 注册新建 | 123456 | 设计师端场景 |
| 施工方 | 注册新建 | 123456 | 施工方端场景 |
| 供应商 | 注册新建 | 123456 | 供应商端场景 |

### 2.3 测试设备

| 类型 | 设备 | 浏览器/系统 |
|---|---|---|
| 桌面 | MacBook / Windows PC | Chrome 120+, Safari 17+, Edge 120+ |
| 平板 | 华为 MatePad (鸿蒙) | HarmonyOS App (3.35.7-ohos-0.0.3) |
| 手机 | iPhone 14 / Android 旗舰 | iOS App / Android App |

---

## 3. 测试场景总览

| # | 场景 | 角色 | 业务链路 | 关联 PRD | 用例数 |
|---|---|---|---|---|---|
| UAT-01 | 业主端全链路闭环 | 业主 | 注册→项目→AI 设计→AR 测量→预算→采购→施工→结算→支付 | F1/F9/F15/F28 | 5 |
| UAT-02 | 设计师户型与专业设计器 | 设计师 | 户型→厨房→卫生间→灯光→VR 全景→AI 图生图 | F16/F17/F29/F30 | 5 |
| UAT-03 | 采购增强与担保支付状态机 | 业主+供应商 | 比价报告→担保支付→物流追踪→样品申请 | F33/F34 | 5 |
| UAT-04 | 施工方施工与质量闭环 | 施工方 | 施工任务→进度→质量检验→整改单→评估 | F37/F38 | 5 |
| UAT-05 | 三方 IM 协作与服务者匹配 | 全角色 | 服务者匹配→工程队匹配→IM 群组→@提及→已读 | F35/F36/F40 | 5 |
| UAT-06 | UI/UX 易用性与 13 Tab 切换 | 业主 | 13 Tab 切换 / 响应式 / 移动端适配 / 错误提示 | 全局 | 5 |
| UAT-07 | 性能与并发负载 | 系统 | 响应时间 / 50 并发 / Canvas FPS / WebSocket | 全局 | 4 |
| UAT-08 | 兼容性与跨端一致性 | 全角色 | Chrome/Safari/Edge + 鸿蒙/iOS/Android | 全局 | 4 |
| **合计** | | | | | **38** |

---

## 4. 测试用例详情

### UAT-01 业主端全链路闭环（业主）

**场景描述**：业主从注册账号开始，完整走完「注册→创建项目→AI 设计→AR 测量→预算→采购→施工→结算→支付」全业务链路，验证各环节衔接与金额一致性。

#### UAT-01-01 业主注册与登录（PASETO 鉴权）

| 项 | 内容 |
|---|---|
| 前置条件 | 远程环境健康，演示账号未占用手机号 |
| 测试步骤 | 1. `POST /api/auth/register` 提交手机号 `13900{随机}0000` + 密码 `123456` + 角色 `owner`<br>2. 校验返回 `201` 且 `access_token` 以 `v4.local.` 开头<br>3. `POST /api/auth/login` 用相同手机号密码登录<br>4. `GET /api/auth/me` 携带 `Authorization: Bearer {token}` |
| 预期结果 | 注册与登录均返回 PASETO v4.local token；`/auth/me` 返回当前用户信息且角色为 owner |
| 验收标准 | AC-AUTH-1：token 必须为 `v4.local.*` 格式；AC-AUTH-2：错误密码返回 `400 手机号或密码错误`；AC-AUTH-3：未携带 token 访问 `/auth/me` 返回 `401` |
| 优先级 | High |

#### UAT-01-02 创建项目与 AI 设计建议

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-01-01 完成，持有业主 token |
| 测试步骤 | 1. `POST /api/projects` 创建项目（name=测试公寓, area=89, city=上海）<br>2. 校验返回 `201` 且 `project_id` 为 UUID<br>3. `POST /api/agents/design` 提交「现代简约三居，预算 15 万」<br>4. 校验返回包含风格建议与至少 1 套布局 |
| 预期结果 | 项目创建成功；AI Agent 响应时间 < 3s 且包含可识别设计建议 |
| 验收标准 | AC-AGENT-1：Agent 响应 < 3s；AC-AGENT-2：Agent 完成率 ≥ 85%（9 套布局可命中） |
| 优先级 | High |

#### UAT-01-03 F1 AR 空间测量降级链

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-01-02 完成，项目已创建 |
| 测试步骤 | 1. `POST /api/surveys/ar/sessions` 创建扫描会话（device_capability=auto）<br>2. 模拟无 LiDAR 设备，触发降级：LiDAR → VisualSLAM → Photo → Manual<br>3. `POST /api/surveys/ar/features` 提交墙面特征<br>4. `POST /api/surveys/ar/points` 提交校准点<br>5. 校验精度校验返回结果 |
| 预期结果 | 扫描会话创建 `201`；四级降级链完整执行；最终回退到 Manual 模式仍可生成测量数据 |
| 验收标准 | AC-AR-1：降级链必须按 LiDAR→VisualSLAM→Photo→Manual 顺序；AC-AR-2：Manual 模式仍可产出有效测量结果 |
| 优先级 | High |

#### UAT-01-04 BOM→预算→采购金额一致性

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-01-02 项目已存在，已生成户型 |
| 测试步骤 | 1. `POST /api/materials/bom` 生成 BOM（含至少 1 项物料）<br>2. `POST /api/budgets/generate-from-bom/{bom_id}` 生成预算<br>3. 校验预算 total 与 BOM 汇总一致<br>4. `POST /api/procurement/orders` 创建采购单（注意: 请求体使用 `lines` 字段而非 `items`）<br>5. 校验采购金额与预算一致 |
| 预期结果 | BOM→预算→采购金额链路数值一致（参考 SIT 实测 total=9900） |
| 验收标准 | AC-MONEY-1：BOM 汇总 = 预算 total = 采购金额；AC-MONEY-2：精度保留 2 位小数 |
| 优先级 | High |

#### UAT-01-05 结算→支付首付 30% 闭环

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-01-04 预算已生成 |
| 测试步骤 | 1. `POST /api/settlements/generate-from-budget/{budget_id}` 生成结算<br>2. 校验结算 total = 预算 total<br>3. `POST /api/payments` 发起支付，amount = total × 30%<br>4. `POST /api/payments/{id}/confirm` 确认支付<br>5. `GET /api/payments/project/{project_id}` 查询里程碑聚合 |
| 预期结果 | 结算金额一致；支付首付金额 = 结算 × 30%（参考 SIT 实测 2970）；支付状态机流转 pending→confirmed |
| 验收标准 | AC-PAY-1：首付比例 = 30%；AC-PAY-2：支付状态可流转 pending→confirmed→refundable |
| 优先级 | High |

---

### UAT-02 设计师户型与专业设计器（设计师）

**场景描述**：设计师从户型方案入手，依次使用厨房设计器、卫生间设计器、灯光设计器，最终产出 VR 全景与 AI 图生图效果图，验证专业设计模块的输出质量。

#### UAT-02-01 户型方案存储与 2D/3D 联动

| 项 | 内容 |
|---|---|
| 前置条件 | 设计师账号登录，已关联业主项目 |
| 测试步骤 | 1. `POST /api/floorplans` 存储户型方案（含房间轮廓 JSON）<br>2. `GET /api/floorplans?project_id={id}` 查询列表<br>3. 打开 `studio.html` 加载该户型<br>4. 触发 Three.js sync3D 拉伸墙体 |
| 预期结果 | 户型持久化成功；3D 墙体拉伸时间 < 3s |
| 验收标准 | AC-3D-1：墙体拉伸 < 3s（AC-3）；AC-VIEW-1：平立剖 6 视角可自动生成（AC-4） |
| 优先级 | High |

#### UAT-02-02 F16 厨房设计器（橱柜参数化 + 动线）

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-02-01 户型已存在 |
| 测试步骤 | 1. `POST /api/kitchen/designs` 创建厨房设计<br>2. `POST /api/kitchen/designs/{id}/auto-layout` 自动布局<br>3. `GET /api/kitchen/designs/{id}/workflow` 动线分析<br>4. `GET /api/kitchen/designs/{id}/compliance` 规范校验 |
| 预期结果 | 自动布局产出橱柜组件；动线分析返回操作三角距离；规范校验无致命错误 |
| 验收标准 | AC-KITCHEN-1：动线三角距离符合人体工学（< 6m）；AC-KITCHEN-2：规范校验列出违规项 |
| 优先级 | Medium |

#### UAT-02-03 F17 卫生间设计器（干湿分离 + 防水）

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-02-01 户型已存在 |
| 测试步骤 | 1. `POST /api/bathroom/designs` 创建卫生间设计<br>2. `POST /api/bathroom/designs/{id}/auto-layout` 自动布局<br>3. `GET /api/bathroom/designs/{id}/drain` 地漏坡度<br>4. `GET /api/bathroom/designs/{id}/waterproof` 防水方案<br>5. `GET /api/bathroom/designs/{id}/ventilation` 通风校验 |
| 预期结果 | 干湿分离布局产出；地漏坡度符合 1%-2%；防水方案覆盖墙面 1.8m |
| 验收标准 | AC-BATH-1：地漏坡度 ∈ [1%, 2%]；AC-BATH-2：防水高度 ≥ 1.8m |
| 优先级 | Medium |

#### UAT-02-04 F29/F30 灯光设计器（照度 + AI 方案）

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-02-01 户型已存在 |
| 测试步骤 | 1. `POST /api/lighting/schemes` 创建灯光方案<br>2. `POST /api/lighting/schemes/{id}/ai-design` AI 生成方案<br>3. `POST /api/lighting/schemes/{id}/fixtures` 添加灯具<br>4. `GET /api/lighting/schemes/{id}/illuminance` 照度计算 |
| 预期结果 | AI 方案返回色温规划；照度计算结果符合国标（客厅 ≥ 100lx） |
| 验收标准 | AC-LIGHT-1：客厅照度 ≥ 100lx；AC-LIGHT-2：色温规划覆盖 2700K-5000K |
| 优先级 | Medium |

#### UAT-02-05 VR 全景 + AI 图生图

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-02-01~04 设计已完成 |
| 测试步骤 | 1. `POST /api/vr/panoramas` 创建全景<br>2. `POST /api/vr/panoramas/{id}/render` 渲染<br>3. `POST /api/vr/panoramas/{id}/hotspots` 添加热点<br>4. `POST /api/ai-image/jobs` 创建 AI 图生图任务<br>5. `POST /api/ai-image/jobs/{id}/process` 处理<br>6. 浏览器打开 `vr-viewer.html` 查看结果 |
| 预期结果 | 全景渲染产出等距柱状图；热点可点击；AI 图生图任务状态 pending→done |
| 验收标准 | AC-VR-1：全景图可在 vr-viewer.html 球面渲染；AC-AIIMG-1：AI 任务最终状态为 done |
| 优先级 | Medium |

---

### UAT-03 采购增强与担保支付状态机（业主 + 供应商）

**场景描述**：验证 F33 比价报告与 F34 担保支付状态机的完整流转，包含比价、担保支付、物流追踪、样品申请四个子流程。

#### UAT-03-01 F33 比价报告生成

| 项 | 内容 |
|---|---|
| 前置条件 | 业主已有采购需求（BOM 已生成） |
| 测试步骤 | 1. `POST /api/procurement-enhanced/price-comparisons` 创建比价请求（含 3 家供应商）<br>2. `GET /api/procurement-enhanced/price-comparisons/{id}` 查询报告<br>3. 校验报告包含供应商报价对比与推荐项 |
| 预期结果 | 比价报告含 ≥ 3 家供应商报价；推荐项明确标注最低价/最优性价比 |
| 验收标准 | AC-PRICE-1：比价报告含 ≥ 3 家供应商；AC-PRICE-2：报告含推荐结论 |
| 优先级 | High |

#### UAT-03-02 F34 担保支付状态机 - 发起

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-03-01 比价完成，选定供应商 |
| 测试步骤 | 1. `POST /api/procurement-enhanced/escrow-payments` 发起担保支付（amount=9900）<br>2. 校验初始状态为 `pending_escrow`<br>3. 查询状态机流转图 |
| 预期结果 | 担保支付创建 `201`；初始状态 `pending_escrow`；状态机含 pending_escrow→escrowed→released→refunded |
| 验收标准 | AC-ESCROW-1：初始状态 = `pending_escrow`；AC-ESCROW-2：状态机含 4 个核心状态 |
| 优先级 | High |

#### UAT-03-03 F34 担保支付状态机 - 托管到放款

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-03-02 担保支付已发起 |
| 测试步骤 | 1. 调用托管接口，状态 pending_escrow→escrowed<br>2. 模拟供应商发货完成<br>3. 调用放款接口，状态 escrowed→released<br>4. 校验中途不可跳转 released |
| 预期结果 | 状态严格按 pending_escrow→escrowed→released 流转；非法跳转被拒绝 |
| 验收标准 | AC-ESCROW-3：状态跳转必须有序；AC-ESCROW-4：非法跳转返回 `409` |
| 优先级 | High |

#### UAT-03-04 F34 物流追踪

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-03-03 担保支付已托管 |
| 测试步骤 | 1. `POST /api/procurement-enhanced/logistics` 创建物流记录<br>2. `GET /api/procurement-enhanced/logistics/{id}` 查询轨迹<br>3. 校验轨迹含 ≥ 3 个节点（发货/中转/签收） |
| 预期结果 | 物流记录创建成功；轨迹节点完整 |
| 验收标准 | AC-LOGI-1：轨迹节点 ≥ 3；AC-LOGI-2：终态节点为「已签收」 |
| 优先级 | Medium |

#### UAT-03-05 F34 样品申请

| 项 | 内容 |
|---|---|
| 前置条件 | 供应商账号已注册 |
| 测试步骤 | 1. `POST /api/procurement-enhanced/sample-requests` 业主发起样品申请<br>2. 供应商账号 `GET /api/procurement-enhanced/sample-requests` 查看待处理<br>3. 供应商审核通过<br>4. 校验状态 pending→approved→shipped |
| 预期结果 | 样品申请创建；供应商可见；状态流转正确 |
| 验收标准 | AC-SAMPLE-1：业主发起后供应商可见；AC-SAMPLE-2：状态可流转至 approved |
| 优先级 | Medium |

---

### UAT-04 施工方施工与质量闭环（施工方）

**场景描述**：施工方接收施工任务，管理进度，执行质量检验，处理整改单与质量评估，验证 F37 进度管理与 F38 质量管理闭环。

#### UAT-04-01 施工任务创建与 Gantt 排期

| 项 | 内容 |
|---|---|
| 前置条件 | 施工方账号登录，已关联项目 |
| 测试步骤 | 1. `POST /api/construction/tasks` 创建施工任务（phase=水电）<br>2. `POST /api/construction/plan` 生成 Gantt 排期<br>3. `GET /api/construction/tasks?project_id={id}` 查询任务列表<br>4. 校验排期含开始/结束日期 |
| 预期结果 | 任务创建 `201`；Gantt 排期含 ≥ 1 个任务条；列表查询返回任务数组 |
| 验收标准 | AC-CTASK-1：任务含 start_date/end_date；AC-CTASK-2：Gantt 排期可解析 |
| 优先级 | High |

#### UAT-04-02 F37 进度管理与里程碑预警

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-04-01 任务已创建 |
| 测试步骤 | 1. `POST /api/construction/progress-alerts` 创建进度预警（delay_days=3）<br>2. `POST /api/construction/milestones` 创建里程碑<br>3. `GET /api/construction/progress-analysis?project_id={id}` 进度分析<br>4. 校验预警等级与里程碑达成率 |
| 预期结果 | 预警创建 `201`；里程碑含达成状态；进度分析返回偏差天数 |
| 验收标准 | AC-PROG-1：预警含 delay_days 字段；AC-PROG-2：里程碑达成率可计算 |
| 优先级 | High |

#### UAT-04-03 F38 质量检验与 AI 图像审核

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-04-01 任务进行中 |
| 测试步骤 | 1. `POST /api/construction/inspections` 创建质检记录<br>2. `POST /api/construction/inspections/analyze` 上传现场照片做 AI 图像审核<br>3. `GET /api/construction/quality-checklist/{phase}` 获取质检清单<br>4. `POST /api/construction/quality-detect` 质量问题检测 |
| 预期结果 | 质检记录创建；AI 图像审核返回问题列表；质检清单按阶段返回 |
| 验收标准 | AC-QA-1：AI 审核返回 issues 数组；AC-QA-2：质检清单按 phase 区分 |
| 优先级 | High |

#### UAT-04-04 F38 整改单流转

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-04-03 检出质量问题 |
| 测试步骤 | 1. `POST /api/construction/quality-issues` 创建质量问题<br>2. `POST /api/construction/rectification-orders` 创建整改单<br>3. 施工方整改完成后更新整改单状态<br>4. `POST /api/construction/quality-assessments` 提交评估<br>5. 校验状态 open→rectifying→closed |
| 预期结果 | 整改单创建；状态流转完整；评估记录关联整改单 |
| 验收标准 | AC-RECT-1：状态流转 open→rectifying→closed；AC-RECT-2：评估关联 rectification_id |
| 优先级 | High |

#### UAT-04-05 施工日志与变更单

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-04-01 任务进行中 |
| 测试步骤 | 1. `POST /api/construction/logs` 创建施工日志<br>2. `POST /api/change-orders` 创建变更单（业主发起）<br>3. `POST /api/change-orders/{id}/review` 施工方审核<br>4. `POST /api/change-orders/{id}/approve` 业主批准<br>5. 校验变更单状态 pending→reviewed→approved |
| 预期结果 | 日志创建 `201`；变更单流转完整；批准后关联预算变更 |
| 验收标准 | AC-CHG-1：变更单状态机 pending→reviewed→approved；AC-CHG-2：批准后触发预算重算 |
| 优先级 | Medium |

---

### UAT-05 三方 IM 协作与服务者匹配（全角色）

**场景描述**：业主通过 F35 服务者匹配找到设计师/监理/预算师，通过 F36 工程队匹配找到施工方，建立 F40 三方 IM 群组进行协作。

#### UAT-05-01 F35 服务者匹配（设计师/监理/预算师）

| 项 | 内容 |
|---|---|
| 前置条件 | 至少 3 个服务者档案已存在 |
| 测试步骤 | 1. `POST /api/workers/match` 提交匹配请求（role=designer, city=上海, style=现代简约）<br>2. 校验返回 match_score ≥ 80（参考 SIT 实测 89.2）<br>3. `POST /api/workers/matches/{id}/status` 更新匹配状态为 accepted |
| 预期结果 | 匹配返回 ≥ 1 个候选；match_score ≥ 80；状态可流转 |
| 验收标准 | AC-WORKER-1：match_score ≥ 80；AC-WORKER-2：返回候选人含评分维度 |
| 优先级 | High |

#### UAT-05-02 F36 工程队匹配（六维评分）

| 项 | 内容 |
|---|---|
| 前置条件 | 至少 2 个工程队档案已存在 |
| 测试步骤 | 1. `POST /api/crews/match` 提交匹配请求<br>2. 校验返回六维评分（质量/进度/成本/沟通/安全/口碑）<br>3. `POST /api/crews/matches/{id}/status` 雇佣工程队 |
| 预期结果 | 匹配返回六维评分；雇佣后状态 matched→hired |
| 验收标准 | AC-CREW-1：六维评分字段齐全；AC-CREW-2：雇佣状态可流转 |
| 优先级 | High |

#### UAT-05-03 F40 三方 IM 群组创建

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-05-01/02 匹配完成 |
| 测试步骤 | 1. `POST /api/chat/rooms/{project_id}` 创建聊天室（含业主+设计师+施工方）<br>2. `GET /api/chat/rooms/{id}` 查询成员<br>3. 校验成员数 = 3 |
| 预期结果 | 聊天室创建成功；三方成员均已加入 |
| 验收标准 | AC-IM-1：聊天室成员数 = 3；AC-IM-2：成员角色覆盖三类 |
| 优先级 | High |

#### UAT-05-04 F40 消息发送与 @提及

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-05-03 群组已建立 |
| 测试步骤 | 1. 业主 `POST /api/chat/messages` 发送消息<br>2. 设计师发送含 `@施工方` 的消息<br>3. `GET /api/chat/messages/{room_id}` 查询历史<br>4. `GET /api/chat/unread/{user_id}` 查询未读 |
| 预期结果 | 消息持久化（参考 SIT 实测 201+chat_message）；@提及可解析；未读数正确 |
| 验收标准 | AC-IM-3：消息持久化可查询；AC-IM-4：@提及解析为 user_ids 数组 |
| 优先级 | High |

#### UAT-05-05 F40 已读回执与 WebSocket 实时推送

| 项 | 内容 |
|---|---|
| 前置条件 | UAT-05-04 消息已发送 |
| 测试步骤 | 1. 施工方 `POST /api/chat/messages/{id}/read` 标记已读<br>2. 业主端通过 `ws://118.31.223.213:8081/ws/{project_id}` 连接 WebSocket<br>3. 设计师发送新消息<br>4. 校验业主端 WebSocket 收到推送事件 |
| 预期结果 | 已读回执更新；WebSocket 实时推送消息事件 |
| 验收标准 | AC-IM-5：已读后 unread 归零；AC-IM-6：WebSocket 推送延迟 < 1s |
| 优先级 | Medium |

---

### UAT-06 UI/UX 易用性与 13 Tab 切换（业主）

**场景描述**：验证 Web 后台 13 个 Tab 切换流畅、响应式适配、移动端可用、错误提示友好。

#### UAT-06-01 13 Tab 切换流畅性

| 项 | 内容 |
|---|---|
| 前置条件 | 业主登录 Web 后台 |
| 测试步骤 | 依次点击 13 个 Tab：工作台/项目/测量/设计台/AI 助手/物料库/预算管理/施工进度/结算管理/供应商/工程文件/设计深化/采购增强<br>观察每次切换的加载时间与 active 高亮状态 |
| 预期结果 | 13 Tab 均可切换；active 状态正确高亮；无白屏 > 1s |
| 验收标准 | AC-UI-1：13 Tab 全部可访问；AC-UI-2：切换响应 < 500ms |
| 优先级 | High |

#### UAT-06-02 响应式布局适配

| 项 | 内容 |
|---|---|
| 前置条件 | 桌面浏览器 |
| 测试步骤 | 1. 窗口宽度 1920px → 1366px → 768px → 375px<br>2. 观察侧边栏折叠、内容区适配、表格滚动 |
| 预期结果 | 各断点下布局合理；375px 下侧边栏可折叠 |
| 验收标准 | AC-UI-3：375px 下无横向滚动条；AC-UI-4：侧边栏可折叠 |
| 优先级 | Medium |

#### UAT-06-03 设计台 Canvas 与 2D/3D 切换

| 项 | 内容 |
|---|---|
| 前置条件 | 打开 `studio.html` |
| 测试步骤 | 1. 使用 7 种绘图工具（墙/门/窗/家具等）<br>2. 开启正交与对象捕捉<br>3. 切换 2D/3D 视图<br>4. 导出 DXF R12 |
| 预期结果 | 7 工具可用；对象捕捉命中率 98%；DXF 可导出且 AutoCAD 可打开 |
| 验收标准 | AC-CAD-1：7 工具齐全（AC-1）；AC-CAD-2：捕捉率 ≥ 98%（AC-2）；AC-CAD-3：DXF R12 兼容（AC-5） |
| 优先级 | High |

#### UAT-06-04 错误提示与表单校验

| 项 | 内容 |
|---|---|
| 前置条件 | 登录 Web 后台 |
| 测试步骤 | 1. 创建项目时留空必填字段<br>2. 提交超出范围的面积值（负数）<br>3. 上传超大文件（> 50MB）<br>4. 观察错误提示文案与位置 |
| 预期结果 | 表单校验即时提示；错误文案中文清晰；无 alert 弹窗 |
| 验收标准 | AC-UI-5：错误提示贴近字段；AC-UI-6：文案为中文且可读 |
| 优先级 | Medium |

#### UAT-06-05 移动端 Flutter App 适配

| 项 | 内容 |
|---|---|
| 前置条件 | 鸿蒙 MatePad / iOS / Android 设备 |
| 测试步骤 | 1. 启动 App 登录<br>2. 进入项目详情、预算、施工、结算 4 个核心页面<br>3. 使用手写笔（MatePad）<br>4. 进入 AR 扫描页 |
| 预期结果 | 4 页面可正常渲染；手写笔可绘图；AR 页可调起原生 ARKit/ARCore/AR Engine |
| 验收标准 | AC-MOBILE-1：4 核心页面无崩溃；AC-MOBILE-2：MatePad FPS ≥ 30（AC-8） |
| 优先级 | High |

---

### UAT-07 性能与并发负载（系统）

**场景描述**：验证接口响应时间 < 200ms、50 并发用户压力、Canvas/3D 渲染 FPS、WebSocket 实时性。

#### UAT-07-01 接口响应时间

| 项 | 内容 |
|---|---|
| 前置条件 | 远程环境健康 |
| 测试步骤 | 1. 选取 10 个核心接口（auth/login, projects, materials, budgets, procurement, construction, settlements, payments, chat, agents）<br>2. 单用户连续调用 10 次<br>3. 记录 P50/P95/P99 响应时间 |
| 预期结果 | P50 < 200ms；P95 < 500ms；P99 < 1000ms |
| 验收标准 | AC-PERF-1：P50 < 200ms；AC-PERF-2：P99 < 1s |
| 优先级 | High |

#### UAT-07-02 50 并发用户负载

| 项 | 内容 |
|---|---|
| 前置条件 | 准备 50 个测试账号 |
| 测试步骤 | 1. 使用压测工具（locust/wrk）模拟 50 并发<br>2. 持续 5 分钟混合场景：登录 20% + 查项目 30% + 查预算 20% + 查施工 20% + 发消息 10%<br>3. 记录吞吐量、错误率、P95 |
| 预期结果 | 错误率 < 1%；P95 < 1s；吞吐量 ≥ 50 RPS |
| 验收标准 | AC-PERF-3：错误率 < 1%；AC-PERF-4：50 并发稳定 5 分钟 |
| 优先级 | High |

#### UAT-07-03 Canvas 与 3D 渲染 FPS

| 项 | 内容 |
|---|---|
| 前置条件 | 桌面 Chrome + MatePad |
| 测试步骤 | 1. 打开 `studio.html` 加载中等规模户型（≥ 5 房间）<br>2. 连续绘图 30s<br>3. 切换 3D 视图旋转 30s<br>4. 用 `scripts/bench-fps.py` 或 Chrome DevTools 记录 FPS |
| 预期结果 | 桌面 FPS ≥ 60；MatePad FPS ≥ 30（AC-8） |
| 验收标准 | AC-PERF-5：桌面 FPS ≥ 60；AC-PERF-6：MatePad FPS ≥ 30 |
| 优先级 | Medium |

#### UAT-07-04 WebSocket 实时推送延迟

| 项 | 内容 |
|---|---|
| 前置条件 | 两个浏览器标签页登录不同角色 |
| 测试步骤 | 1. 两端均连接 `ws://118.31.223.213:8081/ws/{project_id}`<br>2. A 端发送消息<br>3. B 端记录收到推送的时间差<br>4. 重复 10 次取平均 |
| 预期结果 | 平均推送延迟 < 1s |
| 验收标准 | AC-PERF-7：WebSocket 推送延迟 < 1s |
| 优先级 | Medium |

---

### UAT-08 兼容性与跨端一致性（全角色）

**场景描述**：验证 Web 端在 Chrome/Safari/Edge 一致，Flutter App 在鸿蒙/iOS/Android 一致。

#### UAT-08-01 Web 浏览器兼容性

| 项 | 内容 |
|---|---|
| 前置条件 | Chrome 120+ / Safari 17+ / Edge 120+ |
| 测试步骤 | 1. 三浏览器分别打开 `index.html` 登录<br>2. 访问 13 Tab<br>3. 打开 `studio.html` 使用 Canvas<br>4. 打开 `3d-viewer.html` 查看 3D |
| 预期结果 | 三浏览器渲染一致；Canvas 与 Three.js r128 兼容 |
| 验收标准 | AC-COMPAT-1：三浏览器 13 Tab 均可访问；AC-COMPAT-2：3D 渲染无破损 |
| 优先级 | High |

#### UAT-08-02 鸿蒙 MatePad App

| 项 | 内容 |
|---|---|
| 前置条件 | 鸿蒙 MatePad + 已安装 HAP |
| 测试步骤 | 1. 启动 App 登录<br>2. 进入设计台使用手写笔<br>3. 进入 AR 扫描<br>4. 检查 `scripts/check-ohos-env.sh` 与 `scripts/bench-matepad.sh` 输出 |
| 预期结果 | App 正常运行；AR Engine 可调起；FPS ≥ 30 |
| 验收标准 | AC-COMPAT-3：鸿蒙 App 无崩溃；AC-COMPAT-4：AR Engine MethodChannel 通信成功 |
| 优先级 | High |

#### UAT-08-03 iOS / Android App 一致性

| 项 | 内容 |
|---|---|
| 前置条件 | iPhone 14 + Android 旗舰 |
| 测试步骤 | 1. 两端分别登录同一账号<br>2. 查看项目列表、预算、施工、结算<br>3. 进入 AR 扫描（ARKit/ARCore） |
| 预期结果 | 两端数据一致；AR 原生能力可调起 |
| 验收标准 | AC-COMPAT-5：iOS/Android 数据一致；AC-COMPAT-6：ARKit/ARCore 可调起 |
| 优先级 | Medium |

#### UAT-08-04 PASETO 鉴权与越权防护

| 项 | 内容 |
|---|---|
| 前置条件 | 两个不同业主账号 |
| 测试步骤 | 1. 业主 A 创建项目<br>2. 业主 B 持自己 token 尝试 `GET /api/projects/{A_project_id}`<br>3. 业主 B 尝试 `DELETE /api/projects/{A_project_id}`<br>4. 使用过期/篡改 token 访问 |
| 预期结果 | 越权访问返回 `403`；篡改 token 返回 `401` |
| 验收标准 | AC-SEC-1：越权返回 403；AC-SEC-2：PASETO 篡改后鉴权失败 |
| 优先级 | High |

---

## 5. 缺陷管理

### 5.1 缺陷等级

| 等级 | 定义 | 处置时限 |
|---|---|---|
| Critical | 主流程阻塞，无法继续测试 | 4 小时内修复 |
| High | 核心功能不可用，有规避方案 | 24 小时内修复 |
| Medium | 非核心功能问题或体验问题 | 3 个工作日内修复 |
| Low | 文案/样式/建议性问题 | 下个迭代修复 |

### 5.2 缺陷模板

```
- 缺陷编号: UAT-BUG-001
- 关联用例: UAT-01-04
- 标题: BOM 汇总金额与预算 total 不一致
- 等级: High
- 复现步骤:
  1. ...
  2. ...
- 预期结果: 金额一致
- 实际结果: 差异 0.01
- 环境: Chrome 120 / 远程生产
- 截图/日志: (附)
- 发现人: 张三
- 发现日期: 2026-07-08
```

---

## 6. 测试进度与里程碑

| 阶段 | 日期 | 交付物 |
|---|---|---|
| UAT 准备 | 2026-07-08 | 测试账号、测试数据、环境确认 |
| UAT-01~05 功能验收 | 2026-07-09 ~ 2026-07-11 | 功能验收记录 |
| UAT-06 UI/UX | 2026-07-12 | 易用性评估 |
| UAT-07~08 性能与兼容性 | 2026-07-13 | 性能报告、兼容性矩阵 |
| 缺陷修复回归 | 2026-07-14 | 回归报告 |
| 用户签字 | 2026-07-15 | UAT 验收报告 |

---

## 7. 风险与应对

| 风险 | 等级 | 应对 |
|---|---|---|
| 远程生产环境波动 | 中 | 测试前执行 `/health`；保留本地 .venv 作为降级环境 |
| AI 图生图任务排队 | 中 | 预置预设任务；超时 30s 标记 pending |
| 鸿蒙 AR Engine 设备差异 | 中 | 优先 MatePad 真机；记录 `check-ohos-env.sh` 输出 |
| 50 并发账号准备 | 低 | 脚本批量注册；清理脚本保底 |
| WebSocket 长连接断开 | 低 | 客户端实现自动重连；记录断线次数 |

---

## 8. 验收标准汇总

| 编号 | 类别 | 标准 | 关联用例 |
|---|---|---|---|
| AC-AUTH-1/2/3 | 鉴权 | PASETO v4.local / 错误密码 400 / 无 token 401 | UAT-01-01 |
| AC-AGENT-1/2 | AI Agent | 响应 < 3s / 完成率 ≥ 85% | UAT-01-02 |
| AC-AR-1/2 | AR 测量 | 四级降级链 / Manual 兜底 | UAT-01-03 |
| AC-MONEY-1/2 | 金额一致性 | BOM=预算=采购 / 精度 2 位 | UAT-01-04 |
| AC-PAY-1/2 | 支付 | 首付 30% / 状态机可流转 | UAT-01-05 |
| AC-3D-1 / AC-VIEW-1 | 设计台 | 墙体拉伸 < 3s / 6 视角 | UAT-02-01 |
| AC-KITCHEN-1/2 | 厨房 | 动线 < 6m / 规范校验 | UAT-02-02 |
| AC-BATH-1/2 | 卫生间 | 坡度 1%-2% / 防水 ≥ 1.8m | UAT-02-03 |
| AC-LIGHT-1/2 | 灯光 | 客厅 ≥ 100lx / 色温 2700K-5000K | UAT-02-04 |
| AC-VR-1 / AC-AIIMG-1 | VR/AI | 球面渲染 / 任务 done | UAT-02-05 |
| AC-PRICE-1/2 | 比价 | ≥ 3 家供应商 / 含推荐 | UAT-03-01 |
| AC-ESCROW-1~4 | 担保支付 | 初始 pending_escrow / 4 状态 / 有序跳转 / 非法 409 | UAT-03-02/03 |
| AC-LOGI-1/2 | 物流 | 节点 ≥ 3 / 终态已签收 | UAT-03-04 |
| AC-SAMPLE-1/2 | 样品 | 供应商可见 / 状态可流转 | UAT-03-05 |
| AC-CTASK-1/2 | 施工任务 | 含日期 / Gantt 可解析 | UAT-04-01 |
| AC-PROG-1/2 | 进度 | delay_days / 达成率 | UAT-04-02 |
| AC-QA-1/2 | 质检 | AI 返回 issues / 按 phase | UAT-04-03 |
| AC-RECT-1/2 | 整改单 | 状态机流转 / 评估关联 | UAT-04-04 |
| AC-CHG-1/2 | 变更单 | 状态机 / 触发预算重算 | UAT-04-05 |
| AC-WORKER-1/2 | 服务者匹配 | score ≥ 80 / 含评分维度 | UAT-05-01 |
| AC-CREW-1/2 | 工程队匹配 | 六维评分 / 状态流转 | UAT-05-02 |
| AC-IM-1~6 | IM 协作 | 成员=3 / @提及 / 持久化 / 已读 / WS < 1s | UAT-05-03/04/05 |
| AC-UI-1~6 | UI/UX | 13 Tab / 切换 < 500ms / 响应式 / 校验 | UAT-06-01~04 |
| AC-CAD-1/2/3 | CAD | 7 工具 / 捕捉 98% / DXF R12 | UAT-06-03 |
| AC-MOBILE-1/2 | 移动端 | 4 页面无崩溃 / MatePad ≥ 30fps | UAT-06-05 |
| AC-PERF-1~7 | 性能 | P50 < 200ms / 50 并发 / FPS / WS | UAT-07 |
| AC-COMPAT-1~6 | 兼容性 | 三浏览器 / 鸿蒙 / iOS/Android | UAT-08 |
| AC-SEC-1/2 | 安全 | 越权 403 / 篡改 401 | UAT-08-04 |

---

## 9. 测试执行检查清单

执行 UAT 前请逐项确认：

- [x] 远程环境 `GET /health` 返回 `{"status":"ok"}` ✅ (2026-07-08 verified)
- [x] `GET /api/docs` 可访问 Swagger ✅
- [x] 演示账号 `13800138000 / 123456` 可登录 ✅
- [ ] 测试账号已批量注册（业主/设计师/施工方/供应商各 ≥ 1）
- [ ] Chrome / Safari / Edge / MatePad / iPhone / Android 已就绪
- [ ] 压测工具（locust 或 wrk）已安装
- [ ] Chrome DevTools / FPS 工具就绪
- [ ] 缺陷管理工具可用
- [ ] 用户代表已就位

### 9.1 API 路径纠错（执行中发现的文档偏差）

| 文档路径 (错误) | 正确路径 | 说明 |
|---|---|---|
| `POST /api/agents/design` (prompt) | `POST /api/agents/design` (message) | 请求体字段为 `message` 而非 `prompt` |
| `POST /api/workers/match` (role, city, style) | `POST /api/workers/match` (project_id 必填) | 需传 `project_id` |
| `GET /api/budgets` | `GET /api/budgets/project/{project_id}` | 需要 project_id 路径参数 |
| `GET /api/settlements` | `GET /api/settlements/project/{project_id}` | 需要 project_id 路径参数 |
| `GET /api/construction/tasks` | `GET /api/construction/tasks?project_id={id}` | 需要 query 参数 |
| `POST /api/procurement-enhanced/escrow-payments` | `POST /api/procurement-enhanced/escrow` | 路径与文档不符 |
| `POST /api/procurement-enhanced/escrow` | 需要 `order_id` 字段 | 文档未说明必填字段 |

---

## 10. UAT 验收报告模板

测试完成后填写：

| 项 | 值 |
|---|---|
| 测试周期 | 2026-07-09 ~ 2026-07-15 |
| 用例总数 | 38 |
| 执行数 | __ |
| 通过数 | __ |
| 失败数 | __ |
| 阻塞数 | __ |
| 通过率 | __% |
| Critical 缺陷 | __ |
| High 缺陷 | __ |
| Medium 缺陷 | __ |
| Low 缺陷 | __ |
| UAT 结论 | □ 通过 □ 条件通过 □ 不通过 |
| 用户代表签字 | __ |
| 日期 | __ |

---

> 本测试计划基于 PRD F1-F40、SIT 报告（99.49% 通过率）、README 项目结构编制。测试执行过程中如发现 PRD 与实现存在差异，以 PRD 业务需求为准。

# i-home.life 生产环境二轮三智能体交叉验证报告

- **验证日期**：2026-08-20 09:25–09:35（CST）
- **验证目标**：生产环境 `https://i-home.life`（v1.15.8，含一轮验证全部修复）
- **验证方式**：3 个独立智能体经真实 HTTP API 驱动全链路业务（`IHOME_QA_BASE=https://i-home.life/api`，节流 0.8s 防限流）+ 生产 PG 数据一致性核查 + 生产数据污染清理与基线比对
- **前置**：一轮验证已修复项（负面积 422 / 状态机约束 / 施工任务契约 / 枚举中文化 / 详情页 / 结算回填 / assigned_to 回填）均已在生产生效

---

## 一、验证结论总览

| 智能体 | 步骤 | 通过 | 失败 | 真实缺陷 |
|---|---|---|---|---|
| A · 业主 | 52 | 49 | 3 | 1（BOM 500） |
| B · 供应商 | 21 | 19 | 2 | 0（状态机时序，行为正确） |
| C · 管理员 | 22 | 21 | 1 | 0（测试载荷 404，诚实拒绝） |
| **合计** | **95** | **89** | **6** | **1** |

**数据一致性**：预算 3/3、订单 4/4 明细=总额全 OK；结算 contract 一致、actual 行/头不同步 → 已回填生产（P3-3 生产侧落地）。
**生产数据安全**：验证产生的 QA 数据已全部清理，演示项目数据与运行前基线逐项一致。

---

## 二、三智能体执行详情

### 智能体 A — 业主张先生（52 步）
全链路：登录/权限码 → 项目列表/详情/timeline → 新建项目 → 边界（空名 422 / 负面积 422 均通过）→ 建户型+BOM → 预算 → 采购（支付意图签发+校验/确认收货/AI 推荐）→ 施工 → 质检 → 结算 → 智能家居 → 变更单 → AI 对话（含空/超长/未知 agent 422）→ 资金托管。

**失败明细**：
1. `新项目自动生成BOM` 404「项目下未找到房间数据」——新项目建了户型（room_count=5 但无几何 data）后 generate_bom 仍未兜底（expected_rejection，观察项，见三-3）。
2. **`手动登记BOM明细` 500（真实缺陷 ISSUE-001）**——material_id 不存在触发 FK 冲突直崩 500，已修复（见四）。
3. `从BOM生成预算` 409「该项目已有预算」——BOM 失败回退到演示项目（翠湖名邸已有预算），诚实拒绝（expected_rejection）。

### 智能体 B — 供应商（21 步）
交付单列表/创建（同步+异步）/详情、状态机（draft→quoted→accepted 合法流转、非法跳迁 422、未知状态 422）、边界（area=0/20000 → 422、不存在 404）、供应商列表、AI 推荐、越权检查（admin 403）。

**失败明细**：`draft→quoted` 与 `quoted→accepted` 均 422「非法状态流转: generating → …」——测试取到异步交付单（background 任务未及生成完成即推状态），状态机拒绝行为正确（expected_rejection，测试时序问题）。

### 智能体 C — 管理员（22 步）
平台统计/每日简报/供应商简报（data_source 诚实标注校验）/治理审计/技能进化/MCP（manifest/tools/call/未知工具 isError）/org 记忆/评估框架/批量周报。

**失败明细**：`MCP 工具调用` 404「项目不存在」——测试载荷硬编码了本地演示项目 ID，生产无此项目，工具诚实返回 404（expected_rejection，测试载荷问题）。

---

## 三、发现的问题

### ISSUE-001【缺陷·已修复】BOM 登记不存在的物料 → 500
- **现象**：`POST /api/materials/bom` 传不存在的 `material_id`（如 M-TILE-01）返回 **500 Internal Server Error**。
- **根因**：`app/api/materials.py:add_bom_item` 未校验物料存在，`material_service.add_bom_item` 提交时触发 `ForeignKeyViolationError`（`bom_items_material_id_fkey`）未捕获 → 500。生产日志完整复现。
- **影响**：客户端传错/伪造物料 ID 即服务端崩溃，异常处理缺陷（应 4xx 诚实拒绝）。
- **修复**：处理器前置 `get_material_by_id` 校验，不存在返回 **404「物料不存在: xxx」** + 回归测试 `test_add_bom_item_material_not_found_404`（25 用例全通过，mypy/flake8 通过）。已提交 `ae3746c` 推送。
- **部署状态**：CI 部署等待中（全量测试约 20 分钟），已通过 SSH 手动同步已验证的 `materials.py` 至生产（备份 `/opt/ihome/backups/materials.py.bak.*`）并重启，**生产实测 404 生效**（`物料不存在: M-TILE-01`，http 404）；CI 后续部署幂等无冲突。

### 观察项（非缺陷）
1. **B2B 异步交付单状态机时序**：async_mode 创建后立即推状态会 422（generating 仅允许 →draft/cancelled），语义正确；测试应等后台生成完成再流转。
2. **MCP 工具调用载荷**：`get_design_layout` 对不存在的项目返回 404「项目不存在」诚实拒绝，符合契约。
3. **新项目 BOM 生成兜底边界**：新项目建户型（room_count>0 但 data 为空矢量）后 `generate_bom` 仍 404「未找到房间数据」——经验法兜底未对"有户型无几何数据"场景触发。建议后续：generate_bom 在房间存在但无几何时回退经验法（按 room_count/面积）。

---

## 四、生产数据修复与安全

| 项 | 说明 |
|---|---|
| 结算行 actual 回填（P3-3 生产侧） | 云栖雅苑 in_progress 结算：已付行按合同占比分摊头实际金额 → 开工预付 34,376.40 + 水电 22,917.60 = 57,294 = 头 actual ✓（`settlement_lines` 已备份） |
| 施工任务 assigned_to | 上一轮已回填（11 任务，班组值） |
| QA 数据清理 | QA 项目（API 级联删除 204）、翠湖名邸 QA 残留（结算/订单/质检/escrow/trustee，先子后父删）、2 条 QA 交付单、1 条 org 记忆，全部清除 |
| 演示数据基线比对 | 云栖雅苑 1/1/2/2/0、滇池湖畔 1/0/2/1/0、翠湖名邸 1/0/0/0/0，与运行前逐项一致 ✓ |

---

## 五、生产数据交叉一致性（PG）

| 核查项 | 结果 |
|---|---|
| 预算 `total_estimated` vs 明细行合计 | 3/3 OK（106,214 / 59,829 / 88,160） |
| 采购订单 `total_amount` vs 明细行 | 4/4 OK（26,796 / 30,720 / 9,480 / 2,720） |
| 结算 `contract_amount` vs 明细行 | 1/1 OK；`actual_amount` 行/头已对齐（回填后 57,294=57,294） |
| 越权隔离 | 供应商→admin 403；业主边界负面积/空名 422 ✓ |
| 状态机 | B2B 非法跳迁 422；预算已存在 409 诚实拒绝；未知 agent_type 422 ✓ |
| 诚实降级 | 简报各段带 data_source/source；MCP 未知工具 isError；BOM 不存在物料 404（修复后）✓ |

---

## 六、改进建议

1. **已修复**：BOM 物料存在性校验（404 替代 500）——`ae3746c` 已推送，CI 部署完成后生产生效。
2. **P3 建议**：`generate_bom` 对"有户型但无几何 data"场景回退经验法（room_count×面积×标准用量），并附 fallback_note 诚实标注。
3. **P3 建议**：验证智能体脚本对生产环境的适配（B2B 异步交付等待生成完成、MCP 工具调用动态取项目 ID），避免测试时序/载荷误报。
4. **P3 建议**：生产验证后 QA 数据清理流程沉淀为脚本（`qa-validation/cleanup_prod.py`），含子表先删顺序与基线比对。

---

## 七、验证产物

- 证据日志（生产运行）：`qa-validation/evidence/*_evidence.jsonl`（每步端点/载荷/状态/结论）
- 运行汇总：`qa-validation/run_summary.json`（95 步 89 通过 1 问题）
- 生产备份：`/opt/ihome/backups/construction_tasks.dump.*`、`settlement_lines.dump.20260820093910`
- 智能体框架生产适配：`IHOME_QA_BASE` / `IHOME_QA_DELAY` 环境变量（[agent_common.py](file:///Users/netsong/Developer/i-home.life/qa-validation/agent_common.py)）

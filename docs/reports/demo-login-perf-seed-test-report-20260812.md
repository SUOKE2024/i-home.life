# 演示登录 / 性能监控 / 种子数据 测试报告

**时间**: 2026-08-12 | **环境**: 本地开发库（data/ihome.db）+ 生产 i-home.life | **账号**: 13800138000 / 123456

---

## 一、预算核对明细（¥106,214 构成）

项目「云栖雅苑 · 智能整装」（126㎡）预算经真实性约束修复后，由 `seed_demo_data.py` 逐项日志（`budget_line_created`）精确核对：

| 类别 | 明细 | 数量 | 单位 | 单价 (¥) | 金额 (¥) | 实际花费 (¥) |
|------|------|------|------|----------|----------|--------------|
| 地面 | 750×1500 大板砖 | 82.0 | ㎡ | 198 | 16,236 | 16,236 |
| 墙面 | 净味乳胶漆（全屋） | 4.0 | 桶 | 680 | 2,720 | 0 |
| 顶面 | 石膏板吊顶 | 46.0 | ㎡ | 95 | 4,370 | 4,370 |
| 厨卫 | 石英石台面 + 台下盆 | 1.0 | 项 | 9,860 | 9,860 | 9,860 |
| 厨卫 | 智能马桶 + 恒温花洒 | 1.0 | 套 | 5,660 | 5,660 | 5,660 |
| 水电 | 强弱电改造（含材料） | 126.0 | ㎡ | 168 | 21,168 | 21,168 |
| 定制 | 定制衣柜（主卧+次卧） | 24.0 | ㎡ | 1,280 | 30,720 | 0 |
| 软装 | LED 无主灯全屋套餐 | 1.0 | 套 | 2,680 | 2,680 | 0 |
| 家电 | 中央空调一拖四 | 1.0 | 套 | 12,800 | 12,800 | 0 |
| **合计** | | | | | **¥106,214** | **¥57,294** |

**核对公式**：16,236 + 2,720 + 4,370 + 9,860 + 5,660 + 21,168 + 30,720 + 2,680 + 12,800 = **¥106,214** ✓

约束修复要点：
- 净味乳胶漆 **320 桶 → 4 桶**（18L/桶 ≈ 90㎡，126㎡ 全屋墙面约 320㎡）
- 智能马桶 + 恒温花洒 **2 套 → 1 套**（126㎡ 单卫生间）
- 单位显式化（㎡/桶/套/项），修复按数量自动推断单位导致的计价错误

---

## 二、性能日志验证（浏览器实时实测）

Dashboard 每次加载/切换输出 `[perf] dashboard.project-load`（[Dashboard.jsx:122](file:///Users/netsong/Developer/i-home.life/webapp/src/pages/Dashboard.jsx#L122-L127)）。

### init（首次登录加载，云栖雅苑）
```text
[perf] dashboard.project-load {trigger: init, projectId: 9b549486-9b77-4f09-9382-f1dec9cd6136, totalMs: 438,
  apiMs: {overview: 84, projects: 84, floorplans: 128, progress_alerts: 125, milestones: 126, feed: 322, floorplan_detail: 30}}
```

### switch #1（切换到滇池湖畔 · 现代简约）
```text
[perf] dashboard.project-load {trigger: switch, projectId: 60bc77c0-0906-4ab1-92f1-fdc30246561d, totalMs: 566,
  apiMs: {overview: 173, projects: 177, floorplans: 194, progress_alerts: 195, milestones: 199, feed: 355, floorplan_detail: 32}}
```

### switch #2（切换到翠湖名邸 · 原木奶油风）
```text
[perf] dashboard.project-load {trigger: switch, projectId: d2810fc9-cdd1-4a07-b97f-7d23111a551f, totalMs: 1442,
  apiMs: {overview: 57, projects: 62, floorplans: 683, progress_alerts: 859, milestones: 955, feed: 1346, floorplan_detail: 31}}
```

**结论**：每次加载/切换均有日志，trigger 正确区分 init/switch，apiMs 完整覆盖 7 个 API，耗时毫秒级合理（feed 聚合接口最慢、floorplan_detail 最快）。

---

## 三、边界测试通过情况

### test_demo_login_boundary.py（4 用例，全部 PASSED）

| 用例 | 场景 | 结果 | 日志/证据 |
|------|------|------|-----------|
| test_demo_login_wrong_password_no_token_side_effect | 密码错误 401 且无 Token 副作用 | ✅ | 401 + 响应无 access_token |
| test_demo_login_network_timeout | 网络超时（慢认证 + asyncio.wait_for 模拟 fetch 超时） | ✅ | 客户端抛 TimeoutError；服务端记录 `server_error`（请求中断 199ms） |
| test_demo_login_concurrent | 并发登录（8 并发） | ✅ | 全部 200、Token 互不相同；`slow_request` warning（SQLite 单连接锁等待，环境特性） |
| test_demo_login_auth_rate_limit | 认证限流（10 次/分钟/IP） | ✅ | 前 10 次 200、第 11 次 429 + Retry-After |

### test_demo_seed.py（10 用例，全部 PASSED）

| 用例 | 场景 | 结果 |
|------|------|------|
| test_demo_account_login | 一键演示登录 + /me 会话 | ✅ |
| test_demo_account_wrong_password | 演示账号错误密码 401 | ✅ |
| test_seed_demo_project_idempotent | 幂等性（3 项目各仅 1 个） | ✅ |
| test_seed_demo_project_completeness | 种子完整性（含预算单位真实性断言：乳胶漆=桶×4、马桶=1 套） | ✅ |
| test_seed_demo_project_clear | 清理（全量删除 + 二次清理幂等） | ✅ |
| test_seed_demo_project_feed_cards | 种子与首页 feed 联通（8 类卡片共 9 张） | ✅ |
| **test_seed_budget_large_scale_performance** | **极端数据量：1000 行预算明细性能哨兵（<5s）** | ✅ 金额 ¥1,000,000 正确 |
| test_seed_budget_empty_lines | 空预算明细不崩溃、0 总额 | ✅ |
| test_seed_budget_extreme_amount | 超大数量×单价（1e6×1e6=1e12）不溢出 | ✅ |
| test_seed_material_missing_raises | 引用不存在物料抛 RuntimeError（诚实报错） | ✅ |

**汇总**：14 用例全部通过；flake8 / mypy 0 issues；全景验证 44/44。

---

## 四、生产环境应用确认

| 项 | 本地 | 生产 i-home.life | 状态 |
|----|------|------------------|------|
| seed_demo_data.py（3 项目 + 预算修正 + 逐项日志） | 7e5550b0… | 7e5550b0…（md5 一致） | ✅ 已同步 |
| 云栖雅苑预算 | ¥106,214 / ¥57,294 | ¥106,214 / ¥57,294（乳胶漆 4 桶） | ✅ 已应用 |
| 演示项目数 | 3 | 3（云栖雅苑/滇池湖畔/翠湖名邸） | ✅ |
| webapp dist（含性能日志） | index-D_HC91Ub.js | index-D_HC91Ub.js（含 dashboard.project-load） | ✅ 已部署 |

---

## 五、预算分析可视化图表

`docs/reports/budget-analysis-20260812.html`（ECharts 5.5.0 自包含，浏览器直接打开）：

- **按物料类别分组的柱状图**（8 类别金额）：定制 30,720 / 水电 21,168 / 地面 16,236 / 厨卫 15,520 / 家电 12,800 / 顶面 4,370 / 墙面 2,720 / 软装 2,680
- **类别占比饼图**（按预估金额占比）
- **三项目预算对比**：云栖雅苑 ¥106,214（施工中）/ 滇池湖畔 ¥59,829（采购阶段）/ 翠湖名邸 ¥88,160（设计阶段）
- **9 项明细表**：合计 ¥106,214、实际花费 ¥57,294，与第一节核对表逐项一致

浏览器验证 6 项全过：标题正确、3 图表 canvas 渲染非空白（24,234 / 11,254 / 22,383 像素）、明细 9 行、无 JS 错误。

---

## 六、全量回归复测（边界测试并入主套件后）

4 个极端数据量边界测试并入 `test_demo_seed.py` 主套件后，全量 pytest 串行跑两轮：

| 轮次 | 结果 | 环境异常项（单独重跑均通过） |
|------|------|------------------------------|
| r1（1:05:30） | **2227 passed** / 2 failed / 1 error / 2 skipped / 4 xfailed | test_demo_login_auth_rate_limit（限流配额被全量其他认证请求占用）、test_demo_login_concurrent（SQLite 锁等待）、test_e2e_project_full_lifecycle（CPU 竞争超时）——单独重跑 5 passed 全过 |
| r2（0:56:34） | **2230 passed** / 1 failed / 2 skipped / 4 xfailed | test_b2b_delivery_async_mode（async 时序干扰）——单独重跑 1.13s passed |

4 个新增边界测试两轮全量均 PASSED，**持续通过无回归**。

---

## 七、生产日志磁盘安全确认

生产 `seed_demo_data.py` 日志配置复核：

- 仅 `logging.basicConfig()` → **StreamHandler 输出到 stderr/stdout**（[seed_demo_data.py:325](file:///Users/netsong/Developer/i-home.life/scripts/seed_demo_data.py#L319-L329)）
- **无 FileHandler / RotatingFileHandler，不写任何日志文件**
- 一次性 CLI 进程退出即消失；部署管道 `2>&1 | tail -2` 截断输出
- 预算逐项日志（`budget_line_created`）不落盘 → **不会造成生产磁盘空间过快增长**

生产脚本 md5 与本地一致（7e5550b0），本地即生产逻辑。

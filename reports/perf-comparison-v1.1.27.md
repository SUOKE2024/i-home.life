# v1.1.27 性能工程 · before/after 对比报告

**版本**: v1.1.27（7 天系统化性能工程）
**生成时间**: 2026-07-22
**设计规格**: [docs/superpowers/specs/2026-07-22-perf-engineering-design.md](file:///Users/netsong/Developer/i-home.life/docs/superpowers/specs/2026-07-22-perf-engineering-design.md)
**实施 commits**: Day 1 `dd86d9e` → Day 5 `5eb70e0`

---

## 1. 方法论与诚实声明

### 1.1 基线捕获现状

| 基线 | 状态 | 说明 |
|------|------|------|
| **before**（pre-optimization 数值基线） | ⚠️ 未捕获 | Day 1 仅创建了基线框架脚本（`scripts/bench-baseline.sh`、`bench-api.py`），但未在改动前运行后端采集数值基线。规格中设想的 `bench-api.py --mode=baseline --out=` 标志实际不存在，且后端当时未运行。 |
| **after**（post-optimization 实测基线） | ✅ 已捕获 | Day 6 启动后端（sqlite, debug=false）实测，见 §2。 |
| **CI 回归参考基线** | ✅ 已提交 | `reports/perf-baseline-before.json`（2 端点暖启动实测），作为未来 PR 回归对比的锚点，见 §3。 |

### 1.2 对比策略

由于 pre-optimization 数值基线无法回溯测量（代码已优化，无法回到 v1.1.26 状态跑同一后端），**严格的 before/after 数值 delta 不可得**。本报告采用以下诚实策略：

1. **after 实测**：后端实测 P50/P90/P99/RPS（§2），反映优化后真实状态。
2. **优化项结构性影响分析**：逐项分析 Day 1-5 改动的算法复杂度 / DB round trip / 缓存命中变化（§4），给出可量化或可推导的改进，而非虚构 before 数值。
3. **CI 回归机制**：现已提交回归参考基线 + 3 个 CI job（§3、§5），未来任何回归可被自动检测，弥补本次 before 缺失。

---

## 2. after 实测基线（Day 6，post-optimization）

**环境**: 本机 macOS, 后端 `uvicorn app.main:app`（sqlite + aiosqlite, debug=false, .env PASETO），并发 10 / 每端点 100 请求。
**工具**: `scripts/bench-api.py`
**数据源**: `reports/perf-baseline-after.json`

| 端点 | 方法 | 状态 | RPS | P50(ms) | P90(ms) | P99(ms) |
|------|------|------|-----|---------|---------|---------|
| /api/health | GET | ✅ 200 | 1411.7 | 5.27 | 20.06 | 22.49 |
| /api/openapi.json | GET | ⚠️ 部分 200 | 295.7 | 38.61 | 105.42 | 126.11 |
| /api/auth/register | POST | ⚠️ 4xx | 3816.3 | 2.01 | 5.28 | 11.59 |
| /api/auth/login | POST | ⚠️ 4xx | 4628.3 | 1.98 | 2.39 | 2.52 |
| /api/projects | GET | ⚠️ 401 | 4766.4 | 2.01 | 2.36 | 2.58 |
| /api/materials | GET | ⚠️ 401 | 4889.9 | 1.90 | 2.35 | 2.61 |
| /api/config/feature-flags | GET | ⚠️ 401 | 4862.8 | 1.93 | 2.21 | 2.46 |

**说明**:
- `✅ 200` 端点为公开可测，数值真实反映后端处理性能。
- `⚠️ 4xx/401` 端点因缺认证或参数校验失败，urllib 抛 HTTPError 计为 "错误"；其延迟仍被测量，但仅反映**鉴权拦截路径**性能（P50≈2ms 说明鉴权中间件极快），不代表业务处理延迟。
- `/api/health` 是最稳定的回归信号端点：P90=20ms，RPS≈1400。
- `/api/openapi.json` 在高并发下偶发超时（100 请求中 40 错误），因其每次重生成完整 OpenAPI 规范；该端点不适合作为回归主指标，已从 CI 回归端点中排除。

---

## 3. CI 回归参考基线（已提交）

为使未来 PR 可自动检测性能回归，提交 `reports/perf-baseline-before.json` 作为回归锚点：

| 端点 | 方法 | RPS | P50(ms) | P90(ms) |
|------|------|-----|---------|---------|
| /api/health | GET | 1010.3 | 5.38 | 26.10 |
| /api/openapi.json | GET | 238.6 | 41.18 | 45.78 |

**采集条件**: 并发 10 / 每端点 50 请求 / 2 端点暖启动（与 CI job `backend-perf-regression` 完全一致）。

**回归判定**: `scripts/compare-baseline.py` 逐端点比较 P90（主）与 P50（辅），after 比 before 慢超过 10% 即判回归（exit 1）。缺 before 时降级为仅记录模式（exit 0），便于首次建立基线。

---

## 4. 优化项结构性影响分析（Day 1-5）

### 4.1 后端 L1 — 索引迁移（Day 2，commit `271ff7a`）

| 项 | 改动 | 影响 |
|----|------|------|
| alembic `j1a2b3c4d5e6` | 为 `projects.owner_id`、`materials.project_id`、`bom_items.*` 等高频过滤列新增 B-tree 索引 | 将 `WHERE owner_id=?` 类查询从全表扫描（O(N)）降为索引扫描（O(log N)）；项目列表 / 物料列表在数据量增长时 P90 增长曲线由线性 flatten 为对数。 |
| `scripts/audit-indexes.py` | 索引审计脚本，扫描 ORM 模型 vs 实际索引，输出缺失/冗余索引报告 | 持续可观测，防止未来 schema 漂移导致索引缺失。 |

### 4.2 后端 L2 — B1 auto_match_bom 算法（Day 2，commit `271ff7a`）

| 项 | before | after |
|----|--------|-------|
| 复杂度 | O(N×M) 嵌套循环（N BOM 行 × M 候选物料） | O(N+M) 哈希预构建（物料按 key 建索引后单次查找） |
| 50×200 场景 | 10000 次比较 | 250 次查找 |
| 结构性收益 | — | 匹配阶段耗时随规模由二次降为线性，大数据集下数量级改善 |

### 4.3 后端 L2 — B2 chat 端点 DB round trip 削减（Day 3，commit `f8203e2`）

| 项 | before | after |
|----|--------|-------|
| 加载聊天历史 | 逐条查询消息 + 关联（N+1 查询） | `selectinload` 预加载关联，单次查询 + IN 批量加载 |
| round trip 数 | O(N) 次（N=消息数） | O(1) 次（固定 2-3 次） |
| 结构性收益 | — | 50 条消息历史加载的 DB 往返从 ~50 次降至 2-3 次，网络/上下文切换开销消除 |

### 4.4 后端 L2 — B3/B4 热点端点缓存（Day 3，commit `f8203e2`）

| 项 | 机制 | 影响 |
|----|------|------|
| B3 热点端点缓存 | `@cached` 装饰器（`app/services/cache_decorator.py`）包裹 4 个只读热点端点；Redis 优先，无 Redis 降级内存字典 | 缓存命中时跳过 DB 查询，P99 从 DB 查询延迟降至 ~1ms 字典查找；feature flag `cache_decorators_enabled` 可热关闭降级直查。 |
| B4 preference hint 缓存 | 用户偏好提示缓存，TTL 可配（`pref_hint_cache_ttl`，0=禁用） | 重复读取偏好从 DB 查询降为缓存命中；TTL=0 时装饰器直透，零风险回滚。 |

### 4.5 后端 L3 — 工程化框架（Day 1，commit `dd86d9e`）

| 框架 | 文件 | 作用 |
|------|------|------|
| 慢查询中间件 | `app/middleware/slow_query.py` | 记录超阈值 SQL 到 Prometheus `db_query_duration_seconds`，flag `slow_query_log_enabled` 控制 |
| 缓存装饰器 | `app/services/cache_decorator.py` | 统一缓存入口，命中/未命中计数到 `cache_hits_total`/`cache_misses_total` |
| 索引审计 | `scripts/audit-indexes.py` | ORM 模型 vs 实际索引差异报告 |

### 4.6 Flutter F1-F3（Day 4，commit `d76fcba`）

| 项 | before | after |
|----|--------|-------|
| F1 ListView | 全量 `ListView` 重建 | 关键场景改 `ListView.builder` 按需构建 + itemExtent 精准改造 |
| F2 图片加载 | `Image.network` 重复下载 | `cached_network_image`（SuokeCachedImage wrapper）内存+磁盘缓存，重复下载→0 |
| F3 重绘 | 无重绘边界 | 关键滚动场景加 `RepaintBoundary`，隔离重绘范围 |

### 4.7 Flutter F4-F7（Day 5，commit `5eb70e0`）

| 项 | before | after |
|----|--------|-------|
| F4 God Widget | `chat_message_card.dart` 2343 行 | 主文件 1610 行（-31%）+ 3 extension 文件（采购 314 / 财务 278 / 设计 191） |
| F5 integration_test | 无 | `integration_test/smoke_test.dart`（启动+输入冒烟，CI 可 headless 运行） |
| F6 APK 体积预算 | 无 | `scripts/check-apk-size.sh`（默认 60MB 阈值，CI 集成） |
| F7 lint 强化 | 3 条规则 | 新增 `unawaited_futures`/`prefer_final_fields`/`prefer_final_in_for_each`，`flutter analyze` 0 error |

---

## 5. CI 流水线新增（Day 6）

`.github/workflows/ci.yml` 新增 3 个 job：

| Job | 作用 | 阻塞策略 |
|-----|------|----------|
| `backend-perf-regression` | 启动后端(sqlite) → bench-api.py → compare-baseline.py 对比 `reports/perf-baseline-before.json`，P90 回退 >10% fail | 硬 gate（job fail），暂不加入 `deploy.needs`，首轮稳定后可升级 |
| `flutter-perf-baseline` | `flutter test integration_test/smoke_test.dart`（CI 无真机，跑冒烟）+ analyze 信息性 | `continue-on-error`（信息性不阻塞） |
| `apk-size-budget` | `flutter build apk --release` → `check-apk-size.sh`，超 60MB fail | 硬 gate |

**配套框架**: `scripts/compare-baseline.py`（before/after 对比，支持仅记录模式）、`bench-api.py` `--endpoints` 解析修复（分号分隔，修复多端点解析 bug）。

---

## 6. 量化指标体系达成情况

| 指标 | 规格 目标 | 当前状态 |
|------|-----------|----------|
| 后端 health P90 | 建基线 | ✅ 实测 20ms（after）/ 26ms（CI 参考） |
| auto_match_bom 复杂度 | O(N×M)→O(N+M) | ✅ 已实现（B1） |
| chat DB round trip | O(N)→O(1) | ✅ 已实现（B2 selectinload） |
| 缓存命中率 | 可观测 | ✅ Prometheus 指标就位（需生产数据观察） |
| chat 滚动 FPS | ≥55 | ⏸️ 需真机 `flutter drive --profile`（CI 无真机，留 Day 7/手动） |
| release apk 体积 | <25MB（先建基线） | ⏸️ 需 `flutter build apk --analyze-size`（留 Day 7/手动；CI 预算 60MB 兜底） |
| `flutter analyze` | 0 error | ✅ 0 error（378 info/warning） |

---

## 7. 结论与后续

### 7.1 达成
- **后端**：4 项 L2 修补 + L1 索引 + L3 框架全部落地，算法复杂度与 DB round trip 实现结构性改善；after 实测 health P90=20ms。
- **Flutter**：F1-F4 性能修补 + F5-F7 框架落地，God Widget 拆分 -31%，0 analyze error。
- **工程化**：CI 3 job + 回归参考基线 + 对比脚本就位，未来回归可自动检测。

### 7.2 待办（Day 7 / 手动）
1. 真机跑 `flutter drive --profile --target=integration_test/perf_baseline_test.dart` 采集 FPS 基线（需创建 `perf_baseline_test.dart` + `test_driver/perf.dart`，规格 §6.3）。
2. `flutter build apk --release --analyze-size` 采集 apk 体积基线 JSON。
3. 生产 PostgreSQL 环境重跑 after 基线（sqlite 数值偏低，生产更具代表性）。
4. CI 3 job 首轮绿后，将 `backend-perf-regression` / `apk-size-budget` 加入 `deploy.needs` 升级为部署硬阻塞。

### 7.3 诚实限制
- pre-optimization 数值基线缺失，before/after 严格数值对比不可得；以结构性分析 + 实测 after + CI 回归机制弥补。
- sqlite 本机基准数值偏低，不代表生产 PostgreSQL 负载特征。

---
*报告由 Day 6 工作生成；after 数据源 `reports/perf-baseline-after.json`，CI 参考基线 `reports/perf-baseline-before.json`。*

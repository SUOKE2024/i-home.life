# 项目全量全链路工程化系统适配及性能优化 — 设计规格

- **版本**: v1.1.27
- **日期**: 2026-07-22
- **范围**: 后端 DB/查询性能 + Flutter 性能
- **风险容忍度**: 可控激进（允许生产 PG `CONCURRENTLY` 加索引、改连接池参数，需回滚预案）
- **成功标准**: 量化指标 + 工程化能力补齐兼顾，分阶段交付

---

## 1. 背景与目标

i-home.life (索克家居) v1.1.26 是三端架构的全链路家居平台：FastAPI 后端（53 API 文件 / 45 模型 / 25 Agent / 237 Python 文件）+ Flutter 移动端（HarmonyOS/iOS/Android）+ Web 前端。

项目已具备成熟工程化基线（连接池、pytest-xdist 并行、Prometheus 指标、速率限制、审计日志、mypy 渐进式类型检查）。本次在现有形态上做系统化性能工程，**不引入新架构**（无 Docker/K8s/读写分离/Riverpod）。

### 目标

1. 修补后端 4 个真实性能问题（auto_match_bom 算法、chat 端点 DB round trip、热点端点缓存、preference hint 缓存）
2. 修补 Flutter 4 个真实性能问题（ListView 精准改造、图片缓存、RepaintBoundary、大页面拆分）
3. 补齐 6 个工程化能力框架（慢查询中间件、缓存装饰器、索引审计脚本、integration_test 性能基线、apk 体积预算、lint 强化）
4. 建立量化指标基线（P95/QPS/缓存命中率/FPS/apk 体积），所有改动可量化、可回滚

---

## 2. 当前基线（亲自核验）

### 2.1 已有良好实践（保留不动）

**后端**:
- `app/api/projects.py` timeline 端点用 `asyncio.gather` 并行查询 3 表
- `app/api/agents.py` `AGENT_TYPE_TO_INTENT` 显式路由，跳过 ~10s LLM 分类调用
- `app/api/materials.py` `add_bom_item` 用 `selectinload(BOMItem.material).selectinload(Material.category)` 预加载
- service 层 + `skip/limit` 分页（`furniture_catalog.py`、`materials.py` list 端点）
- `app/database.py` 连接池 `pool_size=20 + max_overflow=10 + pool_pre_ping + pool_recycle=1800`
- `app/main.py` PASETO payload 单请求缓存（`request.state.paseto_payload`）

**Flutter**:
- `const` 构造器使用率高（3111 处）
- `lib/pages/tasks_page.dart:692-731` `_buildListView` 正确模式：空状态用 `ListView(children:)`，实际列表用 `ListView.builder`
- `lib/widgets/loading_skeleton.dart` AnimationController 正确 dispose
- `lib/pages/smart_home_page.dart` 3 处全是 `ListView.builder`
- 依赖轻量（无 video_player/webview_flutter/firebase）

### 2.2 真实问题（本次修补）

**后端**:

| # | 位置 | 问题 |
|---|---|---|
| B1 | `app/api/materials.py:269-396` `auto_match_bom` | L308 `sa_select(Material)` 全表加载 + L314-361 三层 `for item in bom_items: for m in all_materials:` 双重循环，最坏 O(N×M×3) |
| B2 | `app/api/agents.py:284-347` `chat_with_agent` | 每次请求 4-5 次顺序 DB round trip：`get_or_create_session` → `get_session_history` → `persist_message(user)` → classify → `get_user_preference_hint` → `persist_message(assistant)` |
| B3 | 全局 | **0 端点使用缓存**——`app/services/cache_service.py` 是空抽象层，仅文档示例，无任何端点实际调用 `cache.get/set` |
| B4 | `app/api/agents.py:381` `BaseAgent.get_user_preference_hint` | 每次 chat 都查 `AgentFeedback` 表，未缓存 |

**Flutter**:

| # | 位置 | 问题 |
|---|---|---|
| F1 | `identity_page.dart`/`takeoff_page.dart`/`budget_page.dart`/`construction_page.dart`/`appliance_page.dart` | 约 10-15 处 `ListView(children:)` 用于动态列表（非空状态），需转 `.builder`。已核验 `smart_home_page.dart` 全用 builder，`tasks_page.dart:710` 是空状态合理用法 |
| F2 | `ai_image_page.dart:382/646/781`、`points_page.dart:743`、`vr_panorama_page.dart:1044`、`chat_message_card.dart:452/1566` | 7 处 `Image.network` 无缓存，pubspec 无 `cached_network_image` 依赖 |
| F3 | 全局 | **0 处 `RepaintBoundary`**（grep 无匹配） |
| F4 | 8 个页面 >1000 行 | `ai_chat_page.dart`(1518)、`smart_home_page.dart`(1419)、`points_page.dart`(1132)、`mep_page.dart`(1093)、`vr_panorama_page.dart`(1081)、`hard_decoration_page.dart`(1077)、`procurement_enhanced_page.dart`(1030)、`ar_scan_page.dart`(1012) |

---

## 3. 方案选择

三套方案对比后选 **方案 2：系统化性能工程**：

| 维度 | 方案 1 保守修补 | 方案 2 系统化（选） | 方案 3 激进重构 |
|---|---|---|---|
| 后端 | 仅修 4 问题点 | 修补 + 慢查询中间件 + 索引审计 + 缓存装饰器 + 性能基线 | 方案 2 + 读写分离 + CQRS |
| Flutter | ListView + cached_network_image | 方案 1 + RepaintBoundary + 大页面拆分 + integration_test + apk 预算 | 方案 2 + Riverpod 重构 |
| 工期 | 2-3 天 | 5-7 天 | 2 周+ |
| 风险 | 低 | 中（含回滚预案） | 高（破坏现有页面） |

**选方案 2 的理由**:
- 用户选"两者兼顾"——方案 2 同时补齐工程化能力与量化指标
- 用户选"可控激进"——方案 2 允许生产 PG `CONCURRENTLY` 加索引，每步有回滚预案
- 方案 3 读写分离在单 PG 实例 + 无 Docker/K8s 部署下意义有限；Riverpod 重构破坏现有 8 个 >1000 行页面

---

## 4. 整体架构与设计原则

### 4.1 改动分层

```
┌─────────────────────────────────────────────────────────┐
│  L4 性能基线与可观测（新增）                              │
│  · bench-api.py 扩展为 P95/QPS/缓存命中率基线套件        │
│  · Flutter integration_test + DevTools trace 自动化      │
│  · apk 体积预算 + build time 基线                        │
├─────────────────────────────────────────────────────────┤
│  L3 工程化能力框架（新增）                                │
│  · 慢查询日志中间件（SQL > N ms 记录 + EXPLAIN 自动触发）│
│  · 缓存装饰器 @cached(ttl, key) 复用 cache_service       │
│  · 索引审计脚本 scripts/audit-indexes.py                 │
│  · Flutter integration_test 性能基线                     │
│  · apk 体积预算脚本                                      │
│  · lint 规则强化                                         │
├─────────────────────────────────────────────────────────┤
│  L2 真实问题修补（针对性）                                │
│  · 后端：auto_match_bom 算法 / chat 并行 / 热点缓存      │
│  · Flutter：ListView.builder / RepaintBoundary / 图片缓存│
├─────────────────────────────────────────────────────────┤
│  L1 数据库索引（生产 PG CONCURRENTLY，含回滚）            │
│  · 审计后的复合索引 + 单列索引                            │
└─────────────────────────────────────────────────────────┘
```

### 4.2 设计原则（硬约束）

1. **复用不重复**: 缓存复用 `app/services/cache_service.py` 单例；越权校验复用 `app/rbac.py:verify_project_access`；ORM 预加载复用 `selectinload` 模式。禁止新建辅助函数
2. **feature flag 开关**: 慢查询中间件、缓存装饰器、preference hint 缓存均通过 `Settings` feature flag 控制，可线上灰度
3. **版本号同步**: `app/config.py:app_version` → `1.1.27`；`flutter_app/pubspec.yaml:version` → `1.1.27+16`；后端改动不涉及 Web JS/CSS，无需升级 `v=` 与 `sw.js:CACHE_VERSION`
4. **不破坏现有契约**: API 响应 schema 不变；Flutter 页面路由不变；PASETO 不变；不引入 Docker
5. **回滚预案先行**: 每项生产改动配套 `DOWN` 迁移或参数还原脚本

---

## 5. 后端组件设计

### 5.1 L2 真实问题修补

#### 修补 B1: `auto_match_bom` 算法从 O(N×M) 降至 O(N+M)

位置: `app/api/materials.py:269-396`

当前: L308 `sa_select(Material)` 全表加载 + L314-361 三层双重循环。

优化（不改 API 响应 schema）:

```python
# 一次性建立三类索引（O(M)）
materials_by_sku = {m.sku.strip(): m for m in all_materials if m.sku}
materials_by_name = [m for m in all_materials if m.name]  # 列表保留模糊匹配
materials_by_cat_unit = {}
for m in all_materials:
    key = ((m.category.name if m.category else ""), (m.unit or ""))
    materials_by_cat_unit.setdefault(key, []).append(m)

# 每个 BOM 项 O(1) / O(k) 查找
for item in bom_items:
    if mat_sku and mat_sku in materials_by_sku:  # O(1)
        match, match_level, confidence = materials_by_sku[mat_sku], "exact", 1.0
    elif mat_name:  # O(M) 但可短路
        ...
    elif mat_category:  # O(k) k=同品类数量
        ...
```

复杂度从 O(N×M×3) 降至 O(N+M)。

#### 修补 B2: `agents/chat` 端点 DB round trip 削减

位置: `app/api/agents.py:284-347`

当前每次请求 4-5 次顺序 DB round trip。

优化:
- **合并 session + history 为一次调用**: 在 `app/services/agent_session_service.py` 新增 `get_session_with_history(db, user_id, session_id, project_id, first_message)`，单次查询返回 `(session, history)`，省 1 次 round trip
- **persist_message(user) 与 project 校验并行**: 当 `project_id` 存在时，`verify_project_access` 与 `persist_message(user)` 用 `asyncio.gather` 并行
- **preference hint 缓存**（见 B4），省 1 次 round trip

净效果: 4-5 次 → 2-3 次 DB round trip。

#### 修补 B3: 热点端点接入缓存（首次实际使用 `cache_service`）

候选热点端点（按"读多写少 + 公共数据"筛选）:

| 端点 | 缓存 key | TTL | 失效时机 |
|---|---|---|---|
| `GET /materials/categories` | `mat:categories` | 300s | POST /materials/categories 时 `cache.delete` |
| `GET /furniture-catalog` | `furn:list:{user_id}:{filters_hash}` | 60s | POST/PATCH/DELETE 时 `cache.delete_pattern("furn:list:*")` |
| `GET /materials?keyword=...` | `mat:search:{keyword_hash}` | 60s | 写入物料时 `cache.delete_pattern("mat:search:*")` |
| `GET /agents/sessions/{id}` | `sess:{id}:{updated_at}` | 120s | persist_message 时自然失效（updated_at 变） |

实现方式: 通过 B5 的 `@cached` 装饰器，不侵入业务逻辑。

#### 修补 B4: L4 preference hint 缓存

位置: `app/api/agents.py:381` `BaseAgent.get_user_preference_hint`

当前每次 chat 都查 `AgentFeedback` 表。优化: 缓存 key `pref_hint:{user_id}:{agent_name}`，TTL 300s（`Settings.pref_hint_cache_ttl`）。在 `POST /api/agents/feedback` 端点写入反馈后 `cache.delete(f"pref_hint:{user_id}:{agent_name}")` 主动失效。

### 5.2 L3 工程化能力框架

#### 框架 B5: 慢查询日志中间件 — 新建 `app/middleware/slow_query.py`

基于 SQLAlchemy 事件（非 HTTP 中间件，更精准）:

```python
@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _before(conn, cursor, statement, parameters, context, executemany):
    context._query_start = time.perf_counter()

@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _after(conn, cursor, statement, parameters, context, executemany):
    duration_ms = (time.perf_counter() - context._query_start) * 1000
    if duration_ms > settings.slow_query_threshold_ms:
        logger.warning("slow_query", sql=statement[:500],
                       duration_ms=round(duration_ms, 2),
                       endpoint=_get_current_endpoint())
        db_query_duration_seconds.labels(...).observe(duration_ms / 1000)
```

- feature flag: `slow_query_log_enabled`（默认 True）
- 阈值可配: `slow_query_threshold_ms`（默认 200）
- EXPLAIN 可选: `slow_query_explain_enabled`（默认 False，仅调试开启）
- 输出: structlog + Prometheus `db_query_duration_seconds` 直方图

#### 框架 B6: 缓存装饰器 — 新建 `app/services/cache_decorator.py`

```python
def cached(ttl: int = 300, key_prefix: str = "",
           key_builder: Callable | None = None):
    """装饰 async 函数，自动缓存返回值。
    
    命中率统计通过 cache.incr('cache:hits') / cache.incr('cache:misses')。
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            if not settings.cache_decorators_enabled:
                return await fn(*args, **kwargs)
            key = key_builder(args, kwargs) if key_builder else _default_key(fn, args, kwargs)
            cached_val = await cache.get(key)
            if cached_val is not None:
                await cache.incr("cache:hits")
                return cached_val
            await cache.incr("cache:misses")
            result = await fn(*args, **kwargs)
            await cache.set(key, result, ttl=ttl)
            return result

        async def invalidate(*args, **kwargs):
            """主动失效：用相同 key_builder 计算并删除对应缓存键。"""
            key = key_builder(args, kwargs) if key_builder else _default_key(fn, args, kwargs)
            await cache.delete(key)
        wrapper.invalidate = invalidate
        return wrapper
    return decorator
```

- 复用 `cache_service` 单例，不新建缓存层
- `invalidate(*args, **kwargs)` 用与缓存写入时相同的 key_builder 计算键，确保删除正确
- 命中率通过 `cache.incr` 计数，Prometheus `cache_hits_total` / `cache_misses_total`
- feature flag: `cache_decorators_enabled`

#### 框架 B7: 索引审计脚本 — 新建 `scripts/audit-indexes.py`

只读脚本，连接生产 PG，输出三份报告:
1. **未使用索引**: `pg_stat_user_indexes.idx_scan = 0`（建议 DROP）
2. **缺失索引建议**: 外键字段无索引（查 `pg_constraint` + `pg_index`）+ 高频 filter 字段（需结合慢查询日志）
3. **重复索引**: 相同列集的多个索引

输出格式: Markdown 报告 + 建议的 alembic 迁移代码片段（`CREATE INDEX CONCURRENTLY`）。

### 5.3 L1 数据库索引

新建 alembic 迁移 `alembic/versions/j1a2b3c4d5e6_add_v1_1_27_perf_indexes.py`，预期索引（最终以审计脚本输出为准）:

- `bom_items.material_id`、`bom_items.project_id`（外键无索引）
- `agent_messages.session_id`、`agent_messages.user_id`
- `materials.sku`（auto_match_bom Level 1 查找）
- `furniture_catalog.category`、`furniture_catalog.brand`
- `construction_tasks.project_id_status`（复合索引，timeline 端点用）
- `audit_logs.user_id_created_at`（复合索引，admin 查询用）

全部 `CREATE INDEX CONCURRENTLY`（不锁表），回滚用 `DROP INDEX CONCURRENTLY`。

### 5.4 Settings 新增 feature flag

```python
# ── 性能优化（v1.1.27）──
slow_query_log_enabled: bool = True
slow_query_threshold_ms: int = 200
slow_query_explain_enabled: bool = False
cache_decorators_enabled: bool = True
pref_hint_cache_ttl: int = 300
hot_endpoint_cache_ttl: int = 300
```

### 5.5 后端量化指标

| 指标 | 基线方式 | 目标 |
|---|---|---|
| `auto_match_bom` P95 延迟 | bench-api.py（50 BOM × 200 物料） | < 200ms（当前估算 > 1s） |
| `agents/chat` DB 部分延迟 | bench-api.py（含 mock LLM） | DB 部分降 40%（LLM 部分不变） |
| `/materials/categories` P95 | bench-api.py | < 20ms（缓存命中） |
| 缓存命中率 | Prometheus `cache_hits / (hits+misses)` | > 70%（热点端点） |
| 慢查询数量 | Prometheus `db_query_duration_seconds` | P95 < 200ms |

---

## 6. Flutter 组件设计

### 6.1 L2 真实问题修补

#### 修补 F1: `ListView(children:)` 精准改造

原则: **只改造动态列表场景，保留空状态/固定项的合理用法**。

改造前先审计: 扫描 `ListView(` 后是否跟随 `.map((e) => ...).toList()` 或动态 list 变量，识别真动态场景。

改造候选（排除空状态合理用法）:

| 文件 | 位置 | 改造方向 |
|---|---|---|
| `lib/pages/identity_page.dart` | 236/391/537 | 动态则转 `.builder` |
| `lib/pages/takeoff_page.dart` | 227/441 | 同上 |
| `lib/pages/budget_page.dart` | 152/250 | 同上 |
| `lib/pages/construction_page.dart` | 204/248 | 同上 |
| `lib/pages/appliance_page.dart` | 505 | 同上 |
| `lib/pages/kitchen_bath_mep_page.dart` | 281 | 同上 |
| `lib/pages/points_page.dart` | 341 | 核验后若是空状态则保留 |

保留不动: `tasks_page.dart:710`（空状态，2 个 children，合理）。

#### 修补 F2: 引入 `cached_network_image` 替换 7 处 `Image.network`

pubspec.yaml 新增 `cached_network_image: ^3.4.1`。

新建 `lib/widgets/cached_image.dart` 统一封装:

```dart
class SuokeCachedImage extends StatelessWidget {
  final String url;
  final double? width, height;
  final BoxFit fit;
  const SuokeCachedImage({super.key, required this.url, ...});

  @override
  Widget build(BuildContext context) {
    return CachedNetworkImage(
      imageUrl: url,
      width: width, height: height, fit: fit,
      placeholder: (_, __) => _shimmer(),
      errorWidget: (_, __, ___) => _placeholder(),
      memCacheWidth: 300,  // 限制内存缓存尺寸，防 OOM
    );
  }
}
```

改造 7 处 `Image.network` → `SuokeCachedImage`:
- `lib/pages/ai_image_page.dart:382/646/781`
- `lib/pages/points_page.dart:743`
- `lib/pages/vr_panorama_page.dart:1044`
- `lib/widgets/chat_message_card.dart:452/1566`

#### 修补 F3: `RepaintBoundary` 关键场景

原则: **只在长列表项 + 复杂卡片 + 动画区域加，不滥用**。

经核验需加的位置:
- `lib/widgets/chat_message_card.dart` 根 Widget 包 `RepaintBoundary`（每条消息独立绘制层）
- `lib/pages/tasks_page.dart` `_buildListTile` 根包 `RepaintBoundary`
- 产品/家具卡片网格的 `itemBuilder` 根包 `RepaintBoundary`
- `lib/widgets/loading_skeleton.dart` 已用 `AnimatedBuilder` 隔离，无需再加

#### 修补 F4: 大页面拆分（8 个 >1000 行文件）

拆分原则: 每个 widget 文件 < 500 行，单一职责，不破坏路由与 API。

| 源文件 | 行数 | 拆分方向 |
|---|---|---|
| `ai_chat_page.dart` | 1518 | `_SessionListSheet`、`_SuggestionPanel`、`_MessageInputBar`、`_VoiceModePanel` 独立文件 |
| `smart_home_page.dart` | 1419 | `_DeviceCard`、`_SceneCard`、`_AddDeviceSheet` 独立 |
| `points_page.dart` | 1132 | `_PointsHeader`、`_ExchangeGrid`、`_HistoryList` 独立 |
| `mep_page.dart` | 1093 | 按 MEP 子模块拆分 |
| `vr_panorama_page.dart` | 1081 | `_PanoramaViewer`、`_SceneList`、`_AudioGuide` 独立 |
| `hard_decoration_page.dart` | 1077 | 按硬装品类拆分 |
| `procurement_enhanced_page.dart` | 1030 | `_OrderCard`、`_FilterSheet`、`_SupplierList` 独立 |
| `ar_scan_page.dart` | 1012 | `_SensorPanel`、`_FallbackSheet`、`_ResultCard` 独立 |

拆分策略: 先抽离已存在的 private widget 类（如 `_SessionListSheet`）到独立文件，零行为变更，回归风险低。

### 6.2 L3 工程化能力框架

#### 框架 F5: `integration_test` 性能基线 — 新建 `flutter_app/integration_test/perf_baseline_test.dart`

```dart
testWidgets('chat_scroll_perf', (tester) async {
  await app.main();
  await tester.pumpAndSettle();
  final timeline = await tester.traceAction(
    () async {
      for (var i = 0; i < 30; i++) {
        await tester.fling(find.byType(ChatListView), const Offset(0, -500), 1000);
        await tester.pumpAndSettle();
      }
    },
  );
  expect(timeline.frames.where((f) => f.buildDuration > 16000).length, 0);  // <16ms
});
```

场景: chat 滚动、产品列表滚动、页面切换。用 `flutter drive --profile --driver=test_driver/perf.dart --target=integration_test/perf_baseline_test.dart` 跑，输出 timeline JSON。

#### 框架 F6: apk 体积预算 — 新建 `flutter_app/scripts/check-apk-size.sh`

```bash
#!/bin/bash
# flutter build apk --release --analyze-size 输出拆解
# 阈值：release apk < 25MB（先建基线，再定阈值）
THRESHOLD_MB=25
SIZE_MB=$(du -m build/app/outputs/flutter-apk/app-release.apk | cut -f1)
if [ "$SIZE_MB" -gt "$THRESHOLD_MB" ]; then
  echo "FAIL: apk size ${SIZE_MB}MB > ${THRESHOLD_MB}MB"
  exit 1
fi
```

CI 加 size budget check job。

#### 框架 F7: lint 规则强化 — 修改 `flutter_app/analysis_options.yaml`

新增规则（从 info/warning 升为 error）:
- `prefer_const_constructors` → error（已用 3111 处，剩余补齐）
- `prefer_const_literals_to_create_immutables` → error
- `avoid_unnecessary_containers` → warning
- `use_build_context_synchronously` → warning（防止 dispose 后用 context）

不引入 `dart_code_metrics`（重依赖，鸿蒙 Flutter-OH 兼容性未验证）。

### 6.3 L4 性能基线与可观测

DevTools trace 自动化 — 新建 `flutter_app/scripts/trace-perf.sh`:

用 `flutter run --profile --trace-systrace --driver=test_driver/perf.dart` 录制 30s 滚动场景，输出 timeline JSON，可导入 DevTools 分析。

### 6.4 Flutter 量化指标

| 指标 | 基线方式 | 目标 |
|---|---|---|
| chat 滚动 FPS | integration_test + DevTools trace | ≥ 55 FPS（先建基线） |
| 产品列表滚动 FPS | 同上 | ≥ 55 FPS |
| release apk 体积 | `flutter build apk --analyze-size` | < 25MB（先建基线） |
| 冷启动时间 | integration_test | < 2s（中端设备模拟） |
| 首屏 build time | DevTools trace | < 100ms |
| `Image.network` 重复下载数 | 抓包验证 | 0（缓存命中） |

### 6.5 配置变更

- `pubspec.yaml`: `version: 1.1.26+15` → `1.1.27+16`；新增 `cached_network_image: ^3.4.1`
- `analysis_options.yaml`: 强化 4 条 lint 规则
- `integration_test/`: 新建 perf_baseline_test.dart + test_driver/perf.dart
- `scripts/`: 新建 check-apk-size.sh + trace-perf.sh

### 6.6 风险与回归

- 大页面拆分: **零行为变更**（只抽离 private widget 到文件），回归风险低，但需 `flutter analyze` + 现有 widget test 全过
- `cached_network_image`: 鸿蒙 Flutter-OH 兼容性需验证（若不兼容则降级为 `Image.network` + 内存缓存 wrapper）
- lint 规则升级为 error: 可能暴露既有违规，需先 `flutter analyze` 清零再升级

---

## 7. 量化指标体系（整合）

### 7.1 基线采集（实施前必做）

实施任何改动前，先跑一次基线，固化 before 数值:

```
scripts/bench-baseline.sh
├── 后端: python scripts/bench-api.py --mode=baseline --out=reports/perf-baseline-v1.1.26.json
│   场景: auto_match_bom(50×200) / agents/chat(mock LLM) / materials/categories / furniture-catalog
├── Flutter: flutter drive --profile --target=integration_test/perf_baseline_test.dart
│   场景: chat 滚动 / 产品列表滚动 / 页面切换
└── 体积: flutter build apk --release --analyze-size --out=reports/apk-size-v1.1.26.json
```

### 7.2 Prometheus 新增指标

```python
# app/metrics.py 新增
db_query_duration_seconds = Histogram(           # 慢查询中间件用
    "db_query_duration_seconds",
    "DB query duration",
    labelnames=["endpoint", "operation"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1, 2.5, 5)
)
cache_hits_total = Counter("cache_hits_total", "Cache hits", ["key_prefix"])
cache_misses_total = Counter("cache_misses_total", "Cache misses", ["key_prefix"])
cache_hit_rate = Gauge("cache_hit_rate", "Cache hit rate", ["key_prefix"])
```

---

## 8. 回滚预案（可控激进的硬约束）

每项生产改动配套回滚方案，**先验证回滚脚本再上线**:

| 改动 | 回滚方式 | 验证点 |
|---|---|---|
| L1 索引迁移 `j1a2b3c4d5e6` | alembic `downgrade -1`（`DROP INDEX CONCURRENTLY`） | 回滚脚本 dry-run 通过 |
| L2 缓存装饰器 | `Settings.cache_decorators_enabled=False` 热重载 | feature flag 关闭后端点降级直查 DB |
| L2 慢查询中间件 | `Settings.slow_query_log_enabled=False` | 关闭后无 Prometheus 指标但功能正常 |
| L2 chat 端点并行化 | 代码回滚（无 flag，但改动隔离在 service 层新方法） | 旧方法保留，新方法可绕过 |
| L2 preference hint 缓存 | `Settings.pref_hint_cache_ttl=0`（禁用缓存，每次查 DB） | TTL=0 时装饰器直透 |
| L3 索引审计脚本 | 只读脚本，无回滚需求 | — |
| Flutter 修补 F1-F3 | 代码回滚（git revert 单 commit） | `flutter analyze` + widget test 全过 |
| Flutter 修补 F4 页面拆分 | git revert（零行为变更，回滚零风险） | 路由不变 |
| Flutter lint 升级 | `analysis_options.yaml` 还原 | `flutter analyze` 0 error |
| Settings feature flags | 全部默认 True，可随时设 False | `.env.production` 改值 + 重启 |

### 生产上线顺序（灰度）

1. 先发 L3 框架（慢查询中间件 + 索引审计脚本）—— 只观测不改动
2. 跑索引审计，生成报告，人工 review 后再发 L1 索引迁移
3. 发 L2 后端修补 + feature flag 默认关闭，逐步开启
4. 发 Flutter 改动（独立 release，不影响后端）
5. 跑 after 基线，对比 before

---

## 9. 测试策略

### 9.1 后端测试

| 测试类型 | 文件 | 覆盖点 |
|---|---|---|
| 单元测试 | `tests/test_auto_match_bom_perf.py` | O(N+M) 算法正确性 + 性能断言（50×200 < 200ms） |
| 单元测试 | `tests/test_cache_decorator.py` | 装饰器 hit/miss/invalidate/feature flag |
| 单元测试 | `tests/test_slow_query_middleware.py` | 阈值触发、EXPLAIN 开关、Prometheus 指标 |
| 集成测试 | `tests/test_agents_chat_parallel.py` | chat 端点 round trip 数 + 并行正确性 |
| 集成测试 | `tests/test_hot_endpoint_cache.py` | 4 个热点端点缓存命中 + 写入失效 |
| 回归测试 | 现有 `tests/test_materials.py` 等 | API 响应 schema 不变 |
| 安全测试 | 现有 `tests/test_security_*.py` | 缓存不泄露跨用户数据（key 含 user_id） |

### 9.2 缓存安全硬约束（防跨用户数据泄露）

- 所有缓存 key 必须含 `user_id` 或为公共数据（`materials/categories` 这种公共目录除外）
- `verify_project_access` 校验**在缓存读取之前**，不缓存鉴权结果
- 列表端点缓存 key 含 filters_hash + user_id（如 `furn:list:{user_id}:{filters_hash}`）

### 9.3 Flutter 测试

| 测试类型 | 文件 | 覆盖点 |
|---|---|---|
| widget test | `test/widgets/cached_image_test.dart` | SuokeCachedImage placeholder/error/cache |
| widget test | 现有 `test/pages/*_test.dart` | 拆分后页面行为不变 |
| integration_test | `integration_test/perf_baseline_test.dart` | FPS/build time 基线 |
| analyze | `flutter analyze` | 0 error（lint 升级后） |
| 鸿蒙兼容 | `flutter analyze`（Flutter-OH） | cached_network_image 不破坏鸿蒙构建 |

### 9.4 CI 流水线变更

`.github/workflows/ci.yml` 新增 3 个 job:
1. `backend-perf-regression`: 跑 bench-api.py，对比基线 JSON，P95 回退 > 10% 则 fail
2. `flutter-perf-baseline`: 跑 integration_test，输出 timeline（信息性，不阻塞）
3. `apk-size-budget`: check-apk-size.sh，超阈值 fail

### 9.5 测试数据库约束

- `tests/conftest.py` 顶部 `os.environ["DATABASE_URL"]` 在 `from app.database import engine` 之前
- 缓存测试用独立 fixture `cache_reset`，每个 test 清空 `cache._memory` + mock Redis

---

## 10. 版本号同步清单

| 文件 | 变更 |
|---|---|
| `app/config.py` | `app_version: "1.1.26"` → `"1.1.27"` |
| `flutter_app/pubspec.yaml` | `version: 1.1.26+15` → `1.1.27+16` |
| Web 资源版本 | 后端改动不涉及 Web JS/CSS，无需升级 `v=` 与 `sw.js:CACHE_VERSION` |
| `mypy.ini` 注释 | `v1.1.26` → `v1.1.27` |
| `scripts/ihome.service` | 无需改（uvicorn 参数不变） |

---

## 11. 不做清单（YAGNI）

明确排除以下，避免范围蔓延:

- ❌ 不引入 Docker / K8s（用户硬约束）
- ❌ 不引入读写分离 / CQRS / 物化视图（单 PG 实例无意义）
- ❌ 不引入 Riverpod / Bloc 重构状态管理（破坏现有页面）
- ❌ 不引入 OpenTelemetry 分布式追踪（本次聚焦 DB/Flutter，可观测性增强留后续）
- ❌ 不引入 dart_code_metrics（鸿蒙兼容性未验证）
- ❌ 不改 PASETO 认证（用户硬约束）
- ❌ 不改 Nginx 配置（性能瓶颈不在反代层）

---

## 12. 实施顺序（5-7 天工期）

| 阶段 | 工作内容 | 产出 |
|---|---|---|
| Day 1 | 基线采集 + L3 框架搭建（慢查询中间件、缓存装饰器、索引审计脚本） | before 基线 JSON + 3 个框架文件 |
| Day 2 | 索引审计 + L1 迁移 + L2 后端 B1（auto_match_bom）+ B4（preference hint 缓存） | alembic 迁移 + 2 修补 + 单元测试 |
| Day 3 | L2 后端 B2（chat 并行）+ B3（热点端点缓存） | 2 修补 + 集成测试 |
| Day 4 | Flutter F1（ListView 精准改造）+ F2（cached_network_image）+ F3（RepaintBoundary） | 3 修补 + widget test |
| Day 5 | Flutter F4（大页面拆分，8 个文件）+ F5-F7 框架 | 拆分 + integration_test + apk 预算 + lint |
| Day 6 | CI 流水线 3 个新 job + after 基线 + 对比报告 | CI 配置 + after 基线 JSON + 对比报告 |
| Day 7 | 缓冲（回归修复、文档更新、冗余清理） | v1.1.27 发布就绪 |

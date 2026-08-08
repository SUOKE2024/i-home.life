# 技术复盘：v1.6.0 F40 业务列迁移链缺口（2026-08-06）

> 触发：全景全量全链路 E2E 验证（空库 `alembic upgrade head` + `check_schema_drift`）
> 修复：迁移 [z8a9b0c1d2e3_add_v160_f40_columns.py](../../alembic/versions/z8a9b0c1d2e3_add_v160_f40_columns.py)（当前 head）
> 状态：已修复并推送（commit `ecc18f3`），全量 pytest 1956 passed 零回退

## 一、问题发现

全景 E2E 验证对**空库**执行 `alembic upgrade head` 后跑 `check_schema_drift.py`，exit=1：

```
DB 缺失表（model 有 DB 无, 0）: []
列差异（3 张表）:
  bom_items: 仅model有=['fallback_note', 'quantity_source'] 仅DB有=[]
  chat_messages: 仅model有=['auto_reply_meta'] 仅DB有=[]
  chat_rooms: 仅model有=['agent_members'] 仅DB有=[]
```

而 `compare_db_schema.py`（空库 vs 真实库 `data/ihome.db`）显示**真实库有这些列**（"仅 B 有"）。三方交叉核验（model / 真实库 / 空库迁移链）指向同一结论：

| 表 | 缺失列 | model | 真实库 | 空库迁移链 |
|----|--------|-------|--------|-----------|
| `chat_rooms` | `agent_members`（Agent 群成员 JSON 数组） | ✅ | ✅ | ❌ |
| `chat_messages` | `auto_reply_meta`（Agent 自动回复标注 JSON dict） | ✅ | ✅ | ❌ |
| `bom_items` | `quantity_source`（几何算量/经验估算标注） | ✅ | ✅ | ❌ |
| `bom_items` | `fallback_note`（经验估算回退说明） | ✅ | ✅ | ❌ |

影响：**空库全新部署（CI schema-compare / 新环境）缺 4 列**，代码读写这些字段会失败或退化为默认值。

## 二、根因分析

### 1. 双轨 schema 机制：运行时轻量迁移 ≠ alembic 迁移链

项目存在**两套并行**的 schema 补列机制：

- **A 轨（alembic 迁移链）**：`alembic/versions/`，CI 迁移测试 / schema-compare 覆盖的权威链路；
- **B 轨（运行时轻量迁移）**：[app/database.py](../../app/database.py) 的 `_run_lightweight_migrations()`，应用启动时按 `_SCHEMA_MIGRATION_VERSION` 逐版 `ALTER TABLE ... ADD COLUMN`，记录在 `_schema_migrations` 表。

v1.6.0 F40 落地时，4 列（+同批 `bom_items.version`）只进了 **B 轨**（`_SCHEMA_MIGRATION_VERSION = 7`），**从未进 A 轨**——`grep` 全量 `alembic/versions/` 无任何 `agent_members / auto_reply_meta / quantity_source / fallback_note` 命中，init 建表（`4356fec95e3e`）也无这些列。

### 2. 为什么此前没被发现（掩盖机制）

- 真实库 `data/ihome.db` 由 B 轨在启动时补列 → 对**真实库**跑 `check_schema_drift` 显示 0 缺失 0 多余；
- 2026-08-06 第五轮（迁移 [z7a8b9c0d1e2](z7a8b9c0d1e2_align_missing_indexes.py)）补索引对齐时，只补了同批的 `bom_items.version` 列（因为建 `ix_bom_items_version` 索引需要该列），**漏了同批另外 4 列**；
- 此前的 drift 检查均针对真实库，从未对"空库 `upgrade head`"语义（CI schema-compare 语义）跑过 → 缺口被掩盖。

### 3. 证据链（确认设计意图，排除"删 model 列"）

- **model 声明**：[app/models/chat.py](../../app/models/chat.py#L43-L65)（`auto_reply_meta` / `agent_members`）、[app/models/material.py](../../app/models/material.py#L63-L67)（`quantity_source` / `fallback_note`）；
- **B 轨补列 DDL**：[app/database.py](../../app/database.py#L729-L770)（`ALTER TABLE` 带 DEFAULT）；
- **完整代码读写路径**（非死字段）：`quantity_source/fallback_note` 由 [material_service.py](../../app/services/material_service.py#L510-L570) 写入、[materials.py API](../../app/api/materials.py#L177-L190) 读取；`auto_reply_meta` 由 [chat_service.py](../../app/services/chat_service.py#L317-L335) 写入、[chat.py API](../../app/api/chat.py#L55-L58) 读取；`agent_members` 由 [chat_service.py](../../app/services/chat_service.py#L86-L107) 读写。

结论：4 列为真实业务字段，**应补 alembic 迁移**，而非删 model 列。

## 三、解决方案

新增迁移 [z8a9b0c1d2e3_add_v160_f40_columns.py](../../alembic/versions/z8a9b0c1d2e3_add_v160_f40_columns.py)（`down_revision=z7a8b9c0d1e2`，head）：

| 列 | DDL（对齐 B 轨运行时迁移） |
|----|---------------------------|
| `bom_items.quantity_source` | `VARCHAR(30) NOT NULL DEFAULT 'empirical'` |
| `bom_items.fallback_note` | `VARCHAR(500)`（nullable） |
| `chat_messages.auto_reply_meta` | `TEXT`（nullable） |
| `chat_rooms.agent_members` | `TEXT NOT NULL DEFAULT '[]'` |

设计要点：

- **upgrade 幂等**：`_has_column` 守卫，已存在 skip（与 z7a8b9c0d1e2 同策略），真实库升级 0 副作用；
- **downgrade 不删列**：业务活跃字段，删列破坏性大，与 `bom_items.version` 处理一致（upgrade 幂等 skip）；
- **日志埋点**：`logging.getLogger("alembic.runtime.migration")`，输出 added/skip 明细。

## 四、验证结果

| 验证项 | 结果 |
|--------|------|
| 空库 `upgrade head` → `check_schema_drift` | **exit=0，Schema 已对齐** |
| `compare_db_schema`（空库 vs 真实库） | 差异 8 表 → **5 表**（仅剩 model 无的 P3 历史残留列） |
| `downgrade -3` → `upgrade head` 幂等重放 | 4 列全 skip，无 `_alembic_tmp` 残留 |
| 真实库升级（备份 `.bak-f40-20260806`） | `upgrade head` 4 skip，drift exit=0 |
| 全量 pytest | **1956 passed + 2 skipped + 3 xfailed**，零回退 |
| flake8 + mypy（迁移文件） | 通过 |

## 五、经验教训与预防

1. **drift 检查必须以"空库 `upgrade head`"为语义**（即 CI schema-compare 语义）。只对真实库跑会被 B 轨运行时迁移掩盖迁移链缺口——真实库有列 ≠ 迁移链有列。
2. **新列必须"双轨同步"**：改 [app/models/](../../app/models/) 加列时，A 轨（alembic 迁移）与 B 轨（`app/database.py` 运行时轻量迁移）都必须补，任何一轨遗漏都会造成空库/真实库/CI 不一致。
3. **批量补列迁移要全量收口**：z7a8b9c0d1e2 补 `version` 时未连带核查同批（`_SCHEMA_MIGRATION_VERSION=7`）其他列，是本次缺口的直接诱因。补列迁移应把 B 轨同一版本号下的全部列一次收口核对。
4. **遗留可选项**（本次未动）：真实库 5 表历史残留列（`escrow_payments.amount` / `milestone_trackers.due_date` / `orchestrator_tasks.agent_type` / `quality_issues.title` / `rectification_orders.issue_id`，model 无，P3 无害）与 B 轨机制是否并入 alembic 链，留待后续 schema 整理评估。

# Migration Downgrade 回归测试报告（2026-08-06）

> 范围：SQLite 下 alembic 迁移 downgrade 全链路回归，修复前（commit 587e7e5 前）/修复后（含本次 commit）对比。
> 环境：macOS 本地、Python 3.12、SQLite（与 CI migration-test 同驱动 `sqlite+aiosqlite`）。

## 一、结论速览

| 维度 | 修复前 | 修复后 |
|------|--------|--------|
| `downgrade -3`（CI 覆盖范围） | ❌ 100% 失败 | ✅ 100% 通过 |
| `downgrade base`（全量回滚） | ❌ 100% 失败 | ✅ 100% 通过 |
| 完整往返 `downgrade base ↔ upgrade head` | ❌ 失败 | ✅ 通过（2.49s） |
| 空库 `upgrade head` | ✅ 通过（1.03s，但有 4 张 model 表缺失，见 §四） | ✅ 通过（同） |

修复前所有 downgrade 均在 w8d9/x9e0 处崩溃，**无一次完整成功执行**，故不存在"修复前耗时"可比数据；修复后耗时见 §三。

## 二、修复的缺陷清单（4 处，均为 2026-08-06 实测复现）

| # | 迁移 | 缺陷 | 触发条件 | 报错 | 修复 |
|---|------|------|----------|------|------|
| 1 | [x9e0f1a2b3c4](file:///Users/netsong/Developer/i-home.life/alembic/versions/x9e0f1a2b3c4_add_quick_install_package_columns.py)（F49 局改快装） | downgrade 删带索引列前未先删索引 | 列存在且带索引（SQLite batch 重建表） | `no such column: package_code` | 入口先 `op.drop_index`（`_has_index` 幂等守卫） |
| 2 | [w8d9e0f1a2b3](file:///Users/netsong/Developer/i-home.life/alembic/versions/w8d9e0f1a2b3_add_board_trace_henf.py)（F50 一板一码） | `BatchOperations` 无 `drop_table` 方法 | 整表删除误用 batch 上下文 | `AttributeError` | 改迁移级 `op.drop_table`；`henf_grade` 删列前补删隐式索引 |
| 3 | [x9e0 / w8d9](file:///Users/netsong/Developer/i-home.life/alembic/versions/x9e0f1a2b3c4_add_quick_install_package_columns.py) | 对**不存在的表**执行 batch 操作（`_has_column` 对缺表 catch 返回 True → 误入删列分支） | 空库（CI 从零迁移）downgrade | `NoSuchTableError: partial_renovation_plans / material_eco_certs` | downgrade 入口 `_has_table` 存在性守卫，缺表则 skip |
| 4 | [k2b3c4d5e6f7](file:///Users/netsong/Developer/i-home.life/alembic/versions/k2b3c4d5e6f7_add_bathroom_waterproof_fields.py)（防水字段） | downgrade 非幂等：与 [n5e6f7a8b9c0](file:///Users/netsong/Developer/i-home.life/alembic/versions/n5e6f7a8b9c0_add_missing_columns_drift_fix.py)（drift fix 重复补列）双重删除 | 空库全量 downgrade（n5e6 先删列） | `KeyError: 'mechanical_vent_airflow'` | 循环内 `_has_column` 幂等守卫 |

## 三、耗时对比（空库、SQLite，本地实测）

| 场景 | 修复后耗时 | 修复前 |
|------|-----------|--------|
| `upgrade head`（空库） | 1.03s | 1.03s（无变化，upgrade 未改） |
| `downgrade -3` | 0.51s | ❌ 崩溃于 x9e0（无成功耗时） |
| `upgrade head` 重放 | 0.52s | — |
| 完整往返 `downgrade base → upgrade head` | 2.49s | ❌ 崩溃于 x9e0（无成功耗时） |

> 注：修复前链路 100% 失败于中途，**不存在"修复前成功耗时"**，表中以"崩溃"标注。修复后新增的 `_has_index` / `_has_table` 检查为毫秒级 inspector 查询，对耗时影响可忽略（downgrade -3 0.51s 中主要为 DDL 重建）。

## 四、附带发现（本次排查新增，非本次修复范围）

1. **4 张 model 表无建表迁移**：`elderly_adaptation_schemes` / `escrow_trustee_accounts` / `material_eco_certs` / `partial_renovation_plans`（均 v1.5.0 新增 model），仅靠 `Base.metadata.create_all` 建表。空库 `upgrade head` 后缺失（118 张 vs model 121 张），`check_schema_drift` 报 drift。本地/生产库因历史 create_all 存在故未暴露。**建议**：后续补建表迁移，使 CI 空库迁移与生产 schema 完全等价。
2. **j0f5a9c2d4e6 / q1f2e3d4c5b6 downgrade 静默 skip**：用非 batch `op.drop_column` + `try/except` 吞错，SQLite 下删列被跳过、列残留，不报错不崩溃。属"静默失败"模式，downgrade 不完整但不阻断。暂不修复（避免扩大改动面），已记录。

## 五、CI 流水线同步

[.github/workflows/ci.yml](file:///Users/netsong/Developer/i-home.life/.github/workflows/ci.yml#L403-L417) migration-test job：

- `downgrade -1`（仅覆盖 head）→ **`downgrade -3`**（覆盖本次修复的 w8d9/x9e0/y0f1 三个迁移）
- 步骤加注释说明 v1.9.0 修复背景；日志埋点（`alembic.runtime.migration` INFO）随命令输出在 CI 日志可见
- 新增步骤耗时估算：downgrade -3 + upgrade head ≈ 1.1s，远低于 job 10 分钟超时

## 六、验证矩阵（修复后最终代码）

| 场景 | 数据库 | 结果 |
|------|--------|------|
| `downgrade -3` → `upgrade head` | 本地真实库 `data/ihome.db` | ✅ 0 Error，无 `_alembic_tmp_*` 残留 |
| `upgrade head` → `downgrade base` → `upgrade head` | 空库探针库 | ✅ EXIT=0，往返一致 |
| 日志埋点 | 全程 | ✅ upgrade/downgrade 起止、每列/表 added/dropped/skip、backfill rowcount 均输出 |
| 全量 pytest | 测试库 | ✅ 1956 passed + 2 skipped + 3 xfailed（无回退） |
| flake8 / mypy | 改动文件 | ✅ Passed / 342 源文件 0 errors |

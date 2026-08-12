# 技术分享：一次「本地全过、生产 500」的 FK 级联删除排障实战

> 分享人：后端组 · 2026-08-12
> 背景：生产 `DELETE /projects/:id` 500 + `health_monitor` 巡检报错，两次「SQLite 过、PostgreSQL 炸」的经典案例
> 配套：完整排查手册见 `docs/reports/fk-cascade-delete-troubleshooting-guide-20260812.md`

---

## 一、开场：两个真实事故

### 事故 1：删除项目 500（用户可感知）
用户在前端点「删除项目」→ 接口返回 500。**本地 pytest 全量 2155 全过**。

### 事故 2：巡检日志刷 error（运维可感知）
生产日志每轮巡检出现 `health_check_project_error: ... Multiple rows were found`，
只发生在演示项目上，重启前后都复现。

两个事故的共同点：**本地测试环境（SQLite）和生产（PostgreSQL）行为不一致**。

---

## 二、根因一：SQLite 默认不强制外键

这是最容易被忽视的环境差异：

| 数据库 | FK 约束默认 | 违反后果 |
|--------|------------|---------|
| PostgreSQL | **强制执行** | DELETE 报 `FOREIGN KEY constraint failed` → 500 |
| SQLite | **默认关闭**（`PRAGMA foreign_keys=OFF`） | 静默通过，删了主表留下孤儿子表 |

所以「本地全量测试通过 ≠ 生产没问题」。凡是**本地过、生产 500**，第一优先级怀疑 FK。

**演示 demo**（会后可自行跑）：

```python
from sqlalchemy import event

@event.listens_for(engine.sync_engine, "connect")
def _fk_on(dbapi_conn, rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")  # 关键一行
    cur.close()
```

开启后同样代码立刻复现生产 500。

## 三、根因二：`scalar_one_or_none()` 的「唯一性幻觉」

```python
existing = await db.execute(select(Alert).where(...))  # 无唯一约束
if existing.scalar_one_or_none():   # 假设最多 1 行
    continue
```

- `scalar_one_or_none()` 的语义是「0 或 1 行」，**不是「任意行」**
- 表结构没有 `(project_id, alert_type, status)` 唯一索引 → 数据一旦膨胀到 2 条即抛 `MultipleResultsFound`
- 排查指南：**凡是对「是否存在」做判断，用 `limit(1)` + `scalar()`；不要对无唯一约束的查询用 `one_or_none()`**

## 四、级联删除的通用修法（metadata 反射）

核心思路：不手写每张子表，而是让 SQLAlchemy `Base.metadata` 告诉我们谁引用了谁，然后**递归从最深子表删起**。

```python
async def _cascade_delete_related(db, parent_id):
    fk_index = {}
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            fk_index.setdefault(fk.column.table.name, []).append(
                (table.name, fk.parent.name, fk.column.name)
            )

    async def _delete_children(table_name, parent_ids):
        if not parent_ids:
            return
        for child_name, child_fk_col, _ in fk_index.get(table_name, []):
            child = Base.metadata.tables.get(child_name)
            if child is None or child_fk_col not in child.c:
                continue
            child_pk = next(iter(child.primary_key.columns)).name
            child_ids = list((await db.execute(
                select(child.c[child_pk]).where(child.c[child_fk_col].in_(parent_ids))
            )).scalars().all())
            await _delete_children(child_name, child_ids)   # 先孙后子
            await db.execute(delete(child).where(child.c[child_pk].in_(child_ids)))

    await _delete_children("projects", [parent_id])
```

要点：
1. **多级依赖**：不只删直接子表（budgets），还要删二级（budget_lines→budgets）
2. **新表自动覆盖**：metadata 反射，以后加表不用改代码
3. **主键取 `primary_key.columns`**，不硬编码 `id`

## 五、给测试的「三点纪律」

1. **FK 回归测试必须局部开约束**：`PRAGMA foreign_keys=ON`，测完 `sa_event.remove` 防污染
2. **断言要查二级**：如 `budget_lines JOIN budgets`，不只查直接子表
3. **别只测 happy path**：生产事故往往在「数据重复/脏数据」分支

## 六、Q&A 互动要点

- **Q：为什么不直接给 FK 加 `ondelete="CASCADE"`？**
  A：可行但需 DB 迁移 + 生产执行；级联行为隐蔽、误删风险高；对「已有大量生产表」场景应用层递归更可控。
- **Q：为什么不用软删除？**
  A：对预警/审计类数据合理，但对项目主链路物理删除更简单，且已有 `deleted_at` 字段的表可混用。
- **Q：怎么避免再次发生？**
  A：① 新增「存在性」查询代码审查清单项；② FK 回归测试进 CI 模板；③ 生产日志巡检纳入日常。

---

## 附录：两个事故的修复对照

| 项目 | 根因 | 修复 | 回归测试 |
|------|------|------|---------|
| DELETE /projects 500 | FK 约束 + 只删主表 | `_cascade_delete_related` 递归级联 | `test_delete_project_cascades_related_data_with_fk` |
| health_monitor 报错 | `scalar_one_or_none` 遇重复数据 | `limit(1)` + `scalar()` 存在性判断 | `test_health_monitor_patrol.py`（3 用例） |

> 源码见 commit `a00d7d9` 及工作树 health_monitor 修复；完整排查手册与修复方案分别见
> `docs/reports/fk-cascade-delete-troubleshooting-guide-20260812.md` 与
> `docs/reports/health-monitor-patrol-fix-plan-20260812.md`

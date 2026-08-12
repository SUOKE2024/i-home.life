# 级联删除（FK）问题通用排查指南

> 适用场景：API DELETE 接口在生产返回 500 / `FOREIGN KEY constraint failed` /
> `IntegrityError`，但本地测试通过。基于 2026-08-12 生产 `DELETE /projects` 500 修复沉淀。
> 适用代码库：i-home.life（FastAPI + SQLAlchemy async + PostgreSQL 生产 / SQLite 测试）。

## 一、故障识别（先判断是否真是级联删除问题）

生产 DELETE 500 的可能原因按概率排序：

| 症状 | 可能根因 | 快速判别 |
|------|---------|---------|
| `FOREIGN KEY constraint failed` / `IntegrityError` | FK 约束违反（子表残留） | 看后端日志 / health/detail |
| `Multiple rows were found` / `MultipleResultsFound` | 查询期望 1 行却多行（`scalar_one_or_none`） | 与 DELETE 无直接关系，单独排查 |
| 未捕获业务异常（404/403/业务校验） | Service 抛错未映射 HTTP | 看 traceback |
| 通用 500（无明确错误） | 中间件/依赖注入/DB 连接 | 看日志 message 字段 |

> 经验：**SQLite 测试默认不强制 FK**（`PRAGMA foreign_keys` 默认 OFF），FK 类 bug
> 本地全量 pytest 全部通过但生产必炸。**凡是「本地过、生产 500」优先怀疑 FK**。

## 二、定位 FK 引用面

找出「被删除表」被哪些表引用（决定级联删除范围）：

```python
# 基于 Base.metadata 反射，一键列出某表的所有直接 FK 引用
from sqlalchemy import create_engine
from app.database import Base
import app.models  # noqa: F401 确保全部模型注册

def fk_children(table_name: str) -> list[tuple[str, str]]:
    """返回 [(child_table, child_fk_col), ...]"""
    out = []
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            if fk.column.table.name == table_name:
                out.append((table.name, fk.parent.name))
    return out

print(fk_children("projects"))  # 例：budgets/project_id、floor_plans/project_id、...
```

注意**多级依赖**：不仅直接引用（budgets→projects），还有二级（budget_lines→budgets→
projects、agent_messages→agent_sessions→projects）。只删直接子表会漏掉二级，删父表时
二级子表又违反 FK。**必须沿 FK 链递归到最深子表**。

## 三、本地复现（模拟生产 FK）

在测试/探针脚本中启用 SQLite FK 约束复现生产行为：

```python
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_fk_probe.db"

from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(os.environ["DATABASE_URL"])

@event.listens_for(engine.sync_engine, "connect")
def _fk_on(dbapi_conn, rec):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")  # 关键：启用 FK 约束
    cur.close()
```

之后按业务路径创建数据（含子表行）→ 调 DELETE → 观察是否抛 IntegrityError。

## 四、修复范式（按推荐度排序）

### 范式 A：应用层递归级联删除（推荐，本次采用）
基于 metadata 反射构建 FK 索引，递归「先删最深子表 → 再删父表」：

```python
async def _cascade_delete_related(db: AsyncSession, parent_id: str) -> None:
    from sqlalchemy import delete
    from app.database import Base

    fk_index: dict[str, list[tuple[str, str, str]]] = {}
    for table in Base.metadata.sorted_tables:
        for fk in table.foreign_keys:
            fk_index.setdefault(fk.column.table.name, []).append(
                (table.name, fk.parent.name, fk.column.name)
            )

    async def _delete_children(table_name: str, parent_ids: list[str]) -> None:
        if not parent_ids:
            return
        for child_name, child_fk_col, _parent_pk in fk_index.get(table_name, []):
            child_table = Base.metadata.tables.get(child_name)
            if child_table is None or child_fk_col not in child_table.c:
                continue
            child_pk = next(iter(child_table.primary_key.columns)).name
            child_ids = list(
                (
                    await db.execute(
                        select(child_table.c[child_pk]).where(
                            child_table.c[child_fk_col].in_(parent_ids)
                        )
                    )
                ).scalars().all()
            )
            await _delete_children(child_name, child_ids)  # 先删孙表
            await db.execute(
                delete(child_table).where(child_table.c[child_pk].in_(child_ids))
            )

    await _delete_children("projects", [parent_id])
```

优点：不依赖 DB 端级联配置、新表自动纳入（metadata 反射）、无迁移。注意：
- 所有表主键须为 `id`（本库约定成立；若异主键需按 primary_key.columns 取值）
- 注意 SQLite 下 `delete()` bulk 语句需在同一 session 内 commit 才生效
- 递归前先查 child_ids（避免对不存在的表/列报错）

### 范式 B：DB 层 ON DELETE CASCADE
模型 FK 加 `ondelete="CASCADE"` + 迁移。优点：DB 自治、无应用层逻辑。
缺点：需迁移、生产执行、级联行为隐蔽（误删风险）、不适用于已有表结构冻结场景。

### 范式 C：软删除/归档替代物理删除
业务上不物理删，标 `deleted_at`。适合审计要求高的表。若采用，DELETE 接口改为
UPDATE，规避 FK 与数据恢复问题（本库 budgets/budget_lines 已有 `deleted_at` 字段）。

## 五、回归测试模板（必须启用 FK 约束）

```python
@pytest.mark.asyncio
async def test_delete_cascades_related_data_with_fk(client, db_session):
    from sqlalchemy import event as sa_event, text
    from app.database import engine

    @sa_event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, rec):
        cur = dbapi_conn.cursor(); cur.execute("PRAGMA foreign_keys=ON"); cur.close()

    try:
        # 1) 创建主记录 + 直接子表行 + 二级子表行（模拟 EventBus 自动建子表）
        # 2) 调 DELETE API → 断言 204（回归：此前 500）
        # 3) 断言直接/二级子表行数 == 0（级联清空）
    finally:
        sa_event.remove(engine.sync_engine, "connect", _fk_on)  # 防污染其他用例
```

关键点：
- **测试结束必须 `sa_event.remove`**，否则 FK 约束残留影响同进程其他用例
- 断言既要查主表已删，也要 join 查二级子表（如 budget_lines JOIN budgets）

## 六、部署验证清单

1. 本地全量 pytest（`.venv/bin/python`，权威基线）+ 新增回归测试单独跑
2. `bash scripts/deploy-remote.sh backend` 部署
3. 远程确认代码生效（`grep -c` 关键函数名、`systemctl status`、health version）
4. 重跑生产 E2E（`python scripts/e2e_test.py`），重点看 DELETE 步骤 200/204
5. 生产日志巡检（`journalctl -u ihome --since '1 hour ago'`）确认无新 FK 报错

## 七、经验教训沉淀

- 测试 conftest 若全局不启用 FK（为兼容既有用例），FK 回归测试必须**局部启用 + finally 移除**
- 版本/flag 灰度导致的行为差异（如 EventBus 自动建子表）是 FK bug 的高发触发源——
  改业务侧自动创建逻辑时同步审计删除路径
- 删除接口返回 500 而非 409/400，说明异常未映射——检查 handler 是否有 try/except
  或 FastAPI 异常处理器兜底
- 排查「本地过、生产 500」时，优先怀疑环境差异（DB 引擎 FK 策略、SQLite/PostgreSQL
  行为差异），而非业务逻辑本身

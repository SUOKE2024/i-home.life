"""修复本地开发库三张表的状态机 CHECK 约束（对齐 alembic f8e7d6c5b4a3 迁移）

背景：本地 SQLite 库由 seed.py create_all 创建，落后迁移
f8e7d6c5b4a3_align_state_machine_constraints（2026-08-17），
budgets/procurement_orders/inspections 三表 CHECK 允许集未含新增状态，
导致预算 submit/execute/close、订单 delivered→completed、质检 failed→rework
真实写入抛 IntegrityError(500)。

本脚本与迁移同策略：仅扩允许集、幂等（已存在则跳过）、先备份再改。
"""
import sqlite3
import shutil
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "ihome.db"

# (表名, 约束名, 新允许集 SQL)
_FIXES = {
    "budgets": (
        "chk_budget_status",
        "status IN ('draft', 'submitted', 'approved', 'executed', 'closed', 'active', 'completed')",
    ),
    "procurement_orders": (
        "chk_procurement_order_status",
        "status IN ('draft', 'pending', 'confirmed', 'shipped', 'delivered', 'completed', 'cancelled')",
    ),
    "inspections": (
        "chk_inspection_status",
        "status IN ('pending', 'passed', 'failed', 'rework')",
    ),
}


def _rebuild_constraint(cur: sqlite3.Cursor, table: str, check_sql: str) -> bool:
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
    row = cur.fetchone()
    if not row:
        return False
    ddl: str = row[0]
    if check_sql.replace(" ", "") in ddl.replace(" ", ""):
        print(f"  [skip] {table} 已含新约束")
        return False
    # 生成新表 DDL：仅替换该表唯一的一个 status CHECK 约束
    import re
    new_ddl = re.sub(
        r"CONSTRAINT chk_(\w+_)?status CHECK \(status IN \([^)]*\)\)",
        f"CONSTRAINT chk_{'procurement_order_' if table == 'procurement_orders' else ''}status "
        f"CHECK ({check_sql})",
        ddl,
        count=1,
    )
    new_name = f"{table}_qa_new"
    cur.execute(f"DROP TABLE IF EXISTS {new_name}")
    cur.execute(new_ddl.replace(f"CREATE TABLE {table} ", f"CREATE TABLE {new_name} "))
    cur.execute(f"INSERT INTO {new_name} SELECT * FROM {table}")
    # 重建索引（sqlite_master 里该表索引）
    cur.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL", (table,))
    indexes = cur.fetchall()
    cur.execute(f"DROP TABLE {table}")
    cur.execute(f"ALTER TABLE {new_name} RENAME TO {table}")
    for idx_name, idx_sql in indexes:
        cur.execute(idx_sql.replace(f"ON {table}", f"ON {table}"))
    print(f"  [ok] {table} 约束已重建")
    return True


def main() -> None:
    if not DB.exists():
        print(f"DB 不存在: {DB}")
        return
    bak = str(DB) + ".bak-qa"
    shutil.copyfile(DB, bak)
    print(f"备份: {bak}")

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        cur = conn.cursor()
        for table, (_, check_sql) in _FIXES.items():
            _rebuild_constraint(cur, table, check_sql)
        conn.commit()
        print("完成。")
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.close()


if __name__ == "__main__":
    main()

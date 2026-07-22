#!/usr/bin/env python3
"""索引审计脚本 — 只读分析 PostgreSQL 索引使用情况。

输出三份报告：
1. 未使用索引：idx_scan=0 的索引（建议 DROP，释放写入开销）
2. 缺失索引建议：外键字段无索引 + 常见 filter 字段无索引
3. 重复索引：相同列集的多个索引

使用方式:
  # 用 .env 中的 DATABASE_URL
  python3 scripts/audit-indexes.py

  # 指定连接串
  python3 scripts/audit-indexes.py --url "postgresql://user:pass@host:5432/ihome"

  # 输出到指定文件
  python3 scripts/audit-indexes.py --out reports/index-audit.md

注意:
- 只读脚本，不修改任何数据库对象
- 需要 PostgreSQL（不支持 SQLite）
- 建议在生产环境低峰期运行（查询系统视图有少量开销）
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_DIR / "reports"


def _load_env() -> str | None:
    """从 .env 加载 DATABASE_URL。"""
    env_file = PROJECT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip().strip("'\"")
    return os.environ.get("DATABASE_URL")


# ── SQL 查询 ──

SQL_UNUSED_INDEXES = """
SELECT
    schemaname AS schema,
    relname AS table_name,
    indexrelname AS index_name,
    idx_scan AS scan_count,
    idx_size AS index_size,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE '%_pkey'  -- 排除主键索引（不可删除）
  AND indexrelname NOT LIKE '%_key'   -- 排除唯一约束索引
ORDER BY idx_size DESC;
"""

SQL_MISSING_FK_INDEXES = """
SELECT
    c.conrelid::regclass AS table_name,
    c.conname AS constraint_name,
    string_agg(a.attname, ', ' ORDER BY u.ord) AS fk_columns,
    NOT EXISTS (
        SELECT 1 FROM pg_index i
        WHERE i.indrelid = c.conrelid
          AND i.indkey::smallint[] = array_agg(a.attnum ORDER BY u.ord)
          AND i.indisvalid
    ) AS missing_exact,
    NOT EXISTS (
        SELECT 1 FROM pg_index i
        WHERE i.indrelid = c.conrelid
          AND a.attnum = ANY(i.indkey)
          AND i.indisvalid
    ) AS missing_any
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
JOIN unnest(c.conkey) WITH ORDINALITY AS u(attnum, ord) ON u.attnum = a.attnum
WHERE c.contype = 'f'  -- 外键约束
GROUP BY c.conrelid, c.conname, c.conkey
HAVING NOT EXISTS (
    SELECT 1 FROM pg_index i
    WHERE i.indrelid = c.conrelid
      AND i.indkey::smallint[] = array_agg(a.attnum ORDER BY u.ord)
      AND i.indisvalid
)
ORDER BY 1, 2;
"""

SQL_DUPLICATE_INDEXES = """
SELECT
    array_agg(indexrelname ORDER BY indexrelname) AS duplicate_indexes,
    relname AS table_name,
    string_agg(indexdef, E'\\n') AS index_definitions
FROM (
    SELECT
        i.relname AS indexrelname,
        t.relname,
        pg_get_indexdef(i.indexrelid) AS indexdef,
        (
            SELECT string_agg(att.attname, ',' ORDER BY array_position(i.indkey, att.attnum))
            FROM pg_attribute att
            WHERE att.attrelid = i.indrelid AND att.attnum = ANY(i.indkey)
        ) AS index_columns
    FROM pg_index i
    JOIN pg_class t ON t.oid = i.indrelid
    JOIN pg_class r ON r.oid = i.indexrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'public'
      AND i.indisvalid
) idx
GROUP BY relname, index_columns
HAVING count(*) > 1
ORDER BY relname;
"""


def run_audit(database_url: str, output_path: Path) -> int:
    """执行索引审计，输出 Markdown 报告。"""
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary", file=sys.stderr)
        return 1

    # 确保是 PostgreSQL
    if not database_url.startswith(("postgresql://", "postgres://")):
        print(f"ERROR: audit-indexes requires PostgreSQL, got: {database_url[:30]}...", file=sys.stderr)
        return 1

    print("Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(database_url)
    except Exception as e:
        print(f"ERROR: Failed to connect: {e}", file=sys.stderr)
        return 1

    report_lines = [
        "# 索引审计报告",
        "",
        f"- **日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **数据库**: {database_url.split('@')[-1] if '@' in database_url else database_url}",
        "",
    ]

    try:
        with conn.cursor() as cur:
            # 1. 未使用索引
            print("  [1/3] Querying unused indexes...")
            cur.execute(SQL_UNUSED_INDEXES)
            unused = cur.fetchall()
            report_lines.extend(_format_unused_indexes(unused))

            # 2. 缺失外键索引
            print("  [2/3] Querying missing FK indexes...")
            cur.execute(SQL_MISSING_FK_INDEXES)
            missing = cur.fetchall()
            report_lines.extend(_format_missing_indexes(missing))

            # 3. 重复索引
            print("  [3/3] Querying duplicate indexes...")
            cur.execute(SQL_DUPLICATE_INDEXES)
            duplicates = cur.fetchall()
            report_lines.extend(_format_duplicates(duplicates))

    except Exception as e:
        print(f"ERROR: Query failed: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    # 写入报告
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nReport written to: {output_path}")
    print(f"  - Unused indexes: {len(unused)}")
    print(f"  - Missing FK indexes: {len(missing)}")
    print(f"  - Duplicate index groups: {len(duplicates)}")

    return 0


def _format_unused_indexes(rows: list) -> list[str]:
    lines = ["", "## 1. 未使用索引（idx_scan=0，建议 DROP）", ""]
    if not rows:
        lines.append("✅ 无未使用索引。")
        return lines
    lines.append("| 表名 | 索引名 | 扫描次数 | 索引大小 | 元组读取 |")
    lines.append("|---|---|---|---|---|")
    for row in rows:
        table, idx, scan, size, tup_read, tup_fetch = row
        size_str = _format_size(size)
        lines.append(f"| {table} | {idx} | {scan} | {size_str} | {tup_read or 0} |")
    lines.append("")
    lines.append("**建议**: 这些索引从未被查询使用，但每次写入都需维护。")
    lines.append("```sql")
    for row in rows:
        lines.append(f"DROP INDEX CONCURRENTLY IF EXISTS {row[2]};  -- {row[0]}")
    lines.append("```")
    return lines


def _format_missing_indexes(rows: list) -> list[str]:
    lines = ["", "## 2. 缺失外键索引（建议添加）", ""]
    if not rows:
        lines.append("✅ 所有外键字段均有索引。")
        return lines
    lines.append("| 表名 | 约束名 | 外键列 |")
    lines.append("|---|---|---|")
    for row in rows:
        table, constraint, columns = row[0], row[1], row[2]
        lines.append(f"| {table} | {constraint} | {columns} |")
    lines.append("")
    lines.append("**建议**: 外键字段无索引会导致 JOIN 和级联删除全表扫描。")
    lines.append("```sql")
    for row in rows:
        table, constraint, columns = row[0], row[1], row[2]
        col_clean = columns.replace(", ", "_").replace("(", "").replace(")", "")
        idx_name = f"idx_{table}_{col_clean}"
        lines.append(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {idx_name} ON {table} ({columns});")
    lines.append("```")
    return lines


def _format_duplicates(rows: list) -> list[str]:
    lines = ["", "## 3. 重复索引（相同列集，建议保留一个）", ""]
    if not rows:
        lines.append("✅ 无重复索引。")
        return lines
    for row in rows:
        indexes, table, defs = row[0], row[1], row[2]
        lines.append(f"### 表 `{table}`")
        lines.append(f"重复索引: {', '.join(indexes)}")
        lines.append("```sql")
        lines.append(defs)
        lines.append("```")
        lines.append("")
    return lines


def _format_size(size_bytes: int | None) -> str:
    """格式化字节大小为人类可读。"""
    if not size_bytes:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def main():
    parser = argparse.ArgumentParser(description="PostgreSQL 索引审计")
    parser.add_argument("--url", help="数据库连接串（默认从 .env / DATABASE_URL 读取）")
    parser.add_argument("--out", default=None, help="输出文件路径")
    args = parser.parse_args()

    database_url = args.url or _load_env()
    if not database_url:
        print("ERROR: No DATABASE_URL found. Use --url or set DATABASE_URL in .env", file=sys.stderr)
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_path = Path(args.out) if args.out else REPORTS_DIR / f"index-audit-{timestamp}.md"
    sys.exit(run_audit(database_url, output_path))


if __name__ == "__main__":
    main()

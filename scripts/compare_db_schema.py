#!/usr/bin/env python3
"""对比两个数据库的表结构差异（生产库 vs 空库/CI 迁移库）

用途（2026-08-06 空库 schema 债排查配套）：
  - 发现"生产库有、空库（CI 从零迁移）无"的表 → 缺建表迁移
  - 发现同表列/索引差异 → 迁移链与 create_all 漂移
  - CI 空库迁移应与生产 schema 等价，本脚本是其校验工具

用法:
  python scripts/compare_db_schema.py <url_a> <url_b>        # 位置参数
  DATABASE_URL_A=... DATABASE_URL_B=... python scripts/compare_db_schema.py
  # url 支持 sqlite+aiosqlite / postgresql+asyncpg（自动 strip 驱动前缀）

退出码:
  0 = 两库表结构完全一致（仅允许 A 中无 model 的已知冗余表，见 --ignore）
  1 = 发现差异
  2 = 参数/连接错误

说明:
  - 列对比：列名 / 类型字符串 / 可空性；索引对比：索引名 / 列 / 唯一性
  - server_default 不参与对比（驱动间表达差异大，噪音高）
"""
import os
import sys

from sqlalchemy import create_engine, inspect

_DEFAULT_IGNORE = {
    "alembic_version",  # 版本表两库必不一致，跳过
    "_schema_migrations",  # 内部迁移表
}


def _connect(url: str):
    # 与 scripts/check_schema_drift.py 一致：strip 异步驱动前缀
    clean = url.replace("+aiosqlite", "").replace("+asyncpg", "")
    return create_engine(clean)


def _normalize_type(col_type) -> str:
    return str(col_type)


def _load_schema(url: str):
    """返回 {table: {"cols": [(name, type_str, nullable)], "indexes": [(name, cols, unique)]}}"""
    eng = _connect(url)
    insp = inspect(eng)
    schema: dict = {}
    for table in insp.get_table_names():
        cols = [
            (c["name"], _normalize_type(c["type"]), bool(c.get("nullable", True)))
            for c in insp.get_columns(table)
        ]
        indexes = [
            (ix["name"], tuple(ix["column_names"] or []), bool(ix.get("unique", False)))
            for ix in insp.get_indexes(table)
            if ix.get("name")  # 跳过 sqlite_autoindex_* 等内部索引
        ]
        schema[table] = {"cols": sorted(cols), "indexes": sorted(indexes)}
    eng.dispose()
    return schema


def _diff_tables(a, b):
    """返回 (仅A有, 仅B有) 表名列表"""
    return sorted(set(a) - set(b)), sorted(set(b) - set(a))


def _diff_columns(a_cols, b_cols):
    """返回 A 有 B 无 / B 有 A 无 的列列表"""
    a_set, b_set = set(a_cols), set(b_cols)
    return sorted(a_set - b_set), sorted(b_set - a_set)


def _diff_indexes(a_idx, b_idx):
    a_set, b_set = set(a_idx), set(b_idx)
    return sorted(a_set - b_set), sorted(b_set - a_set)


def _report_only_tables(only_a, only_b) -> int:
    """输出仅 A/B 有表集合，返回差异类数。"""
    diffs = 0
    if only_a:
        diffs += 1
        print(f"\n🔴 仅 A（生产/基线）有，B（空库/CI）无 —— 疑似缺建表迁移: {len(only_a)} 张")
        for t in only_a:
            print(f"  - {t}")
    if only_b:
        diffs += 1
        print(f"\n🟡 仅 B 有，A 无（B 迁移新建，A 需 upgrade）: {len(only_b)} 张")
        for t in only_b:
            print(f"  - {t}")
    return diffs


def _report_table_diffs(common, schema_a, schema_b) -> int:
    """对比共同表的列/索引，输出差异，返回差异类数。"""
    col_diffs = []
    idx_diffs = []
    for table in common:
        a_cols, b_cols = _diff_columns(
            [c for c, _, _ in schema_a[table]["cols"]],
            [c for c, _, _ in schema_b[table]["cols"]],
        )
        if a_cols or b_cols:
            col_diffs.append((table, a_cols, b_cols))
        a_idx, b_idx = _diff_indexes(schema_a[table]["indexes"], schema_b[table]["indexes"])
        if a_idx or b_idx:
            idx_diffs.append((table, a_idx, b_idx))

    diffs = 0
    if col_diffs:
        diffs += 1
        print(f"\n🔴 列差异（{len(col_diffs)} 张表）:")
        for table, a_only, b_only in col_diffs:
            if a_only:
                print(f"  {table}: 仅 A 有 ={a_only}")
            if b_only:
                print(f"  {table}: 仅 B 有 ={b_only}")

    if idx_diffs:
        diffs += 1
        print(f"\n🟡 索引差异（{len(idx_diffs)} 张表）:")
        for table, a_only, b_only in idx_diffs:
            if a_only:
                print(f"  {table}: 仅 A 有 ={a_only}")
            if b_only:
                print(f"  {table}: 仅 B 有 ={b_only}")
    return diffs


def main() -> int:
    url_a = os.environ.get("DATABASE_URL_A", "")
    url_b = os.environ.get("DATABASE_URL_B", "")
    args = [a for a in sys.argv[1:] if a.startswith(("sqlite", "postgresql"))]
    if len(args) >= 2:
        url_a, url_b = args[0], args[1]
    if not url_a or not url_b:
        print("❌ 需要两个数据库 URL（位置参数或 DATABASE_URL_A / DATABASE_URL_B）", file=sys.stderr)
        return 2

    ignore = _DEFAULT_IGNORE
    print(f"对比: A={url_a}")
    print(f"      B={url_b}")
    print(f"跳过内部表: {sorted(ignore)}\n")

    try:
        schema_a = _load_schema(url_a)
        schema_b = _load_schema(url_b)
    except Exception as e:
        print(f"❌ 连接失败: {e}", file=sys.stderr)
        return 2

    only_a, only_b = _diff_tables(schema_a, schema_b)
    only_a = [t for t in only_a if t not in ignore]
    only_b = [t for t in only_b if t not in ignore]

    print(f"A 表数: {len(schema_a)} | B 表数: {len(schema_b)}")
    diffs = _report_only_tables(only_a, only_b)

    common = sorted(set(schema_a) & set(schema_b))
    diffs += _report_table_diffs(common, schema_a, schema_b)

    print("")
    if diffs:
        print(f"⚠️  发现 {diffs} 类差异")
        return 1
    print("✅ 两库表结构完全一致（除内部表外）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

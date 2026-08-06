#!/usr/bin/env python3
"""DROP 无 model 残留表（2026-08-06 三方核验：全仓零引用 + 0 行数据）

背景（docs/reports/schema-cleanup-20260806.md 第四节 P2）：
8 张表（assets_3d / digital_human_profiles / knowledge_entries /
provider_api_keys / provider_listings / provider_settlements /
service_providers / support_tickets）为历史 create_all 残留：
  - 全仓（app/tests/scripts/web/flutter）零代码引用（仅 docs 报告提及）
  - 真实库 COUNT(*) 全为 0 行
保留它们会让 compare_db_schema.py / schema-compare CI 持续报"仅生产有"噪音。

用法:
  python scripts/drop_legacy_tables.py                # 默认 data/ihome.db
  python scripts/drop_legacy_tables.py --url sqlite:///path/to.db
  python scripts/drop_legacy_tables.py --dry-run      # 仅打印计划不执行
  DATABASE_URL=... python scripts/drop_legacy_tables.py

安全前置校验（不满足即拒绝 DROP）：
  1. 表必须存在
  2. 表必须 0 行（有数据 → 拒绝，防误删）
退出码: 0=全部 DROP 成功 / 1=部分失败或校验未过 / 2=连接或校验异常
"""
import argparse
import os
import sys

from sqlalchemy import create_engine, inspect, text

LEGACY_TABLES = (
    "assets_3d",
    "digital_human_profiles",
    "knowledge_entries",
    "provider_api_keys",
    "provider_listings",
    "provider_settlements",
    "service_providers",
    "support_tickets",
)


def _connect(url: str):
    # 与 scripts/compare_db_schema.py 一致：strip 异步驱动前缀
    clean = url.replace("+aiosqlite", "").replace("+asyncpg", "")
    return create_engine(clean)


def _verify_legacy(eng) -> tuple[list, list]:
    """返回 (可 DROP 的表, 校验失败的表)。

    失败原因：表不存在或行数 > 0（有数据拒绝 DROP，防误删）。
    """
    insp = inspect(eng)
    existing = set(insp.get_table_names())
    droppable: list = []
    failed: list = []
    for table in LEGACY_TABLES:
        if table not in existing:
            failed.append((table, "表不存在"))
            continue
        with eng.connect() as conn:
            rows = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        if rows:
            failed.append((table, f"仍有 {rows} 行数据，拒绝 DROP"))
            continue
        droppable.append(table)
    return droppable, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="DROP 无 model 残留表")
    parser.add_argument(
        "--url",
        default=os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./data/ihome.db"),
    )
    parser.add_argument("--dry-run", action="store_true", help="仅打印计划不执行")
    args = parser.parse_args()

    try:
        eng = _connect(args.url)
        droppable, failed = _verify_legacy(eng)
    except Exception as e:
        print(f"❌ 连接/校验失败: {e}", file=sys.stderr)
        return 2

    print(f"待清理残留表: {len(LEGACY_TABLES)} 张")
    print(f"  可 DROP（0 行）: {len(droppable)} 张: {droppable}")
    for table, reason in failed:
        print(f"  ⚠️ 跳过 {table}: {reason}")

    errors = 0
    if args.dry_run:
        print("（--dry-run，未执行任何 DROP）")
    else:
        with eng.begin() as conn:
            for table in droppable:
                try:
                    conn.execute(text(f"DROP TABLE {table}"))
                    print(f"  ✅ dropped: {table}")
                except Exception as e:
                    print(f"  ❌ drop 失败 {table}: {e}", file=sys.stderr)
                    errors += 1
    eng.dispose()
    return 1 if (errors or failed) else 0


if __name__ == "__main__":
    sys.exit(main())

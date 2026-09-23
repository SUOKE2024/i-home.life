#!/usr/bin/env python3
"""Schema drift 检查：对比 ORM model metadata 与数据库实际结构。

用途：
  - 生产/本地 DB 与 model 对齐核查（create_all 不补列/不补约束的隐性陷阱筛查）
  - alembic stamp head 前的预检（确认 DB 结构等价于 head 迁移状态）

用法:
  DATABASE_URL="postgresql+asyncpg://user:pass@host/db" python scripts/check_schema_drift.py
  DATABASE_URL="sqlite+aiosqlite:///./data/ihome.db" python scripts/check_schema_drift.py

退出码:
  0 = 对齐（仅可能有 prod 多余表）
  1 = 发现 drift（model 有表/列/CHECK 约束而 DB 缺）
"""
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import CheckConstraint, create_engine, inspect

# 项目根目录加入 sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

# 用 dotenv 加载 .env（避免 shell source 把 JSON 数组当字面量导致 pydantic 解析失败）
load_dotenv(os.path.join(_ROOT, ".env"))

from app.database import Base  # noqa: E402
import app.models  # noqa: E402,F401  加载所有模型注册到 Base.metadata


def compare_check_constraints(model_metadata, inspector, tables) -> list:
    """对比 model 声明与 DB 实际的 CHECK 约束 → [(表名, 缺失约束名列表)]。

    2026-09-23 生产实测：模型声明 174 条（37 张表），生产 PG 仅 32 条（13 张表），
    166 条从未落库——「受限枚举前端逐字对齐」在 DB 层没有兜底，越界值可写库
    （冒烟测试 room_type='balcony' 返回 201 而非 IntegrityError）。根因：旧表由
    create_all 建立时模型尚未声明约束，之后模型补约束未配套迁移。
    """
    diffs = []
    for t in sorted(tables):
        model_cons = {
            c.name
            for c in model_metadata.tables[t].constraints
            if isinstance(c, CheckConstraint) and isinstance(c.name, str)
        }
        if not model_cons:
            continue
        try:
            db_cons = {c["name"] for c in inspector.get_check_constraints(t)}
        except Exception:  # 方言不支持反射 → 无法判定，跳过
            continue
        missing = sorted(model_cons - db_cons)
        if missing:
            diffs.append((t, missing))
    return diffs


def main() -> int:
    url = os.environ.get("DATABASE_URL", "").replace("+aiosqlite", "").replace("+asyncpg", "")
    if not url:
        print("ERROR: DATABASE_URL 未设置", file=sys.stderr)
        return 2

    eng = create_engine(url)
    insp = inspect(eng)
    prod_tables = set(insp.get_table_names())
    model_tables = set(Base.metadata.tables.keys())

    # 忽略 alembic 版本表与内部表
    ignore_extra = {"alembic_version"}

    missing_in_prod = sorted(model_tables - prod_tables)
    extra_in_prod = sorted(t for t in (prod_tables - model_tables) if t not in ignore_extra)

    print(f"model 表数: {len(model_tables)} | DB 表数: {len(prod_tables)}")
    print(f"DB 缺失表（model 有 DB 无, {len(missing_in_prod)}）: {missing_in_prod}")
    print(f"DB 多余表（DB 有 model 无, {len(extra_in_prod)}）: {extra_in_prod}")

    col_diffs = []
    for t in sorted(model_tables & prod_tables):
        prod_cols = {c["name"]: c for c in insp.get_columns(t)}
        model_cols = {c.name: c for c in Base.metadata.tables[t].columns}
        only_model = sorted(set(model_cols) - set(prod_cols))
        only_prod = sorted(set(prod_cols) - set(model_cols))
        if only_model or only_prod:
            col_diffs.append((t, only_model, only_prod))

    print(f"\n列差异（{len(col_diffs)} 张表）:")
    for t, m, p in col_diffs:
        print(f"  {t}: 仅model有={m} 仅DB有={p}")

    con_diffs = compare_check_constraints(Base.metadata, insp, model_tables & prod_tables)
    print(f"\n缺失 CHECK 约束（{len(con_diffs)} 张表）:")
    for t, missing in con_diffs:
        print(f"  {t}: {missing}")

    drift = bool(missing_in_prod) or any(m for _, m, _ in col_diffs) or bool(con_diffs)
    if drift:
        print("\n⚠️  发现 schema drift（model 有而 DB 缺）")
        return 1
    print("\n✅ Schema 已对齐（model 定义的表/列/CHECK 约束在 DB 中均存在）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

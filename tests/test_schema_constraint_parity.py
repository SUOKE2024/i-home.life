"""CHECK 约束 model ↔ DB 对齐：迁移冻结清单与 drift 检查器守卫

背景（2026-09-23 v1.17.3 生产部署核查）：生产 PG 仅 32 条 CHECK 约束（13 表），
模型声明 174 条（37 表），166 条从未落库——受限枚举在 DB 层无兜底，越界值可写库。
根因：旧表由 create_all 建立时模型尚未声明约束，之后补约束未配套迁移。
本用例锁死两件事：① 回填迁移的冻结清单不得与模型漂移（改名/改表达式）；
② `scripts/check_schema_drift.py` 的约束对比能真的发现缺失（否则同类漂移再次静默）。
"""
import importlib.util
from pathlib import Path

from sqlalchemy import CheckConstraint, Column, MetaData, String, Table

from app.database import Base
import app.models  # noqa: F401  加载所有模型

_ROOT = Path(__file__).resolve().parent.parent


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MIGRATION = _load_module(
    _ROOT / "alembic" / "versions" / "b8c8d9e0f1a2_backfill_model_check_constraints.py",
    "backfill_check_constraints_migration",
)
_DRIFT = _load_module(_ROOT / "scripts" / "check_schema_drift.py", "check_schema_drift_module")


def test_backfill_migration_frozen_list_matches_models():
    """冻结清单每条 (表, 约束名, 表达式) 必须与模型声明逐字一致（防改名/表达式漂移）。"""
    entries = _MIGRATION._CONSTRAINTS
    assert len(entries) == 166, f"冻结清单条数变化需同步本断言，实为 {len(entries)}"

    drifted = []
    for table, name, sqltext in entries:
        model_table = Base.metadata.tables.get(table)
        if model_table is None:
            drifted.append((table, name, "模型已无该表"))
            continue
        model_sql = {
            c.name: str(c.sqltext)
            for c in model_table.constraints
            if isinstance(c, CheckConstraint)
        }
        if name not in model_sql:
            drifted.append((table, name, "模型已无该约束"))
        elif model_sql[name] != sqltext:
            drifted.append((table, name, f"表达式漂移: 模型={model_sql[name]}"))

    assert not drifted, f"冻结清单与模型不一致（须同步迁移）: {drifted[:5]}"


def test_compare_check_constraints_detects_missing():
    """drift 检查器必须能发现模型有、DB 无的 CHECK 约束。"""
    metadata = MetaData()
    Table(
        "demo_table",
        metadata,
        Column("status", String(20)),
        CheckConstraint("status IN ('a', 'b')", name="chk_demo_status"),
        CheckConstraint("status IS NOT NULL", name="chk_demo_not_null"),
    )

    class _FakeInspector:
        def __init__(self, existing):
            self._existing = existing

        def get_check_constraints(self, table):
            return [{"name": n} for n in self._existing.get(table, [])]

    inspector = _FakeInspector({"demo_table": ["chk_demo_status"]})
    diffs = _DRIFT.compare_check_constraints(metadata, inspector, {"demo_table"})
    assert diffs == [("demo_table", ["chk_demo_not_null"])]

    # DB 侧约束齐全时不报 drift（防误报）
    full = _FakeInspector({"demo_table": ["chk_demo_status", "chk_demo_not_null"]})
    assert _DRIFT.compare_check_constraints(metadata, full, {"demo_table"}) == []

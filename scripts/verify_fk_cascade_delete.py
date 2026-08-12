#!/usr/bin/env python3
"""验证 DELETE /api/projects 级联删除 budgets（启用 FK 约束复现生产行为）

生产错误：DELETE FROM projects 违反 budgets_project_id_fkey（FK 残留）。
本探针用 SQLite + PRAGMA foreign_keys=ON 复现，并验证 _cascade_delete_related
是否覆盖 budgets/budget_lines。
"""
import asyncio
import os
import sys
import uuid

# 确保能从项目根 import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_fk_probe.db"

import app.models  # noqa: F401,E402  确保全部模型注册到 Base.metadata
from sqlalchemy import event, select  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import Base  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.budget import Budget, BudgetLine  # noqa: E402
from app.models.user import User  # noqa: E402


async def main() -> None:
    db_path = "./data/test_fk_probe.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    engine = create_async_engine(os.environ["DATABASE_URL"])

    # 关键：启用 FK 约束（SQLite 默认 OFF，生产 PostgreSQL 默认 ON）
    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_conn, rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = sessionmaker(engine, class_=type("ASession", (), {}), expire_on_commit=False)
    from sqlalchemy.ext.asyncio import AsyncSession
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    db = Session()

    # ── 1. 创建用户 + 项目 + budget + budget_line（二级依赖）──
    db.add(User(id="probe-user", phone="13800000000", name="probe"))
    await db.flush()
    pid = str(uuid.uuid4())
    db.add(Project(id=pid, name="FK探针项目", total_area=100.0, owner_id="probe-user"))
    await db.flush()

    budget_id = str(uuid.uuid4())
    db.add(Budget(id=budget_id, project_id=pid, total_estimated=50000.0))
    await db.flush()

    line_id = str(uuid.uuid4())
    db.add(BudgetLine(id=line_id, budget_id=budget_id, category="硬装", name="水电", estimated_amount=20000.0))
    await db.commit()
    print(f"[1] 已创建 project={pid[:8]} budget={budget_id[:8]} budget_line={line_id[:8]}")

    # ── 2. 调用生产同款级联删除逻辑 ──
    from app.services.project_service import _cascade_delete_related, delete_project
    print("\n[2] 调用 _cascade_delete_related 级联删除...")
    await _cascade_delete_related(db, pid)
    await db.delete((await db.execute(select(Project).where(Project.id == pid))).scalar_one())
    await db.commit()

    # ── 3. 断言全部清空 ──
    b_count = (await db.execute(select(Budget).where(Budget.project_id == pid))).scalars().all()
    l_count = (await db.execute(select(BudgetLine).where(BudgetLine.budget_id == budget_id))).scalars().all()
    p_count = (await db.execute(select(Project).where(Project.id == pid))).scalars().all()
    print(f"    项目残留: {len(p_count)}  budget残留: {len(b_count)}  budget_line残留: {len(l_count)}")
    assert len(p_count) == 0 and len(b_count) == 0 and len(l_count) == 0, "级联删除不完整！"
    print("    ✅ 级联删除完整：projects/budgets/budget_lines 全部清空")

    await db.close()
    await engine.dispose()
    if os.path.exists(db_path):
        os.remove(db_path)
    print("\n✅ FK 探针验证通过：_cascade_delete_related 可正确级联删除 budgets/budget_lines")


if __name__ == "__main__":
    asyncio.run(main())

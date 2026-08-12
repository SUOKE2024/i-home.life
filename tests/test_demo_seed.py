"""演示登录 + 演示项目种子数据测试

覆盖场景（对应「一键演示登录 + 种子数据注入」功能）：
1. 一键演示登录：业主演示账号 13800138000 / 123456 经 /api/auth/login 换取 PASETO Token
2. 登录验证健壮性：错误密码 → 401
3. 种子数据幂等性：seed_demo_project 重复执行不重复注入
4. 种子数据完整性：各业务域行数 / 金额断言
5. 种子数据清理：clear_demo_project 全量删除 + 二次清理幂等
6. 种子数据可被首页 feed 正常组合（9 类卡片）

说明：scripts/ 非 Python 包，通过 importlib 按文件路径加载 scripts/seed_demo_data.py。
"""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.database import async_session
from app.models.budget import Budget, BudgetLine
from app.models.construction import ConstructionTask
from app.models.floorplan import FloorPlan
from app.models.procurement import OrderLine, ProcurementOrder
from app.models.progress_alert import MilestoneTracker, ProgressAlert
from app.models.project import Floor, Project, Room
from app.models.quality import QualityAssessment, QualityIssue
from app.models.settlement import Settlement, SettlementLine
from app.models.smart_home import SmartDevice, SmartHomeScheme
from app.models.user import User
from app.services.home_feed_service import build_feed_cards

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "seed_demo_data.py"
_spec = importlib.util.spec_from_file_location("seed_demo_data", _SCRIPT)
sdd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sdd)

DEMO_PHONE = "13800138000"
DEMO_PASSWORD = "123456"
DEMO_PROJECT_NAME = "云栖雅苑 · 智能整装"


@pytest.fixture(autouse=True)
def _skip_init_db(monkeypatch):
    """跳过 seed_demo_project 内部的 init_db 重复建表。

    conftest setup_db 已创建全量表（~13s），_ensure_base_data 已注入最小基础数据；
    此处 init_db 仅剩重复的 create_all 与提前返回，非被测对象（被测对象是演示
    项目种子逻辑），patch 掉可省每次 ~13s，避免全量测试显著变慢。
    """

    async def _noop_init_db() -> None:
        return None

    monkeypatch.setattr(sdd, "init_db", _noop_init_db)


# seed_demo_data.py 依赖的基础数据（init_db 首启会全量注入；测试用最小集替代，
# 使 init_db 因用户已存在而提前返回——与生产二次部署行为一致，避免 ~40s 目录种子耗时）
# 覆盖 3 个模拟项目全部引用的物料（对齐 init_db 首批数据 sku/价格/品牌）
_BASE_MATERIALS = [
    ("750×1500 大板砖", "FLR-001", "flooring", 198.0, "东鹏"),
    ("400×800 瓷片", "WLL-002", "wall", 88.0, "东鹏"),
    ("定制衣柜", "CF-001", "custom_furniture", 1280.0, "索菲亚"),
    ("强化复合地板", "FLR-003", "flooring", 158.0, "圣象"),
    ("净味乳胶漆", "WLL-001", "wall", 680.0, "立邦"),
    ("石膏板吊顶", "CEL-002", "ceiling", 95.0, "龙牌"),
    ("石英石台面", "KB-001", "kitchen_bath", 680.0, "中迅"),
    ("恒温花洒", "KB-003", "kitchen_bath", 1680.0, "高仪"),
    ("实木多层地板", "FLR-004", "flooring", 328.0, "大自然"),
    ("无纺布墙布", "WLL-004", "wall", 168.0, "欧雅"),
    ("台下盆洗手盆", "KB-002", "kitchen_bath", 580.0, "科勒"),
    ("LED无主灯", "SD-002", "soft_decor", 2680.0, "欧普"),
]
_BASE_SUPPLIERS = [
    ("东鹏瓷砖旗舰店", "flooring"),
    ("索菲亚衣柜", "custom_furniture"),
    ("圣象地板", "flooring"),
    ("立邦涂料", "wall"),
]


async def _ensure_base_data() -> None:
    """最小基础数据：演示业主 + seed 依赖的物料/供应商（对齐 init_db 首批数据）。"""
    from app.services.user_service import _hash_password

    from app.models.material import Material, MaterialCategory
    from app.models.procurement import Supplier

    async with async_session() as db:
        result = await db.execute(select(User).where(User.phone == DEMO_PHONE))
        if not result.scalar_one_or_none():
            db.add(User(
                phone=DEMO_PHONE,
                name="张先生",
                role="homeowner",
                hashed_password=_hash_password(DEMO_PASSWORD),
            ))

        cats = {c.code: c for c in (await db.execute(select(MaterialCategory))).scalars().all()}
        for code in ("flooring", "wall", "custom_furniture", "ceiling", "kitchen_bath", "soft_decor"):
            if code not in cats:
                cat = MaterialCategory(name=code, code=code, description="测试基础数据")
                db.add(cat)
                cats[code] = cat
        await db.flush()

        for name, sku, code, price, brand in _BASE_MATERIALS:
            exists = (await db.execute(select(Material).where(Material.sku == sku))).scalar_one_or_none()
            if not exists:
                db.add(Material(
                    category_id=cats[code].id, name=name, sku=sku,
                    unit="㎡", unit_price=price, brand=brand, is_active=True,
                ))
        for name, cat_code in _BASE_SUPPLIERS:
            exists = (await db.execute(select(Supplier).where(Supplier.name == name))).scalar_one_or_none()
            if not exists:
                db.add(Supplier(name=name, category=cat_code, rating=4.5))
        await db.commit()


async def _count_rows(model, **filters) -> int:
    """按过滤条件统计行数（仅用于演示数据断言）。"""
    async with async_session() as db:
        return (await db.execute(select(func.count()).select_from(model).where(*[
            getattr(model, k) == v for k, v in filters.items()
        ]))).scalar()


# ═══════════════════════════════════════════
# 一键演示登录（登录验证）
# ═══════════════════════════════════════════

async def test_demo_account_login(client):
    """一键演示登录：演示业主账号登录成功，返回 Token + 用户信息，Token 可访问 /me。"""
    await _ensure_base_data()
    resp = await client.post(
        "/api/auth/login",
        json={"phone": DEMO_PHONE, "password": DEMO_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("access_token"), "应返回 PASETO access_token"
    assert data["user"]["phone"] == DEMO_PHONE
    assert data["user"]["role"] == "homeowner"

    # 用返回的 Token 拉取 /api/auth/me 验证会话有效
    me = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["phone"] == DEMO_PHONE


async def test_demo_account_wrong_password(client):
    """登录验证健壮性：演示账号密码错误 → 401。"""
    await _ensure_base_data()
    resp = await client.post(
        "/api/auth/login",
        json={"phone": DEMO_PHONE, "password": "wrong-password"},
    )
    assert resp.status_code == 401


# ═══════════════════════════════════════════
# 种子数据幂等性
# ═══════════════════════════════════════════

async def test_seed_demo_project_idempotent():
    """幂等性：首次注入返回 True，二次执行返回 False，3 个演示项目各仅 1 个。"""
    await _ensure_base_data()
    assert await sdd.seed_demo_project() is True
    assert await sdd.seed_demo_project() is False
    assert await _count_rows(Project, name=DEMO_PROJECT_NAME) == 1
    # 3 个模拟项目全部注入且各仅 1 个
    assert len(sdd.DEMO_PROJECTS) == 3
    for spec in sdd.DEMO_PROJECTS:
        assert await _count_rows(Project, name=spec["name"]) == 1, spec["name"]


# ═══════════════════════════════════════════
# 种子数据完整性
# ═══════════════════════════════════════════

async def test_seed_demo_project_completeness():
    """完整性：演示项目各业务域行数 / 金额与 seed_demo_data.py 常量一致。"""
    await _ensure_base_data()
    assert await sdd.seed_demo_project() is True
    assert await _count_rows(Project, name=DEMO_PROJECT_NAME) == 1

    # 预算：1 条主记录 + 9 条明细，预估/实际金额与 BUDGET_LINES 汇总一致
    async with async_session() as db:
        project = (await db.execute(
            select(Project).where(Project.name == DEMO_PROJECT_NAME)
        )).scalar_one()
        pid = project.id
        assert project.status == "in_progress"
        assert project.phase == "construction"

        budget = (await db.execute(select(Budget).where(Budget.project_id == pid))).scalar_one()
        expected_estimated = round(
            sum(q * p for _, _, q, _, p, _ in sdd.BUDGET_LINES), 2
        )
        expected_actual = round(sum(a for _, _, _, _, _, a in sdd.BUDGET_LINES), 2)
        assert budget.total_estimated == expected_estimated
        assert budget.total_actual == expected_actual
        assert await _count_rows(BudgetLine, budget_id=budget.id) == len(sdd.BUDGET_LINES)

        # 预算单位符合真实装修计价：乳胶漆按「桶」计（18L/桶 ≈ 90㎡），数量 4 桶
        budget_lines = (await db.execute(
            select(BudgetLine).where(BudgetLine.budget_id == budget.id)
        )).scalars().all()
        paint = next((line for line in budget_lines if "乳胶漆" in line.name), None)
        assert paint is not None, "预算应含乳胶漆明细"
        assert paint.unit == "桶", f"乳胶漆单位应为桶，实际 {paint.unit}"
        assert paint.quantity == 4.0, f"乳胶漆应 4 桶（18L/桶≈90㎡），实际 {paint.quantity}"
        # 主卫仅 1 间 → 智能马桶 + 恒温花洒 1 套
        toilet = next((line for line in budget_lines if "智能马桶" in line.name), None)
        assert toilet is not None and toilet.quantity == 1.0
        # 无单位自动推断错误（不存在按「㎡」计价的乳胶漆行）
        assert all(line.unit != "㎡" or "乳胶漆" not in line.name for line in budget_lines)

        # 施工任务 7 条（带前置依赖：至少 1 条有 predecessor）
        tasks = (await db.execute(
            select(ConstructionTask).where(ConstructionTask.project_id == pid)
        )).scalars().all()
        assert len(tasks) == len(sdd.CONSTRUCTION_TASKS)
        assert any(t.predecessor_id for t in tasks)

        # 里程碑 5 条 / 预警 3 条
        assert await _count_rows(MilestoneTracker, project_id=pid) == len(sdd.MILESTONES)
        assert await _count_rows(ProgressAlert, project_id=pid) == len(sdd.ALERTS)
        # 未解决预警（供 Dashboard 健康分估算）为 2 条
        active_alerts = (await db.execute(
            select(ProgressAlert).where(
                ProgressAlert.project_id == pid, ProgressAlert.status == "active"
            )
        )).scalars().all()
        assert len(active_alerts) == 2

        # 质检：问题 2 条 + 评估 1 条
        assert await _count_rows(QualityIssue, project_id=pid) == len(sdd.QUALITY_ISSUES)
        assert await _count_rows(QualityAssessment, project_id=pid) == 1

        # 采购：2 订单（东鹏已送达 + 索菲亚在途），明细 3 条
        orders = (await db.execute(
            select(ProcurementOrder).where(ProcurementOrder.project_id == pid)
        )).scalars().all()
        assert len(orders) == len(sdd.PROCUREMENT_ORDERS)
        order_ids = [o.id for o in orders]
        order_lines = (await db.execute(
            select(OrderLine).where(OrderLine.order_id.in_(order_ids))
        )).scalars().all()
        assert len(order_lines) == sum(len(lines) for *_, lines in sdd.PROCUREMENT_ORDERS)

        # 结算：1 条 + 4 条明细
        assert await _count_rows(Settlement, project_id=pid) == 1
        settlement = (await db.execute(
            select(Settlement).where(Settlement.project_id == pid)
        )).scalar_one()
        assert settlement.contract_amount == expected_estimated
        assert await _count_rows(SettlementLine, settlement_id=settlement.id) == 4

        # 智能家居：3 方案 + 8 设备
        schemes = (await db.execute(
            select(SmartHomeScheme).where(SmartHomeScheme.project_id == pid)
        )).scalars().all()
        assert len(schemes) == len(sdd.SMART_HOME_SCHEMES)
        scheme_ids = [s.id for s in schemes]
        devices = (await db.execute(
            select(SmartDevice).where(SmartDevice.scheme_id.in_(scheme_ids))
        )).scalars().all()
        assert len(devices) == sum(len(d) for *_, d in sdd.SMART_HOME_SCHEMES)

        # 户型：1 张激活户型 + 1 楼层 + 6 房间
        assert await _count_rows(FloorPlan, project_id=pid) == 1
        assert await _count_rows(Floor, project_id=pid) == 1
        floor = (await db.execute(select(Floor).where(Floor.project_id == pid))).scalar_one()
        assert await _count_rows(Room, floor_id=floor.id) == 6


# ═══════════════════════════════════════════
# 种子数据清理
# ═══════════════════════════════════════════

async def test_seed_demo_project_clear():
    """清理：clear_demo_project 删除演示项目及其全部关联数据，二次清理幂等返回 False。"""
    await _ensure_base_data()
    assert await sdd.seed_demo_project() is True
    assert await sdd.clear_demo_project() is True

    assert await _count_rows(Project, name=DEMO_PROJECT_NAME) == 0
    # 关联业务域全部清空（演示数据不残留）
    for model in (
        Budget, ConstructionTask, FloorPlan, MilestoneTracker, ProgressAlert,
        QualityIssue, QualityAssessment, ProcurementOrder, Settlement, SmartHomeScheme,
    ):
        assert await _count_rows(model) == 0, f"{model.__name__} 应有 0 行"

    # 二次清理：项目已不存在 → 返回 False
    assert await sdd.clear_demo_project() is False


# ═══════════════════════════════════════════
# 种子数据与首页 feed 联通
# ═══════════════════════════════════════════

async def test_seed_demo_project_feed_cards():
    """联通性：注入后首页 feed 可组合出全部 8 类卡片（预警 2 张共 9 张）。"""
    await _ensure_base_data()
    assert await sdd.seed_demo_project() is True
    async with async_session() as db:
        project = (await db.execute(
            select(Project).where(Project.name == DEMO_PROJECT_NAME)
        )).scalar_one()
        cards = await build_feed_cards(db, project.id)
    card_types = [c.get("type") for c in cards]
    assert len(cards) == 9
    for expected in (
        "alert_card", "design_plan", "construction_progress", "budget_breakdown",
        "procurement_order", "qa_report", "settlement_summary", "material_card",
    ):
        assert expected in card_types, f"feed 缺少卡片类型 {expected}"


# ═══════════════════════════════════════════
# 预算计算边界场景
# ═══════════════════════════════════════════

async def _demo_owner_id() -> str:
    async with async_session() as db:
        user = (await db.execute(select(User).where(User.phone == DEMO_PHONE))).scalar_one()
        return str(user.id)


async def _make_project(owner_id: str, name: str) -> str:
    async with async_session() as db:
        project = Project(name=name, owner_id=owner_id, status="draft", phase="design")
        db.add(project)
        await db.commit()
        return str(project.id)


async def test_seed_budget_large_scale_performance(db_session):
    """极端数据量：1000 行预算明细下 _seed_budget 耗时可控（性能回归哨兵 <5s），金额正确。"""
    import time

    await _ensure_base_data()
    owner_id = await _demo_owner_id()
    project_id = await _make_project(owner_id, "性能基准测试项目")
    spec = {
        "budget_lines": [
            ("测试", f"物料{i:04d}", 10.0, "㎡", 100.0, 0.0) for i in range(1000)
        ],
        "budget_status": "approved",
        "budget_created_days_ago": 10,
    }
    t0 = time.perf_counter()
    estimated, actual = await sdd._seed_budget(db_session, project_id, spec)
    elapsed = time.perf_counter() - t0

    assert estimated == 1000 * 10 * 100.0, "1000 行 × 10㎡ × ¥100 = ¥1,000,000"
    assert actual == 0.0
    assert await _count_rows(BudgetLine, budget_id=(await db_session.execute(
        select(Budget).where(Budget.project_id == project_id)
    )).scalar_one().id) == 1000
    assert elapsed < 5.0, f"1000 行预算计算耗时 {elapsed:.2f}s 超过性能哨兵 5s"


async def test_seed_budget_empty_lines(db_session):
    """边界：空预算明细不崩溃，生成 0 总额预算。"""
    await _ensure_base_data()
    owner_id = await _demo_owner_id()
    project_id = await _make_project(owner_id, "空预算测试项目")
    spec = {"budget_lines": [], "budget_status": "draft", "budget_created_days_ago": 5}
    estimated, actual = await sdd._seed_budget(db_session, project_id, spec)
    assert estimated == 0.0 and actual == 0.0
    budget = (await db_session.execute(
        select(Budget).where(Budget.project_id == project_id)
    )).scalar_one()
    assert budget.total_estimated == 0.0 and budget.status == "draft"


async def test_seed_budget_extreme_amount(db_session):
    """边界：超大数量×单价不溢出，金额按浮点精确计算（Python float 无溢出风险）。"""
    await _ensure_base_data()
    owner_id = await _demo_owner_id()
    project_id = await _make_project(owner_id, "超大金额测试项目")
    spec = {
        "budget_lines": [("测试", "超大项", 1e6, "㎡", 1e6, 0.0)],
        "budget_status": "approved",
        "budget_created_days_ago": 5,
    }
    estimated, _ = await sdd._seed_budget(db_session, project_id, spec)
    assert estimated == 1e12, f"1e6 × 1e6 应等于 1e12，实际 {estimated}"


async def test_seed_material_missing_raises(db_session):
    """边界：引用了不存在的物料 → _material_id 抛 RuntimeError（诚实报错而非静默写入）。"""
    import pytest

    with pytest.raises(RuntimeError, match="物料不存在"):
        await sdd._material_id(db_session, "不存在的物料 XYZ")

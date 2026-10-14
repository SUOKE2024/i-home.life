"""公开内容新鲜度（「长草」）监测测试（v1.18.0）

借鉴来源：数智前线《万小智，让AI从网站生成走向企业经营》（2026-09-24）——
「一忙起来内容就有点顾不上，网站很容易长草」。

覆盖：
- 衰减与状态阈值（确定性，无 LLM）
- 数据源统计（项目 / 空间资产 / 已发布产品；草稿不计入对外内容）
- 无数据源如实记 insufficient_data，不因缺数据判不合格
- 只提示更新不代写（disclaimer / limitations）
- 端点鉴权 / 权限 / flag 关闭 503
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.services.content_freshness_service import (
    AGING_THRESHOLD,
    FRESH_THRESHOLD,
    _state_for,
    compute_content_freshness,
    decay_factor,
)

from tests.test_ai_visibility import _auth_headers_for, _seed_user

BJ = timezone(timedelta(hours=8))


def _days_ago(days: float) -> datetime:
    return datetime.now(BJ) - timedelta(days=days)


class TestDecay:
    def test_decay_curve(self):
        assert decay_factor(0, 30) == 1.0
        assert decay_factor(30, 30) == pytest.approx(0.5)
        assert decay_factor(60, 30) == pytest.approx(0.25)
        assert decay_factor(90, 30) == pytest.approx(0.125)

    def test_decay_guards(self):
        assert decay_factor(-5, 30) == 1.0          # 未来时间不放大
        assert decay_factor(10, 0) == 1.0           # 非法半衰期不崩
        assert decay_factor(10, -1) == 1.0

    def test_state_thresholds(self):
        assert _state_for(FRESH_THRESHOLD) == "fresh"
        assert _state_for(AGING_THRESHOLD) == "aging"
        assert _state_for(AGING_THRESHOLD - 0.01) == "stale"


async def _seed_project(user_id: str, name: str, age_days: float) -> str:
    from app.database import async_session
    from app.models.project import Project

    pid = str(uuid.uuid4())
    async with async_session() as db:
        db.add(Project(id=pid, name=name, owner_id=user_id, updated_at=_days_ago(age_days)))
        await db.commit()
    return pid


async def _seed_space_asset(user_id: str, name: str, age_days: float) -> str:
    from app.database import async_session
    from app.models.space_asset import SpaceAsset

    aid = str(uuid.uuid4())
    async with async_session() as db:
        db.add(SpaceAsset(id=aid, name=name, owner_id=user_id, asset_holder="某康养运营公司",
                          updated_at=_days_ago(age_days)))
        await db.commit()
    return aid


async def _seed_supplier() -> str:
    from app.database import async_session
    from app.models.procurement import Supplier

    sid = str(uuid.uuid4())
    async with async_session() as db:
        db.add(Supplier(id=sid, name=f"供应商{sid[:6]}", category="tile"))
        await db.commit()
    return sid


async def _seed_product(user_id: str, supplier_id: str, name: str, status: str, age_days: float) -> str:
    from app.database import async_session
    from app.models.product import Product

    pid = str(uuid.uuid4())
    async with async_session() as db:
        db.add(Product(id=pid, user_id=user_id, supplier_id=supplier_id, name=name,
                       status=status, updated_at=_days_ago(age_days)))
        await db.commit()
    return pid


class TestComputeFreshness:
    @pytest.mark.asyncio
    async def test_classifies_by_age(self, db_session):
        user_id = await _seed_user(name="新鲜度用户")
        await _seed_project(user_id, "陈旧项目", age_days=90)     # 0.125 → stale
        await _seed_project(user_id, "新鲜项目", age_days=1)      # ~0.977 → fresh
        await _seed_space_asset(user_id, "老化资产", age_days=45)  # 0.354 → aging

        report = await compute_content_freshness(db_session, now=datetime.now(BJ))
        by_key = {s["key"]: s for s in report["sources"]}

        assert by_key["projects"]["total"] == 2
        assert by_key["projects"]["fresh"] == 1
        assert by_key["projects"]["stale"] == 1
        assert by_key["space_assets"]["aging"] == 1
        assert report["summary"]["stale"] == 1
        assert report["summary"]["stale_ratio"] is not None

    @pytest.mark.asyncio
    async def test_stale_items_ranked_high_priority(self, db_session):
        user_id = await _seed_user()
        await _seed_project(user_id, "很旧的项目", age_days=200)
        report = await compute_content_freshness(db_session, now=datetime.now(BJ))
        top = [i for i in report["priority_items"] if i["type"] == "projects"]
        assert top and top[0]["state"] == "stale"
        assert top[0]["priority"] == "high"
        assert top[0]["age_days"] >= 199

    @pytest.mark.asyncio
    async def test_draft_product_excluded_from_public_content(self, db_session):
        user_id = await _seed_user()
        supplier_id = await _seed_supplier()

        report = await compute_content_freshness(db_session, now=datetime.now(BJ))
        assert next(s for s in report["sources"] if s["key"] == "products")["status"] == "insufficient_data"

        await _seed_product(user_id, supplier_id, "草稿产品", status="draft", age_days=300)
        report = await compute_content_freshness(db_session, now=datetime.now(BJ))
        products = next(s for s in report["sources"] if s["key"] == "products")
        assert products["status"] == "insufficient_data", "草稿不计入对外内容"

        await _seed_product(user_id, supplier_id, "已发布产品", status="published", age_days=300)
        report = await compute_content_freshness(db_session, now=datetime.now(BJ))
        products = next(s for s in report["sources"] if s["key"] == "products")
        assert products["status"] == "ok"
        assert products["total"] == 1

    @pytest.mark.asyncio
    async def test_insufficient_data_is_honest_not_failure(self, db_session):
        report = await compute_content_freshness(db_session, now=datetime.now(BJ))
        empty = [s for s in report["sources"] if s["status"] == "insufficient_data"]
        assert empty, "无数据源应如实标注"
        for s in empty:
            assert "不据此判为内容不合格" in s["note"]
            assert s["total"] == 0 and s["items"] == []
        assert report["summary"]["stale_ratio"] is None
        assert "insufficient_data" not in str(report["summary"]["stale"])

    @pytest.mark.asyncio
    async def test_half_life_parameter_reused(self, db_session, monkeypatch):
        monkeypatch.setattr(get_settings(), "memory_decay_half_life_days", 7.0)
        report = await compute_content_freshness(db_session, now=datetime.now(BJ))
        assert report["half_life_days"] == 7.0

    @pytest.mark.asyncio
    async def test_no_auto_rewrite_disclaimer(self, db_session):
        report = await compute_content_freshness(db_session, now=datetime.now(BJ))
        assert "不代写" in report["disclaimer"]
        assert any("只出清单不代写" in x for x in report["limitations"])
        assert report["method"] == "deterministic_exponential_decay_on_updated_at"


class TestFreshnessEndpoint:
    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/content-freshness")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_forbidden_for_non_admin(self, client: AsyncClient):
        user_id = await _seed_user()
        resp = await client.get("/api/content-freshness", headers=_auth_headers_for(user_id))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_ok(self, client: AsyncClient):
        user_id = await _seed_user(role="admin", name="新鲜度管理员")
        resp = await client.get("/api/content-freshness", headers=_auth_headers_for(user_id, "admin"))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["disclaimer"] and body["sources"]

    @pytest.mark.asyncio
    async def test_flag_off_503(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(get_settings(), "content_freshness_monitor_enabled", False)
        user_id = await _seed_user(role="admin")
        resp = await client.get("/api/content-freshness", headers=_auth_headers_for(user_id, "admin"))
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_invalid_half_life_422(self, client: AsyncClient):
        user_id = await _seed_user(role="admin")
        resp = await client.get("/api/content-freshness?half_life_days=0",
                                headers=_auth_headers_for(user_id, "admin"))
        assert resp.status_code == 422

"""自进化周期生产触发测试（v1.14.1，2026-08-16 全景评估 P0 修复）

背景：distill_skill_from_cases / evaluate_skill_quality 此前在生产代码零调用方
（孤岛函数），蒸馏出的 DRAFT Skill 永远无法晋升 ACTIVE 进入注入链。
v1.14.1 新增 run_skill_evolution_cycle + GET /api/admin/skill-evolution 生产触发方。

覆盖：
- run_skill_evolution_cycle：蒸馏新 Skill / 合并已有 / DRAFT 晋升 / 低质 archive /
  flag 关闭诚实降级（skipped_reasons）
- get_skill_for_injection：DRAFT 试用期回退（无 ACTIVE 时）打破晋升死锁
- API：/api/admin/skill-evolution 非平台管理员 403 / 管理员 200 报告结构完整

测试隔离：monkeypatch.setattr(get_settings(), "flag", value)，teardown 自动还原
"""
import json
import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.models.agent_case import AgentCase
from app.models.agent_skill import AgentSkill, STATUS_DRAFT, STATUS_ACTIVE
from app.services.agent_skill_evolution_service import (
    get_skill_for_injection, run_skill_evolution_cycle,
)

_MOCK_SKILL_JSON = json.dumps({
    "name": "design_living_room",
    "description": "客厅设计 Skill",
    "system_prompt": "你是客厅设计师，步骤：1.确认风格 2.选材 3.预算",
    "tools": ["get_material_list"],
    "acceptance_criteria": [{"input": "北欧风", "expected": "返回方案"}],
})


def _seed_cases(db, *, count: int = 4, agent: str = "designer", owner: str = "u1",
                quality: float = 0.8, prefix: str = "cyc") -> None:
    for i in range(count):
        db.add(AgentCase(
            id=f"{prefix}_{uuid.uuid4().hex[:8]}",
            scope="personal", owner_id=owner, agent_name=agent,
            task_intent=f"设计客厅方案{i}", approach="[]", outcome="success",
            quality_score=quality, created_by=owner,
        ))


# ── run_skill_evolution_cycle ──


@pytest.mark.asyncio
async def test_cycle_distills_new_skill(db_session, monkeypatch):
    """达到阈值的 Case 簇 → 蒸馏新 DRAFT Skill，报告计入 distilled_new"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    _seed_cases(db_session, count=4)

    async def fake_chat(self, messages, **kwargs):
        return _MOCK_SKILL_JSON

    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        report = await run_skill_evolution_cycle(db_session)

    assert report["clusters_found"] == 1
    assert len(report["distilled_new"]) == 1
    assert report["distilled_new"][0]["name"] == "design_living_room"
    assert report["merged_existing"] == []
    # 二次运行：Case 已回写 distilled_to_skill_id，不再发现簇
    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        report2 = await run_skill_evolution_cycle(db_session)
    assert report2["clusters_found"] == 0


@pytest.mark.asyncio
async def test_cycle_merges_into_existing_skill(db_session, monkeypatch):
    """已存在同名 Skill → 合并不新建，报告计入 merged_existing"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    db_session.add(AgentSkill(
        id="merge_sk", name="design_living_room", owner_scope="personal", owner_id="u1",
        agent_name="designer", system_prompt="existing", status=STATUS_ACTIVE,
        created_by="u1",
    ))
    _seed_cases(db_session, count=4)
    await db_session.flush()

    async def fake_chat(self, messages, **kwargs):
        return _MOCK_SKILL_JSON

    with patch("app.agents.base.BaseAgent._chat", fake_chat):
        report = await run_skill_evolution_cycle(db_session)

    assert report["distilled_new"] == []
    assert len(report["merged_existing"]) == 1
    assert report["merged_existing"][0]["skill_id"] == "merge_sk"


@pytest.mark.asyncio
async def test_cycle_promotes_draft_and_archives_low_quality(db_session, monkeypatch):
    """质控：total>=3 且 overall>=0.6 的 DRAFT 晋升 ACTIVE；低质 Skill archive"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", True)
    # 高成功 DRAFT：3 成功 0 失败 → overall≈0.79 → 晋升
    db_session.add(AgentSkill(
        id="promote_sk", name="good_skill", owner_scope="personal", owner_id="u2",
        agent_name="designer", system_prompt="p", status=STATUS_DRAFT,
        success_count=3, fail_count=0, created_by="u2",
    ))
    # 低质 ACTIVE：1 成功 5 失败 → overall<0.3 → archive
    db_session.add(AgentSkill(
        id="archive_sk", name="bad_skill", owner_scope="personal", owner_id="u2",
        agent_name="designer", system_prompt="a", status=STATUS_ACTIVE,
        success_count=1, fail_count=5, created_by="u2",
    ))
    await db_session.flush()

    report = await run_skill_evolution_cycle(db_session)

    assert report["evaluated"] == 2
    promoted_ids = [p["skill_id"] for p in report["promoted_draft_to_active"]]
    archived_ids = [a["skill_id"] for a in report["archived_low_quality"]]
    assert "promote_sk" in promoted_ids
    assert "archive_sk" in archived_ids


@pytest.mark.asyncio
async def test_cycle_flags_off_honest_degradation(db_session, monkeypatch):
    """两 flag 全关 → 跳过蒸馏与质控，skipped_reasons 诚实标注"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", False)
    monkeypatch.setattr(get_settings(), "agent_skill_evolution_enabled", False)
    _seed_cases(db_session, count=4)

    report = await run_skill_evolution_cycle(db_session)

    assert report["clusters_found"] == 0
    assert report["distilled_new"] == []
    assert report["evaluated"] == 0
    assert len(report["skipped_reasons"]) == 2
    assert report["distillation_enabled"] is False
    assert report["evolution_enabled"] is False


@pytest.mark.asyncio
async def test_cycle_below_threshold_no_cluster(db_session, monkeypatch):
    """Case 不足阈值 → clusters_found=0，无蒸馏"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    _seed_cases(db_session, count=2)  # < 3

    report = await run_skill_evolution_cycle(db_session)
    assert report["clusters_found"] == 0
    assert report["distilled_new"] == []


# ── DRAFT 试用期注入回退 ──


@pytest.mark.asyncio
async def test_injection_draft_fallback_when_no_active(db_session, monkeypatch):
    """无 ACTIVE → 回退 DRAFT（打破晋升死锁）；有 ACTIVE → 优先 ACTIVE"""
    monkeypatch.setattr(get_settings(), "agent_skill_distillation_enabled", True)
    db_session.add(AgentSkill(
        id="draft_sk", name="draft_skill", owner_scope="personal", owner_id="u3",
        agent_name="kitchen", system_prompt="d", status=STATUS_DRAFT, created_by="u3",
    ))
    await db_session.flush()

    skill = await get_skill_for_injection(
        db_session, agent_name="kitchen", owner_id="u3",
    )
    assert skill is not None and skill.id == "draft_sk"  # DRAFT 回退生效

    # 加入 ACTIVE 后优先 ACTIVE
    db_session.add(AgentSkill(
        id="active_sk", name="active_skill", owner_scope="personal", owner_id="u3",
        agent_name="kitchen", system_prompt="a", status=STATUS_ACTIVE, created_by="u3",
    ))
    await db_session.flush()
    skill2 = await get_skill_for_injection(
        db_session, agent_name="kitchen", owner_id="u3",
    )
    assert skill2 is not None and skill2.id == "active_sk"


# ── API 端点 ──


@pytest.mark.asyncio
async def test_skill_evolution_endpoint_requires_platform_admin(
    client: AsyncClient, auth_headers: dict,
):
    """非平台管理员访问 /api/admin/skill-evolution 返回 403"""
    resp = await client.get("/api/admin/skill-evolution", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_skill_evolution_endpoint_admin_report(client: AsyncClient):
    """平台管理员获得结构化周期报告（空库基线：字段齐全 + 上限标注）"""
    from app.auth.paseto_handler import create_token
    from app.database import async_session
    from app.models.user import User

    user_id = str(uuid.uuid4())
    async with async_session() as db:
        db.add(User(
            id=user_id, phone=f"139{uuid.uuid4().hex[:8]}", name="进化管理员",
            role="admin", hashed_password="x",
        ))
        await db.commit()
    headers = {"Authorization": f"Bearer {create_token(user_id, 'admin')}"}

    resp = await client.get("/api/admin/skill-evolution", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["cycle"] == "skill_evolution"
    for key in ("clusters_found", "distilled_new", "merged_existing", "evaluated",
                "promoted_draft_to_active", "archived_low_quality", "limits",
                "skipped_reasons"):
        assert key in data
    assert data["limits"]["max_clusters"] > 0

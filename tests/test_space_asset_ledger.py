"""空间资产台账测试（Phase 3，2026-09-13）

覆盖：
- 健康声明合规闸门（prohibited 阻断 / caution 附加免责 / 否定语境豁免 / flag 关闭）
- CareAgent 输出过闸门
- 空间资产台账 CRUD + 轻资产约束 + 状态机 + 就绪度评分 + 汇总
- API 端点鉴权与归属校验
"""
import pytest
from httpx import AsyncClient

from app.config import get_settings


# ════════════════════════════════════════════════════════════════
# Phase 0：健康声明合规
# ════════════════════════════════════════════════════════════════


class TestHealthClaimCompliance:
    def test_prohibited_blocked(self):
        from app.services.health_claim_compliance import ensure_health_claim_compliance

        r = ensure_health_claim_compliance("本康养空间可治疗高血压、降血糖。")
        assert r["blocked"] is True
        assert r["compliant"] is False
        assert r["text"] == ""
        assert "治疗" in r["blocked_reason"]

    def test_caution_appends_disclaimer(self):
        from app.services.health_claim_compliance import (
            STANDARD_HEALTH_DISCLAIMER, ensure_health_claim_compliance,
        )

        r = ensure_health_claim_compliance("药膳小院提供节气调理与祛湿服务。")
        assert r["blocked"] is False
        assert r["compliant"] is True
        assert STANDARD_HEALTH_DISCLAIMER in r["text"]

    def test_clean_text_unchanged(self):
        from app.services.health_claim_compliance import ensure_health_claim_compliance

        text = "该空间照度 300 lux，色温 3000K，噪声低于 35dB。"
        r = ensure_health_claim_compliance(text)
        assert r["text"] == text
        assert r["claims"] == []

    def test_negation_context_not_flagged(self):
        from app.services.health_claim_compliance import scan_health_claims

        text = "本服务不具治疗、调理功效，不替代药物或医师建议。"
        assert scan_health_claims(text) == []

    def test_standard_disclaimer_not_self_flagged(self):
        from app.services.health_claim_compliance import (
            STANDARD_HEALTH_DISCLAIMER, scan_health_claims,
        )

        assert scan_health_claims(STANDARD_HEALTH_DISCLAIMER) == []

    def test_gate_disabled_honest(self, monkeypatch):
        from app.services.health_claim_compliance import ensure_health_claim_compliance

        monkeypatch.setattr(get_settings(), "health_claim_compliance_enabled", False)
        r = ensure_health_claim_compliance("可治疗高血压")
        assert r["gate_enabled"] is False
        assert r["text"] == "可治疗高血压"
        assert "未执行合规校验" in r["blocked_reason"]

    def test_care_agent_blocks_prohibited_reply(self):
        from app.agents.care import CareAgent

        out = CareAgent.apply_claim_compliance("该方案可治疗失眠并根治高血压。")
        assert "已按合规口径拦截" in out
        assert "治疗失眠" not in out

    def test_care_agent_passes_clean_reply(self):
        from app.agents.care import CareAgent

        out = CareAgent.apply_claim_compliance("已联动起夜照明并通知家属。")
        assert out == "已联动起夜照明并通知家属。"


# ════════════════════════════════════════════════════════════════
# Phase 3：空间资产台账（service 层）
# ════════════════════════════════════════════════════════════════


def test_smart_readiness_scoring():
    from app.services.space_asset_service import compute_smart_readiness

    score, breakdown = compute_smart_readiness(
        matter_device_count=10, sensor_count=10, scene_automation_count=5,
        accessibility_status="pass", fire_safety_status="pass",
    )
    assert score == 100.0
    assert breakdown["device_access"]["score"] == 30.0
    assert breakdown["compliance"]["score"] == 20.0


def test_smart_readiness_zero_when_no_data():
    from app.services.space_asset_service import compute_smart_readiness

    score, breakdown = compute_smart_readiness()
    assert score == 0.0
    assert breakdown["device_access"]["count"] == 0


def test_light_asset_holder_constraint():
    from app.services.space_asset_service import _validate_holder

    with pytest.raises(ValueError, match="轻资产改造服务商"):
        _validate_holder("索克家居（昆明）有限公司")
    with pytest.raises(ValueError, match="不能为空"):
        _validate_holder("   ")
    _validate_holder("云南某文旅集团")  # 外部主体，通过


# ════════════════════════════════════════════════════════════════
# Phase 3：API 端点
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_space_assets_requires_auth(client: AsyncClient):
    resp = await client.get("/api/space-assets")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_enums_aligned_with_suoke(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/space-assets/enums", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # 业态对齐索克生活 lodge_manager_registration _lodgeTypes
    for fmt in ("herb_food_courtyard", "forest_herbal_bath", "kangyang_study", "seasonal_stay"):
        assert fmt in data["business_formats"]
    assert data["platform_role"] == "service_provider"


@pytest.mark.asyncio
async def test_create_asset_ok(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/space-assets",
        json={
            "name": "昆明·药膳小院 A",
            "asset_holder": "云南某文旅集团",
            "asset_category": "kangyang",
            "business_format": "herb_food_courtyard",
            "holder_type": "enterprise",
            "city": "昆明市",
            "building_area_sqm": 320.0,
            "matter_device_count": 8,
            "sensor_count": 6,
            "scene_automation_count": 3,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["platform_role"] == "service_provider"
    assert data["renovation_status"] == "pending_assessment"
    assert data["smart_readiness_score"] > 0


@pytest.mark.asyncio
async def test_create_asset_rejects_platform_holder(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/space-assets",
        json={"name": "自持资产", "asset_holder": "索克家居（昆明）联合科技有限责任公司"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_status_transition_and_illegal(client: AsyncClient, auth_headers: dict):
    created = await client.post(
        "/api/space-assets",
        json={"name": "大理·节气旅居 B", "asset_holder": "大理某合作社",
              "asset_category": "travel_residence", "business_format": "seasonal_stay",
              "holder_type": "collective", "city": "大理市"},
        headers=auth_headers,
    )
    asset_id = created.json()["id"]

    ok = await client.post(
        f"/api/space-assets/{asset_id}/status",
        json={"new_status": "assessed"}, headers=auth_headers,
    )
    assert ok.status_code == 200
    assert ok.json()["renovation_status"] == "assessed"

    # 非法跳跃：assessed → operating（必须经 in_renovation → delivered）
    bad = await client.post(
        f"/api/space-assets/{asset_id}/status",
        json={"new_status": "operating"}, headers=auth_headers,
    )
    assert bad.status_code == 409
    assert "非法流转" in bad.json()["detail"]


@pytest.mark.asyncio
async def test_readiness_breakdown(client: AsyncClient, auth_headers: dict):
    created = await client.post(
        "/api/space-assets",
        json={"name": "丽江·森林药浴 C", "asset_holder": "丽江某企业",
              "business_format": "forest_herbal_bath", "matter_device_count": 10,
              "sensor_count": 10, "scene_automation_count": 5,
              "accessibility_status": "pass", "fire_safety_status": "pass"},
        headers=auth_headers,
    )
    asset_id = created.json()["id"]
    resp = await client.get(f"/api/space-assets/{asset_id}/readiness", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 100.0
    assert data["smart_ready"] is True
    assert set(data["breakdown"]) == {
        "device_access", "environment_sensing", "scene_automation", "compliance"
    }


@pytest.mark.asyncio
async def test_summary_isolated_by_owner(client: AsyncClient, auth_headers: dict):
    await client.post(
        "/api/space-assets",
        json={"name": "汇总测试资产", "asset_holder": "某外部业主", "city": "昆明市"},
        headers=auth_headers,
    )
    resp = await client.get("/api/space-assets/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_assets"] >= 1
    assert data["platform_role"] == "service_provider"
    assert "轻资产" in data["note"]


@pytest.mark.asyncio
async def test_summary_all_owners_forbidden_for_non_admin(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/space-assets/summary?all_owners=true", headers=auth_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_space_assets_flag_off_503(client: AsyncClient, auth_headers: dict, monkeypatch):
    monkeypatch.setattr(get_settings(), "space_asset_ledger_enabled", False)
    resp = await client.get("/api/space-assets", headers=auth_headers)
    assert resp.status_code == 503

"""AI 应用服务商培育政策落地测试（v1.17.4）

政策依据：工信厅科函〔2026〕414号《关于开展人工智能应用服务商培育专项行动的通知》。
评估报告：docs/frontier-borrowing-2026-09-23-ai-service-provider.md

覆盖：
- P0 服务商能力档案（确定性证据核验 / 不复用重复治理实现 / 不自评成熟度等级 / 端点鉴权）
- P1 Token 计量口径（聚合 / 仅计量非计费 / 数据源不可用诚实标注 / 端点鉴权与归属）
- P2 FDE 现场服务记录（CRUD / 枚举契约 / capability_tags 不硬凑四维 / 归属隔离）
"""
import uuid

import pytest
from httpx import AsyncClient

from app.config import get_settings


def _auth_headers_for(user_id: str, role: str = "user") -> dict:
    from app.auth.paseto_handler import create_token
    return {"Authorization": f"Bearer {create_token(user_id, role)}"}


async def _seed_user(role: str = "user", name: str = "政策测试用户") -> str:
    """直接落库一个用户并返回 id（绕过注册流程，便于固定 user_id 关联轨迹）。"""
    from app.database import async_session
    from app.models.user import User

    user_id = str(uuid.uuid4())
    async with async_session() as db:
        db.add(User(
            id=user_id, phone=f"137{uuid.uuid4().hex[:8]}", name=name,
            role=role, hashed_password="x",
        ))
        await db.commit()
    return user_id


def _flatten_capabilities(profile: dict) -> list[dict]:
    return [c for cat in profile["service_categories"] for c in cat["capabilities"]]


# ════════════════════════════════════════════════════════════════
# P0 服务商能力档案（service 层）
# ════════════════════════════════════════════════════════════════


class TestServiceProviderProfile:
    def test_categories_follow_policy_definition(self):
        from app.services.ai_service_provider_profile import build_service_provider_profile

        profile = build_service_provider_profile()
        assert profile["policy_basis"]["document"] == "工信厅科函〔2026〕414号"
        assert [c["key"] for c in profile["service_categories"]] == [
            "consulting_planning", "delivery_implementation", "operations_management",
            "security_governance", "supporting_services",
        ]

    def test_maturity_level_never_self_assessed(self):
        """诚实红线：等级判定须第三方评估，平台自检恒为 not_assessed。"""
        from app.services.ai_service_provider_profile import build_service_provider_profile

        profile = build_service_provider_profile()
        assert profile["maturity_level"] == "not_assessed"
        assert "第三方" in profile["maturity_note"]

    def test_disclaimer_always_present(self):
        from app.services.ai_service_provider_profile import build_service_provider_profile

        profile = build_service_provider_profile()
        assert "非第三方认证结论" in profile["disclaimer"]
        assert "不构成资源池入库证明" in profile["disclaimer"]
        assert any("资源池" in x for x in profile["limitations"])

    def test_standards_reference_gb_45907(self):
        from app.services.ai_service_provider_profile import build_service_provider_profile

        codes = [s["code"] for s in build_service_provider_profile()["standards_reference"]]
        assert "GB/T 45907-2025" in codes

    def test_no_dangling_evidence(self):
        """所有声明证据均须经文件存在性核验（不得有悬空证据）。"""
        from app.services.ai_service_provider_profile import build_service_provider_profile

        profile = build_service_provider_profile()
        assert profile["summary"]["missing"] == 0, [
            c["name"] for c in _flatten_capabilities(profile) if c["status"] == "missing"
        ]
        for cap in _flatten_capabilities(profile):
            if cap["evidence"] is not None:
                assert cap["status"] == "evidenced"

    def test_missing_evidence_marked_not_evidenced(self):
        """未实现的条目如实标 not_evidenced（不编造能力充数）。"""
        from app.services.ai_service_provider_profile import build_service_provider_profile

        profile = build_service_provider_profile()
        gaps = [c for c in _flatten_capabilities(profile) if c["evidence"] is None]
        assert gaps, "应如实标注未落地条目的缺口"
        assert all(c["status"] == "not_evidenced" for c in gaps)
        assert all(c["note"] for c in gaps)

    def test_status_rules(self):
        from app.services.ai_service_provider_profile import _status_for

        assert _status_for(None) == "not_evidenced"
        assert _status_for("app/services/ai_service_provider_profile.py") == "evidenced"
        assert _status_for("app/services/__not_exist__.py") == "missing"
        # 非仓库内路径不当作证据
        assert _status_for("https://example.com/x") == "missing"

    def test_governance_evidence_reuses_audit(self):
        """治理证据复用 run_governance_audit()，不重复实现（OWASP 10 + ATH 5）。"""
        from app.services.ai_service_provider_profile import build_service_provider_profile

        gov = build_service_provider_profile()["governance_evidence"]
        assert gov["included"] is True
        assert gov["owasp_agentic_skills_top10"]["summary"]["total"] == 10
        assert gov["ath_trust_layer"]["summary"]["total"] == 5
        assert "run_governance_audit" in gov["source"]

    def test_summary_counts_consistent(self):
        from app.services.ai_service_provider_profile import build_service_provider_profile

        s = build_service_provider_profile()["summary"]
        assert s["capability_count"] == s["evidenced"] + s["missing"] + s["not_evidenced"]
        assert s["category_count"] == 5


@pytest.mark.asyncio
async def test_profile_endpoint_requires_auth(client: AsyncClient):
    resp = await client.get("/api/admin/ai-service-provider-profile")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_profile_endpoint_admin_ok(client: AsyncClient):
    user_id = await _seed_user(role="admin", name="档案管理员")
    resp = await client.get(
        "/api/admin/ai-service-provider-profile", headers=_auth_headers_for(user_id, "admin"),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["maturity_level"] == "not_assessed"


@pytest.mark.asyncio
async def test_profile_endpoint_forbidden_for_non_admin(client: AsyncClient):
    user_id = await _seed_user()
    resp = await client.get(
        "/api/admin/ai-service-provider-profile", headers=_auth_headers_for(user_id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_profile_endpoint_flag_off_503(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_service_provider_profile_enabled", False)
    user_id = await _seed_user(role="admin")
    resp = await client.get(
        "/api/admin/ai-service-provider-profile", headers=_auth_headers_for(user_id, "admin"),
    )
    assert resp.status_code == 503


# ════════════════════════════════════════════════════════════════
# P1 Token 计量口径
# ════════════════════════════════════════════════════════════════


async def _seed_trace(user_id: str, agent_name: str, prompt: int, completion: int) -> None:
    from app.database import async_session
    from app.models.agent_trace import AgentTraceRecord

    async with async_session() as db:
        db.add(AgentTraceRecord(
            agent_name=agent_name, status="success", user_id=user_id,
            provider="deepseek", model="deepseek-chat",
            prompt_tokens=prompt, completion_tokens=completion,
            total_tokens=prompt + completion,
        ))
        await db.commit()


@pytest.mark.asyncio
async def test_token_metering_aggregates_and_flags_not_billing(db_session):
    from app.services.ai_token_metering import aggregate_token_usage

    user_id = await _seed_user()
    await _seed_trace(user_id, "DesignerAgent", 100, 50)
    await _seed_trace(user_id, "DesignerAgent", 200, 100)

    report = await aggregate_token_usage(db_session, user_id=user_id, group_by="agent_name")
    assert report["data_source_available"] is True
    # 计量 ≠ 计费：恒带诚实标注
    assert report["metering_only"] is True
    assert report["billing_ready"] is False
    assert "未接入计费结算闭环" in report["billing_note"]
    assert report["totals"] == {
        "executions": 2, "prompt_tokens": 300,
        "completion_tokens": 150, "total_tokens": 450,
    }
    assert report["items"][0]["key"] == "DesignerAgent"
    assert report["items"][0]["total_tokens"] == 450


@pytest.mark.asyncio
async def test_token_metering_group_by_model(db_session):
    from app.services.ai_token_metering import aggregate_token_usage

    user_id = await _seed_user()
    await _seed_trace(user_id, "BudgetAgent", 10, 5)

    report = await aggregate_token_usage(db_session, user_id=user_id, group_by="model")
    assert report["items"][0]["key"] == "deepseek-chat"


@pytest.mark.asyncio
async def test_token_metering_invalid_group_by(db_session):
    from app.services.ai_token_metering import aggregate_token_usage

    with pytest.raises(ValueError, match="group_by 不合法"):
        await aggregate_token_usage(db_session, group_by="not_a_dimension")


@pytest.mark.asyncio
async def test_token_metering_data_source_unavailable_honest(db_session, monkeypatch):
    """轨迹未落库时不返回 0 伪装无用量，如实标注数据源不可用。"""
    from app.services.ai_token_metering import aggregate_token_usage

    monkeypatch.setattr(get_settings(), "agent_trace_persist_enabled", False)
    report = await aggregate_token_usage(db_session, user_id="whoever")
    assert report["data_source_available"] is False
    assert report["totals"] is None
    assert "不代表用量为 0" in report["data_source_note"]
    assert report["billing_ready"] is False


@pytest.mark.asyncio
async def test_token_usage_endpoint_requires_auth(client: AsyncClient):
    resp = await client.get("/api/ai-usage/tokens")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_token_usage_endpoint_own_scope(client: AsyncClient):
    user_id = await _seed_user()
    await _seed_trace(user_id, "ConciergeAgent", 7, 3)

    resp = await client.get("/api/ai-usage/tokens", headers=_auth_headers_for(user_id))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["totals"]["total_tokens"] == 10
    assert body["billing_ready"] is False
    assert body["filters"]["user_id"] == user_id


@pytest.mark.asyncio
async def test_token_usage_endpoint_invalid_group_by_422(client: AsyncClient):
    user_id = await _seed_user()
    resp = await client.get(
        "/api/ai-usage/tokens?group_by=bad", headers=_auth_headers_for(user_id),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_token_usage_endpoint_flag_off_503(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_token_metering_enabled", False)
    user_id = await _seed_user()
    resp = await client.get("/api/ai-usage/tokens", headers=_auth_headers_for(user_id))
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_admin_token_usage_requires_platform_manage(client: AsyncClient):
    user_id = await _seed_user()
    resp = await client.get("/api/admin/ai-usage/tokens", headers=_auth_headers_for(user_id))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_token_usage_platform_summary(client: AsyncClient):
    admin_id = await _seed_user(role="admin", name="用量管理员")
    user_id = await _seed_user()
    await _seed_trace(user_id, "QaInspectorAgent", 20, 10)

    resp = await client.get(
        "/api/admin/ai-usage/tokens", headers=_auth_headers_for(admin_id, "admin"),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["totals"]["total_tokens"] == 30
    assert body["filters"]["user_id"] is None


# ════════════════════════════════════════════════════════════════
# P2 FDE 现场服务记录
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_fde_requires_auth(client: AsyncClient):
    resp = await client.get("/api/fde-field-visits")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_fde_enums(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/fde-field-visits/enums", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "safety_walkthrough" in body["service_types"]
    assert body["modes"] == ["on_site", "remote_support"]
    assert body["capability_tags"] == ["business", "model", "security", "delivery"]
    assert "不硬凑四维" in body["capability_tags_note"]


@pytest.mark.asyncio
async def test_fde_create_and_partial_capability_tags(client: AsyncClient, auth_headers: dict):
    """只声明实际具备的维度：允许子集（不强制四维齐全）。"""
    resp = await client.post(
        "/api/fde-field-visits",
        json={
            "title": "大理某药膳小院设备联调",
            "engineer_name": "李工",
            "service_type": "commissioning",
            "mode": "on_site",
            "capability_tags": ["delivery", "model"],
            "duration_hours": 6.5,
            "findings": "网关与 3 台设备组网完成，遗留 1 个传感器待复测",
            "resolved": False,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["capability_tags"] == ["delivery", "model"]
    assert body["resolved"] is False
    assert body["owner_id"]


@pytest.mark.asyncio
async def test_fde_create_empty_capability_tags_allowed(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/fde-field-visits",
        json={"title": "现场踏勘（未声明能力维度）", "capability_tags": []},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.asyncio
async def test_fde_rejects_unknown_capability_tag(client: AsyncClient, auth_headers: dict):
    """schema 层受限枚举拦截越界维度（前端须逐字对齐 FDE_CAPABILITY_TAGS）。"""
    resp = await client.post(
        "/api/fde-field-visits",
        json={"title": "越界维度", "capability_tags": ["business", "hardware"]},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "hardware" in resp.text


@pytest.mark.asyncio
async def test_fde_service_rejects_unknown_capability_tag(db_session):
    """service 层防御：直接调用时的友好报错（不硬凑四维）。"""
    from app.services.fde_field_service import create_visit

    with pytest.raises(ValueError, match="不硬凑四维"):
        await create_visit(db_session, {
            "owner_id": "someone", "title": "越界维度用例",
            "capability_tags": ["business", "hardware"],
        })


@pytest.mark.asyncio
async def test_fde_rejects_invalid_enum(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/fde-field-visits",
        json={"title": "非法服务类型", "service_type": "onsite_install"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_fde_update_and_delete(client: AsyncClient, auth_headers: dict):
    created = await client.post(
        "/api/fde-field-visits",
        json={"title": "昆明某康养空间巡检", "service_type": "safety_walkthrough"},
        headers=auth_headers,
    )
    visit_id = created.json()["id"]

    patched = await client.patch(
        f"/api/fde-field-visits/{visit_id}",
        json={"resolved": True, "duration_hours": 2.0},
        headers=auth_headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["resolved"] is True
    assert patched.json()["duration_hours"] == 2.0

    deleted = await client.delete(f"/api/fde-field-visits/{visit_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert (await client.get(f"/api/fde-field-visits/{visit_id}", headers=auth_headers)).status_code == 404


@pytest.mark.asyncio
async def test_fde_owner_isolation(client: AsyncClient):
    owner_id = await _seed_user(name="现场工程师")
    other_id = await _seed_user(name="无关用户")

    created = await client.post(
        "/api/fde-field-visits",
        json={"title": "归属隔离用例"},
        headers=_auth_headers_for(owner_id),
    )
    visit_id = created.json()["id"]

    # 他人不可读、不可改、不可删
    other_headers = _auth_headers_for(other_id)
    assert (await client.get(f"/api/fde-field-visits/{visit_id}", headers=other_headers)).status_code == 403
    assert (await client.patch(
        f"/api/fde-field-visits/{visit_id}", json={"resolved": True}, headers=other_headers,
    )).status_code == 403
    assert (await client.delete(
        f"/api/fde-field-visits/{visit_id}", headers=other_headers,
    )).status_code == 403

    # 列表也隔离：他人看不到该记录
    listing = await client.get("/api/fde-field-visits", headers=other_headers)
    assert all(v["id"] != visit_id for v in listing.json())


@pytest.mark.asyncio
async def test_fde_flag_off_503(client: AsyncClient, auth_headers: dict, monkeypatch):
    monkeypatch.setattr(get_settings(), "fde_field_service_enabled", False)
    resp = await client.get("/api/fde-field-visits", headers=auth_headers)
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_fde_service_rejects_negative_duration(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/fde-field-visits",
        json={"title": "负工时用例", "duration_hours": -1},
        headers=auth_headers,
    )
    assert resp.status_code == 422

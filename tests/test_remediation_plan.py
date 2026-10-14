"""站点修复清单闭环测试（v1.18.0）

借鉴来源：数智前线《万小智，让AI从网站生成走向企业经营》（2026-09-24）——
「诊断完成，并不意味着问题得到解决」；自动化判据是「做错以后用户能不能发现、
能不能改回来」。

覆盖：
- 三级自动化边界（auto / confirm / human_only）确定性判定
- 清单构建（白名单只含说明书层动作；涉及企业事实一律 human_only）
- 白名单动作执行（写 llms.txt / 追加 robots 声明块）+ 越界写拒绝
- 须显式 confirm 才可执行
- 复检（重新审计确定性比对：执行 ≠ 生效）
- 回滚（新增文件删除 / 既有文件还原）
- 端点全链路（生成 → 拒未确认 → 执行 → 复检 → 回滚）+ 鉴权 / flag 503
"""
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.services import ai_visibility_service as avs
from app.services import remediation_plan_service as rps

from tests.test_ai_visibility import INDEX_HTML, ROBOTS_DECLARED, SITEMAP, _auth_headers_for, _seed_user


@pytest.fixture
def site(tmp_path):
    """合成站点（仓库外 tmp 目录，用于服务层动作测试）。"""
    (tmp_path / "robots.txt").write_text(ROBOTS_DECLARED, encoding="utf-8")
    (tmp_path / "sitemap.xml").write_text(SITEMAP.format(lastmod="2026-09-24"), encoding="utf-8")
    (tmp_path / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return tmp_path


@pytest.fixture
def repo_site(monkeypatch):
    """仓库内 webapp/ 下的临时站点目录（满足写入根约束，供端点全链路测试）。

    用例结束即递归删除，不污染工作树（不写入任何受版本控制的路径）。
    """
    base = avs.PROJECT_ROOT / "webapp"
    d = Path(tempfile.mkdtemp(prefix=".pytest_site_", dir=base))
    (d / "robots.txt").write_text(ROBOTS_DECLARED, encoding="utf-8")
    (d / "sitemap.xml").write_text(SITEMAP.format(lastmod="2026-09-24"), encoding="utf-8")
    (d / "index.html").write_text(INDEX_HTML, encoding="utf-8")

    real_resolve = avs.resolve_artifacts

    def fake_resolve(static_root=None):  # 无论传入什么，恒定位到本用例的临时站点
        art = real_resolve(static_root)
        return {**art,
                "public_dir": d,
                "public_dir_rel": str(d.relative_to(avs.PROJECT_ROOT)),
                "index_html": d / "index.html",
                "robots": d / "robots.txt",
                "sitemap": d / "sitemap.xml",
                "llms": (d / "llms.txt") if (d / "llms.txt").exists() else None}

    monkeypatch.setattr(avs, "resolve_artifacts", fake_resolve)
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ════════════════════════════════════════════════════════════════
# 自动化边界
# ════════════════════════════════════════════════════════════════


class TestAutomationBoundary:
    def test_whitelist_action_is_auto(self):
        assert rps.classify_tier("write_llms_txt", reversible=True, changes_facts=False) == "auto"
        assert rps.classify_tier("update_robots_ai_agents", reversible=True, changes_facts=False) == "auto"

    def test_non_whitelist_reversible_needs_confirm(self):
        assert rps.classify_tier(None, reversible=True, changes_facts=False) == "confirm"

    def test_facts_change_is_human_only(self):
        assert rps.classify_tier(None, reversible=True, changes_facts=True) == "human_only"

    def test_irreversible_is_human_only(self):
        assert rps.classify_tier("write_llms_txt", reversible=False, changes_facts=False) == "human_only"


class TestBuildPlan:
    def test_plan_from_synthetic_audit(self, site):
        audit = avs.run_ai_visibility_audit(static_root=str(site))
        plan = rps.build_plan(audit)
        assert plan["requires_confirmation"] is True
        assert plan["summary"]["item_count"] == len(plan["items"])
        assert plan["summary"]["auto"] == len(plan["auto_executable_items"])
        # 白名单动作只在 auto 条目里出现
        for item in plan["items"]:
            if item["action"] in avs.AUTO_REMEDIATION_ACTIONS:
                assert item["tier"] == "auto" and item["auto_executable"] is True
            else:
                assert item["auto_executable"] is False

    def test_facts_items_are_human_only_with_note(self, site):
        audit = avs.run_ai_visibility_audit(static_root=str(site))
        plan = rps.build_plan(audit)
        facts_items = [i for i in plan["items"]
                       if i["source_check_id"] in ("structured_data_business_entity",
                                                   "organization_profile_fields",
                                                   "public_content_pages")]
        assert facts_items
        for item in facts_items:
            assert item["tier"] == "human_only"
            assert item["reversible"] is False

    def test_default_audit_has_llms_auto_item(self):
        """仓库默认站点缺 llms.txt → 清单必含可自动执行的生成条目。"""
        plan = rps.build_plan()
        auto_actions = [i["action"] for i in plan["items"] if i["auto_executable"]]
        assert "write_llms_txt" in auto_actions


# ════════════════════════════════════════════════════════════════
# 动作执行 / 越界防护 / 复检 / 回滚
# ════════════════════════════════════════════════════════════════


class TestExecuteAction:
    def test_write_llms_txt_and_detect(self, site):
        art = avs.resolve_artifacts(str(site))
        audit = avs.run_ai_visibility_audit(static_root=str(site))
        result = rps.execute_action("write_llms_txt", audit=audit, artifacts=art, allowed_root=site)
        assert result["changed"] is True
        assert result["backup"] == {"existed": False, "content": None}
        assert (site / "llms.txt").exists()
        content = (site / "llms.txt").read_text(encoding="utf-8")
        assert "> " in content and "生成器" in content

        after = avs.run_ai_visibility_audit(static_root=str(site))
        status = next(c["status"] for c in after["checks"] if c["id"] == "llms_txt_present")
        assert status == "pass"

    def test_write_llms_txt_is_idempotent(self, site):
        art = avs.resolve_artifacts(str(site))
        audit = avs.run_ai_visibility_audit(static_root=str(site))
        rps.execute_action("write_llms_txt", audit=audit, artifacts=art, allowed_root=site)
        second = rps.execute_action("write_llms_txt", audit=audit, artifacts=art, allowed_root=site)
        assert second["changed"] is False

    def test_robots_append_block_keeps_existing_rules(self, site):
        art = avs.resolve_artifacts(str(site))
        audit = avs.run_ai_visibility_audit(static_root=str(site))
        original = (site / "robots.txt").read_text(encoding="utf-8")
        result = rps.execute_action("update_robots_ai_agents", audit=audit, artifacts=art, allowed_root=site)
        assert result["changed"] is True
        updated = (site / "robots.txt").read_text(encoding="utf-8")
        assert updated.startswith(original.rstrip("\n"))
        assert rps.AI_AGENT_BLOCK_HEADER in updated
        assert "ClaudeBot" in updated
        # 幂等：再次执行不重复追加
        again = rps.execute_action("update_robots_ai_agents", audit=audit, artifacts=art, allowed_root=site)
        assert again["changed"] is False

    def test_rejects_out_of_root_write(self, site):
        art = {**avs.resolve_artifacts(str(site)), "public_dir": rps.PROJECT_ROOT / "app"}
        with pytest.raises(ValueError, match="拒绝越界写入"):
            rps.execute_action("write_llms_txt", audit={"robots": {}}, artifacts=art, allowed_root=site)

    def test_unknown_action_rejected(self, site):
        with pytest.raises(ValueError, match="不在白名单"):
            rps.execute_action("delete_everything", audit={"robots": {}},
                               artifacts=avs.resolve_artifacts(str(site)), allowed_root=site)


class TestApplyVerifyRollback:
    def test_requires_explicit_confirm(self, site):
        plan = rps.build_plan(avs.run_ai_visibility_audit(static_root=str(site)))
        with pytest.raises(ValueError, match="confirm=True"):
            rps.apply_items(plan, plan["auto_executable_items"], confirm=False)

    def test_unknown_item_rejected(self, site):
        plan = rps.build_plan(avs.run_ai_visibility_audit(static_root=str(site)))
        with pytest.raises(ValueError, match="不存在条目"):
            rps.apply_items(plan, ["R99"], confirm=True, allowed_root=site)

    def test_apply_skips_non_auto_items(self, site):
        audit = avs.run_ai_visibility_audit(static_root=str(site))
        plan = rps.build_plan(audit)
        human = next(i for i in plan["items"] if i["tier"] == "human_only")
        result = rps.apply_items(plan, [human["item_id"]], confirm=True,
                                 artifacts=avs.resolve_artifacts(str(site)), allowed_root=site)
        assert result["applied"] == []
        assert result["skipped"][0]["item_id"] == human["item_id"]

    def test_apply_verify_rollback_round_trip(self, site):
        plan = rps.build_plan(avs.run_ai_visibility_audit(static_root=str(site)))
        plan["static_root"] = str(site)
        item_ids = [i["item_id"] for i in plan["items"] if i["action"] == "write_llms_txt"]
        result = rps.apply_items(plan, item_ids, confirm=True,
                                 artifacts=avs.resolve_artifacts(str(site)), allowed_root=site)
        assert result["applied"] and (site / "llms.txt").exists()
        assert result["verification_required"] is True

        verify = rps.verify_items(plan, item_ids)
        assert verify["all_verified"] is True
        assert verify["results"][0]["status_after"] == "pass"

        rolled = rps.rollback_backups(result["backups"], allowed_root=site)
        assert rolled["success"] is True
        assert rolled["removed"] and not (site / "llms.txt").exists()

    def test_rollback_restores_modified_file(self, site):
        original = (site / "robots.txt").read_text(encoding="utf-8")
        art = avs.resolve_artifacts(str(site))
        audit = avs.run_ai_visibility_audit(static_root=str(site))
        result = rps.execute_action("update_robots_ai_agents", audit=audit, artifacts=art, allowed_root=site)
        assert (site / "robots.txt").read_text(encoding="utf-8") != original
        rolled = rps.rollback_backups({result["target"]: result["backup"]}, allowed_root=site)
        assert rolled["success"] is True
        assert (site / "robots.txt").read_text(encoding="utf-8") == original


# ════════════════════════════════════════════════════════════════
# 端点全链路
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_remediation_requires_auth(client: AsyncClient):
    resp = await client.post("/api/remediation-plans")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_remediation_forbidden_for_non_admin(client: AsyncClient):
    user_id = await _seed_user()
    resp = await client.post("/api/remediation-plans", headers=_auth_headers_for(user_id))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_remediation_flag_off_503(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "remediation_plan_enabled", False)
    user_id = await _seed_user(role="admin")
    resp = await client.post("/api/remediation-plans", headers=_auth_headers_for(user_id, "admin"))
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_remediation_full_chain(client: AsyncClient, repo_site):
    """生成 → 拒未确认执行 → 执行 → 复检 → 回滚（全程只动临时站点目录）。"""
    user_id = await _seed_user(role="admin", name="清单管理员")
    headers = _auth_headers_for(user_id, "admin")

    created = await client.post("/api/remediation-plans", headers=headers)
    assert created.status_code == 201, created.text
    plan = created.json()
    plan_id = plan["id"]
    assert plan["status"] == "proposed"
    auto_items = plan["summary"]["auto_executable"]
    assert auto_items >= 1

    # 未确认 → 422（平台不自动改动站点产物）
    refused = await client.post(f"/api/remediation-plans/{plan_id}/apply",
                                json={"confirm": False}, headers=headers)
    assert refused.status_code == 422
    assert not (repo_site / "llms.txt").exists()

    applied = await client.post(f"/api/remediation-plans/{plan_id}/apply",
                                json={"confirm": True}, headers=headers)
    assert applied.status_code == 200, applied.text
    assert applied.json()["applied"]
    assert (repo_site / "llms.txt").exists()

    verified = await client.post(f"/api/remediation-plans/{plan_id}/verify", headers=headers)
    assert verified.status_code == 200, verified.text
    body = verified.json()
    assert body["results"]
    assert body["all_verified"] is True
    assert body["audit_after"]["score"] >= plan["score_before"]
    assert body["status"] == "verified"

    rolled = await client.post(f"/api/remediation-plans/{plan_id}/rollback", headers=headers)
    assert rolled.status_code == 200, rolled.text
    assert rolled.json()["status"] == "rolled_back"
    assert not (repo_site / "llms.txt").exists()


@pytest.mark.asyncio
async def test_remediation_list_and_detail(client: AsyncClient, repo_site):
    user_id = await _seed_user(role="admin")
    headers = _auth_headers_for(user_id, "admin")
    await client.post("/api/remediation-plans", headers=headers)

    listing = await client.get("/api/remediation-plans", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["count"] >= 1

    missing = await client.get(f"/api/remediation-plans/{uuid.uuid4()}", headers=headers)
    assert missing.status_code == 404

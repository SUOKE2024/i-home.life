"""站点 AI 可见度（GEO）就绪度审计测试（v1.18.0）

借鉴来源：数智前线《万小智，让AI从网站生成走向企业经营》（2026-09-24）。

覆盖：
- 解析器（robots 分组语义 / sitemap / JSON-LD / 时间年龄）
- 权重契约（四维合计 100，检查项权重合计 100）
- 仓库实况审计（分数区间、证据齐备、诚实标注）
- 合成站点（AI 爬虫被整站禁止 → fail；未声明 → warn；已声明 → pass）
- 产物缺失时的诚实降级（不猜为通过）
- 端点鉴权 / 权限 / flag 关闭 503
"""
import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.services import ai_visibility_service as avs


def _auth_headers_for(user_id: str, role: str = "user") -> dict:
    from app.auth.paseto_handler import create_token
    return {"Authorization": f"Bearer {create_token(user_id, role)}"}


async def _seed_user(role: str = "user", name: str = "可见度测试用户") -> str:
    import uuid

    from app.database import async_session
    from app.models.user import User

    user_id = str(uuid.uuid4())
    async with async_session() as db:
        db.add(User(id=user_id, phone=f"136{uuid.uuid4().hex[:8]}", name=name,
                    role=role, hashed_password="x"))
        await db.commit()
    return user_id


ROBOTS_DECLARED = """User-agent: *
Allow: /
Disallow: /api/

User-agent: GPTBot
Allow: /
Disallow: /api/

Sitemap: https://i-home.life/sitemap.xml
"""

ROBOTS_UNDECLARED = """User-agent: *
Allow: /
Disallow: /api/

Sitemap: https://i-home.life/sitemap.xml
"""

ROBOTS_BLOCKED = """User-agent: *
Allow: /

User-agent: ClaudeBot
Disallow: /

Sitemap: https://i-home.life/sitemap.xml
"""

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://i-home.life/</loc><lastmod>{lastmod}</lastmod></url>
</urlset>
"""

INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta name="description" content="测试站点描述，长度满足二十字以上要求用于审计判定。">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Organization","name":"索克家居","url":"https://i-home.life/","logo":"https://i-home.life/logo.png"}
</script>
<title>测试站点</title>
</head>
<body><div id="root"></div><noscript><p>需要启用 JavaScript 才能查看完整内容。</p></noscript></body>
</html>
"""


def _write_site(root, robots=ROBOTS_DECLARED, sitemap=True, index=True, lastmod="2026-09-24"):
    if robots is not None:
        (root / "robots.txt").write_text(robots, encoding="utf-8")
    if sitemap:
        (root / "sitemap.xml").write_text(SITEMAP.format(lastmod=lastmod), encoding="utf-8")
    if index:
        (root / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return root


# ════════════════════════════════════════════════════════════════
# 解析器
# ════════════════════════════════════════════════════════════════


class TestParsers:
    def test_robots_consecutive_ua_share_rules(self):
        text = "User-agent: A\nUser-agent: B\nDisallow: /x\n\nUser-agent: *\nAllow: /\n"
        parsed = avs.parse_robots(text)
        assert parsed["groups"]["a"] == ["disallow:/x"]
        assert parsed["groups"]["b"] == ["disallow:/x"]
        assert parsed["groups"]["*"] == ["allow:/"]

    def test_robots_sitemap_and_comments(self):
        parsed = avs.parse_robots("# 注释\nSitemap: https://x/sitemap.xml\nUser-agent: * # 行内注释\nAllow: /\n")
        assert parsed["sitemaps"] == ["https://x/sitemap.xml"]
        assert parsed["groups"]["*"] == ["allow:/"]

    def test_blocks_all_semantics(self):
        assert avs._blocks_all(["disallow:/"]) is True
        assert avs._blocks_all(["disallow:/", "allow:/"]) is False
        assert avs._blocks_all(["disallow:/api/"]) is False

    def test_sitemap_parse_error_reported_not_silent(self):
        parsed = avs.parse_sitemap("<urlset><url>")
        assert parsed["urls"] == []
        assert parsed["error"] and "解析失败" in parsed["error"]

    def test_jsonld_types_and_error(self):
        ok = avs.parse_jsonld(INDEX_HTML)
        assert "Organization" in ok["types"]
        bad = avs.parse_jsonld('<script type="application/ld+json">{oops}</script>')
        assert bad["blocks"] == []
        assert bad["error"] and "JSON-LD 解析失败" in bad["error"]

    def test_age_days(self):
        from datetime import datetime, timedelta, timezone

        now = datetime(2026, 9, 25, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        assert avs._age_days("2026-09-24", now) == pytest.approx(1.5)  # naive 按北京时间零点
        assert avs._age_days("2026-09-24T08:00:00", now) == pytest.approx(1.17, abs=0.02)
        assert avs._age_days("not-a-date", now) is None
        assert avs._age_days(None, now) is None


# ════════════════════════════════════════════════════════════════
# 权重与计分契约
# ════════════════════════════════════════════════════════════════


class TestScoringContract:
    def test_check_weights_sum_to_100(self):
        assert sum(c["weight"] for c in avs.CHECKS) == 100

    def test_dimension_weights_match_check_weights(self):
        dims = {d["key"]: d["weight"] for d in avs.DIMENSIONS}
        for key in dims:
            assert dims[key] == sum(c["weight"] for c in avs.CHECKS if c["dimension"] == key)

    def test_auto_whitelist_is_doc_layer_only(self):
        assert avs.AUTO_REMEDIATION_ACTIONS == ("write_llms_txt", "update_robots_ai_agents")

    def test_levels_cover_full_range(self):
        assert avs._level_for(100)[0] == "ready"
        assert avs._level_for(70)[0] == "partial"
        assert avs._level_for(10)[0] == "insufficient"


# ════════════════════════════════════════════════════════════════
# 合成站点审计
# ════════════════════════════════════════════════════════════════


class TestAuditSynthetic:
    def test_declared_ai_crawler_passes(self, tmp_path):
        _write_site(tmp_path, robots=ROBOTS_DECLARED)
        audit = avs.run_ai_visibility_audit(static_root=str(tmp_path))
        statuses = {c["id"]: c["status"] for c in audit["checks"]}
        assert statuses["ai_crawler_policy"] == "pass"
        assert audit["robots"]["declared"] == ["GPTBot"]

    def test_undeclared_ai_crawler_warns_not_fails(self, tmp_path):
        _write_site(tmp_path, robots=ROBOTS_UNDECLARED)
        audit = avs.run_ai_visibility_audit(static_root=str(tmp_path))
        statuses = {c["id"]: c["status"] for c in audit["checks"]}
        assert statuses["ai_crawler_policy"] == "warn"

    def test_blocking_ai_crawler_fails(self, tmp_path):
        _write_site(tmp_path, robots=ROBOTS_BLOCKED)
        audit = avs.run_ai_visibility_audit(static_root=str(tmp_path))
        statuses = {c["id"]: c["status"] for c in audit["checks"]}
        assert statuses["ai_crawler_policy"] == "fail"
        assert audit["robots"]["blocked_ai"] == ["claudebot"]

    def test_business_entity_required_beyond_organization(self, tmp_path):
        _write_site(tmp_path)
        audit = avs.run_ai_visibility_audit(static_root=str(tmp_path))
        statuses = {c["id"]: c["status"] for c in audit["checks"]}
        # 合成站点只有 Organization（无 Service/Product/FAQ）→ 不足以回答「能提供什么」
        assert statuses["structured_data_business_entity"] == "fail"
        assert statuses["structured_data_present"] == "pass"

    def test_stale_lastmod_flagged(self, tmp_path):
        _write_site(tmp_path, lastmod="2025-01-01")
        audit = avs.run_ai_visibility_audit(static_root=str(tmp_path))
        check = next(c for c in audit["checks"] if c["id"] == "sitemap_lastmod_freshness")
        assert check["status"] == "fail"
        assert "长草" in check["evidence"]

    def test_missing_artifacts_honest_degradation(self, tmp_path):
        """产物缺失时记 fail/unknown 并标注，不猜为通过，也不抛异常。"""
        audit = avs.run_ai_visibility_audit(static_root=str(tmp_path))
        assert audit["score"] == 0
        assert audit["level"] == "insufficient"
        assert audit["summary"]["unknown"] >= 5
        assert audit["artifacts"] == {"robots_txt": False, "sitemap_xml": False,
                                      "index_html": False, "llms_txt": False}

    def test_remediation_candidates_only_for_non_pass(self, tmp_path):
        _write_site(tmp_path)
        audit = avs.run_ai_visibility_audit(static_root=str(tmp_path))
        non_pass = {c["id"] for c in audit["checks"] if c["status"] != "pass"}
        assert all(c["source_check_id"] in non_pass for c in audit["remediation_candidates"])

    def test_content_page_counting(self, tmp_path):
        _write_site(tmp_path)
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "guide.html").write_text("<html></html>", encoding="utf-8")
        (tmp_path / "console").mkdir()
        (tmp_path / "console" / "index.html").write_text("<html></html>", encoding="utf-8")
        assert avs.count_content_pages(tmp_path) == 1

    def test_org_inside_graph_recognized(self, tmp_path):
        """`@graph` 容器下的 Organization 必须被识别（v1.18.0 修复：此前只查顶层 @type）。"""
        graph = (
            '{"@context":"https://schema.org","@graph":['
            '{"@type":"Organization","@id":"https://x/#org","name":"某某公司",'
            '"url":"https://x/","logo":"https://x/logo.png",'
            '"address":{"@type":"PostalAddress","addressRegion":"云南省"},'
            '"contactPoint":{"@type":"ContactPoint","telephone":"0000"},'
            '"sameAs":["https://x/media"]},'
            '{"@type":"Service","name":"改造服务","provider":{"@id":"https://x/#org"}}]}'
        )
        _write_site(tmp_path)
        (tmp_path / "index.html").write_text(
            INDEX_HTML.replace("</head>", f'<script type="application/ld+json">{graph}</script></head>'),
            encoding="utf-8")
        audit = avs.run_ai_visibility_audit(static_root=str(tmp_path))
        statuses = {c["id"]: c["status"] for c in audit["checks"]}
        assert statuses["organization_profile_fields"] == "pass"
        assert statuses["structured_data_business_entity"] == "pass"

    def test_pick_org_prefers_richest(self):
        """多候选时取字段最完整者（扁平 publisher 与 @graph 混存场景）。"""
        lean = {"@type": "Organization", "name": "甲", "url": "https://x/", "logo": "https://x/l.png"}
        rich = {**lean, "sameAs": ["https://x/s"], "contactPoint": {}, "address": {}}
        blocks = [{"@type": "WebSite", "publisher": lean}, {"@graph": [rich]}]
        assert avs._pick_org(avs._collect_org_nodes(blocks)) is rich

    def test_collect_org_nodes_dedupes_and_covers_nesting(self):
        org = {"@type": "Organization", "name": "甲"}
        blocks = [org, {"@graph": [org, {"@type": "WebSite", "publisher": org}]}]
        assert avs._collect_org_nodes(blocks) == [org]

    def test_collect_org_nodes_handles_type_list_and_local_business(self):
        a = {"@type": ["Organization", "LocalBusiness"], "name": "甲"}
        b = {"@type": "LocalBusiness", "name": "乙"}
        assert avs._collect_org_nodes([a, {"@graph": [b]}]) == [a, b]

    def test_single_directory_artifact_set(self, tmp_path, monkeypatch):
        """产物须取自同一目录：不得出现 robots 取自 A、llms.txt 取自 B 的混合集。"""
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir(), b.mkdir()
        (a / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
        (b / "llms.txt").write_text("# 只有 B 有\n", encoding="utf-8")
        monkeypatch.setattr(avs, "PROJECT_ROOT", tmp_path)
        art = avs.resolve_artifacts("a")
        assert art["public_dir"] == a
        assert art["robots"] == a / "robots.txt"
        assert art["llms"] is None, "不得跨目录回退捡到 b/llms.txt"

    def test_explicit_static_root_without_index_falls_back_for_source_dir(self, tmp_path, monkeypatch):
        """源码态：public/ 无 index.html 时回退 webapp/index.html（仅此一种例外）。"""
        public = tmp_path / "webapp" / "public"
        public.mkdir(parents=True)
        (public / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
        (tmp_path / "webapp" / "index.html").write_text("<html></html>", encoding="utf-8")
        monkeypatch.setattr(avs, "PROJECT_ROOT", tmp_path)
        assert avs.resolve_artifacts("webapp/public")["index_html"] == tmp_path / "webapp" / "index.html"
        # 其它目录不享受该回退
        other = tmp_path / "other"
        other.mkdir()
        assert avs.resolve_artifacts("other")["index_html"] is None


# ════════════════════════════════════════════════════════════════
# 仓库实况
# ════════════════════════════════════════════════════════════════


class TestAuditRepo:
    def test_repo_audit_shape_and_honesty(self):
        audit = avs.run_ai_visibility_audit()
        assert 0 <= audit["score"] <= 100
        assert audit["method"] == "static_artifact_deterministic_audit"
        assert audit["model_probing"] is False
        assert "不构成" in audit["disclaimer"]
        assert any("不做真实模型探测" in x for x in audit["limitations"])
        assert audit["summary"]["check_count"] == len(avs.CHECKS)
        assert all(c["evidence"] for c in audit["checks"])

    def test_repo_audit_dimension_math(self):
        audit = avs.run_ai_visibility_audit()
        total = sum(d["earned"] for d in audit["dimensions"])
        assert round(total) == audit["score"]
        assert all(0 <= d["earned"] <= d["max"] for d in audit["dimensions"])


# ════════════════════════════════════════════════════════════════
# 端点
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ai_visibility_requires_auth(client: AsyncClient):
    resp = await client.get("/api/ai-visibility")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_ai_visibility_admin_ok(client: AsyncClient):
    user_id = await _seed_user(role="admin", name="可见度管理员")
    resp = await client.get("/api/ai-visibility", headers=_auth_headers_for(user_id, "admin"))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["model_probing"] is False
    assert "score" in body


@pytest.mark.asyncio
async def test_ai_visibility_forbidden_for_non_admin(client: AsyncClient):
    user_id = await _seed_user()
    resp = await client.get("/api/ai-visibility", headers=_auth_headers_for(user_id))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ai_visibility_flag_off_503(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_visibility_audit_enabled", False)
    user_id = await _seed_user(role="admin")
    resp = await client.get("/api/ai-visibility", headers=_auth_headers_for(user_id, "admin"))
    assert resp.status_code == 503

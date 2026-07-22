"""v1.1.29 家居补短功能测试

测试覆盖 5 项补短任务：
- P0 微服务拆分 (serverless/)
- P0 A2UI 协议内化
- P1 HMAC-SHA256 审计签名 + 字段级脱敏
- P1 装修知识库 + 引用服务
- P2 施工健康 OS 主动干预
"""
import json
import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test_v1129.db")
os.environ.setdefault("PASETO_SECRET_KEY", "test-secret-key-for-v1.1.29-testing-32bytes!")
os.environ.setdefault("QWEN_AUDIO_API_KEY", "")


# ════════════════════════════════════════════════════════════════
# P0 微服务拆分
# ════════════════════════════════════════════════════════════════


class TestMicroServices:
    """FC 3.0 微服务拆分测试"""

    SERVICES = [
        "auth-gateway",
        "agent-orchestrator",
        "design-render",
        "project-flow",
        "commerce",
        "realtime",
    ]

    def test_all_s_yaml_exist(self):
        """所有 7 个服务均有 s.yaml"""
        import yaml
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "serverless"
        for svc in self.SERVICES:
            s_yaml = root / svc / "s.yaml"
            assert s_yaml.exists(), f"{svc}/s.yaml 不存在"
            with open(s_yaml) as f:
                cfg = yaml.safe_load(f)
            assert cfg["edition"] == "3.0.0"
            assert "functions" in cfg

    def test_all_handlers_exist(self):
        """所有服务均有 handler.py"""
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "serverless"
        for svc in self.SERVICES:
            handler = root / svc / "handler.py"
            assert handler.exists(), f"{svc}/handler.py 不存在"

    def test_warmup_exists(self):
        """冷启动预热脚本存在"""
        from pathlib import Path
        warmup = Path(__file__).resolve().parents[1] / "serverless" / "common" / "warmup.py"
        assert warmup.exists()

    def test_service_role_feature_flag(self):
        """service_role feature flag 已定义"""
        from app.config import get_settings
        s = get_settings()
        assert hasattr(s, "service_role")
        assert s.service_role == ""


# ════════════════════════════════════════════════════════════════
# P0 A2UI 协议内化
# ════════════════════════════════════════════════════════════════


class TestA2UIProtocol:
    """A2UI 协议测试"""

    def test_schema_card_types(self):
        """A2UI schema 定义 8 种卡片类型"""
        from app.services.a2ui_schema import CardType
        types = list(CardType)
        assert len(types) >= 8
        type_values = {t.value for t in types}
        required = {"design_plan", "budget_breakdown", "construction_progress",
                     "procurement_order", "qa_report", "settlement_summary",
                     "material_card", "alert_card"}
        assert required.issubset(type_values)

    def test_generator_design_to_card(self):
        """设计输出 → A2UI 卡片转换"""
        from app.services.a2ui_generator import design_to_card
        card = design_to_card({
            "plans": [{"name": "方案A", "brief": "北欧风"}],
            "recommendation": "推荐方案A",
        })
        assert card["type"] == "design_plan"
        assert "data" in card
        assert "version" in card

    def test_generator_budget_to_card(self):
        """预算输出 → A2UI 卡片转换"""
        from app.services.a2ui_generator import budget_to_card
        card = budget_to_card({
            "items": [{"name": "瓷砖", "price": 5000}],
            "total": 50000,
            "tax": 4500,
            "warranty": 0.03,
        })
        assert card["type"] == "budget_breakdown"

    def test_generator_generic_fallback(self):
        """通用文本 → A2UI 卡片 fallback"""
        from app.services.a2ui_generator import generic_to_card
        card = generic_to_card("designer", "方案已生成")
        assert card["type"] == "alert_card"
        assert "方案已生成" in str(card["data"])

    def test_a2ui_feature_flag(self):
        """a2ui_enabled feature flag 已定义"""
        from app.config import get_settings
        s = get_settings()
        assert hasattr(s, "a2ui_enabled")
        assert s.a2ui_enabled is True


# ════════════════════════════════════════════════════════════════
# P1 HMAC-SHA256 审计签名
# ════════════════════════════════════════════════════════════════


class TestAuditIntegrity:
    """HMAC 审计完整性测试"""

    def test_hmac_sign_and_verify(self):
        """签名+验证往返测试"""
        from app.services.audit_integrity import compute_hmac, verify_hmac

        sig = compute_hmac(
            user_id="u-1", action="LOGIN", resource_type="user",
            resource_id="rid-1", details={"role": "admin"},
            timestamp="2026-07-22T10:00:00+00:00",
        )
        assert len(sig) == 64
        all(c in "0123456789abcdef" for c in sig)

        valid = verify_hmac(
            user_id="u-1", action="LOGIN", resource_type="user",
            resource_id="rid-1", details={"role": "admin"},
            timestamp="2026-07-22T10:00:00+00:00",
            signature=sig,
        )
        assert valid is True

    def test_hmac_detects_tampering(self):
        """HMAC 检测到篡改"""
        from app.services.audit_integrity import compute_hmac, verify_hmac

        sig = compute_hmac(
            user_id="u-1", action="LOGIN", resource_type="user",
            resource_id="rid-1", details={}, timestamp="t1",
        )
        # 篡改 user_id
        valid = verify_hmac(
            user_id="u-attacker", action="LOGIN", resource_type="user",
            resource_id="rid-1", details={}, timestamp="t1",
            signature=sig,
        )
        assert valid is False

    def test_sign_audit_entry_returns_none_when_disabled(self):
        """feature flag 关闭时不签名"""
        from app.config import get_settings
        from app.services.audit_integrity import sign_audit_entry

        original = get_settings().audit_hmac_enabled
        try:
            get_settings().audit_hmac_enabled = False
            result = sign_audit_entry("u-1", "LOGIN", "user", "rid-1", {})
            assert result is None
        finally:
            get_settings().audit_hmac_enabled = original

    def test_audit_hmac_feature_flag(self):
        """audit_hmac_enabled feature flag 已定义"""
        from app.config import get_settings
        s = get_settings()
        assert hasattr(s, "audit_hmac_enabled")
        assert s.audit_hmac_enabled is True

    def test_field_mask_levels(self):
        """字段级脱敏级别"""
        from app.services.audit_integrity import get_field_mask_level, should_mask_field
        assert get_field_mask_level("amount") == "L2"
        assert get_field_mask_level("bank_account") == "L3"
        assert get_field_mask_level("phone") == "L1"
        assert get_field_mask_level("note") == "L0"

        assert should_mask_field("amount", "contractor") is True
        assert should_mask_field("amount", "homeowner") is False
        assert should_mask_field("bank_account", "contractor") is True
        assert should_mask_field("bank_account", "admin") is False


# ════════════════════════════════════════════════════════════════
# P1 装修知识库 + 引用服务
# ════════════════════════════════════════════════════════════════


class TestKnowledgeBase:
    """装修知识库测试"""

    def test_4_json_files_exist(self):
        """4 个知识库 JSON 文件存在"""
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "knowledge"
        for fn in ["materials.json", "techniques.json", "standards.json", "faq.json"]:
            assert (root / fn).exists(), f"{fn} 不存在"

    def test_each_file_has_entries(self):
        """每个文件 >=15 条"""
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "knowledge"
        for fn in ["materials.json", "techniques.json", "standards.json", "faq.json"]:
            data = json.loads((root / fn).read_text(encoding="utf-8"))
            assert len(data) >= 15, f"{fn} 仅 {len(data)} 条"

    def test_entries_have_required_fields(self):
        """每条知识条目含 id/content/citation/tags"""
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "knowledge"
        for fn in ["materials.json", "techniques.json", "standards.json", "faq.json"]:
            data = json.loads((root / fn).read_text(encoding="utf-8"))
            for entry in data:
                assert "id" in entry
                assert "content" in entry
                assert "citation" in entry
                assert "tags" in entry

    @pytest.mark.asyncio
    async def test_loader_keyword_search(self):
        """知识库加载器关键词检索"""
        from knowledge.loader import KnowledgeLoader
        loader = KnowledgeLoader()
        results = await loader.search("瓷砖")
        assert len(results) > 0
        for r in results:
            assert "content" in r
            assert "citation" in r

    def test_citation_service(self):
        """引用服务格式化"""
        from app.services.citation_service import CitationService
        service = CitationService()
        evidence = [
            {"source": "materials", "content": "抛光砖...", "citation": "GB/T 4100-2015"},
        ]
        result = service.append_to_reply("这是回复内容", evidence)
        assert "📚" in result
        assert "GB/T 4100-2015" in result

    def test_qa_checklist(self):
        """QA 质检清单"""
        from app.services.qa_knowledge_service import QAKnowledgeService
        service = QAKnowledgeService()
        checklist = service.get_checklist("mep")
        assert len(checklist) > 0

    def test_knowledge_base_flag(self):
        """knowledge_base_enabled feature flag"""
        from app.config import get_settings
        s = get_settings()
        assert hasattr(s, "knowledge_base_enabled")
        assert s.knowledge_base_enabled is True


# ════════════════════════════════════════════════════════════════
# P2 施工健康 OS
# ════════════════════════════════════════════════════════════════


class TestHealthOS:
    """施工健康 OS 测试"""

    def test_rule_engine_normal(self):
        """正常进度判定"""
        from app.services.health_monitor import HealthRuleEngine, AlertLevel
        engine = HealthRuleEngine()
        level, reason = engine.evaluate(80, 82, 0, 0)
        assert level == AlertLevel.NORMAL

    def test_rule_engine_critical_overdue(self):
        """超期里程碑触发严重预警"""
        from app.services.health_monitor import HealthRuleEngine, AlertLevel
        engine = HealthRuleEngine()
        level, reason = engine.evaluate(40, 10, 2, 3)
        assert level == AlertLevel.CRITICAL
        assert "超期" in reason or "滞后" in reason

    def test_rule_engine_warning(self):
        """进度偏差 10-20% 触发警告"""
        from app.services.health_monitor import HealthRuleEngine, AlertLevel
        engine = HealthRuleEngine()
        level, reason = engine.evaluate(50, 35, 1, 0)
        assert level in (AlertLevel.WARNING, AlertLevel.SEVERE)

    def test_compute_health_score(self):
        """施工健康评分计算"""
        from app.services.health_monitor import HealthRuleEngine
        engine = HealthRuleEngine()
        score = engine.compute_health_score(50, 40, 1, 0, 10)
        assert score < 100
        assert score > 0

    def test_score_to_status(self):
        """评分 → 健康状态"""
        from app.services.health_monitor import HealthRuleEngine, HealthStatus
        engine = HealthRuleEngine()
        assert engine.score_to_status(90) == HealthStatus.HEALTHY
        assert engine.score_to_status(70) == HealthStatus.ATTENTION
        assert engine.score_to_status(50) == HealthStatus.AT_RISK
        assert engine.score_to_status(30) == HealthStatus.CRITICAL

    def test_health_os_flag(self):
        """health_os_enabled feature flag"""
        from app.config import get_settings
        s = get_settings()
        assert hasattr(s, "health_os_enabled")
        assert s.health_os_enabled is True

    def test_push_enabled_flag(self):
        """push_enabled feature flag"""
        from app.config import get_settings
        s = get_settings()
        assert hasattr(s, "push_enabled")
        assert s.push_enabled is True


# ════════════════════════════════════════════════════════════════
# 集成：v1.1.29 feature flags 完整性
# ════════════════════════════════════════════════════════════════


class TestV129FeatureFlags:
    """v1.1.29 全部 feature flags"""

    def test_all_v129_flags_in_settings(self):
        """所有 v1.1.29 feature flags 在 settings 中定义"""
        from app.config import get_settings
        s = get_settings()
        flags = [
            "audit_hmac_enabled", "health_os_enabled", "push_enabled",
            "a2ui_enabled", "knowledge_base_enabled", "service_role",
        ]
        for f in flags:
            assert hasattr(s, f), f"缺失 feature flag: {f}"

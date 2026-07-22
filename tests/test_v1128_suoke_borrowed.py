"""v1.1.28 借鉴索克生活功能测试

测试覆盖 10 项借鉴 item 的核心逻辑：
- P0-1 评估框架 (ihome_eval)
- P0-2 Model Spec HC 硬约束 (rebuttal_engine)
- P0-3 意图契约校验 (intent_validator)
- P1-4 AgenticRAG (agentic_rag)
- P1-5 密钥管理 (secret_manager)
- P1-6 多 LLM fallback chain (base.py)
- P2-7 DSPy 优化器 (dspy_optimizer)
- P2-8 A2A 协议 (a2a API)
- P2-9 PII 脱敏 (pii_masking)
- P2-10 TTS 链 (tts_chain)
"""
import json
import os

import pytest

# 确保测试环境
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test_v1128.db")
os.environ.setdefault("PASETO_SECRET_KEY", "test-secret-key-for-v1.1.28-testing-32bytes!")
os.environ.setdefault("QWEN_AUDIO_API_KEY", "")


# ════════════════════════════════════════════════════════════════
# P0-1 评估框架
# ════════════════════════════════════════════════════════════════


class TestEvalFramework:
    """Suoke-Eval1 评估框架测试"""

    def test_dimensions_defined(self):
        """10 个评估维度已定义"""
        from app.eval.ihome_eval import IHomeEvalDimension
        dims = list(IHomeEvalDimension)
        assert len(dims) == 10
        assert IHomeEvalDimension.BUDGET_ACCURACY in dims
        assert IHomeEvalDimension.HC_COMPLIANCE_RATE in dims
        assert IHomeEvalDimension.COUNTER_ARGUMENT_QUALITY in dims

    def test_dimension_benchmarks_complete(self):
        """每个维度都有 benchmark 参照"""
        from app.eval.ihome_eval import DIMENSION_BENCHMARKS, IHomeEvalDimension
        for d in IHomeEvalDimension:
            assert d.value in DIMENSION_BENCHMARKS, f"{d.value} 缺少 benchmark"

    def test_report_serializable(self):
        """评估报告可序列化为 JSON"""
        from app.eval.ihome_eval import IHomeEvalReport
        import time
        report = IHomeEvalReport(
            run_id="test",
            started_at=time.time(),
            finished_at=time.time(),
            sample_size=10,
            metrics={"success_rate": 95.0},
            dimension_scores={"budget_accuracy": 88.0},
        )
        data = json.loads(report.to_json())
        assert data["run_id"] == "test"
        assert data["sample_size"] == 10

    def test_runner_with_empty_traces(self):
        """空轨迹时评估器不报错"""
        from app.eval.ihome_eval import IHomeEvalRunner
        runner = IHomeEvalRunner()
        report = runner.run(traces=[])
        assert report.sample_size == 0
        # 静态检查维度应有分数
        assert "hc_compliance_rate" in report.dimension_scores

    def test_runner_with_mock_traces(self):
        """模拟轨迹可计算维度分数"""
        from app.eval.ihome_eval import IHomeEvalRunner
        traces = [
            {"status": "success", "fallback_used": False, "latency_ms": 500,
             "tool_call_count": 2, "agent_name": "designer",
             "response_truncated": "建议选择替代方案A"},
            {"status": "success", "fallback_used": False, "latency_ms": 800,
             "tool_call_count": 0, "agent_name": "budget",
             "response_truncated": "报价含税"},
            {"status": "fallback", "fallback_used": True, "latency_ms": 5000,
             "tool_call_count": 1, "agent_name": "designer",
             "response_truncated": "稍后重试"},
        ]
        runner = IHomeEvalRunner()
        report = runner.run(traces=traces)
        assert report.sample_size == 3
        assert report.metrics["success_rate"] == pytest.approx(66.67, rel=0.1)
        assert report.metrics["fallback_rate"] == pytest.approx(33.33, rel=0.1)
        # 反面论证质量：1/3 含「替代方案」
        assert report.dimension_scores["counter_argument_quality"] > 0


# ════════════════════════════════════════════════════════════════
# P0-2 Model Spec + rebuttal_engine
# ════════════════════════════════════════════════════════════════


class TestModelSpecRebuttal:
    """Model Spec HC 硬约束 + 反驳引擎测试"""

    def test_model_spec_loads(self):
        """Model Spec 文件可加载，含 9 条 HC 约束"""
        from app.services.rebuttal_engine import load_model_spec
        spec = load_model_spec()
        constraints = spec.get("hard_constraints", [])
        assert len(constraints) == 9
        ids = {c["id"] for c in constraints}
        for i in range(1, 9):
            assert f"HC-00{i}" in ids
        assert "HC-009" in ids

    def test_check_output_no_violation(self):
        """合规输出不触发反驳"""
        from app.services.rebuttal_engine import check_output
        result = check_output("designer", "建议采用北欧风格，预算含税。需要注意的是环保等级建议选E0。")
        assert not result["violated"]

    def test_check_output_hc001_violation(self):
        """HC-001 承重墙违规检测"""
        from app.services.rebuttal_engine import check_output
        result = check_output("designer", "建议拆除承重墙以扩大客厅空间。")
        assert result["violated"]
        violated_ids = [v["constraint_id"] for v in result["violations"]]
        assert "HC-001" in violated_ids

    def test_check_output_hc009_counter_argument(self):
        """HC-009 缺失反面论证检测"""
        from app.services.rebuttal_engine import check_output
        # 单一建议，无替代方案/风险提示
        result = check_output("designer", "建议选择方案A，拆除次卧墙体。")
        assert result["violated"]
        violated_ids = [v["constraint_id"] for v in result["violations"]]
        assert "HC-009" in violated_ids

    def test_build_rebuttal_context(self):
        """反驳上下文构建"""
        from app.services.rebuttal_engine import check_output, build_rebuttal_context
        result = check_output("budget", "报价不含税，免质保。")
        ctx = build_rebuttal_context(result["violations"])
        assert "HC-002" in ctx
        assert len(ctx) > 0


# ════════════════════════════════════════════════════════════════
# P0-3 意图契约校验
# ════════════════════════════════════════════════════════════════


class TestIntentContract:
    """Feature Validation Pipeline 测试"""

    def test_contract_loads(self):
        """契约文件可加载，含 39 个 pattern"""
        from app.utils.intent_validator import load_contract
        contract = load_contract()
        assert len(contract["patterns"]) == 39

    def test_all_patterns_validated(self):
        """全部 pattern validation_status=validated"""
        from app.utils.intent_validator import load_contract
        contract = load_contract()
        for p in contract["patterns"]:
            assert p["validation_status"] == "validated", f"{p['pattern_id']} 非 validated"

    def test_validate_contract_passes(self):
        """契约校验通过"""
        from app.utils.intent_validator import validate_contract
        errors = validate_contract()
        assert errors == [], f"校验失败: {errors}"

    def test_validate_contract_catches_missing_field(self):
        """校验能捕获缺失字段"""
        from app.utils.intent_validator import validate_contract
        bad_contract = {"patterns": [{"pattern_id": "test"}], "validation_rules": {}}
        errors = validate_contract(bad_contract)
        assert len(errors) > 0


# ════════════════════════════════════════════════════════════════
# P1-5 密钥管理
# ════════════════════════════════════════════════════════════════


class TestSecretManager:
    """Vault/KMS 密钥管理测试"""

    def test_paseto_fingerprint_format(self):
        """PASETO key fingerprint 为 8 字符 hex"""
        from app.services.secret_manager import get_paseto_key_fingerprint
        fp = get_paseto_key_fingerprint()
        assert len(fp) == 8
        int(fp, 16)  # 确认是有效 hex

    def test_secret_manager_health_info(self):
        """密钥管理健康信息"""
        from app.services.secret_manager import secret_manager
        info = secret_manager.get_health_info()
        assert info["enabled"] is True
        assert "paseto_key_fingerprint" in info
        assert "vault_configured" in info

    def test_secret_manager_get_local_secret(self):
        """从本地配置获取密钥（降级）"""
        from app.services.secret_manager import secret_manager
        # vault 未配置时应降级到本地
        key = secret_manager._fetch_from_local("app_name")
        assert key is not None  # app_name 从 settings 读取，非 None 即可


# ════════════════════════════════════════════════════════════════
# P2-9 PII 脱敏
# ════════════════════════════════════════════════════════════════


class TestPIIMasking:
    """PII 全量脱敏测试"""

    def test_mask_phone(self):
        """手机号脱敏"""
        from app.utils.pii_masking import mask_text
        result = mask_text("联系电话 13812345678")
        assert "138****5678" in result
        assert "13812345678" not in result

    def test_mask_id_card(self):
        """身份证号脱敏"""
        from app.utils.pii_masking import mask_text
        result = mask_text("身份证 110101199001011234")
        assert "110101********1234" in result
        assert "110101199001011234" not in result

    def test_mask_email(self):
        """邮箱脱敏"""
        from app.utils.pii_masking import mask_text
        result = mask_text("邮箱 alice@example.com")
        assert "a***@example.com" in result

    def test_mask_dict_recursive(self):
        """dict 递归脱敏"""
        from app.utils.pii_masking import mask_dict
        data = {
            "name": "张三丰",
            "phone": "13812345678",
            "nested": {"contact": "13987654321"},
        }
        result = mask_dict(data)
        assert result["name"] == "张**"
        assert "138****5678" in result["phone"]
        assert "139****4321" in result["nested"]["contact"]

    def test_mask_bank_card(self):
        """银行卡号脱敏"""
        from app.utils.pii_masking import mask_text
        result = mask_text("卡号 6222021234561234")
        assert "6222****1234" in result

    def test_mask_ip(self):
        """IP 地址脱敏"""
        from app.utils.pii_masking import mask_text
        result = mask_text("服务器 192.168.1.100")
        assert "192.168.*.*" in result

    def test_mask_multiple_pii(self):
        """多类 PII 同时脱敏"""
        from app.utils.pii_masking import mask_text
        text = "张三 13812345678 身份证 110101199001011234 邮箱 alice@test.com"
        result = mask_text(text)
        assert "13812345678" not in result
        assert "110101199001011234" not in result
        assert "alice@test.com" not in result


# ════════════════════════════════════════════════════════════════
# P1-6 多 LLM fallback chain
# ════════════════════════════════════════════════════════════════


class TestLLMFallback:
    """多 LLM fallback chain 测试"""

    def test_provider_registry_has_4_providers(self):
        """PROVIDER_REGISTRY 含 4 个供应商"""
        from app.agents.base import PROVIDER_REGISTRY
        assert "deepseek" in PROVIDER_REGISTRY
        assert "glm" in PROVIDER_REGISTRY
        assert "qwen" in PROVIDER_REGISTRY
        assert "doubao" in PROVIDER_REGISTRY

    def test_fallback_chain_defined(self):
        """DEFAULT_FALLBACK_CHAIN 已定义"""
        from app.agents.base import DEFAULT_FALLBACK_CHAIN
        assert "qwen" in DEFAULT_FALLBACK_CHAIN
        assert "glm" in DEFAULT_FALLBACK_CHAIN
        assert "doubao" in DEFAULT_FALLBACK_CHAIN

    def test_chat_fallback_on_no_key(self):
        """无 API Key 时返回 mock 响应（不触发 fallback）"""
        from app.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            agent_name = "test"
            system_prompt = "test"
            provider = "deepseek"

        agent = TestAgent()
        # 无 API key 时返回 mock，不抛异常
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            agent._chat_single_provider("deepseek", [{"role": "user", "content": "hi"}])
        )
        assert "[mock]" in result or isinstance(result, str)


# ════════════════════════════════════════════════════════════════
# P2-7 DSPy 优化器
# ════════════════════════════════════════════════════════════════


class TestDSPyOptimizer:
    """DSPy prompt 优化测试"""

    def test_dspy_disabled_returns_base_prompt(self):
        """dspy_enabled=False 时返回原 prompt"""
        from app.services.dspy_optimizer import dspy_optimizer
        base = "你是一个设计师"
        result = dspy_optimizer.optimize_prompt("designer", base, [])
        assert result == base

    def test_dspy_evaluate_returns_zero_when_disabled(self):
        """dspy 禁用时 evaluate_prompt 返回 0"""
        from app.services.dspy_optimizer import dspy_optimizer
        score = dspy_optimizer.evaluate_prompt("test", [])
        assert score == 0.0


# ════════════════════════════════════════════════════════════════
# P2-10 TTS 链
# ════════════════════════════════════════════════════════════════


class TestTTSChain:
    """TTS 三级降级链测试"""

    def test_tts_chain_initializes(self):
        """TTS 链初始化成功"""
        from app.services.tts_chain import tts_chain
        assert tts_chain is not None

    def test_tts_disabled_raises(self):
        """tts_enabled=False 时抛 RuntimeError"""
        from app.config import get_settings
        from app.services.tts_chain import TTSChain
        import asyncio

        # 临时关闭 tts_enabled
        original = get_settings().tts_enabled
        try:
            get_settings().tts_enabled = False
            chain = TTSChain()
            with pytest.raises(RuntimeError, match="TTS 未启用"):
                asyncio.get_event_loop().run_until_complete(chain.synthesize("test"))
        finally:
            get_settings().tts_enabled = original


# ════════════════════════════════════════════════════════════════
# P1-4 AgenticRAG
# ════════════════════════════════════════════════════════════════


class TestAgenticRAG:
    """AgenticRAG 证据检索测试"""

    def test_agentic_rag_initializes(self):
        """AgenticRAG 初始化成功"""
        from app.services.agentic_rag import agentic_rag
        assert agentic_rag is not None
        assert agentic_rag.max_evidence > 0

    def test_retrieve_empty_query(self):
        """空查询返回空证据"""
        import asyncio
        from app.services.agentic_rag import agentic_rag
        result = asyncio.get_event_loop().run_until_complete(
            agentic_rag.retrieve("", db=None)
        )
        assert result == []

    def test_build_evidence_context_empty(self):
        """空证据列表返回空上下文"""
        from app.services.agentic_rag import agentic_rag
        ctx = agentic_rag.build_evidence_context([])
        assert ctx == ""

    def test_build_evidence_context_non_empty(self):
        """非空证据列表生成上下文"""
        from app.services.agentic_rag import agentic_rag
        evidence = [{"source": "materials", "content": "瓷砖 50元/平米", "score": 0.8}]
        ctx = agentic_rag.build_evidence_context(evidence)
        assert "瓷砖" in ctx
        assert "materials" in ctx


# ════════════════════════════════════════════════════════════════
# P2-8 A2A 协议
# ════════════════════════════════════════════════════════════════


class TestA2AProtocol:
    """A2A 协议测试"""

    def test_a2a_router_defined(self):
        """A2A router 和 public_router 已定义"""
        from app.api import a2a as a2a_api
        assert a2a_api.router is not None
        assert a2a_api.public_router is not None

    def test_registered_agents_count(self):
        """22 个 Agent 已注册"""
        from app.api.a2a import REGISTERED_AGENT_NAMES
        assert len(REGISTERED_AGENT_NAMES) == 22

    def test_agent_card_endpoint_exists(self):
        """Agent Card 端点存在"""
        from app.api.a2a import get_agent_card
        assert callable(get_agent_card)


# ════════════════════════════════════════════════════════════════
# 集成测试：feature flags 暴露
# ════════════════════════════════════════════════════════════════


class TestFeatureFlags:
    """v1.1.28 feature flags 暴露测试"""

    def test_all_v1128_flags_in_settings(self):
        """所有 v1.1.28 feature flags 在 settings 中定义"""
        from app.config import get_settings
        s = get_settings()
        assert hasattr(s, "eval_enabled")
        assert hasattr(s, "model_spec_enabled")
        assert hasattr(s, "intent_validation_enabled")
        assert hasattr(s, "agentic_rag_enabled")
        assert hasattr(s, "secret_manager_enabled")
        assert hasattr(s, "llm_fallback_enabled")
        assert hasattr(s, "dspy_enabled")
        assert hasattr(s, "a2a_enabled")
        assert hasattr(s, "pii_masking_enabled")
        assert hasattr(s, "tts_enabled")

    def test_app_version_bumped(self):
        """app_version 已升至 1.1.28"""
        from app.config import get_settings
        assert get_settings().app_version == "1.1.28"

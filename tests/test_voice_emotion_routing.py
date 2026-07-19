"""测试语音情绪路由层与 Qwen-Audio-3.0-Realtime Plus 支持。

测试覆盖：
- _get_emotion_aware_system_prefix 各情绪分支与置信度阈值
- _route_voice_to_agent 接收 emotion 参数（mock 模式不报错）
- emotion_prefix 确实被注入到 user_ctx（非 mock 模式 + Mock Agent.think 捕获）
- VOICE_SYSTEM_INSTRUCTIONS_PLUS 常量包含 Plus 关键字
- 实时语音端点未认证返回 401
"""

import pytest


# ── 情绪路由辅助函数测试 ──

class TestGetEmotionAwareSystemPrefix:
    """_get_emotion_aware_system_prefix 函数测试"""

    def test_get_emotion_aware_system_prefix_neutral(self):
        """neutral 情绪应返回空字符串"""
        from app.api.voice_realtime import _get_emotion_aware_system_prefix

        result = _get_emotion_aware_system_prefix({"label": "neutral", "score": 0.9})
        assert result == ""

    def test_get_emotion_aware_system_prefix_anxious(self):
        """anxious 情绪应返回包含"焦虑"的前缀"""
        from app.api.voice_realtime import _get_emotion_aware_system_prefix

        result = _get_emotion_aware_system_prefix({"label": "anxious", "score": 0.8})
        assert result  # 非空
        assert "焦虑" in result

    def test_get_emotion_aware_system_prefix_low_score(self):
        """score < 0.4 应返回空字符串（置信度低，不注入）"""
        from app.api.voice_realtime import _get_emotion_aware_system_prefix

        result = _get_emotion_aware_system_prefix({"label": "anxious", "score": 0.3})
        assert result == ""

    def test_get_emotion_aware_system_prefix_angry(self):
        """angry 情绪应返回包含"不满"的前缀"""
        from app.api.voice_realtime import _get_emotion_aware_system_prefix

        result = _get_emotion_aware_system_prefix({"label": "angry", "score": 0.85})
        assert result  # 非空
        assert "不满" in result

    def test_get_emotion_aware_system_prefix_none(self):
        """emotion 为 None 应返回空字符串"""
        from app.api.voice_realtime import _get_emotion_aware_system_prefix

        result = _get_emotion_aware_system_prefix(None)
        assert result == ""

    def test_get_emotion_aware_system_prefix_other_emotions(self):
        """其他情绪（sad/tired/excited/happy）也应返回对应前缀"""
        from app.api.voice_realtime import _get_emotion_aware_system_prefix

        cases = {
            "sad": "低落",
            "tired": "疲惫",
            "excited": "兴奋",
            "happy": "愉悦",
        }
        for label, keyword in cases.items():
            result = _get_emotion_aware_system_prefix({"label": label, "score": 0.7})
            assert keyword in result, f"label={label} 应包含 '{keyword}'"


# ── Agent 管道路由测试 ──

class TestRouteVoiceWithEmotion:
    """_route_voice_to_agent 接收 emotion 参数测试"""

    @pytest.mark.asyncio
    async def test_route_voice_with_emotion(self):
        """调用 _route_voice_to_agent 传入 emotion 参数，mock 模式下不报错"""
        from app.api.voice_realtime import _route_voice_to_agent

        emotion = {"label": "anxious", "score": 0.8}
        # conftest.py 已禁用 API Key，强制走 mock 模式
        reply = await _route_voice_to_agent(
            "我家装修延期了很着急", "design", "test_user", emotion=emotion
        )
        assert isinstance(reply, str)
        assert len(reply) > 0

    @pytest.mark.asyncio
    async def test_route_voice_emotion_injection(self, monkeypatch):
        """验证 emotion_prefix 确实被注入到 user_ctx（通过 mock Agent.think 捕获）"""
        from app.api import voice_realtime
        from app.config import get_settings

        # 启用非 mock 模式以走 agent.think(text, user_ctx) 路径
        settings = get_settings()
        monkeypatch.setattr(settings, "deepseek_api_key", "fake_key_for_test")

        captured_user_ctx = []

        class MockDesignerAgent:
            """Mock DesignerAgent，仅捕获 user_ctx 参数"""

            def __init__(self):
                pass

            async def think(self, text, user_ctx):
                captured_user_ctx.append(user_ctx)
                return '{"reply": "测试回复"}'

            async def close(self):
                pass

        # Mock DesignerAgent 类（函数内部 from ... import 会拿到 patched 版本）
        import app.agents.designer as designer_mod
        monkeypatch.setattr(designer_mod, "DesignerAgent", MockDesignerAgent)

        # Mock _extract_reply_from_llm_json（函数内部 from ... import 会拿到 patched 版本）
        import app.api.agents as agents_mod
        monkeypatch.setattr(
            agents_mod, "_extract_reply_from_llm_json", lambda raw: "测试回复"
        )

        emotion = {"label": "anxious", "score": 0.8}
        reply = await voice_realtime._route_voice_to_agent(
            "我家装修延期了", "design", "test_user", emotion=emotion
        )

        assert reply == "测试回复"
        # 验证 Agent.think 被调用且 user_ctx 包含情绪前缀
        assert len(captured_user_ctx) == 1
        captured = captured_user_ctx[0]
        assert "【用户情绪：焦虑】" in captured
        assert "焦虑" in captured
        # 用户上下文也应保留
        assert "test_user" in captured

    @pytest.mark.asyncio
    async def test_route_voice_without_emotion(self):
        """不传 emotion 参数时应正常工作（向后兼容）"""
        from app.api.voice_realtime import _route_voice_to_agent

        # general 意图在 mock 模式下走 _get_enhanced_reply，返回 str
        reply = await _route_voice_to_agent(
            "你好，想咨询装修", "general", "test_user"
        )
        assert isinstance(reply, str)
        assert len(reply) > 0


# ── Plus 模型指令常量测试 ──

class TestPlusInstructionsConstant:
    """VOICE_SYSTEM_INSTRUCTIONS_PLUS 常量测试"""

    def test_voice_plus_instructions_constant(self):
        """VOICE_SYSTEM_INSTRUCTIONS_PLUS 应包含 Plus 关键字"""
        from app.api.voice_realtime import (
            VOICE_SYSTEM_INSTRUCTIONS,
            VOICE_SYSTEM_INSTRUCTIONS_PLUS,
        )

        assert "Plus" in VOICE_SYSTEM_INSTRUCTIONS_PLUS
        # Plus 变体应基于原指令扩展（包含原文）
        assert VOICE_SYSTEM_INSTRUCTIONS in VOICE_SYSTEM_INSTRUCTIONS_PLUS
        # Plus 变体应比原指令更长
        assert len(VOICE_SYSTEM_INSTRUCTIONS_PLUS) > len(VOICE_SYSTEM_INSTRUCTIONS)

    def test_voice_plus_instructions_contains_emotion_keywords(self):
        """Plus 指令应包含情感感知相关关键词"""
        from app.api.voice_realtime import VOICE_SYSTEM_INSTRUCTIONS_PLUS

        # 验证 Plus 模型增强能力描述
        assert "情感感知" in VOICE_SYSTEM_INSTRUCTIONS_PLUS
        assert "副语言" in VOICE_SYSTEM_INSTRUCTIONS_PLUS


# ── 实时语音端点认证测试 ──

class TestVoiceRealtimeEndpointAuth:
    """实时语音端点认证测试"""

    @pytest.mark.asyncio
    async def test_voice_realtime_endpoint_unauth(self, client):
        """未认证调用实时语音端点应返回 401"""
        resp = await client.post(
            "/api/voice/process-enhanced",
            json={"text": "你好", "emotion_enabled": False},
        )
        assert resp.status_code == 401

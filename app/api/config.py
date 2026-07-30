"""配置查询 API — 暴露 feature flags 给前端，支持按需加载长线技术决策模块

注：/config/feature-flags 为公开端点（无认证），因为：
1. feature flags 是全局开关非用户数据，无敏感性
2. Flutter main() 在登录前调用（feature_flags_service.dart→main.dart:27）
3. Web 控制台 PlaceholderHome 在登录前调用（api-client.ts:92）
4. 若加认证，登录前的 401 会触发全局 401 回调强制登出，破坏登录流程
"""
from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(prefix="/config", tags=["配置"])
settings = get_settings()


@router.get("/feature-flags")
async def get_feature_flags():
    """返回前端可用的 feature flags，用于按需加载 Filament/OpenCascade.js 等

    公开端点：Flutter 应用启动时（登录前）需先拉取特性标志决定按需加载策略。
    """
    return {
        "filament_enabled": settings.filament_enabled,
        "opencascade_enabled": settings.opencascade_enabled,
        "agent_learning_enabled": settings.agent_learning_enabled,
        "agent_function_call_enabled": settings.agent_function_call_enabled,
        "vector_db_url_configured": bool(settings.vector_db_url),
        "harness_enabled": settings.harness_trace_enabled,
        "agent_evolution_enabled": settings.agent_evolution_enabled,
        # v1.1.12 新增 feature flags
        "mcp_enabled": settings.mcp_enabled,
        "ai_render_enabled": settings.ai_render_enabled,
        "voice_emotion_routing_enabled": settings.voice_emotion_routing_enabled,
        "qwen_audio_model": settings.qwen_audio_model,
        "qwen_audio_model_variant": "plus" if settings.qwen_audio_model.endswith("-plus") else "flash",
        # v1.1.21 暴露
        "voice_audio_prompt_enabled": settings.voice_audio_prompt_enabled,
        # v1.2.7 借鉴 Qwen-Audio-3.0-Realtime：语音编排 + 场景画像
        "voice_agent_orchestration_enabled": settings.voice_agent_orchestration_enabled,
        "voice_scenario": settings.voice_scenario,
        "voice_duplex_mode": settings.voice_duplex_mode,
        # v1.2.8 悬浮窗常驻语音 + 讨论式方案交互
        "voice_floating_widget_enabled": settings.voice_floating_widget_enabled,
        "design_proposal_llm_enabled": settings.design_proposal_llm_enabled,
        # v1.1.28 借鉴索克生活 feature flags
        "eval_enabled": settings.eval_enabled,
        "model_spec_enabled": settings.model_spec_enabled,
        "intent_validation_enabled": settings.intent_validation_enabled,
        "agentic_rag_enabled": settings.agentic_rag_enabled,
        "secret_manager_enabled": settings.secret_manager_enabled,
        "llm_fallback_enabled": settings.llm_fallback_enabled,
        "dspy_enabled": settings.dspy_enabled,
        "a2a_enabled": settings.a2a_enabled,
        "pii_masking_enabled": settings.pii_masking_enabled,
        "tts_enabled": settings.tts_enabled,
        # v1.1.29 补短 feature flags
        "audit_hmac_enabled": settings.audit_hmac_enabled,
        "health_os_enabled": settings.health_os_enabled,
        "push_enabled": settings.push_enabled,
        "a2ui_enabled": settings.a2ui_enabled,
        "console_v2_enabled": settings.console_v2_enabled,
        "knowledge_base_enabled": settings.knowledge_base_enabled,
        "service_role": settings.service_role or None,
    }

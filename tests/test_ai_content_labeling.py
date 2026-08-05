"""AI 生成内容标识测试（《人工智能生成合成内容标识办法》合规，v1.9.0 P0）

覆盖:
- build_explicit_label 显式标识构建
- build_implicit_metadata 隐式标识元数据（水印字段预埋）
- annotate_output flag 开关行为（关闭零回归 / 开启追加 ai_content_label + ai_content_meta）
- AIRenderService.render_3d mock 路径集成（flag 关闭不带标识字段 / 开启带标识字段）

遵循项目红线：仅用 monkeypatch.setattr(get_settings(), ...) 切换 flag，
禁止调用 get_settings.cache_clear()（会导致跨文件测试隔离失败）。
"""

import pytest

from app.config import get_settings
from app.services.ai_content_labeling import (
    EXPLICIT_LABEL_TEXT,
    annotate_output,
    build_explicit_label,
    build_implicit_metadata,
)
from app.services.ai_render_service import AIRenderService, _RenderAgent


# ── build_explicit_label 显式标识 ─────────────────────────


def test_build_explicit_label_fields():
    """build_explicit_label 返回 4 个字段且 ai_generated=True、label_text 非空"""
    label = build_explicit_label("render", "render_3d")
    assert set(label.keys()) == {"label_text", "ai_generated", "content_type", "source"}
    assert label["ai_generated"] is True
    assert label["label_text"] == EXPLICIT_LABEL_TEXT
    assert label["content_type"] == "render"
    assert label["source"] == "render_3d"


# ── build_implicit_metadata 隐式标识（水印字段预埋）────────


def test_build_implicit_metadata_fields():
    """build_implicit_metadata 返回 watermark_version 等字段"""
    meta = build_implicit_metadata("render")
    assert meta["ai_generated"] is True
    assert meta["producer"] == "i-home.life-ai"
    assert meta["content_type"] == "render"
    assert meta["watermark_version"] == "1.0"
    assert meta["label_method"] == "meta"
    # 自定义 producer 生效
    assert build_implicit_metadata("render", producer="custom")["producer"] == "custom"


# ── annotate_output flag 开关行为 ─────────────────────────


def test_annotate_output_flag_off_returns_unchanged(monkeypatch):
    """flag 关闭时 annotate_output 原样返回（零回归）"""
    monkeypatch.setattr(get_settings(), "ai_content_labeling_enabled", False)
    result = {"prompt": "test prompt", "style": "modern"}
    out = annotate_output(result, content_type="render", source="render_2d")
    assert out is result
    assert out == {"prompt": "test prompt", "style": "modern"}
    assert "ai_content_label" not in out
    assert "ai_content_meta" not in out


def test_annotate_output_flag_on_appends_fields(monkeypatch):
    """flag 开启时 annotate_output 追加 ai_content_label + ai_content_meta 两个字段且值正确"""
    monkeypatch.setattr(get_settings(), "ai_content_labeling_enabled", True)
    result = {"prompt": "test prompt", "style": "modern"}
    out = annotate_output(result, content_type="render", source="render_2d")
    # 原有字段保持不变
    assert out["prompt"] == "test prompt"
    assert out["style"] == "modern"
    # 显式标识
    label = out["ai_content_label"]
    assert label["ai_generated"] is True
    assert label["label_text"] == EXPLICIT_LABEL_TEXT
    assert label["content_type"] == "render"
    assert label["source"] == "render_2d"
    # 隐式标识
    meta = out["ai_content_meta"]
    assert meta["ai_generated"] is True
    assert meta["producer"] == "i-home.life-ai"
    assert meta["content_type"] == "render"
    assert meta["watermark_version"] == "1.0"
    assert meta["label_method"] == "meta"


# ── AIRenderService 集成（render_3d mock 路径）────────────


async def _mock_render_agent_chat(self, messages):
    """monkeypatch _RenderAgent._chat：跳过真实 LLM 调用，返回确定 JSON"""
    return '{"prompts": ["top view, modern interior, photorealistic"]}'


@pytest.mark.asyncio
async def test_render_3d_mock_flag_off_no_label_fields(monkeypatch):
    """flag 关闭时 render_3d mock 路径返回不带 ai_content_label/ai_content_meta"""
    monkeypatch.setattr(get_settings(), "ai_content_labeling_enabled", False)
    monkeypatch.setattr(_RenderAgent, "_chat", _mock_render_agent_chat)

    svc = AIRenderService()
    result = await svc.render_3d(
        floorplan={"rooms": [{"name": "客厅", "w": 5.0, "h": 4.0}]},
        style="modern",
        user_id="label-test-user",
        db=None,
    )
    # 原有字段保持
    assert "prompts" in result
    assert "model_url" in result
    assert "render_backend" in result
    # 零回归：不带标识字段
    assert "ai_content_label" not in result
    assert "ai_content_meta" not in result


@pytest.mark.asyncio
async def test_render_3d_mock_flag_on_has_label_fields(monkeypatch):
    """flag 开启时 render_3d mock 路径返回带 ai_content_label/ai_content_meta"""
    monkeypatch.setattr(get_settings(), "ai_content_labeling_enabled", True)
    monkeypatch.setattr(_RenderAgent, "_chat", _mock_render_agent_chat)

    svc = AIRenderService()
    result = await svc.render_3d(
        floorplan={"rooms": [{"name": "客厅", "w": 5.0, "h": 4.0}]},
        style="modern",
        user_id="label-test-user",
        db=None,
    )
    # 原有字段保持
    assert "prompts" in result
    assert "model_url" in result
    # 显式标识
    label = result["ai_content_label"]
    assert label["ai_generated"] is True
    assert label["content_type"] == "render"
    assert label["source"] == "render_3d"
    # 隐式标识
    meta = result["ai_content_meta"]
    assert meta["ai_generated"] is True
    assert meta["producer"] == "i-home.life-ai"
    assert meta["watermark_version"] == "1.0"

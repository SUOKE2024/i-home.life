"""AI 生成内容标识（《人工智能生成合成内容标识办法》合规）

显式标识：内容可感知提示（文本标注）
隐式标识：文件元数据字段预埋（水印字段）
受 settings.ai_content_labeling_enabled 控制，关闭时 annotate_output 原样返回。
"""

from app.config import get_settings

# 显式标识文案（简短、可感知）
EXPLICIT_LABEL_TEXT = "本内容由 AI 生成，请注意甄别"


def build_explicit_label(content_type: str, source: str) -> dict:
    """构建显式标识。返回：
    {"label_text": "本内容由 AI 生成，请注意甄别", "ai_generated": True,
     "content_type": ..., "source": ...}"""
    return {
        "label_text": EXPLICIT_LABEL_TEXT,
        "ai_generated": True,
        "content_type": content_type,
        "source": source,
    }


def build_implicit_metadata(content_type: str, producer: str = "i-home.life-ai") -> dict:
    """构建隐式标识元数据（水印字段预埋）。返回：
    {"ai_generated": True, "producer": ..., "content_type": ...,
     "watermark_version": "1.0", "label_method": "meta"}"""
    return {
        "ai_generated": True,
        "producer": producer,
        "content_type": content_type,
        "watermark_version": "1.0",
        "label_method": "meta",
    }


def annotate_output(result: dict, content_type: str, source: str) -> dict:
    """flag 开启时在 result 中补显式标识字段 "ai_content_label" 与
    隐式标识字段 "ai_content_meta"；flag 关闭时原样返回 result（零回归）。
    读取 settings 用 `from app.config import get_settings; get_settings().ai_content_labeling_enabled`。"""
    if not get_settings().ai_content_labeling_enabled:
        return result
    result["ai_content_label"] = build_explicit_label(content_type, source)
    result["ai_content_meta"] = build_implicit_metadata(content_type)
    return result

"""图片识别服务 — 图片预处理 + 多模态 AI 识别产品信息"""

import base64
import io
import json
import logging
import re

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger("ihome")

# 产品分类映射（中文 → 代码）
CATEGORY_CN_TO_CODE = {
    "瓷砖": "tile", "地砖": "tile", "墙砖": "tile", "岩板": "tile",
    "地板": "flooring", "木地板": "flooring", "复合地板": "flooring",
    "橱柜": "cabinet", "衣柜": "cabinet", "定制柜": "cabinet",
    "涂料": "paint", "乳胶漆": "paint", "油漆": "paint", "艺术漆": "paint",
    "灯具": "lighting", "灯": "lighting", "吊灯": "lighting", "吸顶灯": "lighting", "筒灯": "lighting", "射灯": "lighting",
    "家电": "appliance", "空调": "appliance", "冰箱": "appliance", "洗衣机": "appliance", "洗碗机": "appliance", "电视": "appliance",
    "窗帘": "curtain", "百叶窗": "curtain", "纱帘": "curtain",
    "定制家具": "custom_furniture", "沙发": "custom_furniture", "餐桌": "custom_furniture",
    "床": "custom_furniture", "书柜": "custom_furniture", "鞋柜": "custom_furniture",
    "服务": "service",
    "其他": "other",
}

CATEGORY_UNIT_MAP = {
    "tile": "㎡", "flooring": "㎡", "cabinet": "m",
    "paint": "桶", "lighting": "个", "appliance": "台",
    "curtain": "m", "custom_furniture": "件", "service": "次", "other": "个",
}


def preprocess_image(image_data: bytes, max_size: int = 1024, quality: int = 80) -> bytes:
    """图片预处理：调整大小 + WebP 格式压缩

    Args:
        image_data: 原始图片字节
        max_size: 最大边长（px）
        quality: WebP 压缩质量 1-100

    Returns:
        处理后的 WebP 字节
    """
    # v1.1.14: 延迟导入 PIL，减少应用启动时间和内存占用
    from PIL import Image
    img = Image.open(io.BytesIO(image_data))

    # 转换为 RGB（WebP 不支持 RGBA 透明度）
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # 等比缩放
    w, h = img.size
    if max(w, h) > max_size:
        ratio = max_size / max(w, h)
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # 导出 WebP
    output = io.BytesIO()
    img.save(output, format="WEBP", quality=quality)
    output.seek(0)
    return output.getvalue()


def image_to_base64(image_data: bytes) -> str:
    """将图片字节转为 base64 data URI"""
    b64 = base64.b64encode(image_data).decode("utf-8")
    return f"data:image/webp;base64,{b64}"


async def recognize_product_from_image(image_data: bytes, context: str = "") -> dict:
    """使用多模态 AI 识别图片中的产品信息

    Args:
        image_data: 预处理后的图片字节
        context: 用户补充的文字说明（如语音输入）

    Returns:
        {"name": str, "category": str, "category_cn": str, "material": str, "color": str,
         "style": str, "confidence": float, "suggested_tags": list[str], "raw_reply": str}
    """
    # 预处理图片
    processed = preprocess_image(image_data)
    b64_uri = image_to_base64(processed)

    # 选择可用的多模态模型
    provider, model, api_key, api_base = _get_vision_provider()
    if not api_key:
        return _fallback_recognize(context)

    prompt = """请识别这张装修材料/家居产品图片，提取以下信息并以 JSON 格式回复：

{
  "name": "产品名称（含主要规格，如 800×800 灰色防滑地砖）",
  "category": "产品分类中文名（从以下列表中选最匹配的）：瓷砖、地板、橱柜、涂料、灯具、家电、窗帘、定制家具、服务、其他",
  "material": "主要材质（如陶瓷、实木、不锈钢等）",
  "color": "主要颜色",
  "style": "风格（如现代简约、北欧、新中式、工业风等）",
  "confidence": 0.85,
  "tags": ["标签1", "标签2", "标签3"]
}

识别要点：
1. name 必须包含主要尺寸规格（如有）
2. category 必须从上述列表中选择
3. confidence 表示识别置信度 0-1
4. tags 选取 3-5 个最相关的标签
5. 如果图片不清晰或无法确定，confidence 设低并说明原因
"""

    if context:
        prompt += f"\n\n用户补充说明：{context}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": b64_uri}},
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 512,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            return _parse_recognition_result(content, context)

    except Exception as e:
        logger.warning(f"多模态 AI 识别失败: {e}")
        return _fallback_recognize(context)


def _get_vision_provider() -> tuple[str, str, str, str]:
    """获取可用的多模态模型提供商"""
    # 优先使用 DeepSeek vision
    if settings.deepseek_api_key:
        return ("deepseek", settings.deepseek_model, settings.deepseek_api_key, settings.deepseek_api_base)
    # 降级 GLM vision
    if settings.glm_api_key:
        return ("glm", "glm-4v-plus", settings.glm_api_key, settings.glm_api_base)
    return ("", "", "", "")


def _parse_recognition_result(content: str, context: str = "") -> dict:
    """解析 AI 返回的识别结果"""
    text = content.strip()
    result = _try_parse_json(text)

    # 补充 context 信息
    if context and result.get("confidence", 0) < 0.7:
        result = _merge_context(result, context)

    # 补充分类信息
    category_cn = result.get("category", "")
    if category_cn:
        for cn, code in CATEGORY_CN_TO_CODE.items():
            if cn in category_cn:
                result["category_code"] = code
                result["category_cn"] = cn
                result["suggested_unit"] = CATEGORY_UNIT_MAP.get(code, "个")
                break
    if "category_code" not in result:
        result["category_code"] = "other"
        result["category_cn"] = "其他"
        result["suggested_unit"] = "个"

    return result


def _try_parse_json(text: str) -> dict:
    """尝试解析 JSON，失败则用正则提取"""
    if not text:
        return {"confidence": 0.6, "name": "未识别产品", "category": "其他"}

    # 清除 markdown 代码块
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    # 用正则兜底提取
    result = {"raw_reply": text[:300]}
    patterns = {
        "name": r'"name"\s*:\s*"([^"]+)"',
        "category": r'"category"\s*:\s*"([^"]+)"',
        "material": r'"material"\s*:\s*"([^"]+)"',
        "color": r'"color"\s*:\s*"([^"]+)"',
        "style": r'"style"\s*:\s*"([^"]+)"',
        "confidence": r'"confidence"\s*:\s*([\d.]+)',
    }
    for key, pat in patterns.items():
        m = re.search(pat, text)
        if m:
            val = m.group(1)
            if key == "confidence":
                try:
                    result[key] = float(val)
                except ValueError:
                    result[key] = 0.7
            else:
                result[key] = val

    # 提取 tags
    tags_m = re.findall(r'"tags"\s*:\s*\[([^\]]+)\]', text)
    if tags_m:
        tags_str = tags_m[0]
        result["tags"] = [t.strip().strip('"').strip("'") for t in tags_str.split(",") if t.strip()]

    result.setdefault("confidence", 0.6)
    result.setdefault("name", "未识别产品")
    result.setdefault("category", "其他")
    return result


def _merge_context(result: dict, context: str) -> dict:
    """将用户补充的文字说明合并到识别结果"""
    # 从 context 中提取价格信息
    price_m = re.search(r'(\d+\.?\d*)\s*元', context)
    if price_m:
        result["suggested_price"] = float(price_m.group(1))

    # 提取标签
    tags = re.findall(r'#(\S+)', context)
    if tags:
        existing = result.get("tags", [])
        result["tags"] = list(dict.fromkeys(existing + tags))[:8]

    # 提取产地
    place_m = re.search(r'(广东|佛山|浙江|上海|北京|成都|深圳|东莞)[\u4e00-\u9fa5]{0,3}(产|制造)', context)
    if place_m:
        result["origin"] = place_m.group(0)

    return result


def _fallback_recognize(context: str = "") -> dict:
    """无 AI API 时的降级识别（基于文字推断）"""
    result = {
        "name": "未识别产品（请手动输入）",
        "category": "other",
        "category_cn": "其他",
        "category_code": "other",
        "suggested_unit": "个",
        "material": "",
        "color": "",
        "style": "",
        "confidence": 0.0,
        "tags": [],
        "fallback": True,
    }

    if context:
        # 从文字中推断分类
        for cn, code in CATEGORY_CN_TO_CODE.items():
            if cn in context:
                result["category"] = cn
                result["category_cn"] = cn
                result["category_code"] = code
                result["suggested_unit"] = CATEGORY_UNIT_MAP.get(code, "个")
                result["confidence"] = 0.5
                break

        # 提取标签
        tags = re.findall(r'#(\S+)', context)
        if tags:
            result["tags"] = tags[:5]

        # 提取价格
        price_m = re.search(r'(\d+\.?\d*)\s*元', context)
        if price_m:
            result["suggested_price"] = float(price_m.group(1))

        if len(context) > 5 and result["confidence"] < 0.5:
            result["name"] = context[:40]
            result["confidence"] = 0.3

    return result

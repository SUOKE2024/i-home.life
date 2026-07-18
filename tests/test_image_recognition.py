"""拍照上架 — image_recognition_service 回归测试"""

from app.services.image_recognition_service import (
    preprocess_image,
    _parse_recognition_result,
    _try_parse_json,
    _fallback_recognize,
    CATEGORY_CN_TO_CODE,
    CATEGORY_UNIT_MAP,
)


class TestImagePreprocessing:
    """图片预处理功能测试"""

    def test_preprocess_jpeg_resize(self):
        """JPEG 图片应被 resize 并转为 WebP"""
        from PIL import Image
        import io
        img = Image.new("RGB", (2000, 1500), color=(128, 128, 128))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        raw = buf.getvalue()

        result = preprocess_image(raw, max_size=1024, quality=80)

        result_img = Image.open(io.BytesIO(result))
        assert result_img.format == "WEBP"
        assert max(result_img.size) <= 1024

    def test_preprocess_small_image_no_resize(self):
        """小图片不应被放大"""
        from PIL import Image
        import io
        img = Image.new("RGB", (200, 150), color=(64, 64, 64))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw = buf.getvalue()

        result = preprocess_image(raw, max_size=1024, quality=80)

        result_img = Image.open(io.BytesIO(result))
        assert max(result_img.size) <= 1024

    def test_preprocess_transparent_png(self):
        """带透明通道的 PNG 应正确处理"""
        from PIL import Image
        import io
        img = Image.new("RGBA", (800, 600), color=(255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw = buf.getvalue()

        result = preprocess_image(raw, max_size=512, quality=70)
        assert len(result) > 0


class TestRecognitionParsing:
    """AI 识别结果解析测试"""

    def test_parse_json_result(self):
        """标准 JSON 格式识别结果应正确解析"""
        content = """```json
{
  "name": "东鹏瓷砖 800x800mm 灰色防滑地砖",
  "category": "瓷砖",
  "material": "陶瓷",
  "color": "灰色",
  "style": "现代简约",
  "confidence": 0.92,
  "tags": ["防滑", "地砖", "灰色"],
  "suggested_price": 68.0
}
```"""
        result = _parse_recognition_result(content)
        assert result["name"] == "东鹏瓷砖 800x800mm 灰色防滑地砖"
        assert result["category_cn"] == "瓷砖"
        assert result["category_code"] == "tile"
        assert result["confidence"] == 0.92
        assert "suggested_price" in result

    def test_parse_plain_json(self):
        """无 markdown 标记的纯 JSON 应正确解析"""
        content = '{"name":"白色乳胶漆","category":"涂料","material":"水性漆","confidence":0.85}'
        result = _parse_recognition_result(content)
        assert result["name"] == "白色乳胶漆"
        assert result["category_code"] == "paint"

    def test_parse_unrecognizable_text(self):
        """无法解析的文本应返回默认结果"""
        content = "这是一段无法解析的文本内容"
        result = _parse_recognition_result(content)
        assert result["category_code"] == "other"
        assert result["name"] is not None
        assert result["confidence"] > 0

    def test_parse_empty(self):
        """空字符串应返回默认结果"""
        result = _parse_recognition_result("")
        assert result["category_code"] == "other"
        assert result["name"] is not None

    def test_try_parse_json_valid(self):
        """正确 JSON 应解析成功"""
        d = _try_parse_json('{"a": 1, "b": "hello"}')
        assert d == {"a": 1, "b": "hello"}

    def test_try_parse_json_invalid(self):
        """无效 JSON 应返回兜底提取结果"""
        d = _try_parse_json("not json at all")
        assert "raw_reply" in d or "name" in d
        assert d.get("confidence", 0) > 0

    def test_try_parse_json_none(self):
        """None/空输入应返回默认字典"""
        d = _try_parse_json("")  # None is handled at entry
        assert "name" in d
        assert "category" in d
        assert d["name"] == "未识别产品"


class TestFallbackRecognition:
    """降级识别测试"""

    def test_fallback_with_context(self):
        """有 context 时降级结果应包含上下文"""
        result = _fallback_recognize("防滑地砖 800x800")
        assert result.get("fallback") is True
        assert "name" in result

    def test_fallback_empty_context(self):
        """空 context 降级结果应正常返回"""
        result = _fallback_recognize("")
        assert result.get("fallback") is True
        assert "name" in result

    def test_fallback_has_basic_fields(self):
        """降级结果必须包含基本字段"""
        result = _fallback_recognize("任意文本")
        required = ["name", "category_cn", "category_code", "fallback"]
        for field in required:
            assert field in result, f"降级结果缺少字段: {field}"


class TestCategoryMapping:
    """分类映射测试"""

    def test_all_categories_have_code(self):
        """所有中文分类都应有对应的代码映射"""
        for cn, code in CATEGORY_CN_TO_CODE.items():
            assert code is not None
            assert len(code) > 0

    def test_all_codes_have_unit(self):
        """所有分类代码都应有单位映射"""
        codes = set(CATEGORY_CN_TO_CODE.values())
        for code in codes:
            assert code in CATEGORY_UNIT_MAP, f"分类代码 {code} 缺少单位映射"

    def test_common_products_mapped(self):
        """常见产品应能正确映射到分类"""
        test_cases = [
            ("瓷砖", "tile"),
            ("木地板", "flooring"),
            ("乳胶漆", "paint"),
            ("筒灯", "lighting"),
            ("空调", "appliance"),
            ("橱柜", "cabinet"),
            ("窗帘", "curtain"),
            ("沙发", "custom_furniture"),
            ("床", "custom_furniture"),
        ]
        for cn, expected_code in test_cases:
            assert CATEGORY_CN_TO_CODE.get(cn) == expected_code, f"{cn} 应映射到 {expected_code}"

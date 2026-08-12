"""质检 Agent — 照片比对、缺陷识别、验收报告生成、诊断可视化

F38: detect_defects / compare_with_design 支持真实 CV（多模态视觉 LLM），
受 settings.real_cv_quality_enabled 控制；默认关闭时保持 hash mock 路径，
响应体携带 cv_mode="mock" + note 诚实标注（禁止伪装真实视觉能力）。

视觉感知闭环（v1.13.x）：
- 验收报告视觉化：generate_acceptance_report 支持 images（现场照片），
  真实 CV 缺陷识别结果汇入报告（vision_defects + 整改建议来源标注）；
- 诊断数据可视化看图：include_chart=True 时用 Pillow 渲染验收统计图表
  （分项合格率 + 缺陷类别分布，确定性真实数据），再交给多模态视觉模型
  "看图"解读（chart_analysis 结构化诊断），无视觉 key/失败时诚实标注。
"""

import base64
import io
import json
import logging
import os
from typing import Any

import httpx
from PIL import Image, ImageDraw, ImageFont

from app.agents.base import BaseAgent, PROVIDER_REGISTRY
from app.config import get_settings
from app.services.agent_tool_registry import tool_registry

settings = get_settings()
logger = logging.getLogger(__name__)

_QA_TOOL_SCHEMAS = tool_registry.get_openai_schemas_for_category("qa")

# F38: 真实 CV 视觉模型供应商优先级（对齐 sketch_to_3d，复用 LLM fallback 供应商）
_CV_VISION_PROVIDER_PRIORITY = ("deepseek", "glm", "qwen")


# 各阶段验收项目（分项验收清单）
ACCEPTANCE_ITEMS = [
    {
        "phase": "mep",
        "name": "水电工程验收",
        "items": [
            {"item": "水管打压测试", "standard": "0.8MPa 保压 30 分钟不掉压", "pass_criteria": "压力下降 < 0.05MPa"},
            {"item": "电路绝缘测试", "standard": "绝缘电阻 ≥ 0.5MΩ", "pass_criteria": "绝缘电阻 ≥ 0.5MΩ"},
            {"item": "线管布局", "standard": "横平竖直，无三管交叉", "pass_criteria": "符合规范"},
            {"item": "强弱电间距", "standard": "≥ 500mm", "pass_criteria": "间距 ≥ 500mm"},
            {"item": "开关插座位置", "standard": "符合图纸偏差 ≤ 5mm", "pass_criteria": "偏差 ≤ 5mm"},
        ],
    },
    {
        "phase": "masonry",
        "name": "泥瓦工程验收",
        "items": [
            {"item": "防水闭水试验", "standard": "蓄水 48h 无渗漏", "pass_criteria": "无渗漏"},
            {"item": "瓷砖空鼓率", "standard": "单砖空鼓 < 5%，整体 < 3%", "pass_criteria": "空鼓率达标"},
            {"item": "瓷砖平整度", "standard": "2m 靠尺 ≤ 2mm", "pass_criteria": "偏差 ≤ 2mm"},
            {"item": "阴阳角方正度", "standard": "偏差 ≤ 3mm", "pass_criteria": "偏差 ≤ 3mm"},
            {"item": "地漏坡度", "standard": "坡度 1%-2%，无积水", "pass_criteria": "排水通畅无积水"},
        ],
    },
    {
        "phase": "carpentry",
        "name": "木工工程验收",
        "items": [
            {"item": "吊顶平整度", "standard": "2m 靠尺 ≤ 3mm", "pass_criteria": "偏差 ≤ 3mm"},
            {"item": "柜体对角线偏差", "standard": "≤ 2mm", "pass_criteria": "偏差 ≤ 2mm"},
            {"item": "柜门缝隙", "standard": "均匀 1.5-2.5mm", "pass_criteria": "缝隙均匀达标"},
            {"item": "抽屉滑轨", "standard": "顺滑无异响", "pass_criteria": "推拉顺滑"},
        ],
    },
    {
        "phase": "painting",
        "name": "油漆工程验收",
        "items": [
            {"item": "墙面平整度", "standard": "2m 靠尺 ≤ 3mm", "pass_criteria": "偏差 ≤ 3mm"},
            {"item": "色差", "standard": "无可见色差", "pass_criteria": "无可见色差"},
            {"item": "流坠/漏刷", "standard": "无流坠、无漏刷", "pass_criteria": "无流坠漏刷"},
            {"item": "阴阳角", "standard": "顺直，偏差 ≤ 2mm", "pass_criteria": "顺直达标"},
        ],
    },
    {
        "phase": "installation",
        "name": "安装工程验收",
        "items": [
            {"item": "灯具安装牢固度", "standard": "承重 ≥ 灯具重量 4 倍", "pass_criteria": "牢固可靠"},
            {"item": "插座接线", "standard": "左零右火上地线", "pass_criteria": "接线正确"},
            {"item": "卫浴下水", "standard": "排水通畅无堵塞", "pass_criteria": "排水通畅"},
            {"item": "橱柜门板", "standard": "开关顺滑，缝隙均匀", "pass_criteria": "开关顺滑"},
        ],
    },
]


# 缺陷类别（按常见质量缺陷分类）
DEFECT_CATEGORIES = [
    {"code": "hollow", "name": "空鼓", "severity": "high", "description": "瓷砖/墙面空鼓，敲击有空音", "rectification": "拆除空鼓部位重新施工"},
    {"code": "crack", "name": "裂缝", "severity": "high", "description": "墙面/瓷砖/吊顶出现裂缝", "rectification": "排查裂缝原因，修补或返工"},
    {
        "code": "leak", "name": "渗漏", "severity": "critical",
        "description": "水管/防水/管道渗漏",
        "rectification": "立即排查渗漏点，重做防水/更换管道",
    },
    {
        "code": "color_diff", "name": "色差", "severity": "medium",
        "description": "墙面/瓷砖存在可见色差",
        "rectification": "重新涂刷/更换有色差材料",
    },
    {
        "code": "flatness", "name": "平整度", "severity": "medium",
        "description": "墙面/地面/吊顶平整度不达标",
        "rectification": "打磨找平或返工处理",
    },
    {"code": "gap", "name": "缝隙", "severity": "medium", "description": "瓷砖缝隙/柜门缝隙不均匀", "rectification": "调整缝隙至标准范围"},
    {
        "code": "installation", "name": "安装", "severity": "medium",
        "description": "灯具/卫浴/橱柜安装不当",
        "rectification": "重新调整安装位置和紧固度",
    },
    {"code": "other", "name": "其他", "severity": "low", "description": "其他工艺缺陷", "rectification": "根据具体情况整改"},
]


# 缺陷类别关键词映射（用于 mock CV 检测时的类别识别）
DEFECT_KEYWORD_MAP = {
    "空鼓": ["空鼓", "空音", "脱落"],
    "裂缝": ["裂缝", "开裂", "裂纹"],
    "渗漏": ["渗漏", "漏水", "渗水", "水印"],
    "色差": ["色差", "颜色不均", "发花"],
    "平整度": ["不平", "凹凸", "波浪", "平整度"],
    "缝隙": ["缝隙", "缝不均", "对角线"],
    "安装": ["安装", "松动", "歪斜", "不牢固"],
}


# ── F38 真实 CV 视觉模型辅助（模块级，便于单测 monkeypatch）──


def _fetch_image_bytes(url: str) -> tuple[bytes, str]:
    """获取图片内容，返回 (bytes, mime_type)。支持 data: URL 与 http(s) URL。"""
    if url.startswith("data:"):
        header, _, b64data = url.partition(",")
        mime = header[5:].split(";")[0] or "image/png"
        return base64.b64decode(b64data), mime
    if url.startswith(("http://", "https://")):
        resp = httpx.get(url, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        mime = resp.headers.get("content-type", "image/jpeg")
        return resp.content, mime
    raise ValueError(f"不支持的图片 URL: {url}")


def _call_vision_llm(prompt: str, image_bytes: bytes, mime_type: str) -> str:
    """调用多模态视觉模型（DeepSeek → GLM → Qwen 优先），返回原始文本。

    未配置任何视觉模型 API key 时抛出 RuntimeError（调用方诚实降级到 mock）。
    """
    provider = api_key = api_base = model = None
    for name in _CV_VISION_PROVIDER_PRIORITY:
        cfg = PROVIDER_REGISTRY[name]
        if cfg["api_key"]():
            provider = name
            api_key = cfg["api_key"]()
            api_base = cfg["api_base"]()
            model = cfg["model"]()
            break
    if not api_key:
        raise RuntimeError("未配置视觉模型 API key（deepseek/glm/qwen）")
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    response = httpx.post(
        f"{api_base}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.1,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    data = response.json()
    logger.debug("qa_inspector vision_llm: provider=%s model=%s", provider, model)
    return data["choices"][0]["message"]["content"] or ""


def _parse_vision_json(content: str) -> dict:
    """解析视觉模型返回的 JSON，处理 markdown 代码块包裹。"""
    text = content.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())


def _build_defect_vision_prompt(location: str, img_type: str, check_categories: list[str]) -> str:
    """构建缺陷识别视觉 prompt。"""
    cat_names = "、".join(
        next((c["name"] for c in DEFECT_CATEGORIES if c["code"] == code), code)
        for code in check_categories
    )
    loc_part = f"照片位置：{location}；照片类型：{img_type}。" if (location or img_type) else ""
    return f"""你是索克家居（i-home.life）AI 质检视觉模型。请仔细分析这张施工现场照片，检测以下类别的工艺缺陷：{cat_names}。

{loc_part}
请以 JSON 格式返回检测结果，仅返回 JSON：
```json
{{
  "defects": [
    {{
      "category": "缺陷类别代码（hollow/crack/leak/color_diff/flatness/gap/installation/other）",
      "description": "缺陷描述（简要中文）",
      "confidence": 0.0-1.0,
      "location_hint": "照片中的大致位置描述",
      "suggestion": "整改建议（中文）"
    }}
  ]
}}
```
注意：未检出缺陷时返回 {{"defects": []}}。只返回 JSON，不要包含其他文字。"""


def _build_compare_vision_prompt(img: dict, specs: dict, expected_dims: dict) -> str:
    """构建照片与设计图纸比对视觉 prompt。"""
    loc = img.get("location", "")
    spec_lines = "\n".join(f"- {k}: {v}" for k, v in (specs or {}).items()) or "- 无"
    dim_lines = "\n".join(f"- {k}: {v}" for k, v in (expected_dims or {}).items()) or "- 无"
    return f"""你是索克家居（i-home.life）AI 质检视觉模型。请将这张施工现场照片与设计图纸规格进行比对（位置：{loc}）。

设计规格：
{spec_lines}

尺寸公差要求：
{dim_lines}

请以 JSON 格式返回比对结果，仅返回 JSON：
```json
{{
  "image_analysis": {{"matches_design": true, "confidence": 0.0-1.0, "notes": "简要说明"}},
  "spec_comparisons": [
    {{"spec_item": "规格项名称", "design_value": "设计值", "actual_value": "照片实测值/描述", "consistent": true}}
  ],
  "dimension_deviations": [
    {{"dimension": "尺寸项", "standard": "标准", "measured_value": 0.0, "deviation": 0.0, "pass": true}}
  ]
}}
```
只返回 JSON，不要包含其他文字。"""


# ── 诊断数据可视化（Pillow 渲染图表 → 多模态视觉模型"看图"解读）──
#
# 图表为确定性渲染（真实验收统计，无外部调用、无视觉 key 依赖）；
# 图表"看图"解读（chart_analysis）才走真实 CV，不可用/失败时诚实标注 None。

_CHART_WIDTH, _CHART_HEIGHT = 900, 520
# 图表标签全部用 ASCII（phase/category code + 数字），避免依赖中文字体文件
# （macOS PingFang / Linux Noto 路径不可移植）。中文字体存在时仅用于标题增强。
_CHART_FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def _load_chart_font(size: int) -> Any:
    """加载图表字体（候选列表探测，全部失败回退默认字体，绝不抛错）。"""
    for path in _CHART_FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _defect_category_code(name: str) -> str:
    """缺陷类别中文名 → code（图表标签用 ASCII，避免中文字体依赖）。"""
    return next((c["code"] for c in DEFECT_CATEGORIES if c["name"] == name), "other")


def render_acceptance_chart(report: dict) -> bytes:
    """渲染验收报告诊断图表（PNG bytes）— 确定性渲染真实数据。

    布局：左 = 各分项合格率条形图（Pass rate by phase, %）；
          右 = 缺陷类别数量分布条形图（Defect count by category）。
    无外部调用、无需视觉 key；视觉模型不可用时图表本身仍可返回。
    """
    img = Image.new("RGB", (_CHART_WIDTH, _CHART_HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    title_font = _load_chart_font(22)
    label_font = _load_chart_font(14)

    draw.text(
        (_CHART_WIDTH // 2 - 180, 12),
        "Acceptance Report Diagnostic Chart",
        fill="black", font=title_font,
    )

    chart_top, chart_bottom = 80, 460
    sections = report.get("sections", [])
    cat_counts: dict[str, int] = {}
    for sug in report.get("rectification_suggestions", []):
        code = _defect_category_code(str(sug.get("category", "other")))
        cat_counts[code] = cat_counts.get(code, 0) + 1

    # ── 左图：分项合格率 ──
    left_x0, left_x1 = 40, 440
    draw.text((left_x0, 48), "Pass rate by phase (%)", fill="black", font=label_font)
    if sections:
        bar_w = min(30, (left_x1 - left_x0 - 20) // max(len(sections), 1))
        for i, sec in enumerate(sections):
            try:
                rate = float(sec.get("pass_rate", 0.0))
            except (TypeError, ValueError):
                rate = 0.0
            h = int(rate / 100 * (chart_bottom - chart_top))
            x = left_x0 + 10 + i * (bar_w + 12)
            draw.rectangle([x, chart_bottom - h, x + bar_w, chart_bottom], fill="#2f80ed")
            draw.text((x, chart_bottom - h - 18), f"{rate:.0f}", fill="black", font=label_font)
            draw.text((x, chart_bottom + 6), str(sec.get("phase", "")), fill="black", font=label_font)
    else:
        draw.text((left_x0, chart_top + 80), "No phase data", fill="gray", font=label_font)
    for pct in (0, 25, 50, 75, 100):
        y = chart_bottom - int(pct / 100 * (chart_bottom - chart_top))
        draw.line([left_x0, y, left_x1, y], fill="#dddddd")
        draw.text((left_x0 - 6, y - 8), str(pct), fill="gray", font=label_font)

    # ── 右图：缺陷类别分布 ──
    right_x0, right_x1 = 470, 880
    draw.text((right_x0, 48), "Defect count by category", fill="black", font=label_font)
    if cat_counts:
        max_count = max(cat_counts.values())
        bar_w = min(34, (right_x1 - right_x0 - 20) // max(len(cat_counts), 1))
        for i, (code, cnt) in enumerate(sorted(cat_counts.items(), key=lambda kv: -kv[1])):
            h = int(cnt / max(max_count, 1) * (chart_bottom - chart_top))
            x = right_x0 + 10 + i * (bar_w + 14)
            draw.rectangle([x, chart_bottom - h, x + bar_w, chart_bottom], fill="#eb5757")
            draw.text((x, chart_bottom - h - 18), str(cnt), fill="black", font=label_font)
            draw.text((x, chart_bottom + 6), code, fill="black", font=label_font)
    else:
        draw.text((right_x0, chart_top + 80), "No defects detected", fill="gray", font=label_font)
    draw.line([right_x0, chart_bottom, right_x1, chart_bottom], fill="#bbbbbb")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_chart_analysis_prompt(report: dict) -> str:
    """构建图表"看图"解读 prompt（图表为 render_acceptance_chart 输出）。"""
    summary = report.get("summary", {})
    return f"""你是索克家居（i-home.life）AI 质检诊断模型。这是验收报告诊断统计图表：
- 左半部分：各施工分项合格率（Pass rate by phase, %）
- 右半部分：缺陷类别数量分布（Defect count by category）

报告概要：总体验收结论「{report.get("overall_verdict_text", "")}」，整体合格率 {summary.get("pass_rate", 0)}%。

请仔细观察图表并返回 JSON（仅返回 JSON）：
```json
{{
  "summary": "总体诊断结论（中文 2-3 句，引用图表中的具体数值）",
  "key_risks": [
    {{"phase": "合格率明显偏低（<85%）或缺陷集中的分项 code", "risk": "风险描述（中文）"}}
  ],
  "recommendations": ["整改建议（中文）"]
}}
```
注意：无风险分项时 key_risks 返回空数组。只返回 JSON，不要包含其他文字。"""


def _analyze_chart_with_vision(prompt: str, chart_bytes: bytes) -> dict | None:
    """通用图表"看图"解读：多模态视觉模型解读图表 PNG → 结构化诊断。

    受 settings.real_cv_quality_enabled 门控；无视觉 key / 调用失败 → None
    （调用方以 chart_analysis_note 诚实标注，绝不伪装真实解读）。
    """
    if not settings.real_cv_quality_enabled:
        return None
    try:
        raw = _call_vision_llm(prompt, chart_bytes, "image/png")
        parsed = _parse_vision_json(raw)
        if not isinstance(parsed, dict):
            return None
        return {
            "summary": str(parsed.get("summary", "")),
            "key_risks": [r for r in parsed.get("key_risks", []) if isinstance(r, dict)],
            "recommendations": [str(r) for r in parsed.get("recommendations", [])],
        }
    except Exception as e:
        logger.error("图表视觉解读失败: %s", e)
        return None


def analyze_acceptance_chart(report: dict, chart_bytes: bytes) -> dict | None:
    """多模态视觉模型"看图"解读验收诊断图表（薄封装，保持对外接口）。"""
    return _analyze_chart_with_vision(_build_chart_analysis_prompt(report), chart_bytes)


def _attach_chart(result: dict, *, render_fn, prompt_builder) -> dict:
    """渲染诊断图表 + 视觉模型"看图"解读，结果挂到 result。

    - chart_b64 / chart_mime：确定性渲染的真实数据 PNG（零视觉依赖）
    - chart_analysis：视觉解读（结构化）；不可用时 None + chart_analysis_note 诚实标注
    """
    chart_bytes = render_fn(result)
    result["chart_b64"] = base64.b64encode(chart_bytes).decode("ascii")
    result["chart_mime"] = "image/png"
    analysis = _analyze_chart_with_vision(prompt_builder(result), chart_bytes)
    result["chart_analysis"] = analysis
    result["chart_analysis_note"] = (
        None if analysis else "视觉模型不可用或图表解读失败；图表为真实数据渲染，未做 LLM 解读"
    )
    return result


def render_defect_chart(result: dict) -> bytes:
    """渲染缺陷识别诊断图表（PNG bytes）— 确定性渲染真实数据。

    布局：左 = 缺陷类别数量分布（Defect count by category）；
          右 = 缺陷严重度分布（Severity: critical/high/medium/low）。
    """
    img = Image.new("RGB", (_CHART_WIDTH, _CHART_HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    title_font = _load_chart_font(22)
    label_font = _load_chart_font(14)

    draw.text(
        (_CHART_WIDTH // 2 - 150, 12),
        "Defect Detection Diagnostic Chart",
        fill="black", font=title_font,
    )

    chart_top, chart_bottom = 80, 460
    cat_counts: dict[str, int] = {}
    for d in result.get("detected_defects", []):
        code = _defect_category_code(str(d.get("category_name", "other")))
        cat_counts[code] = cat_counts.get(code, 0) + 1
    sev_counts: dict[str, int] = {}
    for d in result.get("detected_defects", []):
        sev = str(d.get("severity", "low"))
        sev_counts[sev] = sev_counts.get(sev, 0) + 1

    # ── 左图：缺陷类别分布 ──
    left_x0, left_x1 = 40, 440
    draw.text((left_x0, 48), "Defect count by category", fill="black", font=label_font)
    if cat_counts:
        bar_w = min(34, (left_x1 - left_x0 - 20) // max(len(cat_counts), 1))
        for i, (code, cnt) in enumerate(sorted(cat_counts.items(), key=lambda kv: -kv[1])):
            h = int(cnt / max(max(cat_counts.values()), 1) * (chart_bottom - chart_top))
            x = left_x0 + 10 + i * (bar_w + 14)
            draw.rectangle([x, chart_bottom - h, x + bar_w, chart_bottom], fill="#eb5757")
            draw.text((x, chart_bottom - h - 18), str(cnt), fill="black", font=label_font)
            draw.text((x, chart_bottom + 6), code, fill="black", font=label_font)
    else:
        draw.text((left_x0, chart_top + 80), "No defects detected", fill="gray", font=label_font)
    for pct in (0, 25, 50, 75, 100):
        y = chart_bottom - int(pct / 100 * (chart_bottom - chart_top))
        draw.line([left_x0, y, left_x1, y], fill="#dddddd")

    # ── 右图：严重度分布 ──
    right_x0, right_x1 = 470, 880
    draw.text((right_x0, 48), "Severity distribution", fill="black", font=label_font)
    if sev_counts:
        sev_order = ("critical", "high", "medium", "low")
        max_count = max(sev_counts.values())
        bar_w = min(34, (right_x1 - right_x0 - 20) // max(len(sev_counts), 1))
        for i, sev in enumerate(sev_order):
            cnt = sev_counts.get(sev, 0)
            h = int(cnt / max(max_count, 1) * (chart_bottom - chart_top))
            x = right_x0 + 10 + i * (bar_w + 20)
            draw.rectangle([x, chart_bottom - h, x + bar_w, chart_bottom], fill="#9b51e0")
            draw.text((x, chart_bottom - h - 18), str(cnt), fill="black", font=label_font)
            draw.text((x, chart_bottom + 6), sev, fill="black", font=label_font)
    else:
        draw.text((right_x0, chart_top + 80), "No defects detected", fill="gray", font=label_font)
    draw.line([right_x0, chart_bottom, right_x1, chart_bottom], fill="#bbbbbb")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_defect_chart_prompt(result: dict) -> str:
    """构建缺陷图表"看图"解读 prompt（图表为 render_defect_chart 输出）。"""
    return f"""你是索克家居（i-home.life）AI 质检诊断模型。这是工艺缺陷识别诊断图表：
- 左半部分：缺陷类别数量分布（Defect count by category）
- 右半部分：缺陷严重度分布（Severity: critical/high/medium/low）

识别结果：共检出 {result.get("defect_count", 0)} 项缺陷，结论「{result.get("verdict_text", "")}」。

请仔细观察图表并返回 JSON（仅返回 JSON）：
```json
{{
  "summary": "缺陷诊断结论（中文 2-3 句，引用图表中的具体数值）",
  "key_risks": [
    {{"phase": "缺陷集中或严重度高的项", "risk": "风险描述（中文）"}}
  ],
  "recommendations": ["整改建议（中文）"]
}}
```
注意：无风险项时 key_risks 返回空数组。只返回 JSON，不要包含其他文字。"""


def analyze_defect_chart(result: dict, chart_bytes: bytes) -> dict | None:
    """多模态视觉模型"看图"解读缺陷识别诊断图表。"""
    return _analyze_chart_with_vision(_build_defect_chart_prompt(result), chart_bytes)


def render_compare_chart(result: dict) -> bytes:
    """渲染图纸比对诊断图表（PNG bytes）— 确定性渲染真实数据。

    布局：左 = 规格比对一致/不一致 + 照片一致/不一致计数条形图；
          右 = 尺寸偏差分布（deviation mm，按项）。
    """
    img = Image.new("RGB", (_CHART_WIDTH, _CHART_HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    title_font = _load_chart_font(22)
    label_font = _load_chart_font(14)

    draw.text(
        (_CHART_WIDTH // 2 - 150, 12),
        "Design Comparison Diagnostic Chart",
        fill="black", font=title_font,
    )

    chart_top, chart_bottom = 80, 460
    specs = result.get("spec_comparisons", []) or []
    imgs = result.get("image_analyses", []) or []
    spec_match = sum(1 for s in specs if s.get("consistent"))
    spec_mismatch = len(specs) - spec_match
    img_match = sum(1 for i in imgs if i.get("matches_design"))
    img_mismatch = len(imgs) - img_match

    # ── 左图：一致性计数（规格 + 照片）──
    left_x0, left_x1 = 40, 440
    draw.text((left_x0, 48), "Consistency counts", fill="black", font=label_font)
    groups = [
        ("spec_match", "Spec OK", spec_match, "#27ae60"),
        ("spec_mismatch", "Spec diff", spec_mismatch, "#eb5757"),
        ("img_match", "Photo OK", img_match, "#2f80ed"),
        ("img_mismatch", "Photo diff", img_mismatch, "#eb5757"),
    ]
    max_count = max([spec_match, spec_mismatch, img_match, img_mismatch], default=0)
    for i, (_k, label, cnt, color) in enumerate(groups):
        h = int(cnt / max(max_count, 1) * (chart_bottom - chart_top))
        x = left_x0 + 10 + i * 100
        draw.rectangle([x, chart_bottom - h, x + 70, chart_bottom], fill=color)
        draw.text((x, chart_bottom - h - 18), str(cnt), fill="black", font=label_font)
        draw.text((x, chart_bottom + 6), label, fill="black", font=label_font)
    for pct in (0, 25, 50, 75, 100):
        y = chart_bottom - int(pct / 100 * (chart_bottom - chart_top))
        draw.line([left_x0, y, left_x1, y], fill="#dddddd")

    # ── 右图：尺寸偏差 ──
    right_x0, right_x1 = 470, 880
    draw.text((right_x0, 48), "Dimension deviation (mm)", fill="black", font=label_font)
    devs = result.get("dimension_deviations", []) or []
    if devs:
        devs = [d for d in devs if isinstance(d, dict)]
        bar_w = min(34, (right_x1 - right_x0 - 20) // max(len(devs), 1))
        max_dev = max([abs(float(d.get("deviation", 0.0) or 0.0)) for d in devs], default=0.0)
        for i, d in enumerate(devs):
            try:
                dev = float(d.get("deviation", 0.0) or 0.0)
            except (TypeError, ValueError):
                dev = 0.0
            h = int(abs(dev) / max(max_dev, 0.1) * (chart_bottom - chart_top))
            x = right_x0 + 10 + i * (bar_w + 14)
            draw.rectangle([x, chart_bottom - h, x + bar_w, chart_bottom], fill="#f2994a")
            draw.text((x, chart_bottom - h - 18), f"{dev:.1f}", fill="black", font=label_font)
            draw.text((x, chart_bottom + 6), str(d.get("dimension", ""))[:10], fill="black", font=label_font)
    else:
        draw.text((right_x0, chart_top + 80), "No dimension deviations", fill="gray", font=label_font)
    draw.line([right_x0, chart_bottom, right_x1, chart_bottom], fill="#bbbbbb")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_compare_chart_prompt(result: dict) -> str:
    """构建图纸比对图表"看图"解读 prompt（图表为 render_compare_chart 输出）。"""
    return f"""你是索克家居（i-home.life）AI 质检诊断模型。这是照片与设计图纸比对诊断图表：
- 左半部分：一致性计数（规格比对 Spec OK/diff + 照片比对 Photo OK/diff）
- 右半部分：各尺寸项偏差值（Dimension deviation, mm）

比对结果：共 {result.get("total_checks", 0)} 项检查，一致 {result.get("matched_count", 0)} 项，
一致率 {result.get("consistency_rate", 0)}%，结论「{result.get("verdict_text", "")}」。

请仔细观察图表并返回 JSON（仅返回 JSON）：
```json
{{
  "summary": "比对诊断结论（中文 2-3 句，引用图表中的具体数值）",
  "key_risks": [
    {{"phase": "偏差超标或比对不一致的项", "risk": "风险描述（中文）"}}
  ],
  "recommendations": ["整改建议（中文）"]
}}
```
注意：无风险项时 key_risks 返回空数组。只返回 JSON，不要包含其他文字。"""


def analyze_compare_chart(result: dict, chart_bytes: bytes) -> dict | None:
    """多模态视觉模型"看图"解读图纸比对诊断图表。"""
    return _analyze_chart_with_vision(_build_compare_chart_prompt(result), chart_bytes)


class QAInspectorAgent(BaseAgent):
    agent_name = "qa_inspector"
    tools = _QA_TOOL_SCHEMAS
    system_prompt = """你是索克家居（i-home.life）AI 质检 Agent。

你的职责：
1. 照片与设计图纸比对，检测施工是否与设计一致
2. 尺寸偏差检测，识别超出公差的施工项
3. 工艺缺陷识别（空鼓/裂缝/渗漏/色差/平整度/缝隙/安装缺陷）
4. 生成验收报告（分项验收 + 总体验收结论）

验收标准依据：
- GB 50210-2018 建筑装饰装修工程质量验收标准
- GB 50327-2001 住宅装饰装修工程施工规范
- GB 50300-2013 建筑工程施工质量验收统一标准

缺陷类别：
- 空鼓：瓷砖/墙面空鼓（高）
- 裂缝：墙面/瓷砖/吊顶裂缝（高）
- 渗漏：水管/防水/管道渗漏（严重）
- 色差：墙面/瓷砖可见色差（中）
- 平整度：墙面/地面/吊顶不平（中）
- 缝隙：瓷砖缝隙/柜门缝隙不均匀（中）
- 安装：灯具/卫浴/橱柜安装不当（中）
- 其他：其他工艺缺陷（低）

请用中文回复，注重专业性和准确性，给出明确的验收结论和整改建议。"""

    def generate_acceptance_report(self, project_data: dict) -> dict:  # noqa: C901
        """生成验收报告（分项验收 + 总体验收结论）

        project_data 结构：
        {
            "project_id": "P001",
            "project_name": "张先生家装项目",
            "inspector": "质检员姓名",
            "acceptance_date": "2026-07-08",
            "phases": ["mep", "masonry", "carpentry", "painting", "installation"],
            "inspection_results": {
                "mep": [{"item": "水管打压测试", "result": "pass", "issues": []}, ...],
                ...
            },
            # 视觉感知增强层（可选）：
            "images": [{"url": "...", "type": "tile_surface", "location": "客厅东墙", "captured_at": "..."}],
            "include_chart": true
        }
        """
        project_id = project_data.get("project_id", "")
        project_name = project_data.get("project_name", "")
        inspector = project_data.get("inspector", "")
        acceptance_date = project_data.get("acceptance_date", "")
        phases = project_data.get("phases", [])
        inspection_results = project_data.get("inspection_results", {})
        # 视觉感知增强层（可选）：现场照片 → 真实 CV 缺陷识别；include_chart → 图表可视化看图
        images = project_data.get("images", []) or []
        include_chart = bool(project_data.get("include_chart", False))

        # 分项验收
        section_results = []
        total_items = 0
        passed_items = 0
        failed_items = 0

        for phase in phases:
            # 找到该阶段的验收项定义
            phase_def = next((p for p in ACCEPTANCE_ITEMS if p["phase"] == phase), None)
            if not phase_def:
                continue

            results = inspection_results.get(phase, [])
            item_results = []
            section_passed = 0
            section_failed = 0

            for item_def in phase_def["items"]:
                total_items += 1
                # 从 inspection_results 中匹配结果，若无则 mock 判定
                match = next(
                    (r for r in results if r.get("item") == item_def["item"]),
                    None,
                )
                if match:
                    result = match.get("result", "pass")
                    issues = match.get("issues", [])
                else:
                    # Mock 判定：约 85% 通过率
                    result = "pass" if (hash(item_def["item"]) % 20) < 17 else "fail"
                    issues = [] if result == "pass" else [
                        f"「{item_def['item']}」未达标，标准要求：{item_def['standard']}"
                    ]

                if result == "pass":
                    passed_items += 1
                    section_passed += 1
                else:
                    failed_items += 1
                    section_failed += 1

                item_results.append({
                    "item": item_def["item"],
                    "standard": item_def["standard"],
                    "pass_criteria": item_def["pass_criteria"],
                    "result": result,
                    "issues": issues,
                })

            pass_rate = round(section_passed / max(len(item_results), 1) * 100, 2)
            if pass_rate >= 95:
                section_verdict = "excellent"
                section_verdict_text = "优秀"
            elif pass_rate >= 85:
                section_verdict = "pass"
                section_verdict_text = "合格"
            elif pass_rate >= 70:
                section_verdict = "conditional_pass"
                section_verdict_text = "有条件合格"
            else:
                section_verdict = "fail"
                section_verdict_text = "不合格"

            section_results.append({
                "phase": phase,
                "name": phase_def["name"],
                "total_items": len(item_results),
                "passed": section_passed,
                "failed": section_failed,
                "pass_rate": pass_rate,
                "verdict": section_verdict,
                "verdict_text": section_verdict_text,
                "items": item_results,
            })

        # 总体验收结论
        overall_pass_rate = round(passed_items / max(total_items, 1) * 100, 2)
        if overall_pass_rate >= 95:
            overall_verdict = "excellent"
            overall_verdict_text = "优秀"
        elif overall_pass_rate >= 85:
            overall_verdict = "pass"
            overall_verdict_text = "合格"
        elif overall_pass_rate >= 70:
            overall_verdict = "conditional_pass"
            overall_verdict_text = "有条件合格（需整改后复验）"
        else:
            overall_verdict = "fail"
            overall_verdict_text = "不合格（需返工）"

        # 收集所有问题
        all_issues = []
        for section in section_results:
            for item in section["items"]:
                if item["result"] != "pass":
                    all_issues.extend(item["issues"])

        # 整改建议
        rectification_suggestions = []
        for issue in all_issues:
            category = self._classify_defect(issue)
            rectification_suggestions.append({
                "issue": issue,
                "category": category,
                "suggestion": self._get_rectification_suggestion(category),
            })

        # ── 视觉感知增强层（真实 CV 门控，可选）──
        # 现场照片 → 多模态视觉模型缺陷识别，结果汇入报告（vision_defects）；
        # 视觉结果驱动的整改建议带 source="vision_llm" 来源标注（诚实）。
        vision_defects: list[dict] = []
        if images and settings.real_cv_quality_enabled:
            vision_defects = self._detect_report_vision_defects(images)

        result = {
            "project_id": project_id,
            "project_name": project_name,
            "inspector": inspector,
            "acceptance_date": acceptance_date,
            "sections": section_results,
            "summary": {
                "total_items": total_items,
                "passed": passed_items,
                "failed": failed_items,
                "pass_rate": overall_pass_rate,
            },
            "overall_verdict": overall_verdict,
            "overall_verdict_text": overall_verdict_text,
            "all_issues": all_issues,
            "rectification_suggestions": rectification_suggestions,
            "vision_defects": vision_defects,
            "vision_defect_count": len(vision_defects),
            # 诚实降级标注：默认规则引擎 mock（hash 模拟）；接入视觉后 engine/source 如实更新
            "source": "mock",
            "engine": "mock_rule_engine",
            "is_placeholder": True,
            "note": None,
            "reply": (
                f"验收报告已生成：{project_name}，"
                f"共 {len(section_results)} 个分项，{total_items} 个检查点，"
                f"合格 {passed_items} 项，不合格 {failed_items} 项，"
                f"合格率 {overall_pass_rate}%，结论：{overall_verdict_text}"
            ),
        }

        if vision_defects:
            # 视觉检出的缺陷并入整改建议（来源标注，不伪装为规则判定）
            result["rectification_suggestions"].extend([
                {
                    "issue": f"[视觉]「{d['category_name']}」缺陷（{d['location'] or '图中位置未知'}）",
                    "category": d["category_name"],
                    "suggestion": d["rectification"],
                    "confidence": d["confidence"],
                    "source": "vision_llm",
                }
                for d in vision_defects
            ])
            result["engine"] = "mock_rule_engine+vision_llm"
            result["source"] = "rule_engine+vision_llm"
            result["is_placeholder"] = False
            result["cv_mode"] = "real_vision_llm"
            result["note"] = (
                f"分项判定由规则引擎生成，缺陷识别由多模态视觉模型分析 "
                f"{len(images)} 张现场照片（检出 {len(vision_defects)} 项）"
            )
            result["reply"] += f" 视觉检出 {len(vision_defects)} 项缺陷"
        elif images:
            result["note"] = (
                "已提供现场照片，但视觉模型不可用（未配置视觉 key 或调用失败），"
                "缺陷识别为规则引擎模拟，非真实视觉"
            )

        # ── 诊断数据可视化看图（可选）──
        # 图表为确定性渲染（真实数据，无视觉依赖）；图表解读才走真实 CV。
        if include_chart:
            _attach_chart(
                result,
                render_fn=render_acceptance_chart,
                prompt_builder=_build_chart_analysis_prompt,
            )

        return result

    def _detect_report_vision_defects(self, images: list[dict]) -> list[dict]:
        """对现场照片执行真实 CV 缺陷识别（供验收报告视觉化）。

        复用 detect_defects 的真实视觉路径；失败整体降级为空列表
        （调用方以 note 诚实标注，绝不阻断报告生成）。
        """
        try:
            return self._detect_defects_real_cv({
                "project_id": "",
                "phase": "",
                "images": images,
                "check_categories": [c["code"] for c in DEFECT_CATEGORIES],
            }).get("detected_defects", [])
        except Exception as e:
            logger.error("generate_acceptance_report 视觉缺陷识别失败: %s", e)
            return []

    def compare_with_design(self, inspection_data: dict) -> dict:
        """照片与设计图纸比对

        F38: settings.real_cv_quality_enabled=True 且视觉模型可用时走真实 CV
        （多模态视觉 LLM）；否则保持 hash mock 路径并带 cv_mode="mock" 诚实标注。

        inspection_data 结构：
        {
            "project_id": "P001",
            "phase": "masonry",
            "images": [
                {"url": "...", "type": "tile_surface", "location": "客厅东墙", "captured_at": "..."}
            ],
            "design_reference": {"url": "...", "specs": {"tile_size": "800x800", "gap": "2mm"}},
            "expected_dimensions": {"tile_gap": "2mm", "flatness": "≤3mm", "wall_straightness": "≤2mm"},
            # 诊断数据可视化看图（可选）：
            "include_chart": true
        }
        """
        if settings.real_cv_quality_enabled:
            try:
                result = self._compare_with_design_real_cv(inspection_data)
            except Exception as e:
                logger.error("compare_with_design real_cv 失败，降级 mock: %s", e)
                result = self._compare_with_design_mock(inspection_data)
                result["note"] = f"真实 CV 调用失败，已降级为 mock 模拟: {e}"
        else:
            result = self._compare_with_design_mock(inspection_data)
        if inspection_data.get("include_chart"):
            _attach_chart(
                result,
                render_fn=render_compare_chart,
                prompt_builder=_build_compare_chart_prompt,
            )
        return result

    def _compare_with_design_mock(self, inspection_data: dict) -> dict:
        """照片与设计图纸比对（hash mock CV，非真实图像识别）"""
        project_id = inspection_data.get("project_id", "")
        phase = inspection_data.get("phase", "")
        images = inspection_data.get("images", [])
        design_ref = inspection_data.get("design_reference", {})
        expected_dims = inspection_data.get("expected_dimensions", {})

        # Mock CV 比对结果
        comparisons = []
        deviations = []
        matched = 0

        # 1. 比对设计规格
        specs = design_ref.get("specs", {}) if isinstance(design_ref, dict) else {}
        for spec_key, spec_value in specs.items():
            # Mock：90% 一致
            is_consistent = (hash(spec_key) % 10) < 9
            actual_value = spec_value if is_consistent else f"偏差（预期 {spec_value}）"
            comparisons.append({
                "spec_item": spec_key,
                "design_value": spec_value,
                "actual_value": actual_value,
                "consistent": is_consistent,
            })
            if is_consistent:
                matched += 1

        # 2. 尺寸偏差检测
        for dim_key, dim_standard in expected_dims.items():
            # Mock 偏差值
            is_pass = (hash(dim_key) % 10) < 8
            mock_deviation = 0.0 if is_pass else round(1.5 + (hash(dim_key) % 30) / 10, 2)
            deviations.append({
                "dimension": dim_key,
                "standard": dim_standard,
                "measured_value": mock_deviation,
                "deviation": mock_deviation,
                "pass": is_pass,
            })

        # 3. 照片与图纸一致性
        image_analyses = []
        for img in images:
            img_type = img.get("type", "unknown")
            location = img.get("location", "")
            # Mock：85% 一致
            is_match = (hash(img.get("url", "") + img_type) % 20) < 17
            image_analyses.append({
                "url": img.get("url", ""),
                "type": img_type,
                "location": location,
                "captured_at": img.get("captured_at", ""),
                "matches_design": is_match,
                "confidence": round(0.80 + (hash(img.get("url", "")) % 20) / 100, 2),
                "notes": "与设计图纸一致" if is_match else "与设计图纸存在偏差，需复核",
            })
            if is_match:
                matched += 1

        total_checks = len(comparisons) + len(image_analyses)
        consistency_rate = round(matched / max(total_checks, 1) * 100, 2)
        verdict, verdict_text = self._judge_design_consistency(consistency_rate)
        failed_deviations = [d for d in deviations if not d["pass"]]

        return {
            "project_id": project_id,
            "phase": phase,
            "image_count": len(images),
            "spec_comparisons": comparisons,
            "dimension_deviations": deviations,
            "image_analyses": image_analyses,
            "matched_count": matched,
            "total_checks": total_checks,
            "consistency_rate": consistency_rate,
            "verdict": verdict,
            "verdict_text": verdict_text,
            "failed_deviations": failed_deviations,
            "repair_suggestions": [
                f"尺寸偏差项「{d['dimension']}」：测量值 {d['measured_value']}，标准 {d['standard']}"
                for d in failed_deviations
            ],
            # 诚实降级标注：mock CV 比对，非真实图像识别
            "source": "mock",
            "engine": "mock_cv_engine",
            "is_placeholder": True,
            "cv_mode": "mock",
            "note": "真实 CV 需配置视觉模型 API",
            "reply": (
                f"设计图纸比对完成：{phase} 阶段，"
                f"共 {total_checks} 项检查，一致 {matched} 项，"
                f"一致率 {consistency_rate}%，结论：{verdict_text}"
            ),
        }

    def _compare_with_design_real_cv(self, inspection_data: dict) -> dict:
        """照片与设计图纸比对（真实 CV：多模态视觉 LLM 逐张分析照片）"""
        project_id = inspection_data.get("project_id", "")
        phase = inspection_data.get("phase", "")
        images = inspection_data.get("images", [])
        design_ref = inspection_data.get("design_reference", {}) or {}
        expected_dims = inspection_data.get("expected_dimensions", {}) or {}
        specs = design_ref.get("specs", {}) if isinstance(design_ref, dict) else {}

        comparisons = []
        deviations = []
        image_analyses = []
        matched = 0

        for img in images:
            prompt = _build_compare_vision_prompt(img, specs, expected_dims)
            image_bytes, mime = _fetch_image_bytes(img.get("url", ""))
            raw = _call_vision_llm(prompt, image_bytes, mime)
            parsed = _parse_vision_json(raw)

            for sc in parsed.get("spec_comparisons", []):
                if not isinstance(sc, dict):
                    continue
                item = str(sc.get("spec_item", "")).strip()
                if not item:
                    continue
                consistent = bool(sc.get("consistent", True))
                comparisons.append({
                    "spec_item": item,
                    "design_value": str(sc.get("design_value", specs.get(item, ""))),
                    "actual_value": str(sc.get("actual_value", "")),
                    "consistent": consistent,
                })
                if consistent:
                    matched += 1

            for dd in parsed.get("dimension_deviations", []):
                if not isinstance(dd, dict):
                    continue
                dim = str(dd.get("dimension", "")).strip()
                if not dim:
                    continue
                try:
                    measured = float(dd.get("measured_value", 0.0))
                    dev = float(dd.get("deviation", 0.0))
                except (TypeError, ValueError):
                    measured = 0.0
                    dev = 0.0
                deviations.append({
                    "dimension": dim,
                    "standard": str(dd.get("standard", expected_dims.get(dim, ""))),
                    "measured_value": measured,
                    "deviation": dev,
                    "pass": bool(dd.get("pass", True)),
                })
                if dd.get("pass", True):
                    matched += 1

            ia = parsed.get("image_analysis")
            ia = ia if isinstance(ia, dict) else {}
            is_match = bool(ia.get("matches_design", True))
            try:
                confidence = float(ia.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
            image_analyses.append({
                "url": img.get("url", ""),
                "type": img.get("type", ""),
                "location": img.get("location", ""),
                "captured_at": img.get("captured_at", ""),
                "matches_design": is_match,
                "confidence": round(min(max(confidence, 0.0), 1.0), 2),
                "notes": str(ia.get("notes", "与设计图纸一致" if is_match else "与设计图纸存在偏差，需复核")),
            })
            if is_match:
                matched += 1

        total_checks = len(comparisons) + len(image_analyses)
        consistency_rate = round(matched / max(total_checks, 1) * 100, 2)
        verdict, verdict_text = self._judge_design_consistency(consistency_rate)
        failed_deviations = [d for d in deviations if not d["pass"]]

        return {
            "project_id": project_id,
            "phase": phase,
            "image_count": len(images),
            "spec_comparisons": comparisons,
            "dimension_deviations": deviations,
            "image_analyses": image_analyses,
            "matched_count": matched,
            "total_checks": total_checks,
            "consistency_rate": consistency_rate,
            "verdict": verdict,
            "verdict_text": verdict_text,
            "failed_deviations": failed_deviations,
            "repair_suggestions": [
                f"尺寸偏差项「{d['dimension']}」：测量值 {d['measured_value']}，标准 {d['standard']}"
                for d in failed_deviations
            ],
            # 真实 CV 标注：多模态视觉 LLM 输出
            "source": "vision_llm",
            "engine": "vision_llm",
            "is_placeholder": False,
            "cv_mode": "real_vision_llm",
            "note": f"由多模态视觉模型比对 {len(images)} 张照片与设计图纸生成",
            "reply": (
                f"设计图纸比对完成：{phase} 阶段，"
                f"共 {total_checks} 项检查，一致 {matched} 项，"
                f"一致率 {consistency_rate}%，结论：{verdict_text}"
            ),
        }

    @staticmethod
    def _judge_design_consistency(consistency_rate: float) -> tuple[str, str]:
        """按一致率判定比对结论（mock 与真实 CV 共用）"""
        if consistency_rate >= 90:
            return "consistent", "与设计一致"
        if consistency_rate >= 75:
            return "minor_deviation", "轻微偏差（建议调整）"
        return "major_deviation", "重大偏差（需返工）"

    def detect_defects(self, image_data: dict) -> dict:
        """工艺缺陷识别

        F38: settings.real_cv_quality_enabled=True 且视觉模型可用时走真实 CV
        （多模态视觉 LLM，输出结构化缺陷列表：类型/位置/置信度/建议）；
        否则保持 hash mock 路径并带 cv_mode="mock" 诚实标注。

        image_data 结构：
        {
            "project_id": "P001",
            "phase": "masonry",
            "images": [
                {"url": "...", "type": "tile_surface", "location": "卫生间墙面", "captured_at": "..."}
            ],
            "check_categories": ["hollow", "crack", "flatness"],
            # 诊断数据可视化看图（可选）：
            "include_chart": true
        }
        """
        if settings.real_cv_quality_enabled:
            try:
                result = self._detect_defects_real_cv(image_data)
            except Exception as e:
                logger.error("detect_defects real_cv 失败，降级 mock: %s", e)
                result = self._detect_defects_mock(image_data)
                result["note"] = f"真实 CV 调用失败，已降级为 mock 模拟: {e}"
        else:
            result = self._detect_defects_mock(image_data)
        if image_data.get("include_chart"):
            _attach_chart(
                result,
                render_fn=render_defect_chart,
                prompt_builder=_build_defect_chart_prompt,
            )
        return result

    def _detect_defects_mock(self, image_data: dict) -> dict:
        """工艺缺陷识别（hash mock CV，非真实图像识别）"""
        project_id = image_data.get("project_id", "")
        phase = image_data.get("phase", "")
        images = image_data.get("images", [])
        check_categories = image_data.get("check_categories", [c["code"] for c in DEFECT_CATEGORIES])

        # Mock CV 检测结果
        detected_defects = []
        checked_items = 0

        for img in images:
            url = img.get("url", "")
            location = img.get("location", "")
            img_type = img.get("type", "")

            for cat_code in check_categories:
                cat_def = next((c for c in DEFECT_CATEGORIES if c["code"] == cat_code), None)
                if not cat_def:
                    continue
                checked_items += 1
                # Mock：约 15% 检出缺陷
                has_defect = (hash(url + cat_code) % 20) >= 17
                if has_defect:
                    confidence = round(0.75 + (hash(url + cat_code) % 25) / 100, 2)
                    detected_defects.append({
                        "image_url": url,
                        "image_type": img_type,
                        "location": location,
                        "category": cat_code,
                        "category_name": cat_def["name"],
                        "severity": cat_def["severity"],
                        "description": cat_def["description"],
                        "confidence": confidence,
                        "bbox": {
                            "x": hash(url + cat_code) % 80 + 10,
                            "y": hash(url + "y" + cat_code) % 80 + 10,
                            "w": 15 + (hash(url + "w" + cat_code) % 20),
                            "h": 15 + (hash(url + "h" + cat_code) % 20),
                        },
                        "rectification": cat_def["rectification"],
                    })

        return self._finalize_defect_result(
            project_id=project_id,
            phase=phase,
            image_count=len(images),
            checked_items=checked_items,
            detected_defects=detected_defects,
            source="mock",
            engine="mock_cv_engine",
            cv_mode="mock",
            is_placeholder=True,
            note="真实 CV 需配置视觉模型 API",
        )

    def _detect_defects_real_cv(self, image_data: dict) -> dict:
        """工艺缺陷识别（真实 CV：多模态视觉 LLM 逐张分析照片）"""
        project_id = image_data.get("project_id", "")
        phase = image_data.get("phase", "")
        images = image_data.get("images", [])
        check_categories = image_data.get("check_categories", [c["code"] for c in DEFECT_CATEGORIES])
        check_categories = [c for c in check_categories if any(d["code"] == c for d in DEFECT_CATEGORIES)]

        detected_defects = []
        for img in images:
            prompt = _build_defect_vision_prompt(img.get("location", ""), img.get("type", ""), check_categories)
            image_bytes, mime = _fetch_image_bytes(img.get("url", ""))
            raw = _call_vision_llm(prompt, image_bytes, mime)
            parsed = _parse_vision_json(raw)
            for d in parsed.get("defects", []):
                defect = self._normalize_defect(img, d)
                if defect:
                    detected_defects.append(defect)

        checked_items = len(images) * len(check_categories)
        return self._finalize_defect_result(
            project_id=project_id,
            phase=phase,
            image_count=len(images),
            checked_items=checked_items,
            detected_defects=detected_defects,
            source="vision_llm",
            engine="vision_llm",
            cv_mode="real_vision_llm",
            is_placeholder=False,
            note=f"由多模态视觉模型分析 {len(images)} 张现场照片生成",
        )

    @staticmethod
    def _normalize_defect(img: dict, d: dict) -> dict | None:
        """将视觉模型输出的缺陷条目归一化为标准缺陷结构（类型/位置/置信度/建议）"""
        if not isinstance(d, dict):
            return None
        category = str(d.get("category", "")).strip()
        cat_def = next(
            (c for c in DEFECT_CATEGORIES if c["code"] == category or c["name"] == category),
            None,
        ) or DEFECT_CATEGORIES[-1]
        try:
            confidence = float(d.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        location = str(d.get("location_hint") or img.get("location") or "").strip()
        return {
            "image_url": img.get("url", ""),
            "image_type": img.get("type", ""),
            "location": location,
            "category": cat_def["code"],
            "category_name": cat_def["name"],
            "severity": cat_def["severity"],
            "description": str(d.get("description") or cat_def["description"]),
            "confidence": round(min(max(confidence, 0.0), 1.0), 2),
            "bbox": d.get("bbox") if isinstance(d.get("bbox"), dict) else None,
            "rectification": str(d.get("suggestion") or cat_def["rectification"]),
        }

    def _finalize_defect_result(
        self,
        *,
        project_id: str,
        phase: str,
        image_count: int,
        checked_items: int,
        detected_defects: list[dict],
        source: str,
        engine: str,
        cv_mode: str,
        is_placeholder: bool,
        note: str,
    ) -> dict:
        """构建缺陷识别结果（统计/结论/标注，mock 与真实 CV 共用）"""
        # 缺陷统计
        severity_count = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for defect in detected_defects:
            severity_count[defect["severity"]] = severity_count.get(defect["severity"], 0) + 1

        # 缺陷类别统计
        category_count = {}
        for defect in detected_defects:
            cat = defect["category_name"]
            category_count[cat] = category_count.get(cat, 0) + 1

        # 总体评价
        if not detected_defects:
            verdict = "pass"
            verdict_text = "未检出缺陷，工艺合格"
        elif severity_count["critical"] > 0:
            verdict = "fail"
            verdict_text = "检出严重缺陷，必须返工"
        elif severity_count["high"] > 0:
            verdict = "conditional_pass"
            verdict_text = "检出高危缺陷，需整改后复检"
        else:
            verdict = "minor_issues"
            verdict_text = "检出轻微缺陷，建议整改"

        return {
            "project_id": project_id,
            "phase": phase,
            "image_count": image_count,
            "checked_items": checked_items,
            "detected_defects": detected_defects,
            "defect_count": len(detected_defects),
            "severity_count": severity_count,
            "category_count": category_count,
            "verdict": verdict,
            "verdict_text": verdict_text,
            "repair_suggestions": [
                f"「{d['category_name']}」缺陷（{d['location']}）：{d['rectification']}"
                for d in detected_defects
            ],
            # 诚实标注：source/engine/is_placeholder/cv_mode 明示数据来源
            "source": source,
            "engine": engine,
            "is_placeholder": is_placeholder,
            "cv_mode": cv_mode,
            "note": note,
            "reply": (
                f"工艺缺陷识别完成：{phase} 阶段，"
                f"共检测 {checked_items} 项，检出缺陷 {len(detected_defects)} 项"
                f"（严重 {severity_count['critical']}，高 {severity_count['high']}，"
                f"中 {severity_count['medium']}，低 {severity_count['low']}），"
                f"结论：{verdict_text}"
            ),
        }

    @staticmethod
    def detect_qa_intent(message: str) -> str:
        """识别质检相关子意图"""
        if any(kw in message for kw in ["验收", "验收报告", "分项验收", "竣工验收"]):
            return "acceptance"
        if any(kw in message for kw in ["比对", "图纸比对", "设计对比", "一致性"]):
            return "compare"
        if any(kw in message for kw in ["缺陷", "空鼓", "裂缝", "渗漏", "色差", "平整度", "工艺"]):
            return "defect"
        if any(kw in message for kw in ["质检", "质量检测", "检查", "巡检"]):
            return "inspection"
        if any(kw in message for kw in ["整改", "返工", "修补", "修复"]):
            return "rectification"
        return "general"

    def _classify_defect(self, text: str) -> str:
        """根据文本内容识别缺陷类别"""
        for category, keywords in DEFECT_KEYWORD_MAP.items():
            if any(kw in text for kw in keywords):
                return category
        return "other"

    def _get_rectification_suggestion(self, category: str) -> str:
        """根据缺陷类别获取整改建议"""
        cat_def = next((c for c in DEFECT_CATEGORIES if c["name"] == category), None)
        if cat_def:
            return cat_def["rectification"]
        return "根据具体情况整改至符合标准要求"


# ── 模块级函数 ──


def get_acceptance_items(phase: str | None = None) -> dict:
    """获取验收项目清单（可按阶段过滤）

    Args:
        phase: 施工阶段代码（如 mep/masonry/carpentry/painting/installation），为空则返回全部

    Returns:
        验收项目清单
    """
    if phase:
        phase_def = next((p for p in ACCEPTANCE_ITEMS if p["phase"] == phase), None)
        if not phase_def:
            return {
                "phase": phase,
                "items": [],
                "reply": f"阶段「{phase}」暂无预设验收项目",
            }
        return {
            "phase": phase,
            "name": phase_def["name"],
            "items": phase_def["items"],
            "total": len(phase_def["items"]),
            "reply": f"「{phase_def['name']}」验收项目：共 {len(phase_def['items'])} 项",
        }

    return {
        "phases": [
            {"phase": p["phase"], "name": p["name"], "item_count": len(p["items"])}
            for p in ACCEPTANCE_ITEMS
        ],
        "total_phases": len(ACCEPTANCE_ITEMS),
        "total_items": sum(len(p["items"]) for p in ACCEPTANCE_ITEMS),
        "reply": f"共 {len(ACCEPTANCE_ITEMS)} 个验收阶段，{sum(len(p['items']) for p in ACCEPTANCE_ITEMS)} 个验收项目",
    }


def list_defect_categories() -> dict:
    """列出所有缺陷类别"""
    return {
        "categories": DEFECT_CATEGORIES,
        "total": len(DEFECT_CATEGORIES),
        "reply": f"共 {len(DEFECT_CATEGORIES)} 个缺陷类别：{'、'.join(c['name'] for c in DEFECT_CATEGORIES)}",
    }


def assess_defect_severity(category: str, count: int = 1) -> dict:
    """评估缺陷严重程度及建议处理方式

    Args:
        category: 缺陷类别名称（空鼓/裂缝/渗漏/色差/平整度/缝隙/安装/其他）
        count: 缺陷数量

    Returns:
        严重程度评估结果
    """
    cat_def = next((c for c in DEFECT_CATEGORIES if c["name"] == category or c["code"] == category), None)
    if not cat_def:
        return {
            "category": category,
            "error": f"未知缺陷类别: {category}",
            "available": [c["name"] for c in DEFECT_CATEGORIES],
        }

    severity = cat_def["severity"]
    # 根据数量调整优先级
    if count >= 5 and severity == "medium":
        priority = "high"
    elif count >= 3 and severity == "high":
        priority = "critical"
    else:
        priority = severity

    return {
        "category": cat_def["name"],
        "category_code": cat_def["code"],
        "base_severity": severity,
        "count": count,
        "priority": priority,
        "description": cat_def["description"],
        "rectification": cat_def["rectification"],
        "reply": f"缺陷「{cat_def['name']}」×{count}，严重级别：{severity}，处理优先级：{priority}",
    }

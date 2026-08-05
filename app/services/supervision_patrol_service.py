"""F48 施工可视化 — AI 工地监理（闭水试验监测 + 安全违规抓拍）

托管式整装的"透明化信任基础设施"：以 AI 巡检照片，自动输出工地健康告警。
复用 F38 质检的多模态视觉模型链（DeepSeek → GLM → Qwen），无视觉 key 时
诚实降级 rule_mock（source 标注，绝不伪装真实视觉能力）。

场景：
- waterproofing : 防水闭水试验监测（48h 蓄水无渗漏 → 检测渗水/水位/空鼓）
- safety        : 安全违规抓拍（未佩戴安全帽/反光衣/防护）

来源标注：
- source="ai_vision"  : 多模态视觉模型真实检测
- source="rule_mock"  : 无视觉 key 时基于规则/关键词的诚实降级
"""

import logging

from app.agents.qa_inspector import (
    _call_vision_llm,
    _fetch_image_bytes,
    _parse_vision_json,
)

logger = logging.getLogger(__name__)

# 被检测事件类型
SCENE_TYPES = ("waterproofing", "safety")

# 规则降级关键词（诚实标注，非真实视觉）
_WATERPROOF_RULE_KEYWORDS = ["渗水", "漏水", "水印", "积水", "空鼓"]
_SAFETY_RULE_KEYWORDS = ["未戴安全帽", "未穿反光衣", "违规", "无防护"]


def _build_waterproof_vision_prompt(location: str) -> str:
    """构建闭水试验监测视觉 prompt"""
    loc = f"照片位置：{location}。" if location else ""
    return f"""你是索克家居（i-home.life）AI 工地监理视觉模型。请分析这张防水闭水试验照片。
{loc}
检测以下问题并返回 JSON（仅返回 JSON）：
```json
{{
  "waterproofing": {{
    "leak_detected": false,
    "water_level_ok": true,
    "confidence": 0.0-1.0,
    "notes": "简要说明"
  }},
  "issues": [
    {{"type": "leak|water_level|hollow|other", "description": "描述",
      "severity": "low|medium|high|critical", "suggestion": "整改建议"}}
  ]
}}
```
注意：未发现问题时返回 issues 为空数组。只返回 JSON。"""


def _build_safety_vision_prompt(location: str) -> str:
    """构建安全违规抓拍视觉 prompt"""
    loc = f"照片位置：{location}。" if location else ""
    return f"""你是索克家居（i-home.life）AI 工地监理视觉模型。请分析这张工地施工照片。
{loc}
检测安全违规（未佩戴安全帽/反光衣/防护等）并返回 JSON（仅返回 JSON）：
```json
{{
  "violations_detected": false,
  "confidence": 0.0-1.0,
  "issues": [
    {{"type": "no_helmet|no_reflective|no_protection|other", "description": "描述",
      "severity": "low|medium|high|critical", "suggestion": "整改建议"}}
  ]
}}
```
注意：无违规时返回 issues 为空数组。只返回 JSON。"""


def _rule_fallback(photo: dict, scene_type: str, content: str) -> list[dict]:
    """规则降级：从描述文本中按关键词粗判（诚实标注 rule_mock）"""
    issues: list[dict] = []
    keywords = (
        _WATERPROOF_RULE_KEYWORDS if scene_type == "waterproofing" else _SAFETY_RULE_KEYWORDS
    )
    for kw in keywords:
        if kw in content:
            issues.append({
                "type": "other",
                "description": f"疑似{kw}",
                "severity": "medium",
                "suggestion": "请人工复查确认",
                "source": "rule_mock",
            })
    return issues


async def run_ai_patrol(project_id: str, photos: list[dict]) -> dict:
    """AI 工地巡检：逐张分析闭水试验/安全照片，输出结构化发现

    Args:
        project_id: 项目 ID
        photos: [{url, scene_type, location, captured_at}]
            scene_type ∈ waterproofing / safety

    Returns:
        结构化巡检报告（含 source 诚实标注）
    """
    findings: list[dict] = []
    vision_used = None
    degrade_count = 0

    for photo in photos:
        url = photo.get("url", "")
        scene_type = photo.get("scene_type", "waterproofing")
        location = photo.get("location", "")
        captured_at = photo.get("captured_at", "")
        if scene_type not in SCENE_TYPES:
            scene_type = "waterproofing"

        prompt = (
            _build_waterproof_vision_prompt(location)
            if scene_type == "waterproofing"
            else _build_safety_vision_prompt(location)
        )

        try:
            image_bytes, mime = _fetch_image_bytes(url)
            raw = _call_vision_llm(prompt, image_bytes, mime)
            parsed = _parse_vision_json(raw)
            vision_used = "ai_vision"
            issues = _extract_issues(parsed, scene_type)
            for issue in issues:
                issue["source"] = "ai_vision"
            findings.append({
                "url": url,
                "scene_type": scene_type,
                "location": location,
                "captured_at": captured_at,
                "source": "ai_vision",
                "issues": issues,
            })
        except Exception as exc:  # noqa: BLE001 — 视觉不可用诚实降级 rule_mock
            logger.warning("ai_patrol_degrade_to_rule: scene=%s error=%s", scene_type, exc)
            degrade_count += 1
            issues = _rule_fallback(photo, scene_type, str(exc))
            findings.append({
                "url": url,
                "scene_type": scene_type,
                "location": location,
                "captured_at": captured_at,
                "source": "rule_mock",
                "issues": issues,
            })

    total_issues = sum(len(f["issues"]) for f in findings)
    critical = sum(
        1 for f in findings for i in f["issues"] if i.get("severity") == "critical"
    )
    return {
        "project_id": project_id,
        "photo_count": len(photos),
        "findings": findings,
        "summary": {
            "total_issues": total_issues,
            "critical": critical,
            "degraded_to_rule": degrade_count,
        },
        "source": "ai_vision" if vision_used else "rule_mock",
        "note": (
            "AI 工地监理完成（多模态视觉模型）"
            if vision_used
            else "未配置视觉模型 key，已诚实降级规则判定，请人工复核"
        ),
    }


def _extract_issues(parsed: dict, scene_type: str) -> list[dict]:
    """从视觉模型返回的 JSON 提取 issues 列表"""
    issues: list[dict] = []
    if scene_type == "waterproofing":
        wf = parsed.get("waterproofing", {}) if isinstance(parsed, dict) else {}
        if wf and isinstance(wf, dict):
            if wf.get("leak_detected"):
                issues.append({
                    "type": "leak",
                    "description": wf.get("notes", "检测到渗漏"),
                    "severity": "critical",
                    "suggestion": "立即排查渗漏点并重做防水",
                })
            if not wf.get("water_level_ok", True):
                issues.append({
                    "type": "water_level",
                    "description": "水位异常，闭水试验可能不足",
                    "severity": "medium",
                    "suggestion": "补充蓄水至标准水位",
                })
    else:
        if parsed.get("violations_detected"):
            issues.append({
                "type": "no_helmet",
                "description": parsed.get("issues", [{}])[0].get("description", "检测到安全违规")
                if isinstance(parsed.get("issues"), list) and parsed.get("issues")
                else "检测到安全违规",
                "severity": "high",
                "suggestion": "立即停止作业并整改",
            })

    raw_issues = parsed.get("issues", []) if isinstance(parsed, dict) else []
    if isinstance(raw_issues, list):
        for issue in raw_issues:
            if isinstance(issue, dict) and issue.get("type") and issue["type"] != "other":
                issues.append({
                    "type": issue.get("type"),
                    "description": issue.get("description", ""),
                    "severity": issue.get("severity", "medium"),
                    "suggestion": issue.get("suggestion", ""),
                })
    return issues

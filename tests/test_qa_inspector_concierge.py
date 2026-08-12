"""QA Inspector Agent 与 Concierge Agent 核心方法测试

覆盖:
- QAInspectorAgent: generate_acceptance_report / compare_with_design / detect_defects / detect_qa_intent
- F38 真实 CV：多模态视觉 LLM 路径（cv_mode=real_vision_llm / engine=vision_llm）+ 失败诚实降级
- ConciergeAgent: answer_faq / classify_inquiry / generate_response / detect_concierge_intent
- 模块级函数: get_acceptance_items / list_defect_categories / search_knowledge_base / check_escalation
- Orchestrator 路由: qa_inspector / concierge 意图
- API 端点: /qa-inspector/* /concierge/* (mock 模式)
"""

import json

import pytest
from httpx import AsyncClient

from app.agents.qa_inspector import (
    QAInspectorAgent,
    ACCEPTANCE_ITEMS,
    DEFECT_CATEGORIES,
    get_acceptance_items,
    list_defect_categories,
    assess_defect_severity,
)
from app.agents.concierge import (
    ConciergeAgent,
    FAQ_KNOWLEDGE_BASE,
    search_knowledge_base,
    list_faq_by_category,
    check_escalation,
    get_all_faq_categories,
)
from app.agents.orchestrator import OrchestratorAgent


async def _register(client: AsyncClient, phone: str = "13900006001") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "新Agent测试用户", "password": "test123456"},
    )
    return resp.json()["access_token"]


# === QAInspectorAgent 单元测试 ===


def test_qa_acceptance_report_basic():
    """验收报告生成 — 基本结构验证"""
    agent = QAInspectorAgent()
    project_data = {
        "project_id": "P001",
        "project_name": "测试项目",
        "inspector": "质检员",
        "acceptance_date": "2026-07-08",
        "phases": ["mep", "masonry"],
        "inspection_results": {
            "mep": [
                {"item": "水管打压测试", "result": "pass", "issues": []},
                {"item": "电路绝缘测试", "result": "pass", "issues": []},
            ],
        },
    }
    report = agent.generate_acceptance_report(project_data)

    assert report["project_id"] == "P001"
    assert report["project_name"] == "测试项目"
    assert len(report["sections"]) == 2
    # mep 阶段有 5 个验收项
    mep_section = next(s for s in report["sections"] if s["phase"] == "mep")
    assert mep_section["total_items"] == 5
    assert "summary" in report
    assert "overall_verdict" in report
    assert "reply" in report
    assert "合格率" in report["reply"]
    # 诚实降级标注（P1-4：mock 引擎必须显式标注，禁止伪装真实能力）
    assert report["source"] == "mock"
    assert report["engine"] == "mock_rule_engine"
    assert report["is_placeholder"] is True


def test_qa_acceptance_report_all_phases():
    """验收报告 — 全部 5 个阶段"""
    agent = QAInspectorAgent()
    project_data = {
        "project_id": "P002",
        "project_name": "全阶段验收",
        "phases": ["mep", "masonry", "carpentry", "painting", "installation"],
        "inspection_results": {},
    }
    report = agent.generate_acceptance_report(project_data)

    assert len(report["sections"]) == 5
    assert report["summary"]["total_items"] > 0
    # 总体验收结论应为有效值
    assert report["overall_verdict"] in ("excellent", "pass", "conditional_pass", "fail")


def test_qa_acceptance_report_with_failures():
    """验收报告 — 含不合格项的整改建议"""
    agent = QAInspectorAgent()
    project_data = {
        "project_id": "P003",
        "project_name": "整改项目",
        "phases": ["masonry"],
        "inspection_results": {
            "masonry": [
                {"item": "防水闭水试验", "result": "fail", "issues": ["卫生间防水渗漏"]},
                {"item": "瓷砖空鼓率", "result": "fail", "issues": ["客厅瓷砖空鼓超标"]},
            ],
        },
    }
    report = agent.generate_acceptance_report(project_data)

    masonry = report["sections"][0]
    assert masonry["failed"] >= 2
    assert len(report["all_issues"]) >= 2
    assert len(report["rectification_suggestions"]) >= 2
    # 渗漏问题应识别为对应缺陷类别
    leak_suggestion = next(
        (s for s in report["rectification_suggestions"] if "渗漏" in s["issue"]),
        None,
    )
    assert leak_suggestion is not None


def test_qa_compare_with_design():
    """照片与设计图纸比对"""
    agent = QAInspectorAgent()
    inspection_data = {
        "project_id": "P001",
        "phase": "masonry",
        "images": [
            {"url": "http://example.com/img1.jpg", "type": "tile_surface", "location": "客厅东墙"},
            {"url": "http://example.com/img2.jpg", "type": "wall_surface", "location": "卫生间"},
        ],
        "design_reference": {"url": "http://example.com/design.pdf", "specs": {"tile_size": "800x800", "gap": "2mm"}},
        "expected_dimensions": {"tile_gap": "2mm", "flatness": "≤3mm"},
    }
    result = agent.compare_with_design(inspection_data)

    assert result["project_id"] == "P001"
    assert result["phase"] == "masonry"
    assert result["image_count"] == 2
    assert len(result["spec_comparisons"]) == 2
    assert len(result["dimension_deviations"]) == 2
    assert len(result["image_analyses"]) == 2
    assert "consistency_rate" in result
    assert "verdict" in result
    assert result["verdict"] in ("consistent", "minor_deviation", "major_deviation")
    assert "reply" in result
    # 诚实降级标注（P1-4）
    assert result["source"] == "mock"
    assert result["engine"] == "mock_cv_engine"
    assert result["is_placeholder"] is True
    # F38 诚实说明：mock 路径必须携带 cv_mode + note
    assert result["cv_mode"] == "mock"
    assert "真实 CV" in result["note"]


def test_qa_detect_defects():
    """工艺缺陷识别"""
    agent = QAInspectorAgent()
    image_data = {
        "project_id": "P001",
        "phase": "masonry",
        "images": [
            {"url": "http://example.com/defect1.jpg", "type": "tile_surface", "location": "卫生间墙面"},
            {"url": "http://example.com/defect2.jpg", "type": "wall_surface", "location": "客厅墙面"},
            {"url": "http://example.com/defect3.jpg", "type": "ceiling", "location": "厨房吊顶"},
        ],
        "check_categories": ["hollow", "crack", "leak", "flatness"],
    }
    result = agent.detect_defects(image_data)

    assert result["project_id"] == "P001"
    assert result["phase"] == "masonry"
    assert result["image_count"] == 3
    assert result["checked_items"] == 12  # 3 张图 × 4 个类别
    assert "severity_count" in result
    assert "category_count" in result
    assert "verdict" in result
    assert result["verdict"] in ("pass", "fail", "conditional_pass", "minor_issues")
    assert "reply" in result
    # 诚实降级标注（P1-4）
    assert result["source"] == "mock"
    assert result["engine"] == "mock_cv_engine"
    assert result["is_placeholder"] is True
    # F38 诚实说明：mock 路径必须携带 cv_mode + note
    assert result["cv_mode"] == "mock"
    assert "真实 CV" in result["note"]


def test_qa_detect_defects_no_defects():
    """工艺缺陷识别 — 无缺陷场景"""
    agent = QAInspectorAgent()
    image_data = {
        "project_id": "P004",
        "phase": "painting",
        "images": [],
        "check_categories": ["hollow", "crack"],
    }
    result = agent.detect_defects(image_data)

    assert result["defect_count"] == 0
    assert result["verdict"] == "pass"
    assert "合格" in result["verdict_text"]


# === F38 真实 CV（多模态视觉 LLM）测试 ===


def test_qa_detect_defects_real_cv(monkeypatch):
    """F38: 真实 CV 路径 — 视觉模型返回结构化缺陷 → cv_mode=real_vision_llm/engine=vision_llm"""
    from app.agents import qa_inspector as qa_mod
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "real_cv_quality_enabled", True)
    monkeypatch.setattr(qa_mod, "_fetch_image_bytes", lambda url: (b"fake-image", "image/jpeg"))
    monkeypatch.setattr(
        qa_mod, "_call_vision_llm",
        lambda prompt, image_bytes, mime: json.dumps({
            "defects": [
                {
                    "category": "hollow",
                    "description": "客厅东墙瓷砖空鼓",
                    "confidence": 0.92,
                    "location_hint": "墙面中下部",
                    "suggestion": "拆除空鼓瓷砖重新铺贴",
                },
                {
                    "category": "crack",
                    "description": "卫生间墙面裂缝",
                    "confidence": 0.85,
                    "location_hint": "墙角",
                    "suggestion": "裂缝修补后复检",
                },
            ]
        }),
    )

    agent = QAInspectorAgent()
    result = agent.detect_defects({
        "project_id": "P001",
        "phase": "masonry",
        "images": [
            {"url": "http://example.com/d1.jpg", "type": "tile_surface", "location": "卫生间墙面"},
        ],
        "check_categories": ["hollow", "crack"],
    })

    assert result["cv_mode"] == "real_vision_llm"
    assert result["engine"] == "vision_llm"
    assert result["source"] == "vision_llm"
    assert result["is_placeholder"] is False
    assert result["defect_count"] == 2
    defect = result["detected_defects"][0]
    # 结构化输出：类型/位置/置信度/建议
    assert defect["category"] == "hollow"
    assert defect["location"] == "墙面中下部"
    assert defect["confidence"] == 0.92
    assert defect["rectification"] == "拆除空鼓瓷砖重新铺贴"


def test_qa_detect_defects_real_cv_failure_degrades_to_mock(monkeypatch):
    """F38: 真实 CV 调用失败 → 诚实降级为 mock（engine=mock_cv_engine + note 标注）"""
    from app.agents import qa_inspector as qa_mod
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "real_cv_quality_enabled", True)
    monkeypatch.setattr(
        qa_mod, "_fetch_image_bytes",
        lambda url: (_ for _ in ()).throw(RuntimeError("vision api down")),
    )

    agent = QAInspectorAgent()
    result = agent.detect_defects({
        "project_id": "P001",
        "phase": "masonry",
        "images": [{"url": "http://example.com/d1.jpg", "type": "tile_surface"}],
        "check_categories": ["hollow"],
    })

    assert result["engine"] == "mock_cv_engine"
    assert result["cv_mode"] == "mock"
    assert result["is_placeholder"] is True
    assert "降级" in result["note"]


def test_qa_compare_with_design_real_cv(monkeypatch):
    """F38: 真实 CV 路径 — 图纸比对走视觉模型 → cv_mode=real_vision_llm"""
    from app.agents import qa_inspector as qa_mod
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "real_cv_quality_enabled", True)
    monkeypatch.setattr(qa_mod, "_fetch_image_bytes", lambda url: (b"fake-image", "image/jpeg"))
    monkeypatch.setattr(
        qa_mod, "_call_vision_llm",
        lambda prompt, image_bytes, mime: json.dumps({
            "image_analysis": {"matches_design": False, "confidence": 0.7, "notes": "瓷砖缝隙明显偏大"},
            "spec_comparisons": [
                {"spec_item": "tile_size", "design_value": "800x800", "actual_value": "约800x800", "consistent": True},
            ],
            "dimension_deviations": [
                {"dimension": "tile_gap", "standard": "2mm", "measured_value": 3.5, "deviation": 1.5, "pass": False},
            ],
        }),
    )

    agent = QAInspectorAgent()
    result = agent.compare_with_design({
        "project_id": "P001",
        "phase": "masonry",
        "images": [{"url": "http://example.com/1.jpg", "type": "tile_surface", "location": "客厅东墙"}],
        "design_reference": {"specs": {"tile_size": "800x800"}},
        "expected_dimensions": {"tile_gap": "2mm"},
    })

    assert result["cv_mode"] == "real_vision_llm"
    assert result["engine"] == "vision_llm"
    assert result["is_placeholder"] is False
    assert result["image_analyses"][0]["matches_design"] is False
    assert result["dimension_deviations"][0]["pass"] is False
    assert result["verdict"] in ("consistent", "minor_deviation", "major_deviation")


# === 视觉感知：验收报告视觉化 + 诊断数据可视化看图 ===


def _vision_settings(monkeypatch, enabled: bool):
    """获取并设置 real_cv_quality_enabled（模块级 settings 单例，teardown 自动还原）。"""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "real_cv_quality_enabled", enabled)
    return settings


def test_qa_acceptance_report_vision_defects(monkeypatch):
    """验收报告视觉化：提供现场照片 + 真实 CV → 视觉缺陷汇入报告并如实标注来源"""
    from app.agents import qa_inspector as qa_mod

    _vision_settings(monkeypatch, True)
    monkeypatch.setattr(qa_mod, "_fetch_image_bytes", lambda url: (b"fake-image", "image/jpeg"))
    monkeypatch.setattr(
        qa_mod, "_call_vision_llm",
        lambda prompt, image_bytes, mime: json.dumps({
            "defects": [
                {
                    "category": "hollow",
                    "description": "客厅东墙瓷砖空鼓",
                    "confidence": 0.91,
                    "location_hint": "客厅东侧",
                    "suggestion": "拆除空鼓瓷砖重新铺贴",
                }
            ]
        }),
    )

    agent = QAInspectorAgent()
    report = agent.generate_acceptance_report({
        "project_id": "P004",
        "project_name": "视觉验收项目",
        "phases": ["masonry"],
        "inspection_results": {},
        "images": [
            {"url": "data:image/jpeg;base64,AAAA", "type": "tile_surface", "location": "客厅东墙"},
        ],
    })

    # 真实 CV 缺陷汇入报告（结构化：类型/位置/置信度/建议）
    assert report["vision_defect_count"] == 1
    defect = report["vision_defects"][0]
    assert defect["category"] == "hollow"
    assert defect["confidence"] == 0.91
    assert defect["rectification"] == "拆除空鼓瓷砖重新铺贴"
    # 视觉缺陷并入整改建议且带来源标注（诚实，不伪装规则判定）
    vision_sug = next(
        (s for s in report["rectification_suggestions"] if s.get("source") == "vision_llm"),
        None,
    )
    assert vision_sug is not None
    assert "视觉" in vision_sug["issue"]
    # 数据来源如实更新 + 诚实标注
    assert report["source"] == "rule_engine+vision_llm"
    assert report["engine"] == "mock_rule_engine+vision_llm"
    assert report["is_placeholder"] is False
    assert report["cv_mode"] == "real_vision_llm"
    assert "视觉" in report["note"]
    assert "视觉检出 1 项缺陷" in report["reply"]


def test_qa_acceptance_report_vision_degrades_to_mock(monkeypatch):
    """验收报告视觉化降级：有照片但视觉不可用 → 保持 mock + 诚实标注（不伪装视觉）"""
    from app.agents import qa_inspector as qa_mod

    _vision_settings(monkeypatch, True)
    monkeypatch.setattr(
        qa_mod, "_fetch_image_bytes",
        lambda url: (_ for _ in ()).throw(RuntimeError("vision api down")),
    )

    agent = QAInspectorAgent()
    report = agent.generate_acceptance_report({
        "project_id": "P004",
        "project_name": "降级项目",
        "phases": ["masonry"],
        "inspection_results": {},
        "images": [{"url": "http://example.com/d1.jpg", "type": "tile_surface"}],
    })

    assert report["vision_defect_count"] == 0
    assert report["vision_defects"] == []
    assert report["source"] == "mock"
    assert report["is_placeholder"] is True
    assert report["note"] is not None
    assert "视觉模型不可用" in report["note"]


def test_qa_acceptance_report_chart_render_and_analysis(monkeypatch):
    """诊断数据可视化看图：include_chart=True → Pillow 渲染 PNG 图表 + 视觉模型"看图"解读"""
    from app.agents import qa_inspector as qa_mod

    _vision_settings(monkeypatch, True)
    monkeypatch.setattr(
        qa_mod, "_call_vision_llm",
        lambda prompt, image_bytes, mime: json.dumps({
            "summary": "整体质量良好，泥瓦工程合格率偏低需重点关注。",
            "key_risks": [{"phase": "masonry", "risk": "合格率 80%，存在空鼓风险"}],
            "recommendations": ["对泥瓦工程复检空鼓与渗漏"],
        }),
    )

    agent = QAInspectorAgent()
    report = agent.generate_acceptance_report({
        "project_id": "P005",
        "project_name": "图表项目",
        "phases": ["mep", "masonry"],
        "inspection_results": {
            "masonry": [
                {"item": "瓷砖空鼓率", "result": "fail", "issues": ["客厅瓷砖空鼓超标"]},
            ],
        },
        "include_chart": True,
    })

    # 图表为确定性渲染（真实数据 PNG），独立于视觉模型可用性
    import base64 as b64

    assert report["chart_mime"] == "image/png"
    png = b64.b64decode(report["chart_b64"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    # 视觉模型"看图"解读（结构化）
    assert report["chart_analysis"]["summary"]
    assert report["chart_analysis"]["key_risks"][0]["phase"] == "masonry"
    assert report["chart_analysis"]["recommendations"]
    assert report["chart_analysis_note"] is None


def test_qa_acceptance_report_chart_analysis_degrades(monkeypatch):
    """图表解读降级：视觉模型不可用 → chart_analysis=None + 诚实标注，图表仍返回"""
    from app.agents import qa_inspector as qa_mod

    _vision_settings(monkeypatch, True)
    monkeypatch.setattr(
        qa_mod, "_call_vision_llm",
        lambda prompt, image_bytes, mime: (_ for _ in ()).throw(RuntimeError("no vision key")),
    )

    agent = QAInspectorAgent()
    report = agent.generate_acceptance_report({
        "project_id": "P006",
        "project_name": "解读降级项目",
        "phases": ["mep"],
        "inspection_results": {},
        "include_chart": True,
    })

    assert report["chart_b64"]
    assert report["chart_analysis"] is None
    assert report["chart_analysis_note"] is not None
    assert "视觉模型不可用" in report["chart_analysis_note"]


def test_qa_acceptance_report_chart_without_vision_flag(monkeypatch):
    """real_cv_quality_enabled=False：图表仍渲染（确定性真实数据），但不做 LLM 解读"""
    _vision_settings(monkeypatch, False)

    agent = QAInspectorAgent()
    report = agent.generate_acceptance_report({
        "project_id": "P007",
        "project_name": "无视觉项目",
        "phases": ["mep"],
        "inspection_results": {},
        "include_chart": True,
    })

    assert report["chart_b64"]
    assert report["chart_analysis"] is None
    assert report["chart_analysis_note"] is not None
    assert "视觉模型不可用" in report["chart_analysis_note"]


def test_qa_detect_intent():
    """质检意图识别"""
    assert QAInspectorAgent.detect_qa_intent("生成分项验收报告") == "acceptance"
    assert QAInspectorAgent.detect_qa_intent("照片与图纸比对") == "compare"
    assert QAInspectorAgent.detect_qa_intent("检测瓷砖空鼓缺陷") == "defect"
    assert QAInspectorAgent.detect_qa_intent("质检检查") == "inspection"
    assert QAInspectorAgent.detect_qa_intent("需要返工整改") == "rectification"
    assert QAInspectorAgent.detect_qa_intent("你好") == "general"


def test_acceptance_checklist_phase_aliases():
    """P2-8：前端阶段命名别名归一化（water_electricity→mep、acceptance→completion）"""
    from app.standards.acceptance_checklists import get_checklist

    mep = get_checklist("water_electricity")
    assert len(mep) > 0
    assert mep == get_checklist("mep")
    completion = get_checklist("acceptance")
    assert len(completion) > 0
    assert completion == get_checklist("completion")
    # 未知阶段回退空列表，不抛异常
    assert get_checklist("unknown_phase_xyz") == []


def test_qa_module_functions():
    """质检模块级函数测试"""
    # get_acceptance_items — 全部
    all_items = get_acceptance_items()
    assert all_items["total_phases"] == len(ACCEPTANCE_ITEMS)
    assert all_items["total_items"] > 0

    # get_acceptance_items — 按阶段
    mep_items = get_acceptance_items("mep")
    assert mep_items["phase"] == "mep"
    assert mep_items["total"] == 5

    # get_acceptance_items — 未知阶段
    unknown = get_acceptance_items("unknown_phase")
    assert unknown["items"] == []

    # list_defect_categories
    cats = list_defect_categories()
    assert cats["total"] == len(DEFECT_CATEGORIES)
    assert cats["total"] == 8

    # assess_defect_severity
    leak_assessment = assess_defect_severity("渗漏", 1)
    assert leak_assessment["base_severity"] == "critical"
    # 多个 medium 缺陷升级为 high
    flatness_assessment = assess_defect_severity("平整度", 6)
    assert flatness_assessment["priority"] == "high"


# === ConciergeAgent 单元测试 ===


def test_concierge_answer_faq_found():
    """FAQ 知识问答 — 匹配成功"""
    agent = ConciergeAgent()
    result = agent.answer_faq("装修预算大概多少钱")

    assert result["found"] is True
    assert "预算" in result["answer"]
    assert result["match_score"] > 0
    assert result["need_human"] is False
    assert len(result["matched_faqs"]) >= 1


def test_concierge_answer_faq_not_found():
    """FAQ 知识问答 — 无匹配"""
    agent = ConciergeAgent()
    result = agent.answer_faq("量子力学基本原理是什么")

    assert result["found"] is False
    assert result["need_human"] is True
    assert result["matched_faqs"] == []


def test_concierge_answer_faq_waterproof():
    """FAQ 知识问答 — 防水相关"""
    agent = ConciergeAgent()
    result = agent.answer_faq("防水怎么做才算合格")

    assert result["found"] is True
    assert "闭水" in result["answer"] or "48" in result["answer"]


def test_concierge_classify_inquiry_design():
    """咨询分类 — 设计咨询"""
    agent = ConciergeAgent()
    result = agent.classify_inquiry("我想了解一下装修风格有哪些")

    assert result["inquiry_type"] == "design"
    assert result["type_name"] == "设计咨询"
    assert result["need_human"] is False
    assert result["urgency"] == "low"
    assert len(result["suggestions"]) > 0


def test_concierge_classify_inquiry_complaint():
    """咨询分类 — 投诉需转人工"""
    agent = ConciergeAgent()
    result = agent.classify_inquiry("我要投诉你们的服务态度很差")

    assert result["inquiry_type"] == "complaint"
    assert result["need_human"] is True
    assert result["urgency"] == "high"
    assert "人工" in " ".join(result["suggestions"])


def test_concierge_classify_inquiry_urgent():
    """咨询分类 — 紧急售后（漏水）"""
    agent = ConciergeAgent()
    result = agent.classify_inquiry("紧急！卫生间漏水了怎么办")

    assert result["need_human"] is True
    assert result["urgency"] == "critical"


def test_concierge_classify_inquiry_refund():
    """咨询分类 — 退款请求"""
    agent = ConciergeAgent()
    result = agent.classify_inquiry("我要申请退款")

    assert result["need_human"] is True
    assert result["urgency"] == "medium"


def test_concierge_detect_intent():
    """客服意图识别"""
    assert ConciergeAgent.detect_concierge_intent("常见问题FAQ") == "faq"
    assert ConciergeAgent.detect_concierge_intent("我要投诉") == "complaint"
    assert ConciergeAgent.detect_concierge_intent("售后保修维修") == "after_sale"
    assert ConciergeAgent.detect_concierge_intent("申请退款") == "refund"
    assert ConciergeAgent.detect_concierge_intent("转人工客服") == "help"
    assert ConciergeAgent.detect_concierge_intent("你好在吗") == "greeting"
    assert ConciergeAgent.detect_concierge_intent("今天天气不错") == "general"


@pytest.mark.asyncio
async def test_concierge_generate_response_fallback():
    """客服回复生成 — LLM 不可用时 FAQ 兜底"""
    agent = ConciergeAgent()
    try:
        # 无 API key 时 think 会抛异常，generate_response 应走 FAQ 兜底
        reply = await agent.generate_response("装修预算多少钱")
        assert isinstance(reply, str)
        assert len(reply) > 0
    finally:
        await agent.close()


def test_concierge_module_functions():
    """客服模块级函数测试"""
    # search_knowledge_base
    results = search_knowledge_base("防水")
    assert results["total"] > 0
    assert any("防水" in r["answer"] for r in results["results"])

    # search_knowledge_base — 无结果
    no_results = search_knowledge_base("量子力学")
    assert no_results["total"] == 0

    # list_faq_by_category
    construction_faqs = list_faq_by_category("construction")
    assert construction_faqs["total"] >= 2

    # check_escalation — 触发升级
    escalation = check_escalation("我要投诉你们")
    assert escalation["need_human"] is True
    assert escalation["urgency"] == "high"

    # check_escalation — 未触发
    no_escalation = check_escalation("装修风格有哪些")
    assert no_escalation["need_human"] is False

    # get_all_faq_categories
    cats = get_all_faq_categories()
    assert cats["total_faqs"] == len(FAQ_KNOWLEDGE_BASE)
    assert cats["total_faqs"] >= 10


# === Orchestrator 路由测试 ===


def test_orchestrator_fallback_qa_inspector():
    """Orchestrator 规则分类 — 质检意图"""
    r = OrchestratorAgent.fallback_classify("生成验收报告，检查瓷砖空鼓缺陷")
    assert r["intent"] == "qa_inspector"


def test_orchestrator_fallback_concierge():
    """Orchestrator 规则分类 — 客服意图"""
    r = OrchestratorAgent.fallback_classify("我要投诉，转人工客服")
    assert r["intent"] == "concierge"


def test_orchestrator_fallback_construction_still_works():
    """Orchestrator 规则分类 — 施工意图仍正确（含验收但不以质检为主）"""
    r = OrchestratorAgent.fallback_classify("施工进度怎么样了,什么时候验收")
    assert r["intent"] == "construction"


# === API 端点集成测试（mock 模式）===


@pytest.fixture(autouse=False)
def force_mock_mode(monkeypatch):
    """MOCK_MODE 已移除，该 fixture 不再生效。mock 路径测试需改为真实 LLM 测试或 skip。"""
    pass


@pytest.mark.asyncio
async def test_api_qa_acceptance_report(client: AsyncClient):
    """API: 生成验收报告"""
    token = await _register(client, "13900006010")
    resp = await client.post(
        "/api/agents/qa-inspector/acceptance-report",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "project_id": "P001",
            "project_name": "API测试项目",
            "phases": ["mep", "masonry"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == "P001"
    assert len(data["sections"]) == 2
    assert "overall_verdict" in data
    # 诚实降级标注透传（P1-4）
    assert data["source"] == "mock"
    assert data["is_placeholder"] is True


@pytest.mark.asyncio
async def test_api_qa_compare_design(client: AsyncClient):
    """API: 图纸比对"""
    token = await _register(client, "13900006011")
    resp = await client.post(
        "/api/agents/qa-inspector/compare-design",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "project_id": "P001",
            "phase": "masonry",
            "images": [{"url": "http://example.com/1.jpg", "type": "tile"}],
            "design_reference": {"specs": {"tile_size": "800x800"}},
            "expected_dimensions": {"flatness": "≤3mm"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["phase"] == "masonry"
    assert "consistency_rate" in data
    # 诚实降级标注透传（P1-4）
    assert data["source"] == "mock"
    assert data["is_placeholder"] is True


@pytest.mark.asyncio
async def test_api_qa_defects(client: AsyncClient):
    """API: 缺陷检测"""
    token = await _register(client, "13900006012")
    resp = await client.post(
        "/api/agents/qa-inspector/defects",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "project_id": "P001",
            "phase": "masonry",
            "images": [{"url": "http://example.com/d1.jpg", "type": "tile"}],
            "check_categories": ["hollow", "crack"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["defect_count"] >= 0
    assert "verdict" in data
    # 诚实降级标注透传（P1-4）
    assert data["source"] == "mock"
    assert data["is_placeholder"] is True


@pytest.mark.asyncio
async def test_api_concierge_faq(client: AsyncClient):
    """API: FAQ 知识问答"""
    token = await _register(client, "13900006013")
    resp = await client.post(
        "/api/agents/concierge/faq",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "装修预算多少钱"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert "预算" in data["answer"]


@pytest.mark.asyncio
async def test_api_concierge_classify(client: AsyncClient):
    """API: 咨询分类"""
    token = await _register(client, "13900006014")
    resp = await client.post(
        "/api/agents/concierge/classify",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "我要投诉服务态度差"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["inquiry_type"] == "complaint"
    assert data["need_human"] is True


@pytest.mark.asyncio
async def test_api_concierge_chat(client: AsyncClient, force_mock_mode):
    """API: 客服对话（mock 模式）"""
    token = await _register(client, "13900006015")
    resp = await client.post(
        "/api/agents/concierge/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "装修一般需要多长时间"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_type"] == "concierge"
    assert len(data["reply"]) > 0


@pytest.mark.asyncio
async def test_api_qa_endpoints_require_auth(client: AsyncClient):
    """API: 质检端点需认证"""
    resp = await client.post(
        "/api/agents/qa-inspector/acceptance-report",
        json={"phases": []},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_concierge_endpoints_require_auth(client: AsyncClient):
    """API: 客服端点需认证"""
    resp = await client.post(
        "/api/agents/concierge/faq",
        json={"question": "测试"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_qa_inspector_intent_mock(client: AsyncClient, force_mock_mode):
    """Orchestrator chat 路由 — 质检意图路由到 qa_inspector"""
    token = await _register(client, "13900006016")
    resp = await client.post(
        "/api/agents/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "生成验收报告，检查质量缺陷", "agent_type": "orchestrator"},
    )
    assert resp.status_code == 200
    assert resp.json()["agent_type"] == "qa_inspector"


@pytest.mark.asyncio
async def test_chat_concierge_intent_mock(client: AsyncClient, force_mock_mode):
    """Orchestrator chat 路由 — 客服意图路由到 concierge"""
    token = await _register(client, "13900006017")
    resp = await client.post(
        "/api/agents/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "我要投诉，转人工客服", "agent_type": "orchestrator"},
    )
    assert resp.status_code == 200
    assert resp.json()["agent_type"] == "concierge"

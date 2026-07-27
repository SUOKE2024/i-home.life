"""v1.1.29 家居补短功能测试

测试覆盖 4 项补短任务（v1.2.4 清理 P0 微服务拆分）：
- P0 A2UI 协议内化
- P1 HMAC-SHA256 审计签名
- P1 装修知识库
- P2 施工健康 OS
"""
import json
import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test_v1129.db")
os.environ.setdefault("PASETO_SECRET_KEY", "test-secret-key-for-v1.1.29-testing-32bytes!")
os.environ.setdefault("QWEN_AUDIO_API_KEY", "")


# ════════════════════════════════════════════════════════════════
# P0 A2UI 协议内化
# ════════════════════════════════════════════════════════════════


class TestA2UIProtocol:
    """A2UI 协议测试"""

    def test_schema_card_types(self):
        """A2UI schema 定义 8 种卡片类型"""
        from app.services.a2ui_schema import CardType
        types = list(CardType)
        assert len(types) >= 8
        type_values = {t.value for t in types}
        required = {"design_plan", "budget_breakdown", "construction_progress",
                     "procurement_order", "qa_report", "settlement_summary",
                     "material_card", "alert_card"}
        assert required.issubset(type_values)

    def test_generator_design_to_card(self):
        """设计输出 → A2UI 卡片转换"""
        from app.services.a2ui_generator import design_to_card
        card = design_to_card({
            "plans": [{"name": "方案A", "brief": "北欧风"}],
            "recommendation": "推荐方案A",
        })
        assert card["type"] == "design_plan"
        assert "data" in card
        assert "version" in card

    def test_generator_budget_to_card(self):
        """预算输出 → A2UI 卡片转换"""
        from app.services.a2ui_generator import budget_to_card
        card = budget_to_card({
            "items": [{"name": "瓷砖", "price": 5000}],
            "total": 50000,
            "tax": 4500,
            "warranty": 0.03,
        })
        assert card["type"] == "budget_breakdown"

    def test_generator_generic_fallback(self):
        """通用文本 → A2UI 卡片 fallback"""
        from app.services.a2ui_generator import generic_to_card
        card = generic_to_card("designer", "方案已生成")
        assert card["type"] == "alert_card"
        assert "方案已生成" in str(card["data"])

    def test_a2ui_feature_flag(self):
        """a2ui_enabled feature flag 已定义"""
        from app.config import get_settings
        s = get_settings()
        assert hasattr(s, "a2ui_enabled")
        assert s.a2ui_enabled is True

    # ── v1.2.3 补齐: 全部转换器 + 自动路由 + 批量 + 序列化 ──

    def test_generator_construction_to_card(self):
        """施工输出 → A2UI 卡片转换"""
        from app.services.a2ui_generator import construction_to_card
        card = construction_to_card({
            "project_name": "测试项目",
            "overall_progress": 0.65,
            "phases": [
                {"name": "水电", "progress": 1.0, "status": "completed"},
                {"name": "瓦工", "progress": 0.5, "status": "in_progress"},
            ],
            "crew_info": {"leader": "王工", "team_size": 8, "specialties": ["水电", "瓦工"]},
            "next_milestone": {"name": "木工进场", "date": "2026-03-01"},
        })
        assert card["type"] == "construction_progress"
        assert card["data"]["overall_progress"] == 0.65
        assert len(card["data"]["phases"]) == 2

    def test_generator_procurement_to_card(self):
        """采购输出 → A2UI 卡片转换"""
        from app.services.a2ui_generator import procurement_to_card
        card = procurement_to_card({
            "order_id": "PO-2026-001",
            "items": [{"name": "瓷砖", "specs": "800x800mm", "quantity": 50, "unit": "箱"}],
            "supplier": {"name": "东鹏建材", "contact": "138xxxx"},
            "total_amount": 12000,
            "delivery_date": "2026-03-15",
            "status": "ordered",
        })
        assert card["type"] == "procurement_order"
        assert card["data"]["total_amount"] == 12000

    def test_generator_qa_to_card(self):
        """质检输出 → A2UI 卡片转换（含 pass/fail 统计）"""
        from app.services.a2ui_generator import qa_to_card
        card = qa_to_card({
            "project_name": "测试项目",
            "checkpoints": [
                {"name": "墙面平整度", "result": "pass", "standard": "偏差≤2mm", "actual": "1.2mm"},
                {"name": "地面空鼓", "result": "fail", "standard": "无空鼓", "actual": "3处空鼓"},
                {"name": "水电验收", "result": "pass", "standard": "通电通水", "actual": "正常"},
            ],
            "inspector": "李工",
            "inspection_date": "2026-03-01",
        })
        assert card["type"] == "qa_report"
        assert card["data"]["failed_count"] == 1
        assert card["data"]["passed_count"] == 2
        assert card["data"]["overall_result"] == "fail"

    def test_generator_qa_all_pass(self):
        """质检 — 全部通过时 overall=pass"""
        from app.services.a2ui_generator import qa_to_card
        card = qa_to_card({
            "checkpoints": [
                {"name": "墙面", "result": "pass"},
                {"name": "地面", "result": "pass"},
            ],
        })
        assert card["data"]["overall_result"] == "pass"

    def test_generator_qa_has_pending(self):
        """质检 — 有 pending 且无 fail 时 overall=pending"""
        from app.services.a2ui_generator import qa_to_card
        card = qa_to_card({
            "checkpoints": [
                {"name": "墙面", "result": "pass"},
                {"name": "水电", "result": "pending"},
            ],
        })
        assert card["data"]["overall_result"] == "pending"

    def test_generator_settlement_to_card(self):
        """结算输出 → A2UI 卡片转换"""
        from app.services.a2ui_generator import settlement_to_card
        card = settlement_to_card({
            "project_name": "测试项目",
            "total_amount": 100000,
            "paid_amount": 60000,
            "payment_history": [
                {"date": "2026-01-10", "amount": 30000, "method": "银行转账", "status": "completed"},
            ],
        })
        assert card["type"] == "settlement_summary"
        assert card["data"]["balance_amount"] == 40000

    def test_generator_settlement_balance_given(self):
        """结算 — balance_amount 显式指定时不重算"""
        from app.services.a2ui_generator import settlement_to_card
        card = settlement_to_card({
            "total_amount": 100000,
            "paid_amount": 60000,
            "balance_amount": 50000,  # 显式指定
        })
        assert card["data"]["balance_amount"] == 50000

    def test_generator_material_to_card(self):
        """材料输出 → A2UI 卡片转换"""
        from app.services.a2ui_generator import material_to_card
        card = material_to_card({
            "name": "东鹏瓷砖",
            "category": "瓷砖",
            "specs": "800×800mm",
            "eco_level": "E0",
            "unit_price": 128,
            "unit": "㎡",
            "supplier": "东鹏建材",
            "stock_status": "in_stock",
            "certifications": ["CCC", "ISO9001"],
        })
        assert card["type"] == "material_card"
        assert card["data"]["eco_level"] == "E0"
        assert len(card["data"]["certifications"]) == 2

    def test_generator_agent_router(self):
        """agent_output_to_card 自动路由 — 设计/预算/施工/采购/质检/结算/材料"""
        from app.services.a2ui_generator import agent_output_to_card
        # 设计 → design_plan
        c = agent_output_to_card("design", {"project_name": "测试", "total_area": 100})
        assert c["type"] == "design_plan"
        # 预算 → budget_breakdown
        c = agent_output_to_card("budget", {"total": 50000, "items": []})
        assert c["type"] == "budget_breakdown"
        # 施工 → construction_progress
        c = agent_output_to_card("construction", {"overall_progress": 0.5, "phases": []})
        assert c["type"] == "construction_progress"
        # 采购 → procurement_order
        c = agent_output_to_card("procurement", {"order_id": "PO-001", "items": []})
        assert c["type"] == "procurement_order"
        # 质检 → qa_report
        c = agent_output_to_card("quality", {"checkpoints": []})
        assert c["type"] == "qa_report"
        # 结算 → settlement_summary
        c = agent_output_to_card("settlement", {"total_amount": 100})
        assert c["type"] == "settlement_summary"
        # 材料 → material_card
        c = agent_output_to_card("products", {"name": "瓷砖"})
        assert c["type"] == "material_card"

    def test_generator_batch_to_cards(self):
        """batch_to_cards 批量转换"""
        from app.services.a2ui_generator import batch_to_cards
        outputs = [
            {"agent_key": "design", "project_name": "测试A", "total_area": 80},
            {"agent_key": "budget", "total": 50000, "items": []},
            {"agent_key": "procurement", "order_id": "PO-001", "items": []},
        ]
        cards = batch_to_cards(outputs)
        assert len(cards) == 3
        assert cards[0]["type"] == "design_plan"
        assert cards[1]["type"] == "budget_breakdown"
        assert cards[2]["type"] == "procurement_order"

    def test_generator_batch_no_agent_key(self):
        """batch_to_cards — 无 agent_key 时使用默认值"""
        from app.services.a2ui_generator import batch_to_cards
        cards = batch_to_cards([{"text": "hello"}], agent_key="design")
        assert len(cards) == 1
        # 没有 project_name/total_area → 走 design_to_card 但字段为空 → 仍然是 design_plan 类型
        assert cards[0]["type"] == "design_plan"

    def test_generator_str_input_fallback(self):
        """agent_output_to_card — 纯文本输入走 generic fallback"""
        from app.services.a2ui_generator import agent_output_to_card
        c = agent_output_to_card("unknown", "这是一段文本回复")
        assert c["type"] == "alert_card"

    def test_generator_already_a2ui_card(self):
        """agent_output_to_card — 已是 A2UI 卡片格式则直接返回"""
        from app.services.a2ui_generator import agent_output_to_card
        existing = {"type": "budget_breakdown", "data": {"total": 100}, "version": "1.0"}
        c = agent_output_to_card("budget", existing)
        assert c is existing  # 直接返回同一对象

    def test_schema_serialization(self):
        """A2UI 序列化 — card_to_json + encode_cards_to_wire"""
        from app.services.a2ui_schema import make_card, CardType, card_to_json, encode_cards_to_wire
        card = make_card(CardType.DESIGN_PLAN, {"project_name": "测试"})
        json_str = card_to_json(card, indent=2)
        assert '"type": "design_plan"' in json_str
        assert '"project_name"' in json_str

        wire = encode_cards_to_wire([card])
        parsed = json.loads(wire)
        assert parsed["version"] == "1.1.0"
        assert len(parsed["cards"]) == 1

    def test_schema_all_card_types_have_to_card(self):
        """所有卡片数据类都有 to_card() 方法"""
        from app.services.a2ui_schema import (
            DesignPlanData, BudgetBreakdownData, ConstructionProgressData,
            ProcurementOrderData, QAReportData, SettlementSummaryData,
            MaterialCardData, AlertCardData,
        )
        instances = [
            DesignPlanData(project_name="x", floor_layout="", total_area=0),
            BudgetBreakdownData(project_name="x"),
            ConstructionProgressData(project_name="x", overall_progress=0),
            ProcurementOrderData(order_id="x"),
            QAReportData(project_name="x"),
            SettlementSummaryData(project_name="x"),
            MaterialCardData(name="x"),
            AlertCardData(),
        ]
        for instance in instances:
            card = instance.to_card()
            assert "type" in card, f"{type(instance).__name__} missing type"
            assert "data" in card, f"{type(instance).__name__} missing data"
            assert "version" in card, f"{type(instance).__name__} missing version"

    def test_agents_api_a2ui_cards_integration(self):
        """v1.2.3: /agents/chat 响应包含 a2ui_cards 字段（designer 结构化输出）"""
        from app.api.agents import _generate_a2ui_cards
        # 模拟 DesignerAgent JSON 输出
        designer_json = json.dumps({
            "project_name": "朝阳丽景",
            "floor_layout": "三室两厅",
            "total_area": 120,
            "style": "现代简约",
            "rooms": [{"name": "客厅", "area": 28, "orientation": "南"}],
        })
        cards = _generate_a2ui_cards("designer", designer_json)
        assert cards is not None
        assert len(cards) == 1
        assert cards[0]["type"] == "design_plan"

    def test_agents_api_plain_text_no_cards(self):
        """纯文本 Agent 回复不生成 A2UI 卡片"""
        from app.api.agents import _generate_a2ui_cards
        cards = _generate_a2ui_cards("designer", "推荐您选择现代简约风格的核心体系设计方案")
        assert cards is None

    def test_agents_api_unregistered_agent(self):
        """未注册转换器的 Agent 不生成 A2UI 卡片"""
        from app.api.agents import _generate_a2ui_cards
        cards = _generate_a2ui_cards("concierge", json.dumps({"reply": "你好"}))
        assert cards is None

    def test_make_alert_card_factory(self):
        """make_alert_card 快捷工厂"""
        from app.services.a2ui_schema import make_alert_card
        card = make_alert_card(
            title="预算超支",
            message="装修预算已超出 15%",
            severity="warning",
            alert_type="budget_overrun",
            source_agent="budget",
        )
        assert card["type"] == "alert_card"
        assert card["data"]["severity"] == "warning"
        assert card["data"]["title"] == "预算超支"

    # ── v1.2.3 端到端集成测试 ──

    def test_e2e_agent_response_with_a2ui_cards(self):
        """端到端: AgentResponse JSON 序列化含 a2ui_cards 字段"""
        from app.api.agents import AgentResponse
        from app.services.a2ui_schema import make_card, CardType
        # 模拟 DesignerAgent 产生的 A2UI 卡片
        card = make_card(CardType.DESIGN_PLAN, {
            "project_name": "朝阳丽景",
            "floor_layout": "三室两厅",
            "total_area": 120,
            "rooms": [{"name": "客厅", "area": 28}],
            "style": "现代简约",
            "preview_3d_url": "",
            "preview_image_url": "",
            "estimated_timeline": "90天",
            "notes": "",
        })
        response = AgentResponse(
            agent_type="designer",
            reply="已为您生成 1 套设计方案。推荐方案A。",
            suggestions=["调整方案", "查看材料清单"],
            session_id="sess-123",
            a2ui_cards=[card],
        )
        # 验证 JSON 序列化（模拟 FastAPI 响应）
        data = response.model_dump(mode="json")
        assert data["agent_type"] == "designer"
        assert data["a2ui_cards"] is not None
        assert len(data["a2ui_cards"]) == 1
        # 验证卡片结构（Flutter 客户端期望的格式）
        c = data["a2ui_cards"][0]
        assert c["type"] == "design_plan"
        assert "version" in c
        assert "id" in c
        assert "timestamp" in c
        assert "data" in c
        assert c["data"]["project_name"] == "朝阳丽景"

    def test_e2e_agent_response_no_cards(self):
        """端到端: a2ui_cards=None 时 JSON 不包含空列表"""
        from app.api.agents import AgentResponse
        response = AgentResponse(
            agent_type="concierge",
            reply="您好，有什么可以帮您的？",
            a2ui_cards=None,
        )
        data = response.model_dump(mode="json")
        assert data["a2ui_cards"] is None  # None 而非 []
        assert "a2ui_cards" in data  # 字段存在但值为 None

    def test_e2e_designer_raw_json_flow(self):
        """端到端: DesignerAgent 原始 JSON → _generate_a2ui_cards 完整链路"""
        from app.api.agents import _generate_a2ui_cards
        # 模拟真实的 DesignerAgent.think() 返回的 JSON (含 ```json 包裹)
        raw_json = """```json
{
  "plans": [
    {"name": "方案A", "brief": "北欧简约风", "area": 120}
  ],
  "recommendation": "推荐方案A",
  "materials": ["实木地板", "乳胶漆"],
  "reply": "已为您生成 1 套设计方案",
  "project_name": "测试项目",
  "floor_layout": "两室一厅",
  "total_area": 80,
  "style": "北欧风",
  "rooms": [{"name": "客厅", "area": 25, "orientation": "南"}]
}
```"""
        cards = _generate_a2ui_cards("designer", raw_json)
        assert cards is not None, "DesignerAgent原始JSON应生成A2UI卡片"
        assert len(cards) == 1
        card = cards[0]
        assert card["type"] == "design_plan"
        assert card["data"]["project_name"] == "测试项目"
        assert card["data"]["total_area"] == 80
        # 验证 cards 中每个字段都是 JSON 可序列化的
        json_str = json.dumps(card, ensure_ascii=False)
        assert "design_plan" in json_str
        assert "测试项目" in json_str

    def test_e2e_finalize_with_raw_output(self):
        """端到端: _finalize 优先使用 raw_output 生成 A2UI 卡片"""
        from app.api.agents import _generate_a2ui_cards
        # 模拟 _finalize 的行为：raw_output 传入原始 JSON，reply_text 传入提取文本
        raw_json = '{"project_name": "测试", "total_area": 100, "style": "简约"}'
        reply_text = "已为您生成设计方案"

        # raw_output 应成功生成卡片
        cards_from_raw = _generate_a2ui_cards("designer", raw_json)
        assert cards_from_raw is not None

        # reply_text (纯文本) 应不生成卡片
        cards_from_text = _generate_a2ui_cards("designer", reply_text)
        assert cards_from_text is None

    def test_e2e_ss_end_to_end_card_structure(self):
        """端到端: 验证 A2UI 卡片完整结构可被 Flutter A2UIRenderer 消费"""
        from app.services.a2ui_schema import (
            make_card, CardType, DesignPlanData, BudgetBreakdownData,
            ConstructionProgressData, ProcurementOrderData, QAReportData,
            SettlementSummaryData, MaterialCardData, encode_cards_to_wire,
        )
        # 构造所有 7 种业务卡片类型
        cards = [
            DesignPlanData(project_name="A", floor_layout="", total_area=80).to_card(),
            BudgetBreakdownData(project_name="A", items=[], total=50000).to_card(),
            ConstructionProgressData(project_name="A", overall_progress=0.5).to_card(),
            ProcurementOrderData(order_id="PO-001", items=[], total_amount=12000).to_card(),
            QAReportData(project_name="A", checkpoints=[]).to_card(),
            SettlementSummaryData(project_name="A", total_amount=100000).to_card(),
            MaterialCardData(name="瓷砖", eco_level="E0", unit_price=128).to_card(),
        ]
        # 模拟 SSE done 事件的 a2ui_cards 字段
        wire = encode_cards_to_wire(cards)
        parsed = json.loads(wire)
        assert parsed["version"] == "1.1.0"
        assert len(parsed["cards"]) == 7

        # 模拟 Flutter SSE 解析：每条卡片都有 type / data / version / id / timestamp
        for card in parsed["cards"]:
            assert "type" in card, f"missing type in {card}"
            assert "data" in card, f"missing data in {card}"
            assert "version" in card, f"missing version in {card}"
            assert "id" in card, f"missing id in {card}"
            assert "timestamp" in card, f"missing timestamp in {card}"
            # 验证 type 是有效的 CardType
            valid_types = {t.value for t in CardType}
            assert card["type"] in valid_types, f"unknown type: {card['type']}"

    def test_version_compatibility(self):
        """v1.2.3: 协议版本兼容性检查"""
        from app.services.a2ui_schema import check_version_compatible, PROTOCOL_VERSION, MIN_COMPATIBLE_VERSION
        # 当前版本应兼容自身
        assert check_version_compatible(PROTOCOL_VERSION) is True
        # 最低兼容版本应兼容
        assert check_version_compatible(MIN_COMPATIBLE_VERSION) is True
        # 更高 minor 版本应兼容
        assert check_version_compatible("1.5.0") is True
        # 更低 minor 版本不兼容
        assert check_version_compatible("1.-1.0") is False  # 无效版本
        assert check_version_compatible("0.9.0") is False   # major 不同
        # 卡片带版本字段
        assert check_version_compatible({"version": "1.2.0", "type": "test"}) is True
        assert check_version_compatible({"version": "0.9.0", "type": "test"}) is False
        # 无效输入
        assert check_version_compatible("invalid") is False
        assert check_version_compatible({}) is False


# ════════════════════════════════════════════════════════════════
# P1 HMAC-SHA256 审计签名
# ════════════════════════════════════════════════════════════════


class TestAuditIntegrity:
    """HMAC 审计完整性测试"""

    def test_hmac_sign_and_verify(self):
        """签名+验证往返测试"""
        from app.services.audit_integrity import compute_hmac, verify_hmac

        sig = compute_hmac(
            user_id="u-1", action="LOGIN", resource_type="user",
            resource_id="rid-1", details={"role": "admin"},
            timestamp="2026-07-22T10:00:00+00:00",
        )
        assert len(sig) == 64
        all(c in "0123456789abcdef" for c in sig)

        valid = verify_hmac(
            user_id="u-1", action="LOGIN", resource_type="user",
            resource_id="rid-1", details={"role": "admin"},
            timestamp="2026-07-22T10:00:00+00:00",
            signature=sig,
        )
        assert valid is True

    def test_hmac_detects_tampering(self):
        """HMAC 检测到篡改"""
        from app.services.audit_integrity import compute_hmac, verify_hmac

        sig = compute_hmac(
            user_id="u-1", action="LOGIN", resource_type="user",
            resource_id="rid-1", details={}, timestamp="t1",
        )
        # 篡改 user_id
        valid = verify_hmac(
            user_id="u-attacker", action="LOGIN", resource_type="user",
            resource_id="rid-1", details={}, timestamp="t1",
            signature=sig,
        )
        assert valid is False

    def test_sign_audit_entry_returns_none_when_disabled(self):
        """feature flag 关闭时不签名"""
        from app.config import get_settings
        from app.services.audit_integrity import sign_audit_entry

        original = get_settings().audit_hmac_enabled
        try:
            get_settings().audit_hmac_enabled = False
            result = sign_audit_entry("u-1", "LOGIN", "user", "rid-1", {})
            assert result is None
        finally:
            get_settings().audit_hmac_enabled = original

    def test_audit_hmac_feature_flag(self):
        """audit_hmac_enabled feature flag 已定义"""
        from app.config import get_settings
        s = get_settings()
        assert hasattr(s, "audit_hmac_enabled")
        assert s.audit_hmac_enabled is True

    def test_field_mask_levels(self):
        """字段级脱敏级别"""
        from app.services.audit_integrity import get_field_mask_level, should_mask_field
        assert get_field_mask_level("amount") == "L2"
        assert get_field_mask_level("bank_account") == "L3"
        assert get_field_mask_level("phone") == "L1"
        assert get_field_mask_level("note") == "L0"

        assert should_mask_field("amount", "contractor") is True
        assert should_mask_field("amount", "homeowner") is False
        assert should_mask_field("bank_account", "contractor") is True
        assert should_mask_field("bank_account", "admin") is False


# ════════════════════════════════════════════════════════════════
# P1 装修知识库 + 引用服务
# ════════════════════════════════════════════════════════════════


class TestKnowledgeBase:
    """装修知识库测试"""

    def test_4_json_files_exist(self):
        """4 个知识库 JSON 文件存在"""
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "knowledge"
        for fn in ["materials.json", "techniques.json", "standards.json", "faq.json"]:
            assert (root / fn).exists(), f"{fn} 不存在"

    def test_each_file_has_entries(self):
        """每个文件 >=15 条"""
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "knowledge"
        for fn in ["materials.json", "techniques.json", "standards.json", "faq.json"]:
            data = json.loads((root / fn).read_text(encoding="utf-8"))
            assert len(data) >= 15, f"{fn} 仅 {len(data)} 条"

    def test_entries_have_required_fields(self):
        """每条知识条目含 id/content/citation/tags"""
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "knowledge"
        for fn in ["materials.json", "techniques.json", "standards.json", "faq.json"]:
            data = json.loads((root / fn).read_text(encoding="utf-8"))
            for entry in data:
                assert "id" in entry
                assert "content" in entry
                assert "citation" in entry
                assert "tags" in entry

    @pytest.mark.asyncio
    async def test_loader_keyword_search(self):
        """知识库加载器关键词检索"""
        from knowledge.loader import KnowledgeLoader
        loader = KnowledgeLoader()
        results = await loader.search("瓷砖")
        assert len(results) > 0
        for r in results:
            assert "content" in r
            assert "citation" in r

    def test_citation_service(self):
        """引用服务格式化"""
        from app.services.citation_service import CitationService
        service = CitationService()
        evidence = [
            {"source": "materials", "content": "抛光砖...", "citation": "GB/T 4100-2015"},
        ]
        result = service.append_to_reply("这是回复内容", evidence)
        assert "📚" in result
        assert "GB/T 4100-2015" in result

    def test_qa_checklist(self):
        """QA 质检清单"""
        from app.services.qa_knowledge_service import QAKnowledgeService
        service = QAKnowledgeService()
        checklist = service.get_checklist("mep")
        assert len(checklist) > 0

    def test_knowledge_base_flag(self):
        """knowledge_base_enabled feature flag"""
        from app.config import get_settings
        s = get_settings()
        assert hasattr(s, "knowledge_base_enabled")
        assert s.knowledge_base_enabled is True


# ════════════════════════════════════════════════════════════════
# P2 施工健康 OS
# ════════════════════════════════════════════════════════════════


class TestHealthOS:
    """施工健康 OS 测试"""

    def test_rule_engine_normal(self):
        """正常进度判定"""
        from app.services.health_monitor import HealthRuleEngine, AlertLevel
        engine = HealthRuleEngine()
        level, reason = engine.evaluate(80, 82, 0, 0)
        assert level == AlertLevel.NORMAL

    def test_rule_engine_critical_overdue(self):
        """超期里程碑触发严重预警"""
        from app.services.health_monitor import HealthRuleEngine, AlertLevel
        engine = HealthRuleEngine()
        level, reason = engine.evaluate(40, 10, 2, 3)
        assert level == AlertLevel.CRITICAL
        assert "超期" in reason or "滞后" in reason

    def test_rule_engine_warning(self):
        """进度偏差 10-20% 触发警告"""
        from app.services.health_monitor import HealthRuleEngine, AlertLevel
        engine = HealthRuleEngine()
        level, reason = engine.evaluate(50, 35, 1, 0)
        assert level in (AlertLevel.WARNING, AlertLevel.SEVERE)

    def test_compute_health_score(self):
        """施工健康评分计算"""
        from app.services.health_monitor import HealthRuleEngine
        engine = HealthRuleEngine()
        score = engine.compute_health_score(50, 40, 1, 0, 10)
        assert score < 100
        assert score > 0

    def test_score_to_status(self):
        """评分 → 健康状态"""
        from app.services.health_monitor import HealthRuleEngine, HealthStatus
        engine = HealthRuleEngine()
        assert engine.score_to_status(90) == HealthStatus.HEALTHY
        assert engine.score_to_status(70) == HealthStatus.ATTENTION
        assert engine.score_to_status(50) == HealthStatus.AT_RISK
        assert engine.score_to_status(30) == HealthStatus.CRITICAL

    def test_health_os_flag(self):
        """health_os_enabled feature flag"""
        from app.config import get_settings
        s = get_settings()
        assert hasattr(s, "health_os_enabled")
        assert s.health_os_enabled is True

    def test_push_enabled_flag(self):
        """push_enabled feature flag"""
        from app.config import get_settings
        s = get_settings()
        assert hasattr(s, "push_enabled")
        assert s.push_enabled is True


# ════════════════════════════════════════════════════════════════
# 集成：v1.1.29 feature flags 完整性
# ════════════════════════════════════════════════════════════════


class TestV129FeatureFlags:
    """v1.1.29 全部 feature flags"""

    def test_all_v129_flags_in_settings(self):
        """所有 v1.1.29 feature flags 在 settings 中定义"""
        from app.config import get_settings
        s = get_settings()
        flags = [
            "audit_hmac_enabled", "health_os_enabled", "push_enabled",
            "a2ui_enabled", "knowledge_base_enabled", "service_role",
        ]
        for f in flags:
            assert hasattr(s, f), f"缺失 feature flag: {f}"

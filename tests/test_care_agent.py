"""康养管家 CareAgent 测试（v1.16.x）

覆盖：
- 告警 → 场景联动确定性编排（跌倒/心率/睡眠/空气质量/正常）
- harness 注册
- AID/ACDL 身份卡生成（type_code=08）
"""
from app.agents.care import CareAgent


def test_evaluate_fall_critical_escalates():
    r = CareAgent.evaluate_care_actions("fall_detection", {"fall_detected": True}, "critical")
    assert r["alert_level"] == "critical"
    assert r["escalate"] is True
    assert "notify 家属/护工" in r["actions"]
    assert "turn_on 起夜照明" in r["actions"]


def test_evaluate_heart_rate_critical():
    r = CareAgent.evaluate_care_actions("heart_rate", {"bpm": 130}, "critical")
    assert r["escalate"] is True
    assert "notify 家属" in r["actions"]


def test_evaluate_sleep_warning_no_escalate():
    r = CareAgent.evaluate_care_actions("sleep_quality", {"sleep_score": 50}, "warning")
    assert r["escalate"] is False
    assert "adjust 遮光" in r["actions"]
    assert "adjust 白噪音" in r["actions"]


def test_evaluate_air_quality_warning():
    r = CareAgent.evaluate_care_actions("air_quality", {"pm25": 80}, "warning")
    assert r["escalate"] is False
    assert "turn_on 新风" in r["actions"]


def test_evaluate_normal_no_actions():
    r = CareAgent.evaluate_care_actions("heart_rate", {"bpm": 72}, "normal")
    assert r["actions"] == []
    assert r["escalate"] is False
    assert r["advice"]


def test_agent_registered_in_harness():
    from app.agents import get_harness
    harness = get_harness()
    assert "care" in harness._agent_registry
    assert harness._agent_registry["care"].agent_name == "care"


def test_care_agent_identity_card_type_code():
    from app.services.agent_identity_card import get_agent_identity
    identity = get_agent_identity("care")
    assert identity["aid"][9:11] == "08"  # 9 厂商 + 2 类型码（care=08）
    caps = identity["acdl"]["agent"]["capabilities"]
    assert any("健康" in c or "跌倒" in c or "康养" in c for c in caps)

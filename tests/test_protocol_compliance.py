"""智能家居协议兼容矩阵校验测试（Matter 1.6 / OneConnect / GB-T 46456）

覆盖:
- check_device_compliance 单设备协议合规校验
- check_scheme_compliance 方案级批量校验（汇总）
- recommend_compatible_protocol 最兼容协议推荐
- decorate_protocol_recommendation + recommend_protocol 集成（flag 开关）

遵循项目红线：仅用 monkeypatch.setattr(get_settings(), ...) 切换 flag，
禁止调用 get_settings.cache_clear()（会导致跨文件测试隔离失败）。
"""

from app.config import get_settings
from app.services.protocol_compliance import (
    check_device_compliance,
    check_scheme_compliance,
    recommend_compatible_protocol,
)
from app.services.smart_home_service import recommend_protocol


# ── check_device_compliance 单设备合规校验 ───────────────


def test_check_device_compliance_light_matter_compatible():
    """light + matter → 兼容且 standards.matter=True、带 Matter 1.6 版本说明"""
    result = check_device_compliance("light", "matter")
    assert result["compatible"] is True
    assert result["device_type"] == "light"
    assert result["protocol"] == "matter"
    assert result["standards"]["matter"] is True
    assert result["standards"]["gbt46456"] is True
    assert result["matter_version_note"] == "Matter 1.6 已支持 NFC 配网"


def test_check_device_compliance_security_camera_matter_incompatible():
    """security_camera + matter → 不兼容（Matter 不支持摄像头），alternative_protocols 含 wifi"""
    result = check_device_compliance("security_camera", "matter")
    assert result["compatible"] is False
    assert result["reason"] == "protocol_not_supported"
    assert "wifi" in result["alternative_protocols"]


def test_check_device_compliance_unknown_device_type():
    """未知 device_type → compatible=False 且 reason=unknown_device_type"""
    result = check_device_compliance("unknown_device", "matter")
    assert result["compatible"] is False
    assert result["reason"] == "unknown_device_type"


def test_check_device_compliance_unknown_protocol():
    """未知 protocol → compatible=False 且 reason=unknown_protocol"""
    result = check_device_compliance("light", "carrier_pigeon")
    assert result["compatible"] is False
    assert result["reason"] == "unknown_protocol"


# ── check_scheme_compliance 方案级批量校验 ───────────────


def test_check_scheme_compliance_mixed_stats():
    """混合设备：total/compliant/incompliant 统计正确且 summary 提示不兼容台数"""
    devices = [
        {"device_type": "light", "protocol": "matter"},
        {"device_type": "switch", "protocol": "matter"},
        {"device_type": "security_camera", "protocol": "matter"},
    ]
    result = check_scheme_compliance(devices)
    assert result["total"] == 3
    assert result["compliant"] == 2
    assert result["incompliant"] == 1
    assert len(result["results"]) == 3
    assert result["summary"] == "1 台设备不兼容，需调整协议选型"


def test_check_scheme_compliance_all_compliant():
    """全部兼容设备 → summary 为「全部设备互联互通合规」"""
    devices = [
        {"device_type": "light", "protocol": "matter"},
        {"device_type": "lock", "protocol": "wifi"},
    ]
    result = check_scheme_compliance(devices)
    assert result["total"] == 2
    assert result["compliant"] == 2
    assert result["incompliant"] == 0
    assert result["summary"] == "全部设备互联互通合规"


# ── recommend_compatible_protocol 最兼容协议推荐 ─────────


def test_recommend_compatible_protocol():
    """light 优先推荐 matter；未知设备类型返回 None"""
    assert recommend_compatible_protocol("light") == "matter"
    assert recommend_compatible_protocol("unknown_device") is None


# ── 集成：recommend_protocol flag 开关 ──────────────────


def test_recommend_protocol_flag_off_no_compliance_field(monkeypatch):
    """flag 关闭时 recommend_protocol 返回不含 protocol_compliance 字段（零回归）"""
    monkeypatch.setattr(get_settings(), "smart_protocol_compliance_enabled", False)
    result = recommend_protocol("xiaomi", [])
    assert "protocol_compliance" not in result
    # 原有字段保持不变
    assert result["recommended_protocol"] == "zigbee"
    assert set(result.keys()) == {
        "hub_brand", "recommended_protocol", "alternative_protocols",
        "compatibility", "notes",
    }


def test_recommend_protocol_flag_on_appends_compliance_field(monkeypatch):
    """flag 开启时 recommend_protocol 追加 protocol_compliance 字段且原有字段不变"""
    monkeypatch.setattr(get_settings(), "smart_protocol_compliance_enabled", True)
    result = recommend_protocol("xiaomi", [])
    assert "protocol_compliance" in result
    compliance = result["protocol_compliance"]
    assert set(compliance.keys()) == {
        "matter_ready", "gbt46456_ready", "oneconnect_ready", "note",
    }
    # 原有字段保持不变
    assert result["recommended_protocol"] == "zigbee"
    assert "hub_brand" in result

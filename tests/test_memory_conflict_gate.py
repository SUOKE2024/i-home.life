"""记忆冲突门控测试（v1.9.0，SSGM 防记忆漂移/投毒）

覆盖:
- detect_conflict 纯函数（相似度判定 / 短文本放行 / 相同文本不冲突）
- save_memory 冲突门控：flag 关闭零回归 / flag 开启 + gate_conflict 保留旧值
- build_conflict_gate_result 组装冲突结果
"""

import pytest

from app.config import get_settings
from app.services import agent_memory_service


# ── detect_conflict 纯函数 ──


def test_detect_conflict_same_text_no_conflict():
    """相同文本不应判为冲突"""
    is_conflict, ratio = agent_memory_service.detect_conflict("用户喜欢北欧风格", "用户喜欢北欧风格")
    assert is_conflict is False
    assert ratio == 1.0


def test_detect_conflict_similar_text_no_conflict():
    """高相似度文本不应判为冲突"""
    is_conflict, _ = agent_memory_service.detect_conflict("我喜欢北欧风装修", "我喜欢北欧风格装修")
    assert is_conflict is False


def test_detect_conflict_unrelated_text_conflict():
    """完全无关文本应判为冲突且相似度低于阈值"""
    is_conflict, ratio = agent_memory_service.detect_conflict("用户喜欢北欧风格", "预算上限50万需分期")
    assert is_conflict is True
    assert ratio < agent_memory_service._CONFLICT_SIMILARITY_THRESHOLD


def test_detect_conflict_short_text_passthrough():
    """长度不足最短阈值的记忆直接放行（不判冲突）"""
    is_conflict, _ = agent_memory_service.detect_conflict("A", "预算上限50万需分期")
    assert is_conflict is False


# ── save_memory 冲突门控 ──


@pytest.mark.asyncio
async def test_save_memory_flag_off_upsert(db_session, monkeypatch):
    """flag 关闭时保持原 upsert 行为（覆盖 + 无冲突标记）"""
    monkeypatch.setattr(get_settings(), "memory_conflict_gate_enabled", False)
    await agent_memory_service.save_memory(
        db_session, "u1", "preference", "style", "用户喜欢北欧风格", source="manual",
    )
    mem = await agent_memory_service.save_memory(
        db_session, "u1", "preference", "style", "预算上限50万需分期",
        gate_conflict=True,
    )
    assert getattr(mem, "conflict_detected", False) is False
    assert mem.memory_value == "预算上限50万需分期"  # 已覆盖


@pytest.mark.asyncio
async def test_save_memory_conflict_keeps_old_value(db_session, monkeypatch):
    """flag 开启 + gate_conflict=True + 冲突值 → 保留旧值并标记冲突"""
    monkeypatch.setattr(get_settings(), "memory_conflict_gate_enabled", True)
    await agent_memory_service.save_memory(
        db_session, "u1", "preference", "style", "用户喜欢北欧风格", source="manual",
    )
    mem = await agent_memory_service.save_memory(
        db_session, "u1", "preference", "style", "预算上限50万需分期",
        gate_conflict=True,
    )
    assert getattr(mem, "conflict_detected", False) is True
    assert mem.memory_value == "用户喜欢北欧风格"  # 旧值未被覆盖

    gate = agent_memory_service.build_conflict_gate_result(mem)
    assert gate["conflict"] is True
    assert gate["old_value"] == "用户喜欢北欧风格"
    assert gate["new_value"] == "预算上限50万需分期"


@pytest.mark.asyncio
async def test_save_memory_similar_value_overwrites(db_session, monkeypatch):
    """flag 开启 + gate_conflict=True + 相似值 → 正常覆盖（不误伤）"""
    monkeypatch.setattr(get_settings(), "memory_conflict_gate_enabled", True)
    await agent_memory_service.save_memory(
        db_session, "u1", "preference", "style", "我喜欢北欧风装修", source="manual",
    )
    mem = await agent_memory_service.save_memory(
        db_session, "u1", "preference", "style", "我喜欢北欧风格装修",
        gate_conflict=True,
    )
    assert getattr(mem, "conflict_detected", False) is False
    assert mem.memory_value == "我喜欢北欧风格装修"


@pytest.mark.asyncio
async def test_save_memory_gate_not_requested_overwrites(db_session, monkeypatch):
    """flag 开启但 gate_conflict 未显式开启 → 保持原行为（向后兼容）"""
    monkeypatch.setattr(get_settings(), "memory_conflict_gate_enabled", True)
    await agent_memory_service.save_memory(
        db_session, "u1", "preference", "style", "用户喜欢北欧风格", source="manual",
    )
    mem = await agent_memory_service.save_memory(
        db_session, "u1", "preference", "style", "预算上限50万需分期",
    )
    assert getattr(mem, "conflict_detected", False) is False
    assert mem.memory_value == "预算上限50万需分期"


def test_build_conflict_gate_result_no_conflict():
    """无冲突标记时返回 conflict=False"""
    class _FakeMem:
        pass

    assert agent_memory_service.build_conflict_gate_result(_FakeMem()) == {"conflict": False}

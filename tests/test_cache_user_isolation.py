"""缓存用户隔离硬约束测试（v1.3.0 P0-1）

对标项目硬约束："所有缓存 key 必须含 user_id 或为公共数据，
缓存读取前必须执行项目归属校验"。

覆盖：
- build_isolated_key: 公共数据 / 私有数据（含 project_id / 仅 user_id）/ strict 模式违规
- get_isolated / set_isolated / delete_isolated 便捷方法
- 跨用户隔离：用户 A 的缓存用户 B 读不到（key 前缀不同）
- invalidate_user_keys: 失效某用户全部缓存
- 非 strict 模式回退（开发环境）
"""

import pytest

from app.config import get_settings
from app.services.cache_service import (
    build_isolated_key,
    cache,
)


# === build_isolated_key: key 构造规则 ===


def test_build_isolated_key_public():
    """公共数据 → public: 前缀，无需 user_id"""
    key = build_isolated_key("feature-flags", public=True)
    assert key == "public:feature-flags"


def test_build_isolated_key_private_with_user_and_project():
    """私有数据含 user_id + project_id → u:{uid}:p:{pid}:{base}"""
    key = build_isolated_key("budget:summary", user_id=42, project_id=7)
    assert key == "u:42:p:7:budget:summary"


def test_build_isolated_key_private_with_user_only():
    """私有数据仅 user_id → u:{uid}:{base}"""
    key = build_isolated_key("user:profile", user_id=42)
    assert key == "u:42:user:profile"


def test_build_isolated_key_strict_violation_raises():
    """strict 模式下私有数据未传 user_id → ValueError（硬约束违规）"""
    # 默认 cache_user_isolation_strict=True
    with pytest.raises(ValueError, match="缓存硬约束违规"):
        build_isolated_key("budget:summary")


def test_build_isolated_key_non_strict_fallback(monkeypatch):
    """非 strict 模式下私有数据未传 user_id → 回退 u:anon: 前缀（仅开发环境）"""
    monkeypatch.setattr(get_settings(), "cache_user_isolation_strict", False)
    key = build_isolated_key("budget:summary")
    assert key == "u:anon:budget:summary"


def test_build_isolated_key_non_strict_public_still_works(monkeypatch):
    """非 strict 模式下 public=True 仍走 public: 前缀"""
    monkeypatch.setattr(get_settings(), "cache_user_isolation_strict", False)
    key = build_isolated_key("amap-config", public=True)
    assert key == "public:amap-config"


# === get_isolated / set_isolated / delete_isolated 便捷方法 ===


@pytest.mark.asyncio
async def test_set_isolated_and_get_isolated_roundtrip():
    """写入隔离缓存后能读回（含 user_id + project_id）"""
    await cache.set_isolated("budget:summary", {"total": 10000}, user_id=42, project_id=7, ttl=60)
    value = await cache.get_isolated("budget:summary", user_id=42, project_id=7)
    assert value == {"total": 10000}


@pytest.mark.asyncio
async def test_get_isolated_public():
    """公共数据隔离缓存读写"""
    await cache.set_isolated("feature-flags", {"flag1": True}, public=True, ttl=60)
    value = await cache.get_isolated("feature-flags", public=True)
    assert value == {"flag1": True}


@pytest.mark.asyncio
async def test_delete_isolated():
    """删除隔离缓存"""
    await cache.set_isolated("budget:summary", {"total": 10000}, user_id=42, project_id=7, ttl=60)
    await cache.delete_isolated("budget:summary", user_id=42, project_id=7)
    value = await cache.get_isolated("budget:summary", user_id=42, project_id=7)
    assert value is None


# === 跨用户隔离（核心硬约束：防跨用户数据泄露）===


@pytest.mark.asyncio
async def test_cross_user_isolation_user_a_not_readable_by_user_b():
    """用户 A 写入的缓存，用户 B 用自己的 user_id 读不到（key 前缀隔离）"""
    # 用户 A 写入
    await cache.set_isolated("budget:summary", {"total": 10000}, user_id=42, project_id=7, ttl=60)
    # 用户 B 尝试读取（用自己的 user_id）
    value_b = await cache.get_isolated("budget:summary", user_id=99, project_id=7)
    assert value_b is None, "跨用户读取应返回 None（key 隔离失败=数据泄露）"


@pytest.mark.asyncio
async def test_cross_user_isolation_different_keys():
    """不同用户的隔离 key 不同（前缀隔离的根本机制）"""
    key_a = build_isolated_key("budget:summary", user_id=42, project_id=7)
    key_b = build_isolated_key("budget:summary", user_id=99, project_id=7)
    assert key_a != key_b
    assert key_a == "u:42:p:7:budget:summary"
    assert key_b == "u:99:p:7:budget:summary"


@pytest.mark.asyncio
async def test_cross_user_isolation_project_isolation():
    """同一用户不同项目的缓存相互隔离"""
    await cache.set_isolated("budget:summary", {"total": 10000}, user_id=42, project_id=7, ttl=60)
    await cache.set_isolated("budget:summary", {"total": 20000}, user_id=42, project_id=8, ttl=60)
    v7 = await cache.get_isolated("budget:summary", user_id=42, project_id=7)
    v8 = await cache.get_isolated("budget:summary", user_id=42, project_id=8)
    assert v7 == {"total": 10000}
    assert v8 == {"total": 20000}


# === invalidate_user_keys ===


@pytest.mark.asyncio
async def test_invalidate_user_keys():
    """失效某用户全部缓存（登出/权限变更时）"""
    await cache.set_isolated("budget:summary", {"total": 10000}, user_id=42, project_id=7, ttl=60)
    await cache.set_isolated("user:profile", {"name": "Alice"}, user_id=42, ttl=60)
    # 用户 42 的缓存应存在
    assert await cache.get_isolated("budget:summary", user_id=42, project_id=7) is not None
    # 失效用户 42 全部缓存
    deleted = await cache.invalidate_user_keys(42)
    assert deleted >= 2
    # 失效后读不到
    assert await cache.get_isolated("budget:summary", user_id=42, project_id=7) is None
    assert await cache.get_isolated("user:profile", user_id=42) is None


@pytest.mark.asyncio
async def test_invalidate_user_keys_does_not_affect_other_users():
    """失效用户 A 的缓存不影响用户 B"""
    await cache.set_isolated("budget:summary", {"total": 10000}, user_id=42, project_id=7, ttl=60)
    await cache.set_isolated("budget:summary", {"total": 20000}, user_id=99, project_id=7, ttl=60)
    await cache.invalidate_user_keys(42)
    # 用户 99 的缓存仍在
    assert await cache.get_isolated("budget:summary", user_id=99, project_id=7) == {"total": 20000}


# === strict 模式便捷方法也强制 user_id ===


@pytest.mark.asyncio
async def test_set_isolated_strict_violation_raises():
    """strict 模式下 set_isolated 私有数据未传 user_id → ValueError"""
    with pytest.raises(ValueError, match="缓存硬约束违规"):
        await cache.set_isolated("budget:summary", {"total": 10000}, ttl=60)


@pytest.mark.asyncio
async def test_get_isolated_strict_violation_raises():
    """strict 模式下 get_isolated 私有数据未传 user_id → ValueError"""
    with pytest.raises(ValueError, match="缓存硬约束违规"):
        await cache.get_isolated("budget:summary")


# === v1.4.0 scope 维度（借鉴 YC QM 四级作用域）===


def test_build_isolated_key_with_scope_personal():
    """scope=personal → key 含 s:personal: 段"""
    key = build_isolated_key("budget:summary", user_id=42, project_id=7, scope="personal")
    assert key == "u:42:p:7:s:personal:budget:summary"


def test_build_isolated_key_with_scope_team():
    """scope=team → key 含 s:team: 段（区分团队共享 vs 个人私有）"""
    key = build_isolated_key("budget:summary", user_id=42, project_id=7, scope="team")
    assert key == "u:42:p:7:s:team:budget:summary"


def test_build_isolated_key_with_scope_no_project():
    """scope + 无 project_id → u:{uid}:s:{scope}:{base}"""
    key = build_isolated_key("user:profile", user_id=42, scope="project")
    assert key == "u:42:s:project:user:profile"


def test_build_isolated_key_scope_none_backward_compat():
    """scope=None（默认）→ 维持 v1.3.0 原格式（向后兼容回归测试）"""
    key_with_default = build_isolated_key("budget:summary", user_id=42, project_id=7)
    key_explicit_none = build_isolated_key("budget:summary", user_id=42, project_id=7, scope=None)
    assert key_with_default == "u:42:p:7:budget:summary"
    assert key_explicit_none == "u:42:p:7:budget:summary"


def test_build_isolated_key_scope_ignored_for_public():
    """public=True + scope → 仍为 public:{base}（scope 对公共数据无意义）"""
    key = build_isolated_key("feature-flags", public=True, scope="team")
    assert key == "public:feature-flags"


@pytest.mark.asyncio
async def test_set_isolated_with_scope_roundtrip():
    """set_isolated + scope → get_isolated + scope 能读回；不同 scope 互不干扰"""
    await cache.set_isolated("budget:summary", {"personal": True}, user_id=42, project_id=7, scope="personal")
    await cache.set_isolated("budget:summary", {"team": True}, user_id=42, project_id=7, scope="team")

    personal_val = await cache.get_isolated("budget:summary", user_id=42, project_id=7, scope="personal")
    team_val = await cache.get_isolated("budget:summary", user_id=42, project_id=7, scope="team")
    no_scope_val = await cache.get_isolated("budget:summary", user_id=42, project_id=7)

    assert personal_val == {"personal": True}
    assert team_val == {"team": True}
    # 无 scope 的 key 与有 scope 的 key 互不干扰
    assert no_scope_val is None

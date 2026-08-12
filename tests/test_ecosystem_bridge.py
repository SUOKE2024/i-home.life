"""F46 生态桥接优先级 API 集成测试

覆盖端点:
- GET /api/ecosystem/status    (生态桥接状态报告)
- GET /api/ecosystem/bridges   (生态桥接优先级列表)
"""
import asyncio

import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13950050001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "生态测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── 鉴权 ──


@pytest.mark.asyncio
async def test_ecosystem_unauthorized(client: AsyncClient):
    """未认证用户不能查看生态状态"""
    resp = await client.get("/api/ecosystem/status")
    assert resp.status_code == 401

    resp = await client.get("/api/ecosystem/bridges")
    assert resp.status_code == 401


# ── 状态报告 ──


@pytest.mark.asyncio
async def test_status_report_ecosystems(client: AsyncClient):
    """status 返回 4 个生态，含 configured/status/note 字段"""
    headers = await _auth_headers(client, "13950050002")
    resp = await client.get("/api/ecosystem/status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["bridges"]) == 4
    for bridge in data["bridges"]:
        assert "configured" in bridge
        assert "status" in bridge
        assert "note" in bridge
        assert "required_env_keys" in bridge
    assert "updated_at" in data
    assert "honest_note" in data


@pytest.mark.asyncio
async def test_status_honest_degradation(client: AsyncClient):
    """测试环境无 env key：configured=False 且 status=requires_api_key，note 诚实标注"""
    headers = await _auth_headers(client, "13950050003")
    resp = await client.get("/api/ecosystem/status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    for bridge in data["bridges"]:
        assert bridge["configured"] is False
        assert bridge["status"] == "requires_api_key"
        assert "诚实" in bridge["note"] and "501" in bridge["note"]


# ── 优先级列表 ──


@pytest.mark.asyncio
async def test_bridges_priority_order(client: AsyncClient):
    """bridges 按 priority 升序，含优先级策略说明"""
    headers = await _auth_headers(client, "13950050004")
    resp = await client.get("/api/ecosystem/bridges", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    priorities = [b["priority"] for b in data["bridges"]]
    assert priorities == sorted(priorities)
    assert [b["key"] for b in data["bridges"]] == ["mijia", "harmony", "homekit", "tuya"]
    assert "priority_strategy" in data
    assert "米家" in data["priority_strategy"] and "华为鸿蒙" in data["priority_strategy"]


# ── BridgeConnectionPool 单测（2026-08-12 场景执行并行重构）──


class _CountingBridge:
    """可计数 fake 桥：记录 connect/disconnect/send_command 次数，send 恒成功。"""

    def __init__(self):
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.send_calls = 0

    async def connect(self, credentials):
        self.connect_calls += 1
        return True

    async def disconnect(self):
        self.disconnect_calls += 1

    async def send_command(self, device_id, command, params):
        self.send_calls += 1
        return True


@pytest.mark.asyncio
async def test_bridge_pool_reuse_single_connection(monkeypatch):
    """连接池复用：同 ecosystem 多次 get 仅 1 次 connect，close_all 仅 1 次 disconnect"""
    from app.services import ecosystem_bridge as eb

    fake = _CountingBridge()
    monkeypatch.setattr(
        eb.BridgeFactory, "get_bridge",
        lambda ecosystem, credentials=None: fake,
    )
    pool = eb.BridgeConnectionPool()

    b1 = await pool.get("fake")
    b2 = await pool.get("fake")   # 复用同一实例

    assert b1 is b2
    assert fake.connect_calls == 1   # 仅首次握手
    assert fake.send_calls == 0

    # 复用连接下发命令
    bridge = await pool.get("fake")
    await bridge.send_command("d1", "turn_on", {})
    assert fake.send_calls == 1

    await pool.close_all()
    assert fake.disconnect_calls == 1  # 统一归还，仅 1 次断开


@pytest.mark.asyncio
async def test_bridge_pool_distinct_ecosystems(monkeypatch):
    """不同 ecosystem 各自独立连接"""
    from app.services import ecosystem_bridge as eb

    fake = _CountingBridge()
    fake2 = _CountingBridge()
    monkeypatch.setattr(
        eb.BridgeFactory, "get_bridge",
        lambda ecosystem, credentials=None: fake if ecosystem == "a" else fake2,
    )
    pool = eb.BridgeConnectionPool()

    await pool.get("a")
    await pool.get("b")
    assert fake.connect_calls == 1
    assert fake2.connect_calls == 1

    await pool.close_all()
    assert fake.disconnect_calls == 1
    assert fake2.disconnect_calls == 1


@pytest.mark.asyncio
async def test_bridge_pool_close_all_stub_silent():
    """close_all 对 stub 桥（disconnect 抛 NotImplementedError）静默不抛异常"""
    from app.services import ecosystem_bridge as eb

    pool = eb.BridgeConnectionPool()
    pool._conns["matter"] = eb.MatterBridge()   # stub：connect/disconnect 均 NotImplementedError

    await pool.close_all()  # 不应抛异常
    assert pool._conns == {}


class _SlowConnectBridge:
    """connect 有延迟的 fake 桥：制造并发首次建连的竞争窗口。"""

    def __init__(self):
        self.connect_calls = 0
        self.disconnect_calls = 0

    async def connect(self, credentials):
        self.connect_calls += 1
        await asyncio.sleep(0.05)   # 延迟放大竞争窗口
        return True

    async def disconnect(self):
        self.disconnect_calls += 1

    async def send_command(self, device_id, command, params):
        return True


@pytest.mark.asyncio
async def test_bridge_pool_concurrent_get_single_connect(monkeypatch):
    """并发首次 get 同一 ecosystem：asyncio.Lock 互斥，仅 1 次 connect（gather 并行场景）"""
    from app.services import ecosystem_bridge as eb

    fake = _SlowConnectBridge()
    monkeypatch.setattr(
        eb.BridgeFactory, "get_bridge",
        lambda ecosystem, credentials=None: fake,
    )
    pool = eb.BridgeConnectionPool()

    bridges = await asyncio.gather(*[pool.get("fake") for _ in range(5)])
    assert all(b is bridges[0] for b in bridges)  # 全部拿到同一实例
    assert fake.connect_calls == 1                 # Lock 保证仅首次握手

    await pool.close_all()
    assert fake.disconnect_calls == 1


@pytest.mark.asyncio
async def test_bridge_pool_connect_failure_not_cached(monkeypatch):
    """connect 抛异常：get 抛出且连接不入池，下次 get 重试成功（不缓存失败状态）"""
    from app.services import ecosystem_bridge as eb

    class _FlakyConnectBridge:
        def __init__(self):
            self.attempts = 0
            self.disconnect_calls = 0

        async def connect(self, credentials):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("connect boom")
            return True

        async def disconnect(self):
            self.disconnect_calls += 1

        async def send_command(self, device_id, command, params):
            return True

    fake = _FlakyConnectBridge()
    monkeypatch.setattr(
        eb.BridgeFactory, "get_bridge",
        lambda ecosystem, credentials=None: fake,
    )
    pool = eb.BridgeConnectionPool()

    with pytest.raises(RuntimeError):
        await pool.get("fake")
    assert pool._conns == {}          # 失败的连接未入池

    bridge = await pool.get("fake")   # 重试成功
    assert fake.attempts == 2
    assert bridge is not None

    await pool.close_all()
    assert fake.disconnect_calls == 1

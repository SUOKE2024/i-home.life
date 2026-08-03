"""地理定位 API 集成测试

覆盖端点:
- GET /api/location/search       (POI 搜索)
- GET /api/location/geocode      (地址 → 经纬度)
- GET /api/location/autocomplete  (地址智能提示)
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13900033001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "定位测试", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Auth 校验 ──


@pytest.mark.asyncio
async def test_search_unauthorized(client: AsyncClient):
    """未认证用户不能搜索位置"""
    resp = await client.get("/api/location/search?keywords=北京")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_geocode_unauthorized(client: AsyncClient):
    """未认证用户不能地理编码"""
    resp = await client.get("/api/location/geocode?address=北京市朝阳区")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_autocomplete_unauthorized(client: AsyncClient):
    """未认证用户不能地址提示"""
    resp = await client.get("/api/location/autocomplete?keywords=望京")
    assert resp.status_code == 401


# ── POI 搜索 ──


@pytest.mark.asyncio
async def test_search_places(client: AsyncClient):
    """搜索附近楼盘/小区"""
    headers = await _auth_headers(client, "13900033002")
    resp = await client.get(
        "/api/location/search",
        params={"keywords": "望京", "city": "北京"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "pois" in data
    assert "count" in data
    # 未配置高德 KEY 时返回空列表或 hints
    if data["count"] > 0:
        assert "name" in data["pois"][0]


@pytest.mark.asyncio
async def test_search_places_default_city(client: AsyncClient):
    """不指定城市的 POI 搜索"""
    headers = await _auth_headers(client, "13900033003")
    resp = await client.get(
        "/api/location/search",
        params={"keywords": "小区"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "pois" in data


# ── 地理编码 ──


@pytest.mark.asyncio
async def test_geocode_address(client: AsyncClient):
    """地址转经纬度"""
    headers = await _auth_headers(client, "13900033004")
    resp = await client.get(
        "/api/location/geocode",
        params={"address": "北京市朝阳区望京SOHO"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # 无 KEY 时返回 error
    assert "error" in data or "result" in data


@pytest.mark.asyncio
async def test_geocode_empty_address(client: AsyncClient):
    """空地址地理编码"""
    headers = await _auth_headers(client, "13900033005")
    resp = await client.get(
        "/api/location/geocode",
        params={"address": ""},
        headers=headers,
    )
    assert resp.status_code == 200


# ── 周边 POI 搜索（真实 LBS）──


@pytest.mark.asyncio
async def test_around_unauthorized(client: AsyncClient):
    """未认证用户不能周边搜索"""
    resp = await client.get("/api/location/around?location=116.481028,39.989643")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_around_places(client: AsyncClient):
    """周边 POI 搜索（未配置 key 时诚实降级为 demo 空结果，不伪造数据）"""
    headers = await _auth_headers(client, "13900033007")
    resp = await client.get(
        "/api/location/around",
        params={"location": "116.481028,39.989643", "keywords": "建材市场", "radius": 3000},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "pois" in data
    assert "count" in data
    assert "source" in data  # real / demo 标注（诚实降级）
    if data["count"] > 0:
        assert "name" in data["pois"][0]
        assert "distance" in data["pois"][0]


@pytest.mark.asyncio
async def test_around_invalid_radius(client: AsyncClient):
    """非法半径参数应被校验拒绝"""
    headers = await _auth_headers(client, "13900033008")
    resp = await client.get(
        "/api/location/around",
        params={"location": "116.481028,39.989643", "radius": 10},
        headers=headers,
    )
    assert resp.status_code == 422


# ── 地址智能提示 ──


@pytest.mark.asyncio
async def test_autocomplete(client: AsyncClient):
    """地址输入智能提示"""
    headers = await _auth_headers(client, "13900033006")
    resp = await client.get(
        "/api/location/autocomplete",
        params={"keywords": "望京", "city": "北京"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "pois" in data
    # autocomplete 还包含 IP 定位信息
    assert "current_city" in data

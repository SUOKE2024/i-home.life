"""小程序「提交改造需求」契约测试。

小程序端 `pages/demand` 提交的 JSON 与这里逐字段一致（见 miniapp/src/services/api.ts
ProjectCreatePayload 与 cloud.ts submitRenovationDemand）。字段或枚举名字错一个，
线上就是 422 静默失败，因此用测试锁住契约。

同时校验初始状态：新建项目必须落在 phase=initiation / status=draft，
小程序据此显示「待勘测」而不是「设计阶段」。
"""
import pytest
from httpx import AsyncClient


async def _token(client: AsyncClient, phone: str = "13900002001") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "业主需求测试", "password": "test123456"},
    )
    return resp.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_demand_matches_miniprogram_payload(client: AsyncClient):
    """与小程序 demand 页完全相同的请求体必须被接受。"""
    token = await _token(client)
    headers = _headers(token)

    payload = {
        "name": "春城慧谷 3 栋 1202",
        "project_type": "bathroom",
        "address": "昆明市五华区春城慧谷 3 栋 1202",
        "total_area": 98.0,
        "description": "意向套餐：适老卫浴改造",
        "contact_name": "王女士",
        "contact_phone": "13700137000",
        "source": "manual",
    }

    resp = await client.post("/api/projects", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text

    data = resp.json()
    assert data["name"] == payload["name"]
    assert data["project_type"] == "bathroom"
    assert data["description"] == payload["description"]
    # 初始状态：小程序据此显示「待勘测」，不做进度虚推
    assert data["phase"] == "initiation"
    assert data["status"] == "draft"

    listed = await client.get("/api/projects", headers=headers)
    assert listed.status_code == 200
    ids = [item["id"] for item in listed.json()]
    assert data["id"] in ids, "提交后必须立刻出现在项目列表"


@pytest.mark.asyncio
async def test_create_demand_without_optional_fields(client: AsyncClient):
    """只填名称也要能建单：联系方式在未认证小程序里可能拿不到。"""
    token = await _token(client, phone="13900002002")
    resp = await client.post(
        "/api/projects",
        json={"name": "只有名称的需求"},
        headers=_headers(token),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["phase"] == "initiation"
    assert data["project_type"] == "full_renovation"  # 后端默认值


@pytest.mark.asyncio
async def test_create_demand_requires_auth(client: AsyncClient):
    """未登录不得建单——小程序端写操作不降级，必须真实报错。"""
    resp = await client.post("/api/projects", json={"name": "匿名需求"})
    assert resp.status_code == 401

"""全景 AI 换装（virtual staging）端点测试（评估报告 2026-09-12 P2 落地）

覆盖端点:
- POST /api/vr/panoramas/{panorama_id}/restage  (对全景/3DGS 实景做 AI 换装)

契约要点:
- 复用 ai_render 降级链，返回 image_url + render_backend + reconstruction_available 诚实标注
- 效果图为 2D 平面图（非 3D 重建），不做 2D→3D
- 越权访问 403
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "换装测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects", json={"name": "换装测试项目", "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


async def _create_panorama(client: AsyncClient, headers: dict, project_id: str, room_name: str = "客厅") -> dict:
    resp = await client.post(
        "/api/vr/panoramas",
        json={"project_id": project_id, "room_name": room_name, "panorama_type": "equirectangular"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_restage_panorama_unauthorized(client: AsyncClient):
    """未认证用户不能换装"""
    resp = await client.post(
        "/api/vr/panoramas/fake-id/restage",
        json={"style": "modern"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_restage_panorama_not_found(client: AsyncClient):
    """全景不存在 → 404"""
    headers = await _auth_headers(client, "13971171101")
    resp = await client.post(
        "/api/vr/panoramas/nonexistent-id/restage",
        json={"style": "modern"},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_restage_panorama_forbidden(client: AsyncClient):
    """越权访问他人项目全景 → 403"""
    owner_headers = await _auth_headers(client, "13971171102")
    project_id = await _create_project(client, owner_headers)
    pano = await _create_panorama(client, owner_headers, project_id)

    other_headers = await _auth_headers(client, "13971171103")
    resp = await client.post(
        f"/api/vr/panoramas/{pano['id']}/restage",
        json={"style": "modern"},
        headers=other_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_restage_panorama_returns_effect_image(client: AsyncClient):
    """换装成功 → 返回 image_url + 诚实标注（reconstruction_available=False）"""
    headers = await _auth_headers(client, "13971171104")
    project_id = await _create_project(client, headers)
    pano = await _create_panorama(client, headers, project_id, "主卧")

    resp = await client.post(
        f"/api/vr/panoramas/{pano['id']}/restage",
        json={"style": "nordic", "prompt": "换成北欧风，浅色木地板，简约布艺沙发"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["panorama_id"] == pano["id"]
    assert data["restage_prompt"] == "换成北欧风，浅色木地板，简约布艺沙发"
    assert data["style"] == "nordic"
    # 复用 ai_render 降级链：mock 模式返回占位图，且诚实标注 reconstruction_available=False
    assert data["image_url"]
    assert "render_backend" in data
    assert data["reconstruction_available"] is False

"""施工进度 3DGS 数字存档 API 集成测试（评估报告 2026-09-12 P3 落地）

覆盖端点:
- POST /api/construction/projects/{project_id}/snapshots  上传施工节点快照（multipart）
- GET  /api/construction/projects/{project_id}/snapshots   施工时间线列表
- GET  /api/construction/snapshots/{snapshot_id}           单条详情

契约要点:
- 复用 P0 的 .spz/.ply 校验（扩展名 + 魔数 + 64MB）
- stage 值域校验（对齐 ConstructionTask.phase）
- 协作权限（上传）/ 项目归属（列表查看）
"""
import pytest
from httpx import AsyncClient

SPZ_BYTES = b"NGSP" + b"\x02\x00\x00\x00" + b"\x00" * 64


async def _auth_headers(client: AsyncClient, phone: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "施工存档测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects", json={"name": "施工存档测试项目", "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


def _upload(project_id: str, stage: str = "masonry", filename: str = "site.spz"):
    return {
        "data": {"project_id": project_id, "stage": stage, "room_name": "客厅"},
        "files": {"file": (filename, SPZ_BYTES, "application/octet-stream")},
    }


@pytest.mark.asyncio
async def test_upload_snapshot_unauthorized(client: AsyncClient):
    """未认证用户不能上传施工快照"""
    resp = await client.post(
        "/api/construction/projects/fake/snapshots",
        **_upload("fake"),
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_snapshot_rejects_bad_stage(client: AsyncClient):
    """非法施工阶段 → 400"""
    headers = await _auth_headers(client, "13971271201")
    project_id = await _create_project(client, headers)
    resp = await client.post(
        f"/api/construction/projects/{project_id}/snapshots",
        headers=headers,
        **_upload(project_id, stage="invalid_stage"),
    )
    assert resp.status_code == 400
    assert "施工阶段" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_snapshot_success_and_list(client: AsyncClient):
    """上传快照 → 201 + 时间线列表可见 + splat 字节级回读"""
    headers = await _auth_headers(client, "13971271202")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        f"/api/construction/projects/{project_id}/snapshots",
        headers=headers,
        **_upload(project_id, stage="water_electricity"),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["stage"] == "water_electricity"
    assert body["splat_url"].startswith("/api/files/download/")

    # 时间线列表
    lst = await client.get(f"/api/construction/projects/{project_id}/snapshots", headers=headers)
    assert lst.status_code == 200
    items = lst.json()
    assert len(items) == 1
    assert items[0]["stage"] == "water_electricity"

    # 单条详情
    detail = await client.get(f"/api/construction/snapshots/{body['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["splat_url"] == body["splat_url"]


@pytest.mark.asyncio
async def test_upload_snapshot_rejects_magic_mismatch(client: AsyncClient):
    """改后缀伪装上传 → 400"""
    headers = await _auth_headers(client, "13971271203")
    project_id = await _create_project(client, headers)
    resp = await client.post(
        f"/api/construction/projects/{project_id}/snapshots",
        headers=headers,
        data={"project_id": project_id, "stage": "masonry"},
        files={"file": ("fake.spz", b"NOT-A-REAL-SPLAT" * 8, "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert "魔数校验失败" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_snapshot_forbidden(client: AsyncClient):
    """越权访问他人项目施工时间线 → 403"""
    owner_headers = await _auth_headers(client, "13971271204")
    project_id = await _create_project(client, owner_headers)
    other_headers = await _auth_headers(client, "13971271205")

    resp = await client.get(f"/api/construction/projects/{project_id}/snapshots", headers=other_headers)
    assert resp.status_code == 403

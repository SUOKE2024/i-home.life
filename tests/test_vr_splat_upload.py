"""3DGS 实景资产上传 API 集成测试（评估报告 2026-09-12 P0 落地）

覆盖端点:
- POST /api/vr/panoramas/upload-splat  (上传 .spz/.ply 并登记为高斯全景)

契约要点:
- 扩展名 + 魔数 + 64MB 大小三重校验（防改后缀伪装上传）
- 协作权限（verify_project_collaborator_access：owner/designer/contractor/supplier）
- 落库 panorama_type=gaussian / content_source=actual / status=completed
- splat_url 指向 /api/files/download/{id}，字节级可回读（Spark 渲染数据源）
"""
import pytest
from httpx import AsyncClient

# 最小合法样本：后端仅校验魔数，不解析内容
SPZ_BYTES = b"NGSP" + b"\x02\x00\x00\x00" + b"\x00" * 64
PLY_BYTES = b"ply\nformat binary_little_endian 1.0\n" + b"\x00" * 64
# glTF 二进制（KHR_gaussian_splatting 扩展，P2 落地）：魔数 "glTF" + version 2
GLB_BYTES = b"glTF" + b"\x02\x00\x00\x00" + b"\x00" * 64


async def _auth_headers(client: AsyncClient, phone: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "3DGS 测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "3DGS 测试项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


def _upload(project_id: str, filename: str, content: bytes, room_name: str = "客厅"):
    return {
        "data": {"project_id": project_id, "room_name": room_name},
        "files": {"file": (filename, content, "application/octet-stream")},
    }


@pytest.mark.asyncio
async def test_upload_splat_unauthorized(client: AsyncClient):
    """未认证用户不能上传 3DGS 资产"""
    resp = await client.post(
        "/api/vr/panoramas/upload-splat",
        **_upload("fake-project", "room.spz", SPZ_BYTES),
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_spz_registers_gaussian_panorama(client: AsyncClient):
    """合法 SPZ 上传 → 201 + 高斯全景登记 + 字节级下载回读"""
    headers = await _auth_headers(client, "13970070001")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/vr/panoramas/upload-splat",
        headers=headers,
        **_upload(project_id, "living-room.spz", SPZ_BYTES),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["panorama_type"] == "gaussian"
    assert body["content_source"] == "actual"
    assert body["status"] == "completed"
    assert body["room_name"] == "客厅"
    assert body["splat_url"].startswith("/api/files/download/")
    assert body["file_size_mb"] == round(len(SPZ_BYTES) / (1024 * 1024), 2)

    # splat_url 字节级回读（Spark SplatMesh 直接消费该 URL）
    dl = await client.get(body["splat_url"], headers=headers)
    assert dl.status_code == 200
    assert dl.content == SPZ_BYTES


@pytest.mark.asyncio
async def test_upload_ply_accepted(client: AsyncClient):
    """合法 PLY 上传 → 201"""
    headers = await _auth_headers(client, "13970070002")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/vr/panoramas/upload-splat",
        headers=headers,
        **_upload(project_id, "scan.ply", PLY_BYTES, room_name="主卧"),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["panorama_type"] == "gaussian"


@pytest.mark.asyncio
async def test_upload_glb_accepted(client: AsyncClient):
    """合法 glTF 二进制（.glb，KHR_gaussian_splatting）上传 → 201（P2 落地）"""
    headers = await _auth_headers(client, "13970070009")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/vr/panoramas/upload-splat",
        headers=headers,
        **_upload(project_id, "scene.glb", GLB_BYTES, room_name="书房"),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["panorama_type"] == "gaussian"


@pytest.mark.asyncio
async def test_upload_rejects_bad_extension(client: AsyncClient):
    """非 .spz/.ply 扩展名 → 400"""
    headers = await _auth_headers(client, "13970070003")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/vr/panoramas/upload-splat",
        headers=headers,
        **_upload(project_id, "notes.txt", b"hello world"),
    )
    assert resp.status_code == 400
    assert "仅支持" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_rejects_magic_mismatch(client: AsyncClient):
    """改后缀伪装上传（内容与魔数不符）→ 400"""
    headers = await _auth_headers(client, "13970070004")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/vr/panoramas/upload-splat",
        headers=headers,
        **_upload(project_id, "fake.spz", b"NOT-A-REAL-SPLAT" * 8),
    )
    assert resp.status_code == 400
    assert "魔数校验失败" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_rejects_oversize(client: AsyncClient, monkeypatch):
    """超过大小限制 → 400（monkeypatch 调小限额避免大文件构造）"""
    from app.services import vr_panorama_service

    monkeypatch.setattr(vr_panorama_service, "MAX_SPLAT_FILE_BYTES", 16)
    headers = await _auth_headers(client, "13970070005")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/vr/panoramas/upload-splat",
        headers=headers,
        **_upload(project_id, "big.spz", SPZ_BYTES),
    )
    assert resp.status_code == 400
    assert "大小限制" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_forbidden_for_non_collaborator(client: AsyncClient):
    """非协作角色（他人项目的 homeowner）上传 → 403"""
    owner_headers = await _auth_headers(client, "13970070006")
    project_id = await _create_project(client, owner_headers)
    other_headers = await _auth_headers(client, "13970070007")

    resp = await client.post(
        "/api/vr/panoramas/upload-splat",
        headers=other_headers,
        **_upload(project_id, "room.spz", SPZ_BYTES),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_gaussian_panorama_listed_by_project(client: AsyncClient):
    """上传后项目全景列表可见（前端 VirtualTour 直接渲染入口）"""
    headers = await _auth_headers(client, "13970070008")
    project_id = await _create_project(client, headers)

    await client.post(
        "/api/vr/panoramas/upload-splat",
        headers=headers,
        **_upload(project_id, "room.spz", SPZ_BYTES),
    )
    resp = await client.get(f"/api/vr/panoramas/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["panorama_type"] == "gaussian"
    assert items[0]["splat_url"].startswith("/api/files/download/")

"""Tests for files API endpoints.

覆盖端点:
- POST /api/files/upload                 (上传文件)
- GET  /api/files/project/{project_id}   (列出项目文件)
- GET  /api/files/download/{attachment_id}  (下载文件)
- DELETE /api/files/{attachment_id}      (删除文件)
"""

import io

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict, name: str = "文件管理项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers=headers,
    )
    assert resp.status_code == 201, f"创建项目失败: {resp.json()}"
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_files_requires_auth(client: AsyncClient):
    """未认证上传文件返回 401"""
    resp = await client.post(
        "/api/files/upload",
        data={"project_id": "fake-id", "category": "photo"},
        files={"file": ("test.png", io.BytesIO(b"test"), "image/png")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_file(client: AsyncClient, auth_headers: dict):
    """上传文件到项目"""
    project_id = await _create_project(client, auth_headers)
    content = b"fake-image-bytes-for-test"
    resp = await client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"project_id": project_id, "category": "photo"},
        files={"file": ("test.png", io.BytesIO(content), "image/png")},
    )
    assert resp.status_code == 201, f"上传失败: {resp.json()}"
    data = resp.json()
    assert data["filename"] == "test.png"
    assert data["category"] == "photo"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_project_files(client: AsyncClient, auth_headers: dict):
    """列出项目文件"""
    project_id = await _create_project(client, auth_headers)
    # 先上传一个文件
    await client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"project_id": project_id, "category": "photo"},
        files={"file": ("test.png", io.BytesIO(b"content"), "image/png")},
    )
    resp = await client.get(f"/api/files/project/{project_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_download_file_not_found(client: AsyncClient, auth_headers: dict):
    """下载不存在的文件返回 404"""
    resp = await client.get("/api/files/download/nonexistent-file-id", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_file_not_found(client: AsyncClient, auth_headers: dict):
    """删除不存在的文件返回 404"""
    resp = await client.delete("/api/files/nonexistent-file-id", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_unsupported_file_type(client: AsyncClient, auth_headers: dict):
    """上传不支持的文件类型返回 400"""
    project_id = await _create_project(client, auth_headers)
    resp = await client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"project_id": project_id, "category": "other"},
        files={"file": ("test.exe", io.BytesIO(b"binary"), "application/x-msdownload")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_file_default_category(client: AsyncClient, auth_headers: dict):
    """上传文件不带 category 使用默认值"""
    project_id = await _create_project(client, auth_headers)
    resp = await client.post(
        "/api/files/upload",
        headers=auth_headers,
        data={"project_id": project_id},
        files={"file": ("doc.pdf", io.BytesIO(b"pdf-content"), "application/pdf")},
    )
    assert resp.status_code == 201, f"上传失败: {resp.json()}"
    data = resp.json()
    assert data["category"] == "other"  # 默认值

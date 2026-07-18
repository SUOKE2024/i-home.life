"""文件上传/下载 + 语音处理 端点测试

覆盖:
- /files/upload (multipart)
- /files/project/{id}
- /files/download/{id}
- /files/{id} DELETE
- /voice/process 各意图分支
"""

import io

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, phone: str = "13900004001") -> tuple[str, str]:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "文件测试用户", "password": "test123456"},
    )
    token = resp.json()["access_token"]
    proj = await client.post(
        "/api/projects",
        json={"name": "文件测试项目", "total_area": 80.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, proj.json()["id"]


# === 文件上传/下载/删除 ===


@pytest.mark.asyncio
async def test_upload_file(client: AsyncClient):
    token, proj_id = await _register_and_login(client, "13900004002")
    content = b"fake-image-bytes-for-test"
    resp = await client.post(
        "/api/files/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": proj_id, "category": "photo"},
        files={"file": ("test.png", io.BytesIO(content), "image/png")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["filename"] == "test.png"
    assert data["content_type"] == "image/png"
    assert data["file_size"] == len(content)
    assert data["category"] == "photo"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_files_by_project(client: AsyncClient):
    token, proj_id = await _register_and_login(client, "13900004003")
    # 上传 2 个文件
    for name in ("a.jpg", "b.jpg"):
        await client.post(
            "/api/files/upload",
            headers={"Authorization": f"Bearer {token}"},
            data={"project_id": proj_id, "category": "photo"},
            files={"file": (name, io.BytesIO(b"x"), "image/jpeg")},
        )
    resp = await client.get(
        f"/api/files/project/{proj_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    files = resp.json()
    assert len(files) >= 2


@pytest.mark.asyncio
async def test_list_files_with_category_filter(client: AsyncClient):
    token, proj_id = await _register_and_login(client, "13900004004")
    await client.post(
        "/api/files/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": proj_id, "category": "photo"},
        files={"file": ("p.jpg", io.BytesIO(b"x"), "image/jpeg")},
    )
    await client.post(
        "/api/files/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": proj_id, "category": "document"},
        files={"file": ("d.pdf", io.BytesIO(b"x"), "application/pdf")},
    )
    resp = await client.get(
        f"/api/files/project/{proj_id}?category=document",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    files = resp.json()
    assert len(files) == 1
    assert files[0]["category"] == "document"


@pytest.mark.asyncio
async def test_download_file(client: AsyncClient):
    token, proj_id = await _register_and_login(client, "13900004005")
    upload = await client.post(
        "/api/files/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": proj_id, "category": "doc"},
        files={"file": ("note.txt", io.BytesIO(b"hello-world"), "text/plain")},
    )
    file_id = upload.json()["id"]
    resp = await client.get(
        f"/api/files/download/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.content == b"hello-world"


@pytest.mark.asyncio
async def test_download_nonexistent_file(client: AsyncClient):
    token, _ = await _register_and_login(client, "13900004006")
    resp = await client.get(
        "/api/files/download/nonexistent-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_file(client: AsyncClient):
    token, proj_id = await _register_and_login(client, "13900004007")
    upload = await client.post(
        "/api/files/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": proj_id, "category": "temp"},
        files={"file": ("tmp.bin", io.BytesIO(b"data"), "application/octet-stream")},
    )
    file_id = upload.json()["id"]
    resp = await client.delete(
        f"/api/files/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
    # 二次下载应 404
    resp2 = await client.get(
        f"/api/files/download/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 404


# === 语音处理 ===


@pytest.mark.asyncio
async def test_voice_design_intent(client: AsyncClient):
    token, _ = await _register_and_login(client, "13900004008")
    resp = await client.post(
        "/api/voice/process",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "帮我设计一个三室两厅的户型方案"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "design"
    assert len(data["reply"]) > 5


@pytest.mark.asyncio
async def test_voice_budget_intent(client: AsyncClient):
    token, _ = await _register_and_login(client, "13900004009")
    resp = await client.post(
        "/api/voice/process",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "126平米的装修预算多少钱"},
    )
    assert resp.status_code == 200
    assert resp.json()["intent"] == "budget"


@pytest.mark.asyncio
async def test_voice_procurement_intent(client: AsyncClient):
    token, _ = await _register_and_login(client, "13900004010")
    resp = await client.post(
        "/api/voice/process",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "我要采购瓷砖和地板材料"},
    )
    assert resp.status_code == 200
    assert resp.json()["intent"] == "procurement"


@pytest.mark.asyncio
async def test_voice_construction_intent(client: AsyncClient):
    token, _ = await _register_and_login(client, "13900004011")
    resp = await client.post(
        "/api/voice/process",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "施工进度怎么样了,什么时候验收"},
    )
    assert resp.status_code == 200
    assert resp.json()["intent"] == "construction"


@pytest.mark.asyncio
async def test_voice_general_intent(client: AsyncClient):
    token, _ = await _register_and_login(client, "13900004012")
    resp = await client.post(
        "/api/voice/process",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "你好,今天天气怎么样"},
    )
    assert resp.status_code == 200
    assert resp.json()["intent"] == "general"


@pytest.mark.asyncio
async def test_voice_design_action_add_room(client: AsyncClient):
    """语音指令包含添加房间时应返回 add_room action"""
    token, _ = await _register_and_login(client, "13900004013")
    resp = await client.post(
        "/api/voice/process",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "加一个 3×4 的书房"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "design"
    assert len(data["actions"]) >= 1
    assert data["actions"][0]["action"] == "add_room"
    assert data["actions"][0]["name"] == "书房"


@pytest.mark.asyncio
async def test_voice_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/voice/process",
        json={"text": "测试"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_voice_empty_text_rejected(client: AsyncClient):
    token, _ = await _register_and_login(client, "13900004014")
    resp = await client.post(
        "/api/voice/process",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": ""},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_voice_process_no_project_id_ok(client: AsyncClient):
    """不带 project_id 调用 /voice/process 应正常处理(不触发归属检查)"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900004015", "name": "Voice无项目", "password": "test123456"},
    )
    token = resp.json()["access_token"]
    resp = await client.post(
        "/api/voice/process",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "你好"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_voice_process_project_not_owned(client: AsyncClient):
    """传入他人 project_id 调用 /voice/process 应返回 403(防越权)"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900004016", "name": "OwnerA", "password": "test123456"},
    )
    token_a = resp.json()["access_token"]
    proj_resp = await client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "A项目", "address": "地址A"},
    )
    project_id_a = proj_resp.json()["id"]

    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900004017", "name": "OwnerB", "password": "test123456"},
    )
    token_b = resp.json()["access_token"]

    resp = await client.post(
        "/api/voice/process",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"text": "你好", "project_id": project_id_a},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_voice_process_project_not_found(client: AsyncClient):
    """传入不存在的 project_id 调用 /voice/process 应返回 404"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": "13900004018", "name": "NotFound", "password": "test123456"},
    )
    token = resp.json()["access_token"]
    resp = await client.post(
        "/api/voice/process",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": "你好", "project_id": "nonexistent-project-id"},
    )
    assert resp.status_code == 404

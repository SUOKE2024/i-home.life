"""3DGS 云端重建 API 集成测试（评估报告 2026-09-12 P1 落地）

覆盖端点:
- POST /api/vr/reconstructions  (提交重建任务)
- GET  /api/vr/reconstructions/{job_id}  (查询状态)
- GET  /api/vr/reconstructions/project/{project_id}  (列表)

契约要点:
- 未配置 gaussian_recon_enabled/backend_url 时 503（诚实降级，不自建 GPU）
- 配置后提交创建 queued→processing 任务并回填 backend_job_id
- 后端 completed → 状态轮询刷新 splat_url
- 源数据类型校验（photos/video/ar_scan）
"""
import pytest
from httpx import AsyncClient

from app.config import get_settings


async def _auth_headers(client: AsyncClient, phone: str) -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "重建测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects", json={"name": "重建测试项目", "total_area": 100.0}, headers=headers,
    )
    return resp.json()["id"]


def _enable_backend(monkeypatch, url: str = "http://recon-backend.test"):
    monkeypatch.setattr(get_settings(), "gaussian_recon_enabled", True)
    monkeypatch.setattr(get_settings(), "gaussian_recon_backend_url", url)


@pytest.mark.asyncio
async def test_reconstruction_unconfigured_returns_503(client: AsyncClient, monkeypatch):
    """未配置重建后端 → 503 诚实报错（平台不自建 GPU）"""
    monkeypatch.setattr(get_settings(), "gaussian_recon_enabled", False)
    monkeypatch.setattr(get_settings(), "gaussian_recon_backend_url", "")
    headers = await _auth_headers(client, "13971071001")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/vr/reconstructions",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "source_type": "photos",
            "source_files": ["https://cdn.example/a.jpg"],
        },
        headers=headers,
    )
    assert resp.status_code == 503
    assert "云端重建未配置" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reconstruction_unauthorized(client: AsyncClient):
    """未认证用户不能提交重建任务"""
    resp = await client.post(
        "/api/vr/reconstructions",
        json={"project_id": "fake", "room_name": "客厅", "source_type": "photos"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reconstruction_submit_success(client: AsyncClient, monkeypatch):
    """配置后端后提交 → 201 + backend_job_id 回填 + processing 状态"""
    _enable_backend(monkeypatch)

    import httpx as _httpx

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"job_id": "backend-job-123"}

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return _FakeResponse()

    monkeypatch.setattr(_httpx, "AsyncClient", _FakeClient)

    headers = await _auth_headers(client, "13971071002")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/vr/reconstructions",
        json={
            "project_id": project_id,
            "room_name": "客厅",
            "source_type": "photos",
            "source_files": ["https://cdn.example/a.jpg", "https://cdn.example/b.jpg"],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["backend_job_id"] == "backend-job-123"
    assert body["status"] == "processing"
    assert body["source_files"] == ["https://cdn.example/a.jpg", "https://cdn.example/b.jpg"]


@pytest.mark.asyncio
async def test_reconstruction_rejects_bad_source_type(client: AsyncClient, monkeypatch):
    """非法源数据类型 → 400"""
    _enable_backend(monkeypatch)
    headers = await _auth_headers(client, "13971071003")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/vr/reconstructions",
        json={"project_id": project_id, "room_name": "客厅", "source_type": "pdf"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "源数据类型" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reconstruction_poll_completed(client: AsyncClient, monkeypatch):
    """后端 completed → 查询刷新 splat_url"""
    _enable_backend(monkeypatch)

    import httpx as _httpx

    class _SubmitResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"job_id": "backend-job-456"}

    class _PollResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"status": "completed", "splat_url": "/api/files/download/abc"}

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return _SubmitResponse()

        async def get(self, *a, **k):
            return _PollResponse()

    monkeypatch.setattr(_httpx, "AsyncClient", _FakeClient)

    headers = await _auth_headers(client, "13971071004")
    project_id = await _create_project(client, headers)
    submit = await client.post(
        "/api/vr/reconstructions",
        json={"project_id": project_id, "room_name": "主卧", "source_type": "video",
              "source_files": ["https://cdn.example/scan.mp4"]},
        headers=headers,
    )
    job_id = submit.json()["id"]

    resp = await client.get(f"/api/vr/reconstructions/{job_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["splat_url"] == "/api/files/download/abc"


@pytest.mark.asyncio
async def test_reconstruction_list_by_project(client: AsyncClient, monkeypatch):
    """按项目列重建任务"""
    _enable_backend(monkeypatch)
    headers = await _auth_headers(client, "13971071005")
    project_id = await _create_project(client, headers)

    # 经 API 提交（后端已 mock 可用）
    import httpx as _httpx

    class _R:
        def raise_for_status(self):
            pass

        def json(self):
            return {"job_id": "backend-job-789"}

    class _C:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return _R()

        async def get(self, *a, **k):
            return _R()

    monkeypatch.setattr(_httpx, "AsyncClient", _C)

    await client.post(
        "/api/vr/reconstructions",
        json={"project_id": project_id, "room_name": "客厅", "source_type": "photos",
              "source_files": ["https://cdn.example/a.jpg"]},
        headers=headers,
    )
    resp = await client.get(f"/api/vr/reconstructions/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["room_name"] == "客厅"

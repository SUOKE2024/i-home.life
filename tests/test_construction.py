"""施工管理 API 测试（施工任务 / 里程碑 / 进度）

覆盖端点:
- POST /api/construction/tasks
- GET  /api/construction/tasks/{project_id}
- PATCH /api/construction/tasks/{task_id}/status
"""
import json
import uuid
import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": f"施工测试项目-{uuid.uuid4().hex[:6]}", "total_area": 120.0},
        headers=headers,
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_tasks_unauthorized(client: AsyncClient):
    """未认证用户无法获取施工任务"""
    resp = await client.get("/api/construction/tasks/fake-id")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_task(auth_headers: dict, client: AsyncClient):
    """创建施工任务"""
    project_id = await _create_project(client, auth_headers)
    resp = await client.post(
        "/api/construction/tasks",
        json={
            "project_id": project_id,
            "name": "水电改造",
            "phase": "water_electricity",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "水电改造"


@pytest.mark.asyncio
async def test_list_tasks(auth_headers: dict, client: AsyncClient):
    """列出项目施工任务"""
    project_id = await _create_project(client, auth_headers)
    await client.post(
        "/api/construction/tasks",
        json={"project_id": project_id, "name": "拆改", "phase": "demolition"},
        headers=auth_headers,
    )
    resp = await client.get(f"/api/construction/tasks/{project_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_update_task_status(auth_headers: dict, client: AsyncClient):
    """更新任务状态"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/construction/tasks",
        json={"project_id": project_id, "name": "木工", "phase": "carpentry"},
        headers=auth_headers,
    )
    task_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/construction/tasks/{task_id}/status?status_val=in_progress",
        headers=auth_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_task_not_found_on_fake_project(auth_headers: dict, client: AsyncClient):
    """查询不存在项目返回 404"""
    resp = await client.get("/api/construction/tasks/nonexistent-proj-123", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_user_task_access(auth_headers: dict, client: AsyncClient):
    """其他用户无法操作非自己项目的施工任务"""
    project_id = await _create_project(client, auth_headers)
    create_resp = await client.post(
        "/api/construction/tasks",
        json={"project_id": project_id, "name": "油漆", "phase": "painting"},
        headers=auth_headers,
    )
    task_id = create_resp.json()["id"]
    reg = await client.post(
        "/api/auth/register",
        json={"phone": f"1391002{uuid.uuid4().int % 10000:04d}", "name": "他人", "password": "test123456"},
    )
    other_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    resp = await client.patch(
        f"/api/construction/tasks/{task_id}/status?status_val=completed",
        headers=other_headers,
    )
    assert resp.status_code in (403, 404)


# ── 智能体诚实降级标注（P1-5）──


def test_analyze_inspection_images_mock_annotation():
    """施工图像质检必须携带 mock 标注，禁止伪装真实 CV 能力"""
    from app.agents.construction import ConstructionAgent

    agent = ConstructionAgent()
    result = agent.analyze_inspection_images(
        {
            "phase": "masonry",
            "images": [{"url": "http://example.com/1.jpg", "type": "tile_surface"}],
            "design_reference": "http://example.com/design.pdf",
            "expected_dimensions": {"tile_gap": "2mm", "flatness": "≤3mm"},
        }
    )
    assert result["source"] == "mock"
    assert result["engine"] == "mock_cv_engine"
    assert result["is_placeholder"] is True
    assert result["total_checks"] > 0


def test_detect_quality_issues_mock_annotation():
    """施工质量问题检测必须携带 mock 标注"""
    from app.agents.construction import detect_quality_issues

    result = detect_quality_issues(
        project_id="P001",
        phase="masonry",
        inspection_results=[
            {
                "check_item": "瓷砖空鼓率",
                "standard": "单砖空鼓 < 5%",
                "ai_result": "fail",
                "confidence": 0.9,
                "issues": ["瓷砖空鼓超标"],
            }
        ],
    )
    assert result["source"] == "mock"
    assert result["engine"] == "mock_rule_engine"
    assert result["is_placeholder"] is True
    assert len(result["detected_issues"]) >= 1


# ── F48 AI 工地监理（闭水试验监测 + 安全违规抓拍） ──


@pytest.mark.asyncio
async def test_supervision_patrol_degrade_to_rule(
    auth_headers: dict, client: AsyncClient, monkeypatch
):
    """视觉 key 不可用时诚实降级 rule_mock，绝不伪装真实视觉"""
    from app.services import supervision_patrol_service as sp

    def _boom(*a, **k):
        raise RuntimeError("未配置视觉模型 key")

    monkeypatch.setattr(sp, "_call_vision_llm", _boom)
    project_id = await _create_project(client, auth_headers)
    resp = await client.post(
        "/api/construction/supervision/patrol",
        json={
            "project_id": project_id,
            "photos": [
                {"url": "data:image/png;base64,iVBORw0KGgo=", "scene_type": "waterproofing"},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source"] == "rule_mock"
    assert data["photo_count"] == 1
    assert data["findings"][0]["source"] == "rule_mock"
    assert "诚实降级" in data["note"] or "未配置视觉模型" in data["note"]


@pytest.mark.asyncio
async def test_supervision_patrol_ai_vision(
    auth_headers: dict, client: AsyncClient, monkeypatch
):
    """视觉模型可用时走真实 AI 视觉（source=ai_vision），检出渗漏为 critical"""
    from app.services import supervision_patrol_service as sp

    def _fake_vision(prompt, image_bytes, mime):
        return json.dumps({
            "waterproofing": {
                "leak_detected": True,
                "water_level_ok": False,
                "confidence": 0.95,
                "notes": "检测到渗水印",
            },
            "issues": [
                {"type": "leak", "description": "局部渗水", "severity": "critical", "suggestion": "重做防水"}
            ],
        })

    monkeypatch.setattr(sp, "_call_vision_llm", _fake_vision)
    project_id = await _create_project(client, auth_headers)
    resp = await client.post(
        "/api/construction/supervision/patrol",
        json={
            "project_id": project_id,
            "photos": [
                {"url": "data:image/png;base64,iVBORw0KGgo=", "scene_type": "waterproofing"},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source"] == "ai_vision"
    assert data["summary"]["critical"] >= 1
    assert data["findings"][0]["issues"][0]["source"] == "ai_vision"

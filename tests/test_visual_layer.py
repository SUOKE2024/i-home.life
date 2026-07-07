"""视觉表现层测试 — VR 全景 + AI 图生图

覆盖:
- VR 全景图: CRUD + 渲染 + 热点 + 场景
- AI 图生图: CRUD + 处理 + 预设 + 批量渲染 + 提示词校验 + 成本计算
"""

import pytest
from httpx import AsyncClient

# 导入模型以注册到 Base.metadata (使 conftest 的 setup_db 能创建表)
from app.models.vr_panorama import VRPanorama, VRScene
from app.models.ai_image import AIImageJob, AIImagePreset

# 注册路由到 app (主代理集成前,测试需手动挂载)
# 注意: app.main 在末尾挂载了 StaticFiles 到 "/" 路径,会拦截后续添加的路由,
# 因此需要先移除静态挂载,添加 API 路由后再重新挂载到末尾。
from app.main import app
from app.api import vr_panorama as vr_api
from app.api import ai_image as ai_api

_existing_paths = {getattr(r, "path", "") for r in app.routes}
if "/api/vr/panoramas" not in _existing_paths or "/api/ai-image/jobs" not in _existing_paths:
    # 收集并移除静态文件挂载 (name="web")
    _static_mounts = []
    _other_routes = []
    for _r in app.routes:
        if getattr(_r, "name", "") == "web":
            _static_mounts.append(_r)
        else:
            _other_routes.append(_r)
    app.router.routes = _other_routes
    # 添加 API 路由
    if "/api/vr/panoramas" not in _existing_paths:
        app.include_router(vr_api.router, prefix="/api")
    if "/api/ai-image/jobs" not in _existing_paths:
        app.include_router(ai_api.router, prefix="/api")
    # 重新挂载静态文件到末尾
    for _m in _static_mounts:
        app.router.routes.append(_m)


# ════════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════════


async def _register_and_login(client: AsyncClient, phone: str = "13900009901") -> tuple[str, dict]:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "视觉层测试用户", "password": "test123456"},
    )
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "视觉层测试项目") -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 120.0},
        headers=headers,
    )
    return resp.json()["id"]


async def _create_panorama(
    client: AsyncClient, headers: dict, project_id: str, room_name: str = "客厅"
) -> str:
    resp = await client.post(
        "/api/vr/panoramas",
        json={
            "project_id": project_id,
            "room_name": room_name,
            "panorama_type": "equirectangular",
            "resolution": "4K",
            "fov": 360.0,
            "initial_view": {"heading": 0, "pitch": 0, "fov": 75},
            "render_quality": "standard",
        },
        headers=headers,
    )
    return resp.json()["id"]


async def _create_preset(
    client: AsyncClient, headers: dict, name: str = "现代简约"
) -> str:
    # 不同风格对应不同 prompt (确保批量渲染时 prompt 唯一)
    prompt_map = {
        "现代简约": "modern minimalist interior, bright, clean lines, neutral colors",
        "北欧风": "Scandinavian interior, white, wood, plants, cozy",
        "新中式": "Chinese modern interior, wood, ink painting, elegant",
        "法式": "French interior, elegant, vintage, romantic",
        "工业风": "Industrial interior, concrete, metal, raw",
        "日式": "Japanese interior, tatami, wood, zen, minimal",
        "美式": "American interior, classic, comfortable, warm",
    }
    resp = await client.post(
        "/api/ai-image/presets",
        json={
            "name": name,
            "category": "style",
            "prompt_template": prompt_map.get(name, f"{name} style interior design"),
            "negative_prompt_template": "cluttered, dark, messy",
            "default_params": {
                "model_name": "stable-diffusion-xl",
                "controlnet_type": "canny",
                "guidance_scale": 7.5,
                "num_inference_steps": 30,
            },
            "is_public": True,
        },
        headers=headers,
    )
    return resp.json()["id"]


# ════════════════════════════════════════════════════════════
# VR 全景图 CRUD
# ════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_vr_create_panorama(client: AsyncClient):
    """创建全景图"""
    token, headers = await _register_and_login(client, "13900009910")
    project_id = await _create_project(client, headers, "VR 创建测试")

    resp = await client.post(
        "/api/vr/panoramas",
        json={
            "project_id": project_id,
            "room_name": "主卧",
            "panorama_type": "equirectangular",
            "resolution": "8K",
            "fov": 360.0,
            "initial_view": {"heading": 90, "pitch": 0, "fov": 80},
            "render_quality": "high",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["room_name"] == "主卧"
    assert data["panorama_type"] == "equirectangular"
    assert data["resolution"] == "8K"
    assert data["render_quality"] == "high"
    assert data["status"] == "queued"
    assert data["fov"] == 360.0


@pytest.mark.asyncio
async def test_vr_list_panoramas(client: AsyncClient):
    """列出项目下的全景图"""
    token, headers = await _register_and_login(client, "13900009920")
    project_id = await _create_project(client, headers, "VR 列表测试")

    await _create_panorama(client, headers, project_id, "客厅")
    await _create_panorama(client, headers, project_id, "主卧")

    resp = await client.get(f"/api/vr/panoramas/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_vr_get_panorama(client: AsyncClient):
    """获取单个全景图"""
    token, headers = await _register_and_login(client, "13900009930")
    project_id = await _create_project(client, headers, "VR 获取测试")
    pano_id = await _create_panorama(client, headers, project_id, "书房")

    resp = await client.get(f"/api/vr/panoramas/{pano_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["room_name"] == "书房"


@pytest.mark.asyncio
async def test_vr_get_panorama_not_found(client: AsyncClient):
    """获取不存在的全景图 → 404"""
    token, headers = await _register_and_login(client, "13900009931")
    resp = await client.get("/api/vr/panoramas/nonexistent-id", headers=headers)
    assert resp.status_code == 404


# ════════════════════════════════════════════════════════════
# VR 全景图渲染
# ════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_vr_render_panorama(client: AsyncClient):
    """触发渲染 — 状态从 queued → rendering → completed"""
    token, headers = await _register_and_login(client, "13900009940")
    project_id = await _create_project(client, headers, "VR 渲染测试")
    pano_id = await _create_panorama(client, headers, project_id, "客厅")

    resp = await client.post(
        f"/api/vr/panoramas/{pano_id}/render",
        json={
            "floorplan_data": {"rooms": [{"name": "客厅", "width": 5.2, "length": 4.5}]},
            "quality": "standard",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["image_url"] is not None
    assert data["thumbnail_url"] is not None
    assert data["file_size_mb"] > 0
    assert data["render_duration_sec"] > 0
    assert data["completed_at"] is not None


@pytest.mark.asyncio
async def test_vr_render_quality_profiles(client: AsyncClient):
    """不同渲染质量应产生不同的文件大小和耗时"""
    token, headers = await _register_and_login(client, "13900009941")
    project_id = await _create_project(client, headers, "VR 质量测试")

    # draft
    pano1 = await _create_panorama(client, headers, project_id, "客厅")
    resp1 = await client.post(
        f"/api/vr/panoramas/{pano1}/render",
        json={"quality": "draft"},
        headers=headers,
    )
    assert resp1.status_code == 200

    # high
    pano2 = await _create_panorama(client, headers, project_id, "主卧")
    resp2 = await client.post(
        f"/api/vr/panoramas/{pano2}/render",
        json={"quality": "high"},
        headers=headers,
    )
    assert resp2.status_code == 200

    d1, d2 = resp1.json(), resp2.json()
    assert d2["file_size_mb"] > d1["file_size_mb"]
    assert d2["render_duration_sec"] > d1["render_duration_sec"]


# ════════════════════════════════════════════════════════════
# VR 热点管理
# ════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_vr_add_and_list_hotspots(client: AsyncClient):
    """添加热点 + 列出热点"""
    token, headers = await _register_and_login(client, "13900009950")
    project_id = await _create_project(client, headers, "VR 热点测试")
    pano_id = await _create_panorama(client, headers, project_id, "客厅")

    # 添加热点 1 (跳转其他房间)
    resp = await client.post(
        f"/api/vr/panoramas/{pano_id}/hotspots",
        json={
            "type": "panorama",
            "position": {"yaw": 60, "pitch": 0},
            "label": "前往主卧",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["hotspots"] is not None

    # 添加热点 2 (信息热点)
    resp = await client.post(
        f"/api/vr/panoramas/{pano_id}/hotspots",
        json={
            "type": "info",
            "position": {"yaw": -30, "pitch": 10},
            "label": "电视墙",
        },
        headers=headers,
    )
    assert resp.status_code == 200

    # 列出热点
    resp = await client.get(f"/api/vr/panoramas/{pano_id}/hotspots", headers=headers)
    assert resp.status_code == 200
    hotspots = resp.json()
    assert len(hotspots) == 2
    assert hotspots[0]["label"] == "前往主卧"
    assert hotspots[1]["label"] == "电视墙"
    # 每个热点应有自动分配的 id
    assert "id" in hotspots[0]
    assert "id" in hotspots[1]


@pytest.mark.asyncio
async def test_vr_delete_hotspot_by_index(client: AsyncClient):
    """通过索引删除热点"""
    token, headers = await _register_and_login(client, "13900009951")
    project_id = await _create_project(client, headers, "VR 删热点测试")
    pano_id = await _create_panorama(client, headers, project_id, "客厅")

    # 添加 2 个热点
    await client.post(
        f"/api/vr/panoramas/{pano_id}/hotspots",
        json={"type": "panorama", "position": {"yaw": 0, "pitch": 0}, "label": "热点1"},
        headers=headers,
    )
    await client.post(
        f"/api/vr/panoramas/{pano_id}/hotspots",
        json={"type": "info", "position": {"yaw": 90, "pitch": 0}, "label": "热点2"},
        headers=headers,
    )

    # 删除第 0 个
    resp = await client.delete(
        f"/api/vr/hotspots/{pano_id}/0", headers=headers
    )
    assert resp.status_code == 204

    # 验证只剩 1 个
    resp = await client.get(f"/api/vr/panoramas/{pano_id}/hotspots", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["label"] == "热点2"


@pytest.mark.asyncio
async def test_vr_delete_hotspot_invalid_index(client: AsyncClient):
    """无效索引 → 404"""
    token, headers = await _register_and_login(client, "13900009952")
    project_id = await _create_project(client, headers, "VR 无效索引测试")
    pano_id = await _create_panorama(client, headers, project_id, "客厅")

    resp = await client.delete(f"/api/vr/hotspots/{pano_id}/99", headers=headers)
    assert resp.status_code == 404


# ════════════════════════════════════════════════════════════
# VR 场景
# ════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_vr_create_scene(client: AsyncClient):
    """创建 VR 场景 (多个全景图组合)"""
    token, headers = await _register_and_login(client, "13900009960")
    project_id = await _create_project(client, headers, "VR 场景测试")

    pano1 = await _create_panorama(client, headers, project_id, "客厅")
    pano2 = await _create_panorama(client, headers, project_id, "主卧")
    pano3 = await _create_panorama(client, headers, project_id, "厨房")

    resp = await client.post(
        "/api/vr/scenes",
        json={
            "project_id": project_id,
            "name": "全屋漫游",
            "panorama_ids": [pano1, pano2, pano3],
            "transition_type": "fade",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "全屋漫游"
    assert data["transition_type"] == "fade"
    assert data["default_panorama_id"] == pano1  # 默认取第一个


@pytest.mark.asyncio
async def test_vr_list_and_get_scene(client: AsyncClient):
    """列出 + 获取场景"""
    token, headers = await _register_and_login(client, "13900009961")
    project_id = await _create_project(client, headers, "VR 场景列表测试")
    pano1 = await _create_panorama(client, headers, project_id, "客厅")

    resp = await client.post(
        "/api/vr/scenes",
        json={
            "project_id": project_id,
            "name": "客厅漫游",
            "panorama_ids": [pano1],
        },
        headers=headers,
    )
    scene_id = resp.json()["id"]

    # 列出
    resp = await client.get(f"/api/vr/scenes/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 获取
    resp = await client.get(f"/api/vr/scenes/{scene_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "客厅漫游"


@pytest.mark.asyncio
async def test_vr_update_scene(client: AsyncClient):
    """更新场景 (添加/删除 panorama)"""
    token, headers = await _register_and_login(client, "13900009962")
    project_id = await _create_project(client, headers, "VR 场景更新测试")
    pano1 = await _create_panorama(client, headers, project_id, "客厅")
    pano2 = await _create_panorama(client, headers, project_id, "主卧")

    resp = await client.post(
        "/api/vr/scenes",
        json={
            "project_id": project_id,
            "name": "原始场景",
            "panorama_ids": [pano1],
        },
        headers=headers,
    )
    scene_id = resp.json()["id"]

    # 更新: 添加 pano2, 修改名称和过渡
    resp = await client.patch(
        f"/api/vr/scenes/{scene_id}",
        json={
            "name": "更新后场景",
            "panorama_ids": [pano1, pano2],
            "transition_type": "warp",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "更新后场景"
    assert data["transition_type"] == "warp"


@pytest.mark.asyncio
async def test_vr_delete_scene(client: AsyncClient):
    """删除场景"""
    token, headers = await _register_and_login(client, "13900009963")
    project_id = await _create_project(client, headers, "VR 场景删除测试")
    pano1 = await _create_panorama(client, headers, project_id, "客厅")

    resp = await client.post(
        "/api/vr/scenes",
        json={
            "project_id": project_id,
            "name": "待删除场景",
            "panorama_ids": [pano1],
        },
        headers=headers,
    )
    scene_id = resp.json()["id"]

    resp = await client.delete(f"/api/vr/scenes/{scene_id}", headers=headers)
    assert resp.status_code == 204

    # 验证已删除
    resp = await client.get(f"/api/vr/scenes/{scene_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_vr_delete_panorama(client: AsyncClient):
    """删除全景图"""
    token, headers = await _register_and_login(client, "13900009964")
    project_id = await _create_project(client, headers, "VR 全景删除测试")
    pano_id = await _create_panorama(client, headers, project_id, "客厅")

    resp = await client.delete(f"/api/vr/panoramas/{pano_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/vr/panoramas/{pano_id}", headers=headers)
    assert resp.status_code == 404


# ════════════════════════════════════════════════════════════
# VR 场景时长估算 (单元测试)
# ════════════════════════════════════════════════════════════


def test_compute_scene_duration_basic():
    """单元测试: 场景时长估算"""
    from app.services.vr_panorama_service import compute_scene_duration, VRScene

    # 3 个全景,fade 过渡
    scene = VRScene(
        id="s1",
        project_id="p1",
        name="测试场景",
        panorama_ids='["a", "b", "c"]',
        transition_type="fade",
    )
    duration = compute_scene_duration(scene)
    # 3 × (30 + 2×5) + 1.5 × 2 = 120 + 3 = 123
    assert duration == 123.0


def test_compute_scene_duration_empty():
    """单元测试: 空场景时长为 0"""
    from app.services.vr_panorama_service import compute_scene_duration, VRScene

    scene = VRScene(id="s2", project_id="p1", name="空场景")
    assert compute_scene_duration(scene) == 0.0


def test_compute_scene_duration_warp():
    """单元测试: warp 过渡比 fade 快"""
    from app.services.vr_panorama_service import compute_scene_duration, VRScene

    scene_fade = VRScene(
        id="s3", project_id="p1", name="fade",
        panorama_ids='["a", "b"]', transition_type="fade",
    )
    scene_warp = VRScene(
        id="s4", project_id="p1", name="warp",
        panorama_ids='["a", "b"]', transition_type="warp",
    )
    assert compute_scene_duration(scene_warp) < compute_scene_duration(scene_fade)


def test_generate_equirectangular():
    """单元测试: 等距柱状全景图生成"""
    from app.services.vr_panorama_service import generate_equirectangular

    result = generate_equirectangular({
        "rooms": [{"name": "客厅", "width": 5.2, "length": 4.5}]
    })
    assert "image_url" in result
    assert "thumbnail_url" in result
    assert result["resolution_width"] == 4096
    assert result["resolution_height"] == 2048
    assert result["render_metadata"]["projection"] == "equirectangular"


# ════════════════════════════════════════════════════════════
# AI 图生图 CRUD
# ════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ai_create_job(client: AsyncClient):
    """创建图生图任务"""
    token, headers = await _register_and_login(client, "13900009970")
    project_id = await _create_project(client, headers, "AI 任务测试")

    resp = await client.post(
        "/api/ai-image/jobs",
        json={
            "project_id": project_id,
            "job_type": "style_transfer",
            "input_image_url": "https://example.com/input.jpg",
            "prompt": "modern minimalist living room, bright, clean",
            "negative_prompt": "dark, cluttered",
            "model_name": "stable-diffusion-xl",
            "controlnet_type": "canny",
            "controlnet_strength": 0.6,
            "guidance_scale": 7.5,
            "num_inference_steps": 30,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["job_type"] == "style_transfer"
    assert data["status"] == "queued"
    assert data["prompt"] == "modern minimalist living room, bright, clean"
    assert data["model_name"] == "stable-diffusion-xl"
    assert data["controlnet_type"] == "canny"
    assert data["progress_percent"] == 0.0


@pytest.mark.asyncio
async def test_ai_create_job_with_sensitive_prompt(client: AsyncClient):
    """敏感词提示词 → 400"""
    token, headers = await _register_and_login(client, "13900009971")
    project_id = await _create_project(client, headers, "AI 敏感词测试")

    resp = await client.post(
        "/api/ai-image/jobs",
        json={
            "project_id": project_id,
            "prompt": "包含暴力的内容",
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert "敏感词" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_ai_list_jobs(client: AsyncClient):
    """列出任务"""
    token, headers = await _register_and_login(client, "13900009972")
    project_id = await _create_project(client, headers, "AI 列表测试")

    for i in range(3):
        await client.post(
            "/api/ai-image/jobs",
            json={
                "project_id": project_id,
                "prompt": f"test prompt {i}",
            },
            headers=headers,
        )

    resp = await client.get(f"/api/ai-image/jobs/project/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_ai_get_job(client: AsyncClient):
    """获取单个任务"""
    token, headers = await _register_and_login(client, "13900009973")
    project_id = await _create_project(client, headers, "AI 获取测试")

    resp = await client.post(
        "/api/ai-image/jobs",
        json={"project_id": project_id, "prompt": "test"},
        headers=headers,
    )
    job_id = resp.json()["id"]

    resp = await client.get(f"/api/ai-image/jobs/{job_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id


# ════════════════════════════════════════════════════════════
# AI 图生图处理
# ════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ai_process_job(client: AsyncClient):
    """触发处理 — 状态从 queued → processing → completed"""
    token, headers = await _register_and_login(client, "13900009980")
    project_id = await _create_project(client, headers, "AI 处理测试")

    resp = await client.post(
        "/api/ai-image/jobs",
        json={
            "project_id": project_id,
            "prompt": "modern living room",
            "num_inference_steps": 30,
        },
        headers=headers,
    )
    job_id = resp.json()["id"]

    resp = await client.post(f"/api/ai-image/jobs/{job_id}/process", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["output_image_url"] is not None
    assert data["progress_percent"] == 100.0
    assert data["render_duration_sec"] > 0
    assert data["completed_at"] is not None


@pytest.mark.asyncio
async def test_ai_get_job_status(client: AsyncClient):
    """查询任务状态"""
    token, headers = await _register_and_login(client, "13900009981")
    project_id = await _create_project(client, headers, "AI 状态测试")

    resp = await client.post(
        "/api/ai-image/jobs",
        json={
            "project_id": project_id,
            "prompt": "test",
            "num_inference_steps": 50,
        },
        headers=headers,
    )
    job_id = resp.json()["id"]

    # 处理前
    resp = await client.get(f"/api/ai-image/jobs/{job_id}/status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["cost_yuan"] == 0.5  # 50 × 0.01

    # 处理后
    await client.post(f"/api/ai-image/jobs/{job_id}/process", headers=headers)
    resp = await client.get(f"/api/ai-image/jobs/{job_id}/status", headers=headers)
    data = resp.json()
    assert data["status"] == "completed"
    assert data["output_image_url"] is not None


@pytest.mark.asyncio
async def test_ai_delete_job(client: AsyncClient):
    """删除任务"""
    token, headers = await _register_and_login(client, "13900009982")
    project_id = await _create_project(client, headers, "AI 删除测试")

    resp = await client.post(
        "/api/ai-image/jobs",
        json={"project_id": project_id, "prompt": "test"},
        headers=headers,
    )
    job_id = resp.json()["id"]

    resp = await client.delete(f"/api/ai-image/jobs/{job_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/ai-image/jobs/{job_id}", headers=headers)
    assert resp.status_code == 404


# ════════════════════════════════════════════════════════════
# AI 预设模板
# ════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ai_create_preset(client: AsyncClient):
    """创建预设模板"""
    token, headers = await _register_and_login(client, "13900009990")

    resp = await client.post(
        "/api/ai-image/presets",
        json={
            "name": "北欧风",
            "category": "style",
            "prompt_template": "Scandinavian interior, white, wood, plants, cozy",
            "negative_prompt_template": "dark, heavy",
            "default_params": {
                "model_name": "stable-diffusion-xl",
                "guidance_scale": 8.0,
                "num_inference_steps": 40,
            },
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "北欧风"
    assert data["usage_count"] == 0


@pytest.mark.asyncio
async def test_ai_list_presets(client: AsyncClient):
    """列出预设模板"""
    token, headers = await _register_and_login(client, "13900009991")

    await _create_preset(client, headers, "现代简约")
    await _create_preset(client, headers, "北欧风")
    await _create_preset(client, headers, "新中式")

    resp = await client.get("/api/ai-image/presets", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 3


@pytest.mark.asyncio
async def test_ai_get_preset(client: AsyncClient):
    """获取预设模板"""
    token, headers = await _register_and_login(client, "13900009992")
    preset_id = await _create_preset(client, headers, "日式")

    resp = await client.get(f"/api/ai-image/presets/{preset_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "日式"


# ════════════════════════════════════════════════════════════
# AI 应用预设 / 批量渲染
# ════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_ai_apply_preset(client: AsyncClient):
    """应用预设模板 — 创建任务并触发"""
    token, headers = await _register_and_login(client, "13900009995")
    project_id = await _create_project(client, headers, "AI 应用预设测试")
    preset_id = await _create_preset(client, headers, "现代简约")

    resp = await client.post(
        "/api/ai-image/jobs/apply-preset",
        json={
            "preset_id": preset_id,
            "input_image_url": "https://example.com/room.jpg",
            "customizations": {
                "project_id": project_id,
                "num_inference_steps": 25,
            },
        },
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["input_image_url"] == "https://example.com/room.jpg"
    assert data["prompt"] == "modern minimalist interior, bright, clean lines, neutral colors"
    assert data["status"] == "queued"

    # 预设使用次数应增加
    resp = await client.get(f"/api/ai-image/presets/{preset_id}", headers=headers)
    assert resp.json()["usage_count"] == 1


@pytest.mark.asyncio
async def test_ai_batch_render(client: AsyncClient):
    """批量渲染 — 一个项目应用多个风格预设"""
    token, headers = await _register_and_login(client, "13900009996")
    project_id = await _create_project(client, headers, "AI 批量渲染测试")

    preset1 = await _create_preset(client, headers, "现代简约")
    preset2 = await _create_preset(client, headers, "北欧风")
    preset3 = await _create_preset(client, headers, "新中式")

    resp = await client.post(
        "/api/ai-image/jobs/batch",
        json={
            "project_id": project_id,
            "preset_ids": [preset1, preset2, preset3],
            "input_image_url": "https://example.com/room.jpg",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    jobs = resp.json()
    assert len(jobs) == 3
    # 三个任务的 prompt 应不同 (对应不同预设)
    prompts = {j["prompt"] for j in jobs}
    assert len(prompts) == 3
    # 所有任务状态应为 queued
    assert all(j["status"] == "queued" for j in jobs)


@pytest.mark.asyncio
async def test_ai_batch_render_with_invalid_preset(client: AsyncClient):
    """批量渲染包含无效预设 ID — 应跳过无效项"""
    token, headers = await _register_and_login(client, "13900009997")
    project_id = await _create_project(client, headers, "AI 批量无效测试")

    preset1 = await _create_preset(client, headers, "现代简约")

    resp = await client.post(
        "/api/ai-image/jobs/batch",
        json={
            "project_id": project_id,
            "preset_ids": [preset1, "invalid-id-1", "invalid-id-2"],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert len(resp.json()) == 1  # 只有 1 个有效任务


# ════════════════════════════════════════════════════════════
# AI 单元测试 — 提示词校验 + 成本计算
# ════════════════════════════════════════════════════════════


def test_validate_prompt_valid():
    """单元测试: 正常提示词通过校验"""
    from app.services.ai_image_service import validate_prompt
    is_valid, msg = validate_prompt("modern minimalist living room")
    assert is_valid is True
    assert msg == ""


def test_validate_prompt_empty():
    """单元测试: 空提示词不通过"""
    from app.services.ai_image_service import validate_prompt
    is_valid, msg = validate_prompt("")
    assert is_valid is False
    assert "空" in msg


def test_validate_prompt_sensitive():
    """单元测试: 敏感词不通过"""
    from app.services.ai_image_service import validate_prompt
    is_valid, msg = validate_prompt("包含暴力的内容")
    assert is_valid is False
    assert "敏感词" in msg


def test_validate_prompt_too_long():
    """单元测试: 超长提示词不通过"""
    from app.services.ai_image_service import validate_prompt, MAX_PROMPT_LENGTH
    long_prompt = "a" * (MAX_PROMPT_LENGTH + 1)
    is_valid, msg = validate_prompt(long_prompt)
    assert is_valid is False
    assert "长度" in msg


def test_compute_cost():
    """单元测试: 成本计算 (steps × 0.01 元)"""
    from app.services.ai_image_service import compute_cost, AIImageJob

    job = AIImageJob(
        id="j1",
        project_id="p1",
        num_inference_steps=30,
    )
    assert compute_cost(job) == 0.30

    job.num_inference_steps = 50
    assert compute_cost(job) == 0.50

    job.num_inference_steps = 100
    assert compute_cost(job) == 1.00

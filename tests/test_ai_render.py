"""AI 渲染端点测试 (/api/ai-render/*)

覆盖:
- 2D 效果图生成（mock 模式）
- 3D 场景生成（mock 模式）
- 照片重布置（mock 模式）
- 越权项目访问拒绝（403）
- 未认证请求拒绝（401）
- 无效 mode 拒绝（422）
- 缺少照片拒绝（422）
- 风格自由文本允许
- L4 自适应学习偏好注入
- capabilities 端点
"""

import hashlib
import io

import pytest
from httpx import AsyncClient
from starlette.routing import Mount

from app.main import app
from app.api import ai_render as ai_render_api

# ── 路由注册 ──────────────────────────────────────────────
# 若主代理尚未在 main.py 中注册 ai_render 路由，
# 测试时临时挂载（与 tests/test_idor_v1_1_1.py 相同的引导模式）。
# 注意：需在 StaticFiles("/") 挂载之前插入，否则会被静态资源拦截。
_ai_render_registered = any(
    getattr(r, "path", "").startswith("/api/ai-render") for r in app.routes
)
if not _ai_render_registered:
    _static_mounts = [
        r for r in app.router.routes
        if isinstance(r, Mount) and r.path in ("/", "")
    ]
    app.router.routes = [
        r for r in app.router.routes
        if not (isinstance(r, Mount) and r.path in ("/", ""))
    ]
    app.include_router(ai_render_api.router, prefix="/api")
    app.router.routes.extend(_static_mounts)


# ── 辅助函数 ──────────────────────────────────────────────


async def _register(client: AsyncClient, phone: str = "13900006201") -> str:
    """注册用户并返回 access_token"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "AI渲染测试用户", "password": "test123456"},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["access_token"]


async def _register_with_headers(
    client: AsyncClient, phone: str, name: str
) -> tuple[str, dict]:
    """注册用户并返回 (token, headers)"""
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": name, "password": "test123456"},
    )
    assert resp.status_code in (200, 201), resp.text
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


async def _create_project(client: AsyncClient, headers: dict, name: str) -> str:
    """创建项目并返回 project_id"""
    resp = await client.post(
        "/api/projects",
        json={"name": name, "total_area": 100.0},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _hash(msg: str) -> str:
    return hashlib.sha256(msg.encode("utf-8")).hexdigest()


# ── 2D 渲染测试 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_render_2d_mock(client: AsyncClient):
    """mock 模式下 2D 渲染返回 placeholder + prompt"""
    token = await _register(client, "13900006201")
    resp = await client.post(
        "/api/ai-render/2d",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "layout_json": {"rooms": [{"name": "客厅", "w": 5.0, "h": 4.0}]},
            "style": "modern",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "prompt" in data
    assert "description" in data
    assert "placeholder_image_url" in data
    assert data["style"] == "modern"
    assert "model_used" in data
    assert "processing_time_ms" in data
    # 占位图 URL 应为 placehold.co 格式
    assert "placehold.co" in data["placeholder_image_url"]
    # mock 模式下 preference_hint_applied 字段应存在（False，因为无 L4 反馈）
    assert "preference_hint_applied" in data
    assert data["preference_hint_applied"] is False


@pytest.mark.asyncio
async def test_render_2d_with_project_unauth(client: AsyncClient):
    """非项目 owner 访问他人项目 → 403"""
    token_a, h_a = await _register_with_headers(client, "13900006210", "owner-A")
    token_b, h_b = await _register_with_headers(client, "13900006211", "attacker-B")
    proj_id = await _create_project(client, h_a, "AI渲染项目-越权测试")

    # 攻击者 B 尝试在 A 的项目下渲染 → 必须 403
    resp = await client.post(
        "/api/ai-render/2d",
        headers=h_b,
        json={
            "layout_json": {"rooms": []},
            "style": "modern",
            "project_id": proj_id,
        },
    )
    assert resp.status_code == 403, f"IDOR 未拦截: {resp.status_code} {resp.text}"

    # owner A 自己渲染 → 应成功
    resp = await client.post(
        "/api/ai-render/2d",
        headers=h_a,
        json={
            "layout_json": {"rooms": []},
            "style": "modern",
            "project_id": proj_id,
        },
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_render_2d_invalid_style(client: AsyncClient):
    """无效风格应被允许（style 为自由文本，列表仅供参考）"""
    token = await _register(client, "13900006202")
    resp = await client.post(
        "/api/ai-render/2d",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "layout_json": {"rooms": []},
            "style": "自定义奇葩风格",  # 非推荐列表中的风格
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["style"] == "自定义奇葩风格"


# ── 3D 渲染测试 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_render_3d_mock(client: AsyncClient):
    """mock 模式下 3D 渲染返回多视角 prompts + 重建参数"""
    token = await _register(client, "13900006203")
    resp = await client.post(
        "/api/ai-render/3d",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "floorplan": {"rooms": [{"name": "客厅", "w": 5.0, "h": 4.0}]},
            "style": "nordic",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "prompts" in data
    assert isinstance(data["prompts"], list)
    assert len(data["prompts"]) >= 1
    assert "reconstruction_params" in data
    assert "placeholder_model_url" in data
    assert data["style"] == "nordic"
    # 重建参数应包含 method 字段
    assert "method" in data["reconstruction_params"]
    assert "placehold.co" in data["placeholder_model_url"]


# ── 照片重布置测试 ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_restage_photo_mock(client: AsyncClient):
    """mock 模式下照片重布置返回 prompt + 占位结果"""
    token = await _register(client, "13900006204")
    resp = await client.post(
        "/api/ai-render/restage",
        headers={"Authorization": f"Bearer {token}"},
        data={"mode": "inpainting", "style": "japanese"},
        files={"photo": ("photo.jpg", io.BytesIO(b"fake-photo-bytes"), "image/jpeg")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["mode"] == "inpainting"
    assert "prompt" in data
    assert "placeholder_result_url" in data
    assert "detected_room_type" in data
    assert data["style"] == "japanese"
    assert "placehold.co" in data["placeholder_result_url"]


@pytest.mark.asyncio
async def test_restage_invalid_mode(client: AsyncClient):
    """无效 mode 应返回 422"""
    token = await _register(client, "13900006205")
    resp = await client.post(
        "/api/ai-render/restage",
        headers={"Authorization": f"Bearer {token}"},
        data={"mode": "invalid_mode", "style": "modern"},
        files={"photo": ("photo.jpg", io.BytesIO(b"fake"), "image/jpeg")},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_restage_no_photo(client: AsyncClient):
    """缺少照片字段应返回 422"""
    token = await _register(client, "13900006206")
    resp = await client.post(
        "/api/ai-render/restage",
        headers={"Authorization": f"Bearer {token}"},
        data={"mode": "inpainting", "style": "modern"},
        # 不传 files
    )
    assert resp.status_code == 422, resp.text


# ── capabilities 端点测试 ──────────────────────────────────


@pytest.mark.asyncio
async def test_capabilities(client: AsyncClient):
    """capabilities 端点返回风格和模式列表"""
    token = await _register(client, "13900006207")
    resp = await client.get(
        "/api/ai-render/capabilities",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "styles" in data
    assert "restage_modes" in data
    assert "modern" in data["styles"]
    assert "nordic" in data["styles"]
    assert "inpainting" in data["restage_modes"]
    assert "full_regen" in data["restage_modes"]


# ── 认证测试 ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unauth(client: AsyncClient):
    """未携带 PASETO token 应返回 401"""
    resp = await client.post(
        "/api/ai-render/2d",
        json={"layout_json": {"rooms": []}, "style": "modern"},
    )
    assert resp.status_code == 401

    resp = await client.post(
        "/api/ai-render/3d",
        json={"floorplan": {}, "style": "modern"},
    )
    assert resp.status_code == 401

    resp = await client.post(
        "/api/ai-render/restage",
        data={"mode": "inpainting"},
        files={"photo": ("p.jpg", io.BytesIO(b"x"), "image/jpeg")},
    )
    assert resp.status_code == 401

    resp = await client.get("/api/ai-render/capabilities")
    assert resp.status_code == 401


# ── L4 自适应学习偏好注入测试 ────────────────────────────────


@pytest.mark.asyncio
async def test_render_2d_with_l4_preference(client: AsyncClient, db_session):
    """注入 L4 偏好后，mock 模式下 preference_hint_applied 应为 True"""
    from sqlalchemy import select
    from app.models.user import User
    from app.models.agent_feedback import AgentFeedback

    # 1. 注册用户
    phone = "13900006208"
    token, headers = await _register_with_headers(client, phone, "L4偏好用户")

    # 2. 查询用户 ID
    result = await db_session.execute(select(User).where(User.phone == phone))
    user = result.scalar_one()
    user_id = user.id

    # 3. 插入正向反馈（designer agent）
    user_msg = "帮我设计 90㎡ 现代简约风客厅"
    agent_reply = "推荐现代简约风：客厅 25 ㎡、主卧 15 ㎡，使用浅木色与米白色调"
    db_session.add(AgentFeedback(
        user_id=user_id,
        agent_name="designer",
        message_hash=_hash(user_msg),
        user_message=user_msg,
        agent_reply=agent_reply,
        feedback_type="like",
    ))
    await db_session.commit()

    # 4. 调用 2D 渲染端点
    resp = await client.post(
        "/api/ai-render/2d",
        headers=headers,
        json={
            "layout_json": {"rooms": [{"name": "客厅", "w": 5.0, "h": 4.0}]},
            "style": "modern",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # 5. 验证 preference_hint_applied 为 True
    assert "preference_hint_applied" in data, "响应应包含 preference_hint_applied 字段"
    assert data["preference_hint_applied"] is True, (
        "存在 designer 正向反馈时，preference_hint_applied 应为 True"
    )


@pytest.mark.asyncio
async def test_render_2d_without_l4_preference(client: AsyncClient):
    """无 L4 偏好数据时，preference_hint_applied 应为 False"""
    token = await _register(client, "13900006209")
    resp = await client.post(
        "/api/ai-render/2d",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "layout_json": {"rooms": []},
            "style": "modern",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["preference_hint_applied"] is False

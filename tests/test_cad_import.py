"""CAD 导入端点测试 (/api/cad-import/dxf)

覆盖:
- DXF 文件上传与实体解析（LINE/CIRCLE/TEXT/LWPOLYLINE/ARC）
- 边界框计算正确性
- 未认证请求拒绝
- 不支持的文件类型拒绝（415）
- DWG 转换器缺失时返回 422 + 安装指引
- L4 自适应学习：get_user_preference_hint 在无数据时返回空字符串
"""

import hashlib
import io
import tempfile

import ezdxf
import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, phone: str = "13900006001") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "CAD测试用户", "password": "test123456"},
    )
    return resp.json()["access_token"]


def _make_dxf_bytes() -> bytes:
    """构造包含 LINE/CIRCLE/LWPOLYLINE/TEXT/ARC 的最小 DXF 文件"""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 5))
    msp.add_circle((5, 5), radius=2)
    msp.add_lwpolyline([(0, 0), (3, 0), (3, 3)])
    msp.add_text("Hello", dxfattribs={"insert": (0, 0), "height": 1.0})
    msp.add_arc((8, 8), radius=2, start_angle=0, end_angle=90)

    # 写入临时文件后读回 bytes（ezdxf 的 write() 在某些版本对 BytesIO 兼容性不佳）
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as f:
        doc.saveas(f.name)
    with open(f.name, "rb") as f:
        return f.read()


# === /api/cad-import/dxf 端点 ===


@pytest.mark.asyncio
async def test_import_dxf_success(client: AsyncClient):
    """DXF 上传成功解析所有实体类型并返回结构化 JSON"""
    token = await _register(client, "13900006010")
    content = _make_dxf_bytes()
    resp = await client.post(
        "/api/cad-import/dxf",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test.dxf", io.BytesIO(content), "application/dxf")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["file_type"] == "dxf"
    assert data["converted_from_dwg"] is False
    # 应至少有 5 个实体（line/circle/polyline/text/arc）
    assert data["entity_count"] >= 5
    assert len(data["lines"]) >= 1
    assert len(data["circles"]) >= 1
    assert len(data["polylines"]) >= 1
    assert len(data["texts"]) >= 1
    assert len(data["arcs"]) >= 1
    # 边界框应被填充
    assert data["bounds"] is not None
    assert "min_x" in data["bounds"] and "max_x" in data["bounds"]
    assert "width" in data["bounds"] and "height" in data["bounds"]


@pytest.mark.asyncio
async def test_import_dxf_line_geometry(client: AsyncClient):
    """LINE 实体的几何字段 x1/y1/x2/y2 正确返回"""
    token = await _register(client, "13900006011")
    content = _make_dxf_bytes()
    resp = await client.post(
        "/api/cad-import/dxf",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("line.dxf", io.BytesIO(content), "application/dxf")},
    )
    assert resp.status_code == 200
    line = resp.json()["lines"][0]
    assert {"x1", "y1", "x2", "y2"} <= set(line.keys())


@pytest.mark.asyncio
async def test_import_dxf_circle_geometry(client: AsyncClient):
    """CIRCLE 实体的几何字段 x/y/r 正确返回"""
    token = await _register(client, "13900006012")
    content = _make_dxf_bytes()
    resp = await client.post(
        "/api/cad-import/dxf",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("circle.dxf", io.BytesIO(content), "application/dxf")},
    )
    assert resp.status_code == 200
    circle = resp.json()["circles"][0]
    assert {"x", "y", "r"} <= set(circle.keys())
    assert circle["r"] == 2


@pytest.mark.asyncio
async def test_import_dxf_requires_auth(client: AsyncClient):
    """未携带 PASETO token 应返回 401"""
    content = _make_dxf_bytes()
    resp = await client.post(
        "/api/cad-import/dxf",
        files={"file": ("noauth.dxf", io.BytesIO(content), "application/dxf")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_import_unsupported_file_type(client: AsyncClient):
    """非 .dxf/.dwg 文件应返回 415"""
    token = await _register(client, "13900006013")
    resp = await client.post(
        "/api/cad-import/dxf",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("plan.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_import_invalid_dxf_returns_422(client: AsyncClient):
    """损坏的 DXF 内容应返回 422（解析失败）"""
    token = await _register(client, "13900006014")
    resp = await client.post(
        "/api/cad-import/dxf",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("bad.dxf", io.BytesIO(b"not a real dxf"), "application/dxf")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_dwg_without_converter_returns_422(client: AsyncClient, monkeypatch):
    """DWG 文件且系统未安装 dwg2dxf 时应返回 422 + 安装指引"""
    # 模拟 dwg2dxf 未安装
    monkeypatch.setattr("app.api.cad_import.shutil.which", lambda name: None)

    token = await _register(client, "13900006015")
    # 伪造的 DWG 文件头（不需要是有效的 DWG，因为转换器查找会先失败）
    resp = await client.post(
        "/api/cad-import/dxf",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("drawing.dwg", io.BytesIO(b"AC1015\x00fake"), "application/acad")},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    # 应包含安装指引关键字
    assert "LibreDWG" in detail or "dwg2dxf" in detail or "DXF" in detail


# === L4 自适应学习：get_user_preference_hint ===


def _hash(msg: str) -> str:
    return hashlib.sha256(msg.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_l4_preference_hint_no_data_returns_empty(db_session):
    """无历史正向反馈时返回空字符串（不污染 prompt）"""
    from app.agents.base import BaseAgent
    from app.models.user import User

    # 创建一个用户
    user = User(phone="13900006020", name="L4测试", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    hint = await BaseAgent.get_user_preference_hint(
        user.id, "designer", db_session, max_examples=3
    )
    assert hint == ""


@pytest.mark.asyncio
async def test_l4_preference_hint_disabled_returns_empty(db_session, monkeypatch):
    """agent_learning_enabled=False 时直接返回空字符串"""
    from app.agents.base import BaseAgent, settings as _settings_mod
    # 临时禁用学习
    monkeypatch.setattr(_settings_mod, "agent_learning_enabled", False)

    hint = await BaseAgent.get_user_preference_hint(
        "fake-user-id", "designer", db_session, max_examples=3
    )
    assert hint == ""


@pytest.mark.asyncio
async def test_l4_preference_hint_with_feedback(db_session):
    """存在正向反馈时返回格式化的 few-shot 示例字符串"""
    from app.agents.base import BaseAgent
    from app.models.user import User
    from app.models.agent_feedback import AgentFeedback

    user = User(phone="13900006021", name="L4正向用户", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    fb = AgentFeedback(
        user_id=user.id,
        agent_name="designer",
        message_hash=_hash("帮我设计 90㎡ 小户型"),
        user_message="帮我设计 90㎡ 小户型",
        agent_reply="推荐现代简约风：客厅 25 ㎡、主卧 15 ㎡ ...",
        feedback_type="like",
    )
    db_session.add(fb)
    await db_session.commit()

    hint = await BaseAgent.get_user_preference_hint(
        user.id, "designer", db_session, max_examples=3
    )
    assert hint != ""
    assert "过往满意回复" in hint
    assert "90㎡" in hint
    assert "现代简约" in hint


@pytest.mark.asyncio
async def test_l4_preference_hint_filters_by_agent(db_session):
    """只返回指定 agent 的反馈，其他 agent 的反馈不混入"""
    from app.agents.base import BaseAgent
    from app.models.user import User
    from app.models.agent_feedback import AgentFeedback

    user = User(phone="13900006022", name="L4过滤用户", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # designer 反馈
    db_session.add(AgentFeedback(
        user_id=user.id, agent_name="designer",
        message_hash=_hash("设计需求"),
        user_message="设计需求", agent_reply="设计师回复",
        feedback_type="like",
    ))
    # budget 反馈（不应被 designer 查询返回）
    db_session.add(AgentFeedback(
        user_id=user.id, agent_name="budget",
        message_hash=_hash("预算需求"),
        user_message="预算需求", agent_reply="预算回复",
        feedback_type="like",
    ))
    await db_session.commit()

    hint = await BaseAgent.get_user_preference_hint(
        user.id, "designer", db_session, max_examples=3
    )
    assert "设计师回复" in hint
    assert "预算回复" not in hint


@pytest.mark.asyncio
async def test_l4_preference_hint_ignores_dislike(db_session):
    """feedback_type=dislike 的反馈不被纳入 few-shot 示例"""
    from app.agents.base import BaseAgent
    from app.models.user import User
    from app.models.agent_feedback import AgentFeedback

    user = User(phone="13900006023", name="L4差评用户", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    db_session.add(AgentFeedback(
        user_id=user.id, agent_name="designer",
        message_hash=_hash("差评需求"),
        user_message="差评需求", agent_reply="差评回复内容",
        feedback_type="dislike",
    ))
    await db_session.commit()

    hint = await BaseAgent.get_user_preference_hint(
        user.id, "designer", db_session, max_examples=3
    )
    assert hint == ""

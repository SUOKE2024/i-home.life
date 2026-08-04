"""F45 方案前置决策 API 集成测试

覆盖端点:
- POST /api/solution-first/generate   (生成 3 套方案 + 预算区间)
- GET  /api/solution-first/entry      (入口状态)
"""
import json

import pytest
from httpx import AsyncClient

from app.services import solution_first_service


async def _auth_headers(client: AsyncClient, phone: str = "13940040001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "方案前置测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_project(client: AsyncClient, headers: dict, name: str = "方案前置测试项目") -> str:
    resp = await client.post(
        "/api/projects", json={"name": name, "total_area": 100.0}, headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _generate(client: AsyncClient, headers: dict, project_id: str):
    return await client.post(
        "/api/solution-first/generate", json={"project_id": project_id}, headers=headers,
    )


# ── 鉴权 ──


@pytest.mark.asyncio
async def test_solution_first_unauthorized(client: AsyncClient):
    """未认证用户不能生成方案"""
    resp = await client.post("/api/solution-first/generate", json={"project_id": "fake"})
    assert resp.status_code == 401

    resp = await client.get("/api/solution-first/entry", params={"project_id": "fake"})
    assert resp.status_code == 401


# ── 方案生成 ──


@pytest.mark.asyncio
async def test_generate_package(client: AsyncClient):
    """生成 3 套布局方案 + 预算区间"""
    headers = await _auth_headers(client, "13940040002")
    project_id = await _create_project(client, headers)

    resp = await _generate(client, headers, project_id)
    assert resp.status_code == 201
    data = resp.json()
    assert data["plan_count"] == 3
    assert len(data["layouts"]) == 3
    assert [p["plan_no"] for p in data["layouts"]] == ["A", "B", "C"]
    # 每套方案均含要点/优缺点/诚实标注
    for plan in data["layouts"]:
        assert len(plan["layout_points"]) >= 3
        assert len(plan["pros"]) >= 1
        assert len(plan["cons"]) >= 1
        assert plan["source"] == "rule_based"
    # 预算区间
    budget = data["budget_range"]
    assert "lower" in budget and "upper" in budget
    assert budget["lower"] < budget["upper"]
    assert len(budget["levels"]) == 3
    assert "非精确报价" in budget["note"]
    # 推荐建议
    assert len(data["recommendations"]) >= 1
    assert data["project_name"] == "方案前置测试项目"


@pytest.mark.asyncio
async def test_generate_without_floorplan(client: AsyncClient):
    """无户型方案的项目仍可生成（用 total_area 兜底）"""
    headers = await _auth_headers(client, "13940040003")
    project_id = await _create_project(client, headers)

    resp = await _generate(client, headers, project_id)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["layouts"]) == 3
    # 兜底生成需诚实标注
    assert any("户型数据缺失" in p["source_note"] for p in data["layouts"])


@pytest.mark.asyncio
async def test_generate_with_floorplan_data(client: AsyncClient):
    """有户型数据时按房间结构生成，并诚实标注来源"""
    headers = await _auth_headers(client, "13940040004")
    project_id = await _create_project(client, headers)

    floorplan_data = {
        "rooms": [
            {"name": "客厅", "area": 30.0},
            {"name": "主卧", "area": 18.0},
            {"name": "厨房", "area": 8.0},
        ],
    }
    resp = await client.post(
        "/api/floorplans",
        json={
            "project_id": project_id,
            "name": "三房户型",
            "data": json.dumps(floorplan_data, ensure_ascii=False),
            "total_area": 100.0,
            "room_count": 3,
        },
        headers=headers,
    )
    assert resp.status_code == 201

    resp = await _generate(client, headers, project_id)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["layouts"]) == 3
    assert any("3 个房间" in p["source_note"] for p in data["layouts"])


@pytest.mark.asyncio
async def test_generate_package_project_not_found(client: AsyncClient):
    """项目不存在返回 404"""
    headers = await _auth_headers(client, "13940040005")
    resp = await _generate(client, headers, "no-such-project")
    assert resp.status_code == 404


# ── F45 LLM 生成路径与诚实降级 ──


@pytest.mark.asyncio
async def test_generate_package_llm_source(client: AsyncClient, monkeypatch):
    """LLM 可用（返回有效 JSON）时 source=llm，布局与预算区间来自 LLM"""
    async def fake_chat(self, messages, **kwargs):
        return json.dumps({
            "layouts": [
                {"layout_name": "LLM动静分区", "description": "descA", "rooms": ["客厅"],
                 "layout_points": ["动静分区"], "pros": ["私密好"], "cons": ["通透一般"],
                 "budget_range": {"lower": 100000, "upper": 180000, "level": "comfort"}},
                {"layout_name": "LLM开放融合", "description": "descB", "rooms": ["客厅", "厨房"],
                 "budget_range": {"lower": 120000, "upper": 200000, "level": "comfort"}},
                {"layout_name": "LLM高效收纳", "description": "descC", "rooms": ["主卧"],
                 "budget_range": {"lower": 90000, "upper": 160000, "level": "economy"}},
            ],
            "budget_range": {"lower": 100000, "upper": 180000, "level": "comfort"},
        }, ensure_ascii=False)

    monkeypatch.setattr(solution_first_service.SolutionFirstAgent, "_chat", fake_chat)

    headers = await _auth_headers(client, "13940040050")
    project_id = await _create_project(client, headers)

    resp = await _generate(client, headers, project_id)
    assert resp.status_code == 201
    data = resp.json()
    assert data["source"] == "llm"
    assert data["plan_count"] == 3
    assert [p["plan_no"] for p in data["layouts"]] == ["A", "B", "C"]
    for plan in data["layouts"]:
        assert plan["source"] == "llm"
    assert data["layouts"][0]["name"] == "LLM动静分区"
    assert data["layouts"][0]["rooms"] == ["客厅"]
    # 预算区间来自 LLM 主档
    assert data["budget_range"]["lower"] == 100000
    assert data["budget_range"]["upper"] == 180000
    assert data["budget_range"]["level"] == "comfort"
    assert len(data["budget_range"]["levels"]) == 3


@pytest.mark.asyncio
async def test_generate_package_llm_fallback_on_error(client: AsyncClient, monkeypatch):
    """LLM 抛异常时回退 rule_based 并诚实标注降级"""
    async def fake_chat(self, messages, **kwargs):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(solution_first_service.SolutionFirstAgent, "_chat", fake_chat)

    headers = await _auth_headers(client, "13940040051")
    project_id = await _create_project(client, headers)

    resp = await _generate(client, headers, project_id)
    assert resp.status_code == 201
    data = resp.json()
    assert data["source"] == "rule_based"
    assert "降级" in data["source_note"]
    assert data["plan_count"] == 3
    for plan in data["layouts"]:
        assert plan["source"] == "rule_based"


@pytest.mark.asyncio
async def test_generate_package_llm_fallback_on_non_json(client: AsyncClient, monkeypatch):
    """LLM 返回非 JSON 时回退 rule_based（不伪装 LLM 能力）"""
    async def fake_chat(self, messages, **kwargs):
        return "抱歉，我无法生成结构化输出。"

    monkeypatch.setattr(solution_first_service.SolutionFirstAgent, "_chat", fake_chat)

    headers = await _auth_headers(client, "13940040052")
    project_id = await _create_project(client, headers)

    resp = await _generate(client, headers, project_id)
    assert resp.status_code == 201
    data = resp.json()
    assert data["source"] == "rule_based"
    assert "降级" in data["source_note"]


@pytest.mark.asyncio
async def test_solution_first_cross_user_access_blocked(client: AsyncClient):
    """越权访问他人项目返回 403"""
    headers_a = await _auth_headers(client, "13940040006")
    headers_b = await _auth_headers(client, "13940040007")
    project_id_a = await _create_project(client, headers_a)

    resp = await _generate(client, headers_b, project_id_a)
    assert resp.status_code == 403


# ── 入口状态 ──


@pytest.mark.asyncio
async def test_entry_has_floorplan(client: AsyncClient):
    """entry 返回 has_floorplan 字段（无户型时 False）"""
    headers = await _auth_headers(client, "13940040008")
    project_id = await _create_project(client, headers)

    resp = await client.get("/api/solution-first/entry", params={"project_id": project_id}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id
    assert data["has_floorplan"] is False
    assert data["plan_available"] is True
    assert data["total_area"] == 100.0


@pytest.mark.asyncio
async def test_entry_with_floorplan_true(client: AsyncClient):
    """有户型方案时 entry 的 has_floorplan 为 True"""
    headers = await _auth_headers(client, "13940040009")
    project_id = await _create_project(client, headers)

    await client.post(
        "/api/floorplans",
        json={"project_id": project_id, "name": "户型", "total_area": 88.0},
        headers=headers,
    )

    resp = await client.get("/api/solution-first/entry", params={"project_id": project_id}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_floorplan"] is True
    assert data["total_area"] == 88.0


# ── F45 多风格 + 多轮对话（refine） ──


@pytest.mark.asyncio
async def test_styles_catalog(client: AsyncClient):
    """风格目录返回 6 种主流风格"""
    headers = await _auth_headers(client, "13940040060")
    resp = await client.get("/api/solution-first/styles", headers=headers)
    assert resp.status_code == 200
    styles = resp.json()
    assert len(styles) == 6
    keys = [s["key"] for s in styles]
    assert "modern" in keys and "new_chinese" in keys and "nordic" in keys


@pytest.mark.asyncio
async def test_generate_with_style(client: AsyncClient):
    """generate 支持风格参数，返回风格信息，规则生成标注风格偏好"""
    headers = await _auth_headers(client, "13940040061")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/solution-first/generate",
        json={"project_id": project_id, "style": "new_chinese"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["style"]["key"] == "new_chinese"
    assert data["style"]["name"] == "新中式"
    assert any("风格偏好：新中式" in p["source_note"] for p in data["layouts"])


@pytest.mark.asyncio
async def test_generate_unknown_style_falls_back(client: AsyncClient):
    """未知风格回退现代简约（诚实标注）"""
    headers = await _auth_headers(client, "13940040062")
    project_id = await _create_project(client, headers)
    resp = await client.post(
        "/api/solution-first/generate",
        json={"project_id": project_id, "style": "no_such_style"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["style"]["key"] == "modern"


@pytest.mark.asyncio
async def test_refine_fallback_to_rule(client: AsyncClient, monkeypatch):
    """LLM 不可用时 refine 回退 rule_based 并诚实标注"""
    async def fake_chat(self, messages, **kwargs):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(solution_first_service.SolutionFirstAgent, "_chat", fake_chat)

    headers = await _auth_headers(client, "13940040063")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/solution-first/refine",
        json={"project_id": project_id, "plan_no": "A", "feedback": "希望增加收纳"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["source"] == "rule_based"
    assert "降级" in data["source_note"]
    assert data["refined_layout"]["source"] == "rule_based"
    assert data["refined_layout"]["plan_no"] == "R"
    assert "收纳" in data["refined_layout"]["summary"]


@pytest.mark.asyncio
async def test_refine_llm_source(client: AsyncClient, monkeypatch):
    """LLM 可用时 refine 深化方案 source=llm"""
    async def fake_chat(self, messages, **kwargs):
        return json.dumps({
            "refined_layout": {
                "layout_name": "加大收纳版",
                "description": "在方案 A 基础上强化收纳",
                "layout_points": ["整面墙柜体", "飘窗利用"],
                "pros": ["收纳最大"],
                "cons": ["造价略高"],
            }
        }, ensure_ascii=False)

    monkeypatch.setattr(solution_first_service.SolutionFirstAgent, "_chat", fake_chat)

    headers = await _auth_headers(client, "13940040064")
    project_id = await _create_project(client, headers)

    resp = await client.post(
        "/api/solution-first/refine",
        json={"project_id": project_id, "plan_no": "A", "feedback": "多加点收纳"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["source"] == "llm"
    assert data["refined_layout"]["name"] == "加大收纳版"
    assert data["refined_layout"]["source"] == "llm"


@pytest.mark.asyncio
async def test_refine_empty_feedback(client: AsyncClient):
    """空反馈 → 400"""
    headers = await _auth_headers(client, "13940040065")
    project_id = await _create_project(client, headers)
    resp = await client.post(
        "/api/solution-first/refine",
        json={"project_id": project_id, "plan_no": "A", "feedback": "  "},
        headers=headers,
    )
    assert resp.status_code == 400

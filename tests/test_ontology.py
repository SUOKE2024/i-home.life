"""本体基座 API 测试（P0 本体/领域知识基座）

覆盖：鉴权、领域枚举、三本体加载、Agent 全覆盖、对齐映射、未知领域 404。
"""

import pytest


# 全部 26 个 Agent（25 + 1 Orchestrator），与 app/agents/__init__.py 对齐
_ALL_AGENT_IDS = {
    "orchestrator", "designer", "budget", "procurement", "construction",
    "settlement", "qa_inspector", "concierge", "content_publisher", "admin",
    "kitchen", "bathroom", "mep", "appliance", "furniture", "door_window",
    "files", "products", "identity", "notifications", "takeoff", "ifc_export",
    "growth", "marketing", "competitor_research", "finance_recon",
}


@pytest.mark.asyncio
async def test_ontology_requires_auth(client):
    """无认证 → 401"""
    resp = await client.get("/api/ontology")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_ontologies(client, auth_headers):
    """列出三个本体领域"""
    resp = await client.get("/api/ontology", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 3
    assert set(body["domains"]) == {"renovation", "agent", "material"}


@pytest.mark.asyncio
async def test_load_renovation_ontology(client, auth_headers):
    """加载空间/构件/关系本体"""
    resp = await client.get("/api/ontology/renovation", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ontology"] == "renovation"
    assert "spatial" in body and "element" in body and "relations" in body


@pytest.mark.asyncio
async def test_agent_ontology_covers_all_agents(client, auth_headers):
    """Agent 本体须覆盖全部 26 个 Agent"""
    resp = await client.get("/api/ontology/agent", headers=auth_headers)
    assert resp.status_code == 200
    agents = resp.json()["agents"]
    ids = {a["id"] for a in agents}
    assert ids == _ALL_AGENT_IDS
    assert len(agents) == 26
    # 每个 Agent 必须有分类/角色/能力/边界字段
    for a in agents:
        assert a["category"] in {"orchestration", "execution", "business_ops"}
        assert a["role"] and a["capabilities"] and a["decision_boundary"]


@pytest.mark.asyncio
async def test_load_material_ontology(client, auth_headers):
    """加载材质/环保等级本体"""
    resp = await client.get("/api/ontology/material", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ontology"] == "material"
    assert "materials" in body and "eco_grades" in body


@pytest.mark.asyncio
async def test_unknown_ontology_404(client, auth_headers):
    """未知领域 → 404"""
    resp = await client.get("/api/ontology/nonexistent", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_alignments(client, auth_headers):
    """开放本体对齐映射（Brick/BOT/IFC）"""
    resp = await client.get("/api/ontology/renovation/alignments", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["domain"] == "renovation"
    # room 应对齐 bot:Space / ifc:IfcSpace / brick:Room
    assert "room" in body["alignments"]
    assert body["alignments"]["room"]["ifc"] == "IfcSpace"


@pytest.mark.asyncio
async def test_alignments_unknown_domain_404(client, auth_headers):
    """对齐映射未知领域 → 404"""
    resp = await client.get("/api/ontology/nonexistent/alignments", headers=auth_headers)
    assert resp.status_code == 404

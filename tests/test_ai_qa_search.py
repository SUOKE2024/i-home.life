"""F47 AI 装修问答/案例搜索 API 集成测试

覆盖端点:
- POST /api/ai-qa/search   (知识库问答搜索)
- GET  /api/ai-qa/faq      (FAQ 话题列表)
"""
import pytest
from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, phone: str = "13960060001") -> dict:
    resp = await client.post(
        "/api/auth/register",
        json={"phone": phone, "name": "AI问答测试用户", "password": "test123456"},
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── 鉴权 ──


@pytest.mark.asyncio
async def test_ai_qa_unauthorized(client: AsyncClient):
    """未认证用户不能搜索"""
    resp = await client.post("/api/ai-qa/search", json={"query": "防水"})
    assert resp.status_code == 401

    resp = await client.get("/api/ai-qa/faq")
    assert resp.status_code == 401


# ── 搜索 ──


@pytest.mark.asyncio
async def test_search_empty_query_422(client: AsyncClient):
    """空 query 返回 422"""
    headers = await _auth_headers(client, "13960060002")
    resp = await client.post("/api/ai-qa/search", json={"query": ""}, headers=headers)
    assert resp.status_code == 422

    resp = await client.post("/api/ai-qa/search", json={}, headers=headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_hit_knowledge_base(client: AsyncClient):
    """搜索知识库真实关键词「防水」返回答案与引用来源"""
    headers = await _auth_headers(client, "13960060003")
    resp = await client.post("/api/ai-qa/search", json={"query": "防水"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["match_type"] == "knowledge_base"
    assert data["answer"]
    assert "供参考" in data["answer"]
    assert len(data["sources"]) >= 1
    source = data["sources"][0]
    assert source["domain"] in ("techniques", "faq", "standards")
    assert source["citation"]
    assert source["snippet"]
    assert "honest_note" in data


@pytest.mark.asyncio
async def test_search_no_match(client: AsyncClient):
    """无意义关键词：no_match、sources 空、honest_note 存在（诚实降级不编造）"""
    headers = await _auth_headers(client, "13960060004")
    resp = await client.post("/api/ai-qa/search", json={"query": "zzzqqqxxx"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["match_type"] == "no_match"
    assert data["sources"] == []
    assert "未在内置知识库找到精确匹配" in data["answer"]
    assert data["honest_note"]


# ── FAQ 话题 ──


@pytest.mark.asyncio
async def test_faq_topics(client: AsyncClient):
    """faq 返回 total>0 与 topics 列表"""
    headers = await _auth_headers(client, "13960060005")
    resp = await client.get("/api/ai-qa/faq", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    assert len(data["topics"]) > 0
    topic = data["topics"][0]
    assert topic["id"]
    assert topic["name"]
    assert topic["content"]
    assert topic["citation"]

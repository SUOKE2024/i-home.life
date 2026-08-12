"""OpenAPI 端点测试（v1.13.1 OBS-003）

覆盖 app/main.py cached_openapi_json：
1. GET /api/openapi.json 返回预序列化 JSON + Cache-Control
2. Accept-Encoding: gzip 时返回预压缩 Content-Encoding: gzip
3. 响应体可解析且含 paths（路由已注册）
"""


async def test_openapi_json_returns_valid_schema(client):
    resp = await client.get("/api/openapi.json")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert "cache-control" in resp.headers
    schema = resp.json()
    assert "paths" in schema
    assert "openapi" in schema
    assert len(schema["paths"]) > 0, "应至少注册 1 个路由"


async def test_openapi_json_gzip_encoding(client):
    resp = await client.get("/api/openapi.json", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == "gzip"
    assert resp.headers.get("cache-control") == "public, max-age=3600"


async def test_openapi_json_serializable_and_sizeable(client):
    """响应体为完整可解析 JSON，且预序列化字节非空（预热/惰性缓存任一路径均有效）。"""
    resp = await client.get("/api/openapi.json")
    body = resp.content
    assert len(body) > 0
    import json
    json.loads(body)

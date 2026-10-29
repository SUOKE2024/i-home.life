"""RFC 9728 保护资源元数据（MCP）回归。

覆盖端点:
- GET /.well-known/oauth-protected-resource
- GET /.well-known/oauth-authorization-server
"""


async def test_oauth_protected_resource_exposed(client):
    resp = await client.get("/.well-known/oauth-protected-resource")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["resource"].endswith("/api/mcp")
    assert body["resource_documentation"].endswith("/api/mcp/manifest")
    assert body["scopes_supported"] == ["mcp:tools", "mcp:resources"]
    assert body["bearer_methods_supported"] == ["header"]
    assert body["x-token-types"] == ["paseto"]
    assert "authorization_servers" not in body


async def test_oauth_authorization_server_honest_404(client):
    resp = await client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "not_configured"

"""A2A v1.0 JSON-RPC（message/send）入口测试。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import a2a as a2a_api


def _client(monkeypatch, send_impl):
    app = FastAPI()
    app.include_router(a2a_api.router, prefix="/api")
    app.dependency_overrides[a2a_api.get_current_user] = lambda: SimpleNamespace(
        id="u1", role="user"
    )
    app.dependency_overrides[a2a_api.get_db] = lambda: None
    monkeypatch.setattr(a2a_api, "send_task", send_impl)
    return TestClient(app)


def _completed(task_id="a2a_t1", result="hi"):
    async def _send(request, user, db):
        return a2a_api.A2ATaskResponse(
            task_id=task_id, state=a2a_api.A2ATaskState.COMPLETED, result=result
        )

    return _send


def test_message_send_returns_task_and_artifacts(monkeypatch):
    captured = {}

    def _send(request, user, db):
        captured["request"] = request
        return _completed()(request, user, db)

    client = _client(monkeypatch, _send)
    resp = client.post(
        "/api/a2a",
        json={
            "jsonrpc": "2.0",
            "id": 7,
            "method": "message/send",
            "params": {
                "message": {"role": "user", "parts": [{"kind": "text", "text": "帮我设计客厅"}]}
            },
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["jsonrpc"] == "2.0" and body["id"] == 7
    result = body["result"]
    assert result["id"] == "a2a_t1" and result["status"]["state"] == "completed"
    assert result["artifacts"][0]["parts"][0]["text"] == "hi"
    assert captured["request"].agent_name == "OrchestratorAgent"
    assert captured["request"].message == "帮我设计客厅"


def test_message_send_maps_metadata(monkeypatch):
    captured = {}

    async def _send(request, user, db):
        captured["request"] = request
        return await _completed()(request, user, db)

    client = _client(monkeypatch, _send)
    resp = client.post(
        "/api/a2a",
        json={
            "jsonrpc": "2.0",
            "id": "r1",
            "method": "message/send",
            "params": {
                "message": {"parts": [{"text": "量房"}]},
                "metadata": {
                    "agent_name": "DesignerAgent",
                    "project_id": "proj_1",
                    "app_id": "console",
                    "handshake_token": "hs",
                },
            },
        },
    )

    assert resp.status_code == 200
    req = captured["request"]
    assert req.agent_name == "DesignerAgent"
    assert req.project_id == "proj_1"
    assert req.app_id == "console"
    assert req.handshake_token == "hs"


def test_unknown_method_returns_32601(monkeypatch):
    client = _client(monkeypatch, _completed())
    resp = client.post(
        "/api/a2a",
        json={"jsonrpc": "2.0", "id": 1, "method": "tasks/get", "params": {}},
    )

    body = resp.json()
    assert body["error"]["code"] == -32601
    assert "result" not in body


def test_missing_message_returns_32602(monkeypatch):
    client = _client(monkeypatch, _completed())
    resp = client.post(
        "/api/a2a",
        json={"jsonrpc": "2.0", "id": 1, "method": "message/send", "params": {"message": ""}},
    )

    assert resp.json()["error"]["code"] == -32602


def test_invalid_jsonrpc_version_returns_32600(monkeypatch):
    client = _client(monkeypatch, _completed())
    resp = client.post(
        "/api/a2a",
        json={"jsonrpc": "1.0", "id": 1, "method": "message/send", "params": {"message": "hi"}},
    )

    assert resp.json()["error"]["code"] == -32600


def test_send_task_http_error_maps_to_32001(monkeypatch):
    async def _deny(request, user, db):
        raise HTTPException(status_code=403, detail="handshake required")

    client = _client(monkeypatch, _deny)
    resp = client.post(
        "/api/a2a",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {"message": "hi"},
        },
    )

    body = resp.json()
    assert body["error"]["code"] == -32001
    assert "handshake required" in body["error"]["message"]


def test_failed_task_has_no_artifacts(monkeypatch):
    async def _failed(request, user, db):
        return a2a_api.A2ATaskResponse(
            task_id="a2a_t2",
            state=a2a_api.A2ATaskState.FAILED,
            error="agent down",
        )

    client = _client(monkeypatch, _failed)
    resp = client.post(
        "/api/a2a",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "message/send",
            "params": {"message": "hi"},
        },
    )

    result = resp.json()["result"]
    assert result["status"]["state"] == "failed"
    assert result["error"] == "agent down"
    assert "artifacts" not in result

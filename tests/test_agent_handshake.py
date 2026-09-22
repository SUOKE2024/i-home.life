"""ATH 握手凭证服务测试（v1.16.x 起，v1.17.x 补应用注册表）

覆盖：
- 签发/校验闭环（create → verify）
- 防篡改、字段不匹配（app/agent/actor）、过期拒绝
- 应用注册表：未登记 app_id / 越权 scope 拒签，退登记后存量凭证拒绝
- 应用核验智能体身份（verify_agent_identity，含 AID 比对）
"""
import pytest

from app.services import agent_handshake as hs
from app.services.agent_handshake import (
    create_handshake_credential,
    verify_handshake_credential,
    verify_agent_identity,
)


def test_create_and_verify_ok():
    cred = create_handshake_credential("flutter", "designer", "user-1", scope="a2a:task")
    result = verify_handshake_credential(
        cred["token"], app_id="flutter", agent_name="designer", actor_user_id="user-1"
    )
    assert result["valid"] is True
    assert result["reason"] == "ok"
    assert result["scope"] == "a2a:task"


def test_verify_rejects_tampered_token():
    cred = create_handshake_credential("flutter", "designer", "user-1")
    tampered = cred["token"] + "x"
    result = verify_handshake_credential(
        tampered, app_id="flutter", agent_name="designer", actor_user_id="user-1"
    )
    assert result["valid"] is False


def test_verify_rejects_wrong_app():
    cred = create_handshake_credential("flutter", "designer", "user-1")
    result = verify_handshake_credential(
        cred["token"], app_id="webapp", agent_name="designer", actor_user_id="user-1"
    )
    assert result["valid"] is False
    assert result["reason"] == "app_mismatch"


def test_verify_rejects_wrong_agent():
    cred = create_handshake_credential("flutter", "designer", "user-1")
    result = verify_handshake_credential(
        cred["token"], app_id="flutter", agent_name="budget", actor_user_id="user-1"
    )
    assert result["valid"] is False
    assert result["reason"] == "agent_mismatch"


def test_verify_rejects_wrong_actor():
    cred = create_handshake_credential("flutter", "designer", "user-1")
    result = verify_handshake_credential(
        cred["token"], app_id="flutter", agent_name="designer", actor_user_id="user-2"
    )
    assert result["valid"] is False
    assert result["reason"] == "actor_mismatch"


def test_verify_rejects_expired():
    cred = create_handshake_credential("flutter", "designer", "user-1", ttl_seconds=-1)
    result = verify_handshake_credential(
        cred["token"], app_id="flutter", agent_name="designer", actor_user_id="user-1"
    )
    assert result["valid"] is False
    assert result["reason"] == "expired"


def test_create_rejects_unregistered_app():
    """应用注册表：未登记 app_id 不得签发（应用侧身份不可自报）。"""
    with pytest.raises(ValueError, match="unknown_app"):
        create_handshake_credential("evil_app", "designer", "user-1", scope="a2a:task")


def test_create_rejects_scope_not_allowed():
    """最小权限：scope 不在该应用白名单内即拒签。"""
    with pytest.raises(ValueError, match="scope_not_allowed"):
        create_handshake_credential("flutter", "designer", "user-1", scope="admin:audit")


def test_scope_with_pipe_rejected():
    """scope 含分隔符（消毒后成 a_b）不在白名单 → 拒签，不生成歧义 token。"""
    with pytest.raises(ValueError, match="scope_not_allowed"):
        create_handshake_credential("flutter", "designer", "user-1", scope="a|b")


def test_verify_rejects_unregistered_app_credential(monkeypatch):
    """退登记的 app 其存量凭证一并拒绝（防注册表收紧后被绕过）。"""
    cred = create_handshake_credential("flutter", "designer", "user-1", scope="a2a:task")
    monkeypatch.delitem(hs.REGISTERED_APPS, "flutter")
    result = verify_handshake_credential(
        cred["token"], app_id="flutter", agent_name="designer", actor_user_id="user-1"
    )
    assert result["valid"] is False
    assert result["reason"] == "app_unregistered"


def test_verify_agent_identity_ok():
    result = verify_agent_identity("designer")
    assert result["verified"] is True
    assert len(result["aid"]) == 28
    assert result["acdl"]["agent"]["name"] == "designer"


def test_verify_agent_identity_aid_match():
    aid = verify_agent_identity("designer")["aid"]
    result = verify_agent_identity("designer", expected_aid=aid)
    assert result["match"] is True
    assert result["verified"] is True


def test_verify_agent_identity_aid_mismatch():
    result = verify_agent_identity("designer", expected_aid="0" * 28)
    assert result["verified"] is False
    assert result["match"] is False

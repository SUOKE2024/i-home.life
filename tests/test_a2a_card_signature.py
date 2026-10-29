"""A2A Agent Card Ed25519 签名（原生签名对象，非 JWS）单元与端到端测试。"""

import base64

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.services.agent_card_signature import (
    canonical_payload,
    public_key_document,
    sign_agent_card,
    verify_agent_card,
)

# 固定测试种子（32 字节），仅用于测试，不是生产密钥
TEST_SEED_B64 = base64.b64encode(bytes(range(32))).decode()


@pytest.fixture
def signing_seed(monkeypatch):
    """注入测试种子；teardown 由 monkeypatch 自动还原（禁止 cache_clear）。"""
    monkeypatch.setattr(get_settings(), "a2a_card_ed25519_seed", TEST_SEED_B64)
    return TEST_SEED_B64


def test_sign_and_verify_roundtrip(signing_seed):
    card = {"name": "i-home.life", "version": "1.19.2", "skills": [{"name": "CareAgent"}]}
    sig = sign_agent_card(card)
    assert sig and sig["alg"] == "Ed25519" and sig["sig"]
    signed = {**card, "signature": sig}
    assert verify_agent_card(signed, public_key_document()["public_key"]) is True


def test_signature_excludes_itself_from_payload(signing_seed):
    card = {"name": "n", "version": "v"}
    payload_before = canonical_payload(card)
    sig = sign_agent_card(card)
    payload_after = canonical_payload({**card, "signature": sig})
    assert payload_before == payload_after


def test_tampered_card_fails_verification(signing_seed):
    card = {"name": "n", "version": "v"}
    sig = sign_agent_card(card)
    tampered = {**card, "version": "v2", "signature": sig}
    assert verify_agent_card(tampered, public_key_document()["public_key"]) is False


def test_unconfigured_seed_degrades_to_unsigned(monkeypatch):
    monkeypatch.setattr(get_settings(), "a2a_card_ed25519_seed", "")
    assert sign_agent_card({"name": "n"}) is None
    assert public_key_document() is None


@pytest.mark.asyncio
async def test_card_endpoint_carries_verifiable_signature(client: AsyncClient, signing_seed):
    card = (await client.get("/.well-known/agent-card")).json()
    assert card["signature"]["alg"] == "Ed25519"
    key_doc = (await client.get("/.well-known/agent-card-public-key")).json()
    assert key_doc["fingerprint"] == card["signature"]["kid"]
    assert verify_agent_card(card, key_doc["public_key"]) is True


@pytest.mark.asyncio
async def test_card_exposes_official_a2a_fields(client: AsyncClient):
    """官方字段映射：对端按标准键名即可发现与接入，且不破坏自有字段。"""
    card = (await client.get("/.well-known/agent-card")).json()
    assert card["url"] == "https://i-home.life/api/a2a/tasks/send"
    assert card["provider"]["organization"] == "索克家居"
    assert card["supportedInterfaces"][0]["protocolBinding"] == "HTTP+JSON"
    assert card["supportedInterfaces"][0]["url"] == card["url"]
    assert card["defaultInputModes"] == ["text/plain", "application/json"]
    assert card["defaultOutputModes"] == ["text/plain", "application/json"]
    assert card["securitySchemes"]["paseto"]["scheme"] == "bearer"
    assert card["registered_agents"], "自有字段必须保留"


@pytest.mark.asyncio
async def test_public_key_endpoint_honest_503_without_seed(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(get_settings(), "a2a_card_ed25519_seed", "")
    resp = await client.get("/.well-known/agent-card-public-key")
    assert resp.status_code == 503

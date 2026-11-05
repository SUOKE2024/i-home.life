"""A2A Agent Card Ed25519 签名测试（W-4 2026-11-05：对外统一 JWS 信封）。"""

import base64

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.services.agent_card_signature import (
    canonical_payload,
    public_key_document,
    sign_agent_card,
    sign_agent_card_jws,
    verify_agent_card,
    verify_agent_card_jws,
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
    assert sig and sig["alg"] == "EdDSA" and sig["sig"]
    signed = {**card, "signature": sig}
    assert verify_agent_card(signed, public_key_document()["public_key"]) is True



def test_jws_roundtrip_and_tamper_detection(signing_seed):
    """JWS 信封：正签可验，篡改 payload 必须失败。"""
    card = {"name": "i-home.life", "version": "1.19.2"}
    env = sign_agent_card_jws(card)
    assert env and env["signatures"][0]["protected"]
    pub = public_key_document()["public_key_b64url"]
    assert verify_agent_card_jws(env, pub)["version"] == "1.19.2"

    tampered = {**env, "payload": env["payload"][:-4] + "AAAA"}
    with pytest.raises(ValueError):
        verify_agent_card_jws(tampered, pub)


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
async def test_card_endpoint_carries_verifiable_jws(client: AsyncClient, signing_seed):
    """W-4：对外发现端点发 JWS 信封，且三端同一套验签代码可通。"""
    doc = (await client.get("/.well-known/agent-card.json")).json()
    assert doc["signed"] is True
    assert doc["signatures"], "JWS 信封必须带签名"
    key_doc = (await client.get("/.well-known/agent-card-public-key")).json()
    inner = verify_agent_card_jws(doc, key_doc["public_key_b64url"])
    assert inner["name"] == "索克家居"
    assert inner["registered_agents"], "内层必须是完整卡片"


@pytest.mark.asyncio
async def test_all_discovery_aliases_same_shape(client: AsyncClient, signing_seed):
    """W-4：三个发现别名内容一致（都发 JWS 信封），避免"同一节点两种卡片形态"。"""
    docs = [
        (await client.get(path)).json()
        for path in (".well-known/agent-card", ".well-known/agent.json", ".well-known/agent-card.json")
    ]
    for doc in docs:
        assert doc["signed"] is True and doc["signatures"]
    assert docs[0]["payload"] == docs[1]["payload"] == docs[2]["payload"]


@pytest.mark.asyncio
async def test_unsigned_degrades_honestly(client: AsyncClient, monkeypatch):
    """未配置种子：裸卡 + signed:false，不伪装已签名。"""
    monkeypatch.setattr(get_settings(), "a2a_card_ed25519_seed", "")
    card = (await client.get("/.well-known/agent-card")).json()
    assert card["signed"] is False
    assert "payload" not in card and card["name"] == "索克家居"


@pytest.mark.asyncio
async def test_public_key_doc_dual_encoding(client: AsyncClient, signing_seed):
    """W-3/W-5：公钥双编码 + alg/crv 分离标注。"""
    key_doc = (await client.get("/.well-known/agent-card-public-key")).json()
    assert key_doc["alg"] == "EdDSA" and key_doc["crv"] == "Ed25519"
    assert key_doc["public_key"] == key_doc["public_key_b64url"]
    assert "=" in key_doc["public_key_base64"]
    assert key_doc["fingerprint"] == key_doc["public_key_b64url"][:8]


@pytest.mark.asyncio
async def test_card_exposes_official_a2a_fields(client: AsyncClient):
    """官方字段映射：对端按标准键名即可发现与接入，且不破坏自有字段。"""
    card = (await client.get("/.well-known/agent-card")).json()
    assert card["url"] == "https://i-home.life/api/a2a"
    assert card["provider"]["organization"] == "索克家居"
    assert card["supportedInterfaces"][0]["protocolBinding"] == "JSONRPC"
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

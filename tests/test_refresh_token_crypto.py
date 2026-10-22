from __future__ import annotations

import asyncio

from app.services.refresh_token_store import (
    decrypt_refresh_token,
    encrypt_refresh_token,
    read_refresh_token_text,
)


class _FakeRow:
    def __init__(self, token_text: str):
        self.token_text = token_text


class _FakeDB:
    async def flush(self):
        return None


def test_refresh_token_encrypt_roundtrip():
    token = "v4.public.refresh-token-value"
    blob = encrypt_refresh_token(token)
    assert blob.startswith("v1.")
    assert token not in blob
    assert decrypt_refresh_token(blob) == token


def test_refresh_token_legacy_plaintext_passthrough():
    assert decrypt_refresh_token("legacy-plaintext-token") == "legacy-plaintext-token"
    assert decrypt_refresh_token(None) is None


def test_refresh_token_tampered_ciphertext_returns_none():
    blob = encrypt_refresh_token("token")
    tampered = blob[:-2] + "AA"
    assert decrypt_refresh_token(tampered) is None


def test_read_refresh_token_text_migrates_legacy_plaintext():
    row = _FakeRow("legacy-plaintext-token")
    db = _FakeDB()

    value = asyncio.run(read_refresh_token_text(db, row))

    assert value == "legacy-plaintext-token"
    assert row.token_text.startswith("v1.")
    assert decrypt_refresh_token(row.token_text) == "legacy-plaintext-token"


def test_read_refresh_token_text_reads_ciphertext():
    row = _FakeRow(encrypt_refresh_token("ciphertext-token"))
    db = _FakeDB()

    assert asyncio.run(read_refresh_token_text(db, row)) == "ciphertext-token"


class _CaptureDB:
    def __init__(self):
        self.row = None

    def add(self, row):
        self.row = row

    async def flush(self):
        return None


def test_persist_refresh_token_stores_ciphertext_only():
    from app.services.refresh_token_store import persist_refresh_token

    pair = {
        "refresh_jti": "jti-test",
        "refresh_token": "v4.public.refresh-token-value",
        "family_id": "family-test",
    }
    db = _CaptureDB()

    row = asyncio.run(persist_refresh_token(db, pair, "user-test"))

    assert row.token_text.startswith("v1.")
    assert pair["refresh_token"] not in row.token_text
    assert decrypt_refresh_token(row.token_text) == pair["refresh_token"]

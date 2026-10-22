from __future__ import annotations

import pytest

from app.auth import paseto_handler
from app.auth.paseto_handler import TokenInvalidError, verify_refresh_token, verify_token


def _patch_decode(monkeypatch, payload: dict, footer: dict | None = None):
    monkeypatch.setattr(
        paseto_handler,
        "_decode_public",
        lambda token: (payload, footer or {}),
    )


def test_access_token_accepts_matching_issuer_and_audience(monkeypatch):
    _patch_decode(monkeypatch, {"iss": "i-home-auth", "aud": "i-home-app", "type": "access"})
    payload = verify_token("v4.public.token")
    assert payload["iss"] == "i-home-auth"


def test_access_token_rejects_wrong_issuer(monkeypatch):
    _patch_decode(monkeypatch, {"iss": "suoke-life-auth", "aud": "i-home-app", "type": "access"})
    with pytest.raises(TokenInvalidError, match="签发者"):
        verify_token("v4.public.token")


def test_access_token_rejects_wrong_audience(monkeypatch):
    _patch_decode(monkeypatch, {"iss": "i-home-auth", "aud": "suoke-life-app", "type": "access"})
    with pytest.raises(TokenInvalidError, match="受众"):
        verify_token("v4.public.token")


def test_access_token_allows_legacy_without_issuer_audience(monkeypatch):
    _patch_decode(monkeypatch, {"type": "access"})
    assert verify_token("v4.public.token")["type"] == "access"


def test_refresh_token_rejects_wrong_issuer(monkeypatch):
    _patch_decode(
        monkeypatch,
        {"iss": "suoke-life-auth", "aud": "i-home-app", "type": "refresh"},
        {"typ": "rt"},
    )
    with pytest.raises(TokenInvalidError, match="签发者"):
        verify_refresh_token("v4.public.token")

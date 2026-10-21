"""verify_google_token against a fake Google userinfo endpoint (no network, no database)."""

import asyncio

from services.google_auth_service import GoogleIdentity, verify_google_token


def test_valid_token_returns_the_identity(google_userinfo):
    google_userinfo(email="Someone@Example.com", sub="sub-1", name="Someone", picture="https://example.com/p.jpg")
    identity = asyncio.run(verify_google_token("token"))
    assert identity == GoogleIdentity(
        sub="sub-1", email="someone@example.com", name="Someone", picture="https://example.com/p.jpg"
    )


def test_token_issued_to_another_app_returns_none(google_userinfo):
    google_userinfo(email="someone@example.com", sub="sub-1", aud="another-apps-client-id")
    assert asyncio.run(verify_google_token("token")) is None


def test_token_google_rejects_returns_none(google_userinfo):
    google_userinfo(status_code=401)
    assert asyncio.run(verify_google_token("token")) is None


def test_identity_without_a_sub_returns_none(google_userinfo):
    google_userinfo(email="someone@example.com", sub="")
    assert asyncio.run(verify_google_token("token")) is None


def test_identity_without_an_email_returns_none(google_userinfo):
    google_userinfo(email="", sub="sub-1")
    assert asyncio.run(verify_google_token("token")) is None

"""Roadmap #H, F5 - api/rate_limit.py's session-or-IP key function, and the per-email login limit
that shares its storage with the shared Limiter."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.testclient import TestClient

from api.rate_limit import _session_or_ip_key, enforce_login_email_limit
from config import get_settings
from conftest import mint_invite_code
from main import app


def _fake_request(*, client_host: str = "1.2.3.4", token: str | None = None, extra_headers=()) -> Request:
    headers = list(extra_headers)
    if token is not None:
        headers.append((b"cookie", f"access_token={token}".encode()))
    scope = {"type": "http", "client": (client_host, 12345), "headers": headers}
    return Request(scope)


def _make_token(user_id: uuid.UUID | None = None) -> str:
    # Mirrors AuthService.create_access_token exactly, but skips the DB round-trip a real
    # registration would need - _session_or_ip_key decodes locally and never looks the user up, so
    # a token for an id that was never actually registered is a legitimate test of that fact.
    now = datetime.now(UTC)
    payload = {"sub": str(user_id or uuid.uuid4()), "iat": now, "exp": now + timedelta(days=1)}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


class TestSessionOrIpKey:
    def test_no_cookie_falls_back_to_client_ip(self):
        request = _fake_request(client_host="1.2.3.4")

        assert _session_or_ip_key(request) == "1.2.3.4"

    def test_valid_cookie_keys_by_account_not_ip(self):
        user_id = uuid.uuid4()
        request = _fake_request(client_host="1.2.3.4", token=_make_token(user_id))

        assert _session_or_ip_key(request) == f"user:{user_id}"

    def test_same_account_from_different_ips_shares_one_key(self):
        token = _make_token()
        a = _fake_request(client_host="1.1.1.1", token=token)
        b = _fake_request(client_host="2.2.2.2", token=token)

        assert _session_or_ip_key(a) == _session_or_ip_key(b)

    def test_different_accounts_behind_the_same_ip_get_different_keys(self):
        a = _fake_request(client_host="1.1.1.1", token=_make_token())
        b = _fake_request(client_host="1.1.1.1", token=_make_token())

        assert _session_or_ip_key(a) != _session_or_ip_key(b)

    def test_garbage_cookie_falls_back_to_client_ip(self):
        request = _fake_request(client_host="9.9.9.9", token="not-a-real-jwt")

        assert _session_or_ip_key(request) == "9.9.9.9"

    def test_does_not_trust_x_real_ip_or_x_forwarded_for(self):
        # Decision [A] (docs/TODO/NEW-AUTH.md) - this app assumes nothing about what's in front of
        # it, unlike the old get_client_ip this replaced (which trusted X-Real-IP unconditionally,
        # a deployment-specific assumption this app no longer makes).
        request = _fake_request(
            client_host="1.2.3.4",
            extra_headers=[(b"x-real-ip", b"6.6.6.6"), (b"x-forwarded-for", b"7.7.7.7")],
        )

        assert _session_or_ip_key(request) == "1.2.3.4"


class TestLoginEmailLimit:
    def test_allows_five_then_blocks_the_sixth(self):
        email = f"{uuid.uuid4().hex}@example.com"
        for _ in range(5):
            enforce_login_email_limit(email)  # must not raise

        with pytest.raises(HTTPException) as exc_info:
            enforce_login_email_limit(email)
        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers

    def test_a_different_email_is_unaffected_by_another_emails_exhausted_budget(self):
        exhausted = f"{uuid.uuid4().hex}@example.com"
        other = f"{uuid.uuid4().hex}@example.com"
        for _ in range(5):
            enforce_login_email_limit(exhausted)
        with pytest.raises(HTTPException):
            enforce_login_email_limit(exhausted)

        enforce_login_email_limit(other)  # must not raise


class TestLoginRateLimitEndToEnd:
    """Same guarantee as TestLoginEmailLimit, but through the real POST /login route, from
    several distinct simulated source IPs (starlette.testclient.TestClient's own `client=(ip,
    port)` constructor param, not a spoofable header - see test_does_not_trust_x_real_ip_or_
    x_forwarded_for above for why a header wouldn't prove anything). Proves the wiring in
    api/auth_api.py's login handler, not just the isolated function."""

    def test_same_email_from_six_different_ips_still_429s_on_the_sixth(self, client):
        unique = uuid.uuid4().hex[:8]
        email = f"ratelimit-{unique}@example.com"
        client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": f"ratelimit-{unique}",
                "full_name": "Rate Limit Test",
                "password": "correct-horse-battery-staple",
                "invite_code": mint_invite_code(),
            },
        )

        statuses = []
        for i in range(6):
            with TestClient(app, client=(f"10.0.0.{i}", 12345)) as ip_client:
                response = ip_client.post(
                    "/api/v1/auth/login",
                    json={"email": email, "password": "wrong-password"},
                )
                statuses.append(response.status_code)

        # Each request came from a distinct IP, so the route's own IP-keyed decorator (5/minute,
        # same limit) never itself accumulates past one hit per IP - only the per-email check
        # (api/rate_limit.py's enforce_login_email_limit) can be what blocks the 6th.
        assert statuses[:5] == [401] * 5
        assert statuses[5] == 429

    def test_a_different_email_from_a_fresh_ip_is_unaffected(self, client):
        unique = uuid.uuid4().hex[:8]
        email = f"ratelimit-other-{unique}@example.com"
        client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": f"ratelimit-other-{unique}",
                "full_name": "Rate Limit Other",
                "password": "correct-horse-battery-staple",
                "invite_code": mint_invite_code(),
            },
        )

        with TestClient(app, client=("10.1.0.1", 12345)) as ip_client:
            response = ip_client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "wrong-password"},
            )

        assert response.status_code == 401

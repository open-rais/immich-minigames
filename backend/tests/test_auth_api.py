import time
import uuid
from uuid import UUID

from conftest import mint_invite_code

from persistence.users import UserModel


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _promote_to_admin(db_session, user_id: str) -> None:
    user = db_session.get(UserModel, UUID(user_id))
    user.is_admin = True
    db_session.commit()


def _register(client, **overrides) -> dict:
    body = {
        "email": f"{_unique('user')}@example.com",
        "username": _unique("user"),
        "full_name": "Test User",
        "password": "correct-horse-battery-staple",
        "invite_code": mint_invite_code(),
    }
    body.update(overrides)
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 201
    return body


class TestRegister:
    def test_without_an_invite_code_returns_400(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"{_unique('user')}@example.com",
                "username": _unique("user"),
                "full_name": "Test User",
                "password": "correct-horse-battery-staple",
            },
        )

        assert response.status_code == 400

    def test_sets_a_session_cookie_and_returns_the_user(self, client):
        body = _register(client)

        assert "access_token" in client.cookies
        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["email"] == body["email"]
        assert me.json()["username"] == body["username"]
        assert "password" not in me.json()

    def test_duplicate_email_returns_409(self, client):
        body = _register(client)

        response = client.post(
            "/api/v1/auth/register",
            # Fresh invite_code - body's own was already burned by the _register() call above,
            # and this test wants to hit the email-uniqueness check, not an already-used invite.
            json={**body, "username": _unique("other"), "invite_code": mint_invite_code()},
        )

        assert response.status_code == 409

    def test_duplicate_username_returns_409(self, client):
        body = _register(client)

        response = client.post(
            "/api/v1/auth/register",
            json={**body, "email": f"{_unique('other')}@example.com", "invite_code": mint_invite_code()},
        )

        assert response.status_code == 409

    def test_short_password_returns_422(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"{_unique('user')}@example.com",
                "username": _unique("user"),
                "full_name": "Test User",
                "password": "short",
            },
        )

        assert response.status_code == 422


class TestLogin:
    def test_correct_credentials_sets_cookie(self, client):
        body = _register(client)
        client.cookies.clear()

        response = client.post(
            "/api/v1/auth/login",
            json={"email": body["email"], "password": body["password"]},
        )

        assert response.status_code == 200
        assert "access_token" in client.cookies

    def test_wrong_password_returns_401(self, client):
        body = _register(client)
        client.cookies.clear()

        response = client.post(
            "/api/v1/auth/login",
            json={"email": body["email"], "password": "wrong-password"},
        )

        assert response.status_code == 401

    def test_unknown_email_returns_401(self, client):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "whatever123"},
        )

        assert response.status_code == 401

    def test_cookie_has_the_expected_attributes(self, client):
        body = _register(client)
        client.cookies.clear()

        response = client.post(
            "/api/v1/auth/login",
            json={"email": body["email"], "password": body["password"]},
        )

        set_cookie = response.headers.get("set-cookie")
        assert "HttpOnly" in set_cookie
        assert "SameSite=lax" in set_cookie
        assert "Path=/" in set_cookie
        # cookie_secure defaults to False in this test env (see config.py) - Secure is omitted
        # from the header entirely when False, never written as "Secure=False".
        assert "Secure" not in set_cookie


class TestLogout:
    def test_clears_the_cookie(self, client):
        _register(client)

        response = client.post("/api/v1/auth/logout")

        assert response.status_code == 204
        me = client.get("/api/v1/auth/me")
        assert me.status_code == 401

    def test_deletes_the_cookie_with_the_same_attributes_it_was_set_with(self, client):
        # Browsers can fail to process the deletion if these don't match what the cookie was
        # created with.
        _register(client)

        response = client.post("/api/v1/auth/logout")

        set_cookie = response.headers.get("set-cookie")
        assert "HttpOnly" in set_cookie
        assert "SameSite=lax" in set_cookie
        assert "Path=/" in set_cookie
        assert "Secure" not in set_cookie
        assert "Max-Age=0" in set_cookie


class TestMe:
    def test_without_cookie_returns_401(self, client):
        client.cookies.clear()

        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401


class TestChangePassword:
    def test_correct_current_password_sets_a_new_cookie(self, client):
        body = _register(client)

        response = client.patch(
            "/api/v1/auth/me/password",
            json={"current_password": body["password"], "new_password": "new-password-123"},
        )

        assert response.status_code == 200
        assert "access_token" in response.cookies

    def test_wrong_current_password_returns_401(self, client):
        _register(client)

        response = client.patch(
            "/api/v1/auth/me/password",
            json={"current_password": "wrong-password", "new_password": "new-password-123"},
        )

        assert response.status_code == 401

    def test_the_pre_change_cookie_no_longer_authenticates(self, client):
        body = _register(client)
        pre_change_cookie = client.cookies["access_token"]
        # JWT's iat is an integer-second NumericDate (RFC 7519) - without this, register()'s iat and
        # change_password()'s password_changed_at could truncate to the same second and the strict
        # `<` revocation check in get_user_from_token wouldn't reject the old cookie, making this
        # test flaky depending on execution speed rather than testing a real bug.
        time.sleep(1.1)

        response = client.patch(
            "/api/v1/auth/me/password",
            json={"current_password": body["password"], "new_password": "new-password-123"},
        )
        assert response.status_code == 200

        client.cookies.set("access_token", pre_change_cookie)
        me = client.get("/api/v1/auth/me")

        assert me.status_code == 401

    def test_without_cookie_returns_401(self, client):
        client.cookies.clear()

        response = client.patch(
            "/api/v1/auth/me/password",
            json={"current_password": "whatever123", "new_password": "new-password-123"},
        )

        assert response.status_code == 401


def _register_with_id(client, **overrides) -> dict:
    # _register() above returns just the request body (no id) - other tests in this file rely on
    # that exact shape for **body spreading, so this is a local addition rather than a change to
    # the shared helper. Registering logs the client in as that user, so /auth/me reads its id.
    body = _register(client, **overrides)
    return {**body, "id": client.get("/api/v1/auth/me").json()["id"]}


class TestResetPassword:
    def test_full_flow_admin_generates_target_resets_old_password_stops_working(self, client, db_session):
        target = _register_with_id(client)
        admin = _register_with_id(client)
        _promote_to_admin(db_session, admin["id"])

        created = client.post(f"/api/v1/admin/users/{target['id']}/password-reset")
        assert created.status_code == 201
        token = created.json()["token"]

        client.cookies.clear()
        reset_response = client.post(
            "/api/v1/auth/reset-password", json={"token": token, "new_password": "new-password-123"}
        )
        assert reset_response.status_code == 204
        assert "access_token" not in reset_response.cookies  # no auto-login, see plan/AuthService.reset_password

        old_login = client.post("/api/v1/auth/login", json={"email": target["email"], "password": target["password"]})
        assert old_login.status_code == 401

        new_login = client.post("/api/v1/auth/login", json={"email": target["email"], "password": "new-password-123"})
        assert new_login.status_code == 200

    def test_reusing_the_same_token_returns_400(self, client, db_session):
        target = _register_with_id(client)
        admin = _register_with_id(client)
        _promote_to_admin(db_session, admin["id"])
        token = client.post(f"/api/v1/admin/users/{target['id']}/password-reset").json()["token"]
        client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "new-password-123"})

        response = client.post(
            "/api/v1/auth/reset-password", json={"token": token, "new_password": "another-password-456"}
        )

        assert response.status_code == 400

    def test_unknown_token_returns_400(self, client):
        response = client.post(
            "/api/v1/auth/reset-password", json={"token": "not-a-real-token", "new_password": "new-password-123"}
        )

        assert response.status_code == 400

    def test_short_new_password_returns_422(self, client, db_session):
        target = _register_with_id(client)
        admin = _register_with_id(client)
        _promote_to_admin(db_session, admin["id"])
        token = client.post(f"/api/v1/admin/users/{target['id']}/password-reset").json()["token"]

        response = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "short"})

        assert response.status_code == 422


class TestRateLimit:
    def test_register_returns_429_after_the_limit(self, client):
        responses = [
            client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"{_unique('user')}@example.com",
                    "username": _unique("user"),
                    "full_name": "Test User",
                    "password": "correct-horse-battery-staple",
                    "invite_code": mint_invite_code(),
                },
            )
            for _ in range(4)
        ]

        assert [r.status_code for r in responses[:3]] == [201, 201, 201]
        assert responses[3].status_code == 429

    def test_login_returns_429_after_the_limit(self, client):
        body = _register(client)
        client.cookies.clear()

        responses = [
            client.post(
                "/api/v1/auth/login",
                json={"email": body["email"], "password": "wrong-password"},
            )
            for _ in range(6)
        ]

        assert [r.status_code for r in responses[:5]] == [401] * 5
        assert responses[5].status_code == 429

import uuid


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _register(client, **overrides) -> dict:
    body = {
        "email": f"{_unique('user')}@example.com",
        "username": _unique("user"),
        "full_name": "Test User",
        "password": "correct-horse-battery-staple",
    }
    body.update(overrides)
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 201
    return body


class TestRegister:
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
            json={**body, "username": _unique("other")},
        )

        assert response.status_code == 409

    def test_duplicate_username_returns_409(self, client):
        body = _register(client)

        response = client.post(
            "/api/v1/auth/register",
            json={**body, "email": f"{_unique('other')}@example.com"},
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
        # docs/TODO/CODE-REVIEW.md #12 - browsers can fail to process the deletion if these don't
        # match what the cookie was created with.
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

import uuid
from uuid import UUID

from conftest import mint_invite_code
from persistence.users import UserModel


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


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
    return {**body, "id": response.json()["id"]}


def _register_as_admin(client, db_session) -> dict:
    admin = _register(client)
    user = db_session.get(UserModel, UUID(admin["id"]))
    user.is_admin = True
    db_session.commit()
    return admin


class TestCreateInvite:
    def test_anonymous_returns_401(self, client):
        client.cookies.clear()

        response = client.post("/api/v1/admin/invites")

        assert response.status_code == 401

    def test_non_admin_returns_403(self, client):
        _register(client)

        response = client.post("/api/v1/admin/invites")

        assert response.status_code == 403

    def test_admin_creates_an_invite_with_a_usable_token(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.post("/api/v1/admin/invites")

        assert response.status_code == 201
        body = response.json()
        assert "token" in body and body["token"]
        assert "id" in body
        assert "expires_at" in body

        # The token actually works for registration.
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"{_unique('invited')}@example.com",
                "username": _unique("invited"),
                "full_name": "Invited User",
                "password": "correct-horse-battery-staple",
                "invite_code": body["token"],
            },
        )
        assert register_response.status_code == 201


class TestListInvites:
    def test_lists_created_invites_with_pending_status(self, client, db_session):
        _register_as_admin(client, db_session)

        created = client.post("/api/v1/admin/invites").json()
        response = client.get("/api/v1/admin/invites")

        assert response.status_code == 200
        matching = [i for i in response.json() if i["id"] == created["id"]]
        assert len(matching) == 1
        assert matching[0]["status"] == "pending"

    def test_a_used_invite_shows_used_status(self, client, db_session):
        _register_as_admin(client, db_session)
        created = client.post("/api/v1/admin/invites").json()
        client.cookies.clear()
        client.post(
            "/api/v1/auth/register",
            json={
                "email": f"{_unique('invited')}@example.com",
                "username": _unique("invited"),
                "full_name": "Invited User",
                "password": "correct-horse-battery-staple",
                "invite_code": created["token"],
            },
        )
        _register_as_admin(client, db_session)  # log back in as (a fresh) admin to list

        response = client.get("/api/v1/admin/invites")

        matching = [i for i in response.json() if i["id"] == created["id"]]
        assert matching[0]["status"] == "used"
        assert matching[0]["used_at"] is not None

    def test_pagination_limit_caps_the_page_and_offset_reaches_the_rest(self, client, db_session):
        _register_as_admin(client, db_session)
        # 7 fresh invites, newest-first order (InviteService.list_invites) - guaranteed to be the 7
        # newest kind="invite" rows at query time, same reasoning as test_admin_api.py's equivalent.
        created_ids = {client.post("/api/v1/admin/invites").json()["id"] for _ in range(7)}

        first_page = client.get("/api/v1/admin/invites", params={"limit": 5, "offset": 0})
        second_page = client.get("/api/v1/admin/invites", params={"limit": 5, "offset": 5})

        assert first_page.status_code == 200
        assert len(first_page.json()) == 5
        assert second_page.status_code == 200
        seen_ids = {i["id"] for i in first_page.json()} | {i["id"] for i in second_page.json()}
        assert created_ids <= seen_ids


class TestRevokeInvite:
    def test_revoking_a_pending_invite_makes_it_unusable(self, client, db_session):
        _register_as_admin(client, db_session)
        created = client.post("/api/v1/admin/invites").json()

        response = client.delete(f"/api/v1/admin/invites/{created['id']}")
        assert response.status_code == 204

        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"{_unique('invited')}@example.com",
                "username": _unique("invited"),
                "full_name": "Invited User",
                "password": "correct-horse-battery-staple",
                "invite_code": created["token"],
            },
        )
        assert register_response.status_code == 400

    def test_revoking_an_already_used_invite_returns_404(self, client, db_session):
        _register_as_admin(client, db_session)
        created = client.post("/api/v1/admin/invites").json()
        client.post(
            "/api/v1/auth/register",
            json={
                "email": f"{_unique('invited')}@example.com",
                "username": _unique("invited"),
                "full_name": "Invited User",
                "password": "correct-horse-battery-staple",
                "invite_code": created["token"],
            },
        )
        _register_as_admin(client, db_session)

        response = client.delete(f"/api/v1/admin/invites/{created['id']}")

        assert response.status_code == 404

    def test_revoking_an_unknown_id_returns_404(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.delete(f"/api/v1/admin/invites/{uuid.uuid4()}")

        assert response.status_code == 404

    def test_non_admin_returns_403(self, client, db_session):
        _register_as_admin(client, db_session)
        created = client.post("/api/v1/admin/invites").json()
        _register(client)  # logs in as a non-admin, replacing the admin session

        response = client.delete(f"/api/v1/admin/invites/{created['id']}")

        assert response.status_code == 403

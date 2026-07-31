import uuid
from uuid import UUID

from conftest import mint_invite_code

from persistence.users import UserModel
from services.auth_service import AuthService


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


def _promote_to_admin(db_session, user_id: str) -> None:
    # Registering already logs the client in as that user (see _register) - promoting directly
    # through the DB, same technique as test_admin_bootstrap.py, keeps that session valid while
    # flipping is_admin, rather than going through a promotion endpoint this feature doesn't have.
    user = db_session.get(UserModel, UUID(user_id))
    user.is_admin = True
    db_session.commit()


class TestListUsers:
    def test_anonymous_returns_401(self, client):
        client.cookies.clear()

        response = client.get("/api/v1/admin/users")

        assert response.status_code == 401

    def test_non_admin_returns_403(self, client):
        _register(client)

        response = client.get("/api/v1/admin/users")

        assert response.status_code == 403

    def test_admin_lists_every_registered_user(self, client, db_session):
        first = _register(client)
        second = _register(client)
        admin = _register(client)
        _promote_to_admin(db_session, admin["id"])

        response = client.get("/api/v1/admin/users")

        assert response.status_code == 200
        emails = {u["email"] for u in response.json()}
        assert {first["email"], second["email"], admin["email"]} <= emails

    def test_pagination_limit_caps_the_page_and_offset_reaches_the_rest(self, client, db_session):
        # 7 fresh users, seeded directly through AuthService (not the rate-limited HTTP endpoint -
        # /auth/register is capped at 3/minute, see api/auth_api.py) - these are guaranteed to be
        # the 7 newest rows in the whole (shared, never-reset-per-test) table at query time, so
        # under the newest-first order they land across exactly two pages of limit=5 regardless of
        # how many older rows other tests left behind.
        auth_service = AuthService(db_session)
        seeded = [
            auth_service.register(
                email=f"{_unique('pag')}@example.com",
                username=_unique("pag"),
                full_name="Pagination Test User",
                password="correct-horse-battery-staple",
                invite_code=mint_invite_code(),
            )
            for _ in range(7)
        ]
        _promote_to_admin(db_session, str(seeded[-1].id))
        client.post("/api/v1/auth/login", json={"email": seeded[-1].email, "password": "correct-horse-battery-staple"})
        our_emails = {u.email for u in seeded}

        first_page = client.get("/api/v1/admin/users", params={"limit": 5, "offset": 0})
        second_page = client.get("/api/v1/admin/users", params={"limit": 5, "offset": 5})

        assert first_page.status_code == 200
        assert len(first_page.json()) == 5
        assert second_page.status_code == 200
        seen_emails = {u["email"] for u in first_page.json()} | {u["email"] for u in second_page.json()}
        assert our_emails <= seen_emails


class TestUpdateUser:
    def test_admin_can_rename_another_users_account(self, client, db_session):
        target = _register(client)
        admin = _register(client)
        _promote_to_admin(db_session, admin["id"])
        new_username = _unique("renamed")

        response = client.patch(
            f"/api/v1/admin/users/{target['id']}",
            json={"username": new_username, "full_name": "Renamed User"},
        )

        assert response.status_code == 200
        assert response.json()["username"] == new_username
        assert response.json()["full_name"] == "Renamed User"

    def test_taking_another_users_username_returns_409(self, client, db_session):
        target = _register(client)
        taken = _register(client)
        admin = _register(client)
        _promote_to_admin(db_session, admin["id"])

        response = client.patch(f"/api/v1/admin/users/{target['id']}", json={"username": taken["username"]})

        assert response.status_code == 409

    def test_unknown_user_id_returns_404(self, client, db_session):
        admin = _register(client)
        _promote_to_admin(db_session, admin["id"])

        response = client.patch(f"/api/v1/admin/users/{uuid.uuid4()}", json={"full_name": "Nobody"})

        assert response.status_code == 404

    def test_non_admin_returns_403(self, client):
        target = _register(client)
        _register(client)

        response = client.patch(f"/api/v1/admin/users/{target['id']}", json={"full_name": "Nope"})

        assert response.status_code == 403


class TestUpdateUserSkin:
    def test_admin_can_set_another_users_skin_to_a_real_person(self, client, db_session, immich_service):
        [person] = immich_service.get_persons(named_only=True, limit=1)
        target = _register(client)
        admin = _register(client)
        _promote_to_admin(db_session, admin["id"])

        response = client.put(f"/api/v1/admin/users/{target['id']}/skin", json={"person_id": str(person.id)})

        assert response.status_code == 200
        assert response.json()["skin_person_id"] == str(person.id)

    def test_admin_can_clear_another_users_skin(self, client, db_session):
        target = _register(client)
        admin = _register(client)
        _promote_to_admin(db_session, admin["id"])

        response = client.put(f"/api/v1/admin/users/{target['id']}/skin", json={"person_id": None})

        assert response.status_code == 200
        assert response.json()["skin_person_id"] is None

    def test_unknown_person_id_returns_404(self, client, db_session):
        target = _register(client)
        admin = _register(client)
        _promote_to_admin(db_session, admin["id"])

        response = client.put(f"/api/v1/admin/users/{target['id']}/skin", json={"person_id": str(uuid.uuid4())})

        assert response.status_code == 404

    def test_unknown_user_id_returns_404(self, client, db_session):
        admin = _register(client)
        _promote_to_admin(db_session, admin["id"])

        response = client.put(f"/api/v1/admin/users/{uuid.uuid4()}/skin", json={"person_id": None})

        assert response.status_code == 404


class TestCreatePasswordReset:
    def test_anonymous_returns_401(self, client):
        target = _register(client)
        client.cookies.clear()

        response = client.post(f"/api/v1/admin/users/{target['id']}/password-reset")

        assert response.status_code == 401

    def test_non_admin_returns_403(self, client):
        target = _register(client)
        _register(client)

        response = client.post(f"/api/v1/admin/users/{target['id']}/password-reset")

        assert response.status_code == 403

    def test_unknown_user_id_returns_404(self, client, db_session):
        admin = _register(client)
        _promote_to_admin(db_session, admin["id"])

        response = client.post(f"/api/v1/admin/users/{uuid.uuid4()}/password-reset")

        assert response.status_code == 404

    def test_admin_generates_a_usable_reset_token(self, client, db_session):
        target = _register(client)
        admin = _register(client)
        _promote_to_admin(db_session, admin["id"])

        response = client.post(f"/api/v1/admin/users/{target['id']}/password-reset")

        assert response.status_code == 201
        body = response.json()
        assert "token" in body and body["token"]
        assert "id" in body
        assert "expires_at" in body

        reset_response = client.post(
            "/api/v1/auth/reset-password", json={"token": body["token"], "new_password": "new-password-123"}
        )
        assert reset_response.status_code == 204


class TestAuditEvents:
    """Audit log coverage for admin-triggered password resets."""

    def test_password_reset_creation_emits_password_reset_created(self, client, db_session, audit_log):
        target = _register(client)
        admin = _register(client)
        _promote_to_admin(db_session, admin["id"])
        audit_log.clear()

        response = client.post(f"/api/v1/admin/users/{target['id']}/password-reset")

        assert response.status_code == 201
        record = next(r for r in audit_log.records if r.event == "password_reset_created")
        assert record.target_user_id == target["id"]
        assert record.invite_id == response.json()["id"]

    def test_admin_editing_someone_else_records_admin_as_actor_and_other_as_target(self, client, db_session, audit_log):
        # The actor (whoever the request is authenticated as) lives in the request context, not an
        # explicit field (LOGGING.md §4.4) - target_user_id is the only explicit field, so this is
        # the only way to tell an admin's edit of someone else apart from self-service from the
        # audit trail alone.
        target = _register(client)
        admin = _register(client)
        _promote_to_admin(db_session, admin["id"])
        audit_log.clear()

        response = client.patch(
            f"/api/v1/admin/users/{target['id']}",
            json={"username": _unique("renamed"), "full_name": "Renamed User"},
        )

        assert response.status_code == 200
        index = next(i for i, r in enumerate(audit_log.records) if r.event == "profile_updated")
        record = audit_log.records[index]
        context = audit_log.contexts[index]
        assert record.target_user_id == target["id"]
        assert context["user_id"] == admin["id"]

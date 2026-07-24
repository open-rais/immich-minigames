import uuid
from uuid import UUID

from persistence.users import UserModel


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

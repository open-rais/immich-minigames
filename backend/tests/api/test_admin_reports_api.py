import uuid
from uuid import UUID

from conftest import mint_invite_code

from persistence.users import UserModel

_REASON_FOR_TYPE = {
    "person": "person_birth_date",
    "album": "album_cover_mismatch",
    "asset": "asset_date",
}


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


def _report(client, entity_type: str, entity_id) -> dict:
    reporter = _register(client)
    response = client.post(
        "/api/v1/reports",
        json={
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "reasons": [_REASON_FOR_TYPE[entity_type]],
            "note": None,
        },
    )
    assert response.status_code == 201
    return reporter


class TestListReports:
    def test_anonymous_returns_401(self, client):
        client.cookies.clear()

        response = client.get("/api/v1/admin/reports", params={"entity_type": "asset", "solved": False})

        assert response.status_code == 401

    def test_non_admin_returns_403(self, client):
        _register(client)

        response = client.get("/api/v1/admin/reports", params={"entity_type": "asset", "solved": False})

        assert response.status_code == 403

    def test_resolves_person_name_and_reporter_username(self, client, db_session, immich_service):
        [person] = immich_service.get_persons(named_only=True, limit=1)
        reporter = _report(client, "person", person.id)
        _register_as_admin(client, db_session)

        response = client.get("/api/v1/admin/reports", params={"entity_type": "person", "solved": False})

        assert response.status_code == 200
        [row] = [r for r in response.json() if r["entity_id"] == str(person.id)]
        assert row["entity_name"] == person.name
        assert row["username"] == reporter["username"]
        assert row["reason"] == "person_birth_date"
        assert row["solved"] is False

    def test_resolves_album_name(self, client, db_session, immich_service):
        [album] = immich_service.get_albums(limit=1)
        _report(client, "album", album.id)
        _register_as_admin(client, db_session)

        response = client.get("/api/v1/admin/reports", params={"entity_type": "album", "solved": False})

        [row] = [r for r in response.json() if r["entity_id"] == str(album.id)]
        assert row["entity_name"] == album.name

    def test_resolves_asset_name(self, client, db_session, immich_service):
        [asset] = immich_service.get_assets(randomize=True, limit=1)
        _report(client, "asset", asset.id)
        _register_as_admin(client, db_session)

        response = client.get("/api/v1/admin/reports", params={"entity_type": "asset", "solved": False})

        [row] = [r for r in response.json() if r["entity_id"] == str(asset.id)]
        assert row["entity_name"] == asset.original_file_name

    def test_filters_by_solved(self, client, db_session, immich_service):
        [asset] = immich_service.get_assets(randomize=True, limit=1)
        _report(client, "asset", asset.id)
        _register_as_admin(client, db_session)
        report_id = next(
            r["id"]
            for r in client.get("/api/v1/admin/reports", params={"entity_type": "asset", "solved": False}).json()
            if r["entity_id"] == str(asset.id)
        )
        client.patch(f"/api/v1/admin/reports/{report_id}", json={"solved": True})

        open_reports = client.get("/api/v1/admin/reports", params={"entity_type": "asset", "solved": False}).json()
        solved_reports = client.get("/api/v1/admin/reports", params={"entity_type": "asset", "solved": True}).json()

        assert report_id not in {r["id"] for r in open_reports}
        assert report_id in {r["id"] for r in solved_reports}


class TestReportCounts:
    def test_anonymous_returns_401(self, client):
        client.cookies.clear()

        response = client.get("/api/v1/admin/reports/counts")

        assert response.status_code == 401

    def test_always_includes_all_three_keys(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.get("/api/v1/admin/reports/counts")

        assert response.status_code == 200
        assert set(response.json().keys()) == {"asset", "person", "album"}

    def test_counts_reflect_a_freshly_created_open_report(self, client, db_session, immich_service):
        [asset] = immich_service.get_assets(randomize=True, limit=1)
        _register_as_admin(client, db_session)
        before = client.get("/api/v1/admin/reports/counts").json()["asset"]
        _report(client, "asset", asset.id)
        _register_as_admin(client, db_session)

        after = client.get("/api/v1/admin/reports/counts").json()["asset"]

        assert after >= before + 1


class TestUpdateReport:
    def test_resolving_and_reverting_updates_the_row(self, client, db_session, immich_service):
        [asset] = immich_service.get_assets(randomize=True, limit=1)
        _report(client, "asset", asset.id)
        _register_as_admin(client, db_session)
        report_id = next(
            r["id"]
            for r in client.get("/api/v1/admin/reports", params={"entity_type": "asset", "solved": False}).json()
            if r["entity_id"] == str(asset.id)
        )

        resolved = client.patch(f"/api/v1/admin/reports/{report_id}", json={"solved": True})
        assert resolved.status_code == 200
        assert resolved.json()["solved"] is True
        assert resolved.json()["solved_at"] is not None
        assert resolved.json()["entity_name"] == asset.original_file_name

        reverted = client.patch(f"/api/v1/admin/reports/{report_id}", json={"solved": False})
        assert reverted.status_code == 200
        assert reverted.json()["solved"] is False
        assert reverted.json()["solved_at"] is None

    def test_unknown_id_returns_404(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.patch(f"/api/v1/admin/reports/{uuid.uuid4()}", json={"solved": True})

        assert response.status_code == 404

    def test_non_admin_returns_403(self, client, db_session, immich_service):
        [asset] = immich_service.get_assets(randomize=True, limit=1)
        _report(client, "asset", asset.id)
        _register_as_admin(client, db_session)
        report_id = next(
            r["id"]
            for r in client.get("/api/v1/admin/reports", params={"entity_type": "asset", "solved": False}).json()
            if r["entity_id"] == str(asset.id)
        )
        _register(client)  # logs in as a non-admin, replacing the admin session

        response = client.patch(f"/api/v1/admin/reports/{report_id}", json={"solved": True})

        assert response.status_code == 403

import threading
import uuid
from uuid import UUID, uuid4

import pytest
from conftest import mint_invite_code

from api.deps import get_embedding_job_runner, get_ml_service
from persistence.users import UserModel
from services.ml_service import StaleIds

_URL = "/api/v1/admin/workers/embeddings"


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


@pytest.fixture(autouse=True)
def _reset_embedding_job_runner():
    """The runner is a real, process-wide singleton (api/deps.py's @lru_cache), so a job started by
    one test and left running would otherwise leak into the next one's "is anything running?"
    checks - cancel+join whatever's there, then drop the singleton so the next test starts from a
    clean `current is None`."""
    yield
    runner = get_embedding_job_runner()
    runner.cancel()
    runner.join(timeout=5)
    get_embedding_job_runner.cache_clear()


def _fake_stale(ids: frozenset[UUID]) -> StaleIds:
    return StaleIds(ids=ids, all_ids=ids, total=len(ids))


class TestAuth:
    def test_get_anonymous_returns_401(self, client):
        client.cookies.clear()

        assert client.get(_URL).status_code == 401

    def test_get_non_admin_returns_403(self, client):
        _register(client)

        assert client.get(_URL).status_code == 403

    def test_post_non_admin_returns_403(self, client):
        _register(client)

        response = client.post(_URL, json={"entity": "person", "scope": "missing"})

        assert response.status_code == 403

    def test_delete_non_admin_returns_403(self, client):
        _register(client)

        assert client.delete(_URL).status_code == 403


class TestGetStatus:
    def test_reports_coverage_and_no_job_before_anything_ran(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.get(_URL)

        assert response.status_code == 200
        body = response.json()
        assert body["job"] is None
        for entity in ("persons", "albums"):
            assert body[entity]["total"] >= body[entity]["cached"] >= 0


class TestStartJob:
    def test_start_returns_202_and_the_job_shows_up_in_get(self, client, db_session):
        _register_as_admin(client, db_session)

        response = client.post(_URL, json={"entity": "person", "scope": "missing"})

        assert response.status_code == 202
        body = response.json()
        assert body["entity"] == "person"
        assert body["scope"] == "missing"
        assert body["include_ineligible"] is False
        assert body["status"] in ("running", "done")

        get_embedding_job_runner().join(timeout=30)

        status = client.get(_URL).json()
        assert status["job"]["id"] == body["id"]
        assert status["job"]["status"] in ("done", "cancelled", "failed")

    def test_second_start_while_the_first_is_running_returns_409(self, client, db_session, monkeypatch):
        _register_as_admin(client, db_session)
        ml_service = get_ml_service()
        ready = threading.Event()
        release = threading.Event()

        monkeypatch.setattr(ml_service, "stale_person_ids", lambda **_: _fake_stale(frozenset({uuid4(), uuid4()})))

        def _blocking(_entity_id: UUID, *, force: bool = False) -> None:
            ready.set()
            release.wait(timeout=5)

        monkeypatch.setattr(ml_service, "compute_person_embedding", _blocking)

        first = client.post(_URL, json={"entity": "person", "scope": "missing"})
        assert first.status_code == 202
        assert ready.wait(timeout=5), "background job never reached its first entity"

        second = client.post(_URL, json={"entity": "person", "scope": "missing"})

        assert second.status_code == 409

        release.set()
        get_embedding_job_runner().join(timeout=5)


class TestCancel:
    def test_cancel_stops_the_running_job(self, client, db_session, monkeypatch):
        _register_as_admin(client, db_session)
        ml_service = get_ml_service()
        ready = threading.Event()
        release = threading.Event()
        ids = frozenset({uuid4(), uuid4(), uuid4()})
        calls: list[UUID] = []

        monkeypatch.setattr(ml_service, "stale_person_ids", lambda **_: _fake_stale(ids))

        def _blocking(entity_id: UUID, *, force: bool = False) -> None:
            calls.append(entity_id)
            if len(calls) == 1:
                ready.set()
                release.wait(timeout=5)

        monkeypatch.setattr(ml_service, "compute_person_embedding", _blocking)

        client.post(_URL, json={"entity": "person", "scope": "missing"})
        assert ready.wait(timeout=5), "background job never reached its first entity"

        cancel_response = client.delete(_URL)
        assert cancel_response.status_code == 204

        release.set()
        get_embedding_job_runner().join(timeout=5)

        status = client.get(_URL).json()
        assert status["job"]["status"] == "cancelled"
        assert status["job"]["processed"] == 1
        assert len(calls) == 1  # cancellation was seen before a second entity was ever touched

    def test_cancel_with_nothing_running_is_a_no_op(self, client, db_session):
        _register_as_admin(client, db_session)

        assert client.delete(_URL).status_code == 204

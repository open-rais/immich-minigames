from sqlalchemy.exc import SQLAlchemyError

from api.deps import get_db_session
from main import app


class _FailingSession:
    def execute(self, *_args, **_kwargs):
        raise SQLAlchemyError("boom")


def _failing_db_session():
    yield _FailingSession()


class TestHealthCheck:
    def test_returns_ok_without_a_session_cookie(self, client):
        # Allow-listed in auth_middleware.py - Docker's healthcheck request carries no cookie.
        client.cookies.clear()
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_returns_503_when_the_database_is_unreachable(self, client):
        app.dependency_overrides[get_db_session] = _failing_db_session
        try:
            response = client.get("/api/v1/health")
        finally:
            del app.dependency_overrides[get_db_session]

        assert response.status_code == 503

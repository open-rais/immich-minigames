import uuid

from services.reports_service import ReportsService


def _payload(**overrides) -> dict:
    body = {
        "entity_type": "asset",
        "entity_id": str(uuid.uuid4()),
        "reasons": ["asset_date"],
        "note": None,
    }
    body.update(overrides)
    return body


class TestCreateReport:
    def test_returns_201_and_persists_a_row(self, logged_client, db_session):
        entity_id = uuid.uuid4()

        response = logged_client.post("/api/v1/reports", json=_payload(entity_id=str(entity_id)))

        assert response.status_code == 201
        reports = ReportsService(db_session).list("asset", solved=False)
        assert entity_id in {r.entity_id for r in reports}

    def test_reason_incoherent_with_entity_type_returns_400(self, logged_client):
        response = logged_client.post(
            "/api/v1/reports", json=_payload(entity_type="person", reasons=["asset_date"])
        )

        assert response.status_code == 400

    def test_note_over_200_chars_returns_422(self, logged_client):
        response = logged_client.post("/api/v1/reports", json=_payload(note="x" * 201))

        assert response.status_code == 422

    def test_empty_reasons_returns_422(self, logged_client):
        response = logged_client.post("/api/v1/reports", json=_payload(reasons=[]))

        assert response.status_code == 422

    def test_duplicate_post_leaves_a_single_open_row(self, logged_client, db_session):
        entity_id = uuid.uuid4()
        payload = _payload(entity_id=str(entity_id))

        first = logged_client.post("/api/v1/reports", json=payload)
        second = logged_client.post("/api/v1/reports", json=payload)

        assert first.status_code == 201
        assert second.status_code == 201
        reports = ReportsService(db_session).list("asset", solved=False)
        assert [r.entity_id for r in reports].count(entity_id) == 1

    def test_without_a_cookie_returns_401(self, client):
        client.cookies.clear()

        response = client.post("/api/v1/reports", json=_payload())

        assert response.status_code == 401

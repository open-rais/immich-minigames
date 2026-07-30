"""Access log middleware tests (docs/TODO/LOGGING.md §4.3, phase F1) - capture the `access`
logger's own records directly rather than through caplog: caplog's handler attaches to the root
logger, and `access`/`audit` both set propagate=False (logging_setup.py, decision [H]), so records
emitted on them never reach it. The `access_log` fixture itself lives in conftest.py (shared with
`audit_log`, phase F2's audit tests)."""


def test_logged_in_request_records_status_duration_and_user(logged_client, access_log):
    me = logged_client.get("/api/v1/auth/me")
    access_log.clear()

    response = logged_client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert len(access_log.records) == 1
    record = access_log.records[0]
    assert record.method == "GET"
    assert record.path == "/api/v1/auth/me"
    assert record.status == 200
    assert isinstance(record.duration_ms, float)
    assert record.duration_ms >= 0
    assert record.user_id == me.json()["id"]
    assert record.username == me.json()["username"]
    assert not hasattr(record, "auth_fail")


def test_response_carries_the_request_id_header(logged_client):
    response = logged_client.get("/api/v1/auth/me")

    assert response.headers["x-request-id"]


def test_request_without_a_cookie_is_logged_with_auth_fail_and_no_user(client, access_log):
    client.cookies.clear()

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert len(access_log.records) == 1
    record = access_log.records[0]
    assert record.status == 401
    assert record.auth_fail == "missing_cookie"
    assert not hasattr(record, "user_id")


def test_query_string_is_included_in_the_logged_path(logged_client, access_log):
    logged_client.get("/api/v1/persons/search?query=foo")

    assert access_log.records[-1].path == "/api/v1/persons/search?query=foo"


def test_allow_listed_route_without_a_cookie_is_still_logged(client, access_log):
    client.cookies.clear()

    client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever123"})

    assert len(access_log.records) == 1
    assert access_log.records[0].status == 401
    assert not hasattr(access_log.records[0], "auth_fail")

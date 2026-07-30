"""audit() helper tests (docs/TODO/LOGGING.md §4.4/§4.5, phase F2): field validation, basic
emission via the `audit_log` fixture (conftest.py), and the secrets test §4.5 calls for - a full
register/login/change-password/admin-reset/reset-password sequence through the real `client`, with
every record emitted anywhere (root, `audit`, `access`) checked for the plaintext passwords and
tokens involved."""

import logging
import uuid
from contextlib import contextmanager
from uuid import UUID

import pytest
from conftest import mint_invite_code

from audit import audit
from logging_setup import JsonFormatter
from persistence.users import UserModel


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class _AllCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextmanager
def _capture_root_audit_and_access():
    # "" (root) catches ordinary app logging (propagates up); `audit`/`access` don't propagate
    # (decision [H]) so they need their own handler attached directly - see conftest.py's
    # _LogCapture docstring for the same point.
    handler = _AllCapture()
    loggers = [logging.getLogger(name) for name in ("", "audit", "access")]
    for logger in loggers:
        logger.addHandler(handler)
    try:
        yield handler
    finally:
        for logger in loggers:
            logger.removeHandler(handler)


def _promote_to_admin(db_session, user_id: str) -> None:
    user = db_session.get(UserModel, UUID(user_id))
    user.is_admin = True
    db_session.commit()


class TestAuditFieldValidation:
    def test_field_colliding_with_a_reserved_log_record_attr_raises(self):
        with pytest.raises(ValueError):
            audit("some_event", msg="not allowed")

    def test_normal_call_emits_the_event_and_fields(self, audit_log):
        audit("some_event", foo="bar")

        assert len(audit_log.records) == 1
        record = audit_log.records[0]
        assert record.event == "some_event"
        assert record.foo == "bar"


class TestNoSecretsLogged:
    def test_register_login_change_and_admin_reset_never_log_secrets(self, client, db_session):
        target_invite = mint_invite_code()
        admin_invite = mint_invite_code()
        target_password = f"{_unique('pw')}-horse-battery"
        target_new_password = f"{_unique('newpw')}-horse-battery"
        target_reset_password = f"{_unique('resetpw')}-horse-battery"
        admin_password = "correct-horse-battery-staple"

        with _capture_root_audit_and_access() as capture:
            target_resp = client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"{_unique('target')}@example.com",
                    "username": _unique("target"),
                    "full_name": "Target User",
                    "password": target_password,
                    "invite_code": target_invite,
                },
            )
            assert target_resp.status_code == 201
            target = target_resp.json()

            admin_email = f"{_unique('admin')}@example.com"
            admin_resp = client.post(
                "/api/v1/auth/register",
                json={
                    "email": admin_email,
                    "username": _unique("admin"),
                    "full_name": "Admin User",
                    "password": admin_password,
                    "invite_code": admin_invite,
                },
            )
            assert admin_resp.status_code == 201
            _promote_to_admin(db_session, admin_resp.json()["id"])

            client.post("/api/v1/auth/login", json={"email": target["email"], "password": "wrong-password"})
            client.post("/api/v1/auth/login", json={"email": target["email"], "password": target_password})
            jwt_cookie = client.cookies.get("access_token")

            client.patch(
                "/api/v1/auth/me/password",
                json={"current_password": target_password, "new_password": target_new_password},
            )

            client.post("/api/v1/auth/login", json={"email": admin_email, "password": admin_password})
            reset_resp = client.post(f"/api/v1/admin/users/{target['id']}/password-reset")
            assert reset_resp.status_code == 201
            reset_token = reset_resp.json()["token"]

            client.post(
                "/api/v1/auth/reset-password",
                json={"token": reset_token, "new_password": target_reset_password},
            )

        formatter = JsonFormatter()
        blob = "\n".join(formatter.format(r) for r in capture.records)
        secrets_used = [
            target_password,
            target_new_password,
            target_reset_password,
            admin_password,
            target_invite,
            admin_invite,
            reset_token,
        ]
        if jwt_cookie:
            secrets_used.append(jwt_cookie)
        for secret in secrets_used:
            assert secret not in blob, f"secret {secret!r} leaked into the logs"

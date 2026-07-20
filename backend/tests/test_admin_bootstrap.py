import uuid

from config import Settings, get_settings
from services.admin_bootstrap import ensure_admin


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _register(auth_service, **overrides):
    defaults = {
        "email": f"{_unique('user')}@example.com",
        "username": _unique("user"),
        "full_name": "Test User",
        "password": "correct-horse-battery-staple",
    }
    defaults.update(overrides)
    return auth_service.register(**defaults)


def _settings_with_admin_email(email: str | None) -> Settings:
    # Settings() re-reads the real .env for every other required field (db creds, jwt secret,
    # etc.) and just overrides admin_email on top - same pattern config.py documents for tests
    # that want to isolate their own Settings instance instead of the get_settings() singleton.
    base = get_settings()
    return Settings(
        db_app_username=base.db_app_username,
        db_app_password=base.db_app_password,
        db_database_name=base.db_database_name,
        db_host=base.db_host,
        db_port=base.db_port,
        immich_api_key=base.immich_api_key,
        immich_server_url=base.immich_server_url,
        jwt_secret=base.jwt_secret,
        jwt_expire_days=base.jwt_expire_days,
        admin_email=email,
    )


class TestEnsureAdmin:
    def test_no_admin_email_is_a_no_op(self, db_session, auth_service):
        user = _register(auth_service)

        ensure_admin(db_session, _settings_with_admin_email(None))

        db_session.refresh(user)
        assert user.is_admin is False

    def test_promotes_a_matching_existing_user(self, db_session, auth_service):
        user = _register(auth_service)

        ensure_admin(db_session, _settings_with_admin_email(user.email))

        db_session.refresh(user)
        assert user.is_admin is True

    def test_promoting_an_already_admin_user_is_idempotent(self, db_session, auth_service):
        user = _register(auth_service)
        settings = _settings_with_admin_email(user.email)

        ensure_admin(db_session, settings)
        ensure_admin(db_session, settings)

        db_session.refresh(user)
        assert user.is_admin is True

    def test_no_matching_user_does_not_raise(self, db_session):
        missing_email = f"{_unique('nobody')}@example.com"

        ensure_admin(db_session, _settings_with_admin_email(missing_email))

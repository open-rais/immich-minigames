from config import Settings, get_settings
from main import app


def _settings_with_external_url(external_url: str | None) -> Settings:
    # Same pattern as test_admin_bootstrap.py's _settings_with_admin_email: build off the real
    # get_settings() base for every other required field, override just the one under test.
    # VAPID_* explicitly nulled (push_public_key is null in every response below) - not just left
    # off the constructor call, which would otherwise pick up real VAPID_* from .env on any
    # machine that has actually configured push for manual testing.
    base = get_settings()
    return Settings(
        db_app_username=base.db_app_username,
        db_app_password=base.db_app_password,
        db_database_name=base.db_database_name,
        db_host=base.db_host,
        db_port=base.db_port,
        immich_api_key=base.immich_api_key,
        immich_server_url=base.immich_server_url,
        immich_external_url=external_url,
        jwt_secret=base.jwt_secret,
        jwt_expire_days=base.jwt_expire_days,
        vapid_public_key=None,
        vapid_private_key=None,
        vapid_contact_email=None,
    )


def _settings_with_vapid(public_key: str | None, private_key: str | None, contact_email: str | None) -> Settings:
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
        vapid_public_key=public_key,
        vapid_private_key=private_key,
        vapid_contact_email=contact_email,
    )


class TestGetConfig:
    def test_returns_external_url_when_set(self, logged_client):
        app.dependency_overrides[get_settings] = lambda: _settings_with_external_url("https://fotos.example.cl/")
        try:
            response = logged_client.get("/api/v1/config")
        finally:
            del app.dependency_overrides[get_settings]

        assert response.status_code == 200
        assert response.json() == {"immich_external_url": "https://fotos.example.cl", "push_public_key": None}

    def test_falls_back_to_server_url_when_unset(self, logged_client):
        settings = _settings_with_external_url(None)
        app.dependency_overrides[get_settings] = lambda: settings
        try:
            response = logged_client.get("/api/v1/config")
        finally:
            del app.dependency_overrides[get_settings]

        assert response.json() == {
            "immich_external_url": settings.immich_server_url.rstrip("/"),
            "push_public_key": None,
        }

    def test_returns_null_when_explicitly_set_empty(self, logged_client):
        # An explicitly empty IMMICH_EXTERNAL_URL means "no public link", not "unset" - unlike
        # None, it must NOT fall back to immich_server_url (which is often an internal-only
        # address, e.g. host.docker.internal, that would otherwise leak into this browser-facing
        # response).
        app.dependency_overrides[get_settings] = lambda: _settings_with_external_url("")
        try:
            response = logged_client.get("/api/v1/config")
        finally:
            del app.dependency_overrides[get_settings]

        assert response.json() == {"immich_external_url": None, "push_public_key": None}

    def test_exposes_the_public_key_when_all_three_vapid_settings_are_set(self, logged_client):
        settings = _settings_with_vapid("public-key", "private-key", "owner@example.com")
        app.dependency_overrides[get_settings] = lambda: settings
        try:
            response = logged_client.get("/api/v1/config")
        finally:
            del app.dependency_overrides[get_settings]

        assert response.json()["push_public_key"] == "public-key"

    def test_hides_the_public_key_when_only_partially_configured(self, logged_client):
        # Exposing just the public key here would let the frontend show a notifications section
        # that can subscribe but can never actually send (no private key/contact email).
        settings = _settings_with_vapid("public-key", None, None)
        app.dependency_overrides[get_settings] = lambda: settings
        try:
            response = logged_client.get("/api/v1/config")
        finally:
            del app.dependency_overrides[get_settings]

        assert response.json()["push_public_key"] is None

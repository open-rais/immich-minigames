from config import Settings, get_settings
from main import app


def _settings_with_external_url(external_url: str | None) -> Settings:
    # Same pattern as test_admin_bootstrap.py's _settings_with_admin_email: build off the real
    # get_settings() base for every other required field, override just the one under test.
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
    )


class TestGetConfig:
    def test_returns_external_url_when_set(self, client):
        app.dependency_overrides[get_settings] = lambda: _settings_with_external_url(
            "https://fotos.example.cl/"
        )
        try:
            response = client.get("/api/v1/config")
        finally:
            del app.dependency_overrides[get_settings]

        assert response.status_code == 200
        assert response.json() == {"immich_external_url": "https://fotos.example.cl"}

    def test_falls_back_to_server_url_when_unset(self, client):
        settings = _settings_with_external_url(None)
        app.dependency_overrides[get_settings] = lambda: settings
        try:
            response = client.get("/api/v1/config")
        finally:
            del app.dependency_overrides[get_settings]

        assert response.json() == {"immich_external_url": settings.immich_server_url.rstrip("/")}

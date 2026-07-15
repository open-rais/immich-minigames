"""App configuration, read from the repo-root .env (shared with docker-compose.yml)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_REPO_ROOT_ENV_FILE, extra="ignore")

    # The backend's single DB role (see docker/init-scripts/create_minigames_app_role.sh):
    # read-only on Immich's own schema, full control on this app's own `minigames` schema. Never
    # DB_USERNAME/DB_PASSWORD - those are Immich's own admin connection, not used by this backend.
    db_app_username: str
    db_app_password: str

    db_database_name: str
    db_host: str = "localhost"
    db_port: int = 5432

    # Used to call Immich's own REST API (not Postgres) to serve image bytes - see
    # docs/ARCHITECTURE/IMMICH.md's "Dos formas de hablar con Immich". Create the key from Immich
    # at Account Settings > API Keys.
    immich_api_key: str
    immich_server_url: str = "http://localhost:2283"

    # Signs/verifies this app's own login JWT (services/auth_service.py) - unrelated to Immich.
    # Generate with `openssl rand -hex 32`. Rotating it invalidates every existing session (no
    # server-side session table to selectively revoke, see docs/ARCHITECTURE/BACKEND.md).
    jwt_secret: str
    jwt_expire_days: int = 30

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_app_username}:{self.db_app_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_database_name}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton - Settings() re-parses/re-reads the .env file from disk on every call, so
    hot paths (a request-scoped `settings or Settings()` default, engine construction) should use
    this instead of constructing their own. Callers that genuinely want a fresh read (e.g. tests
    isolating their own Settings instance) can still construct Settings() directly."""
    return Settings()

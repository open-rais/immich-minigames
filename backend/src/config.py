"""App configuration, read from the repo-root .env (shared with docker-compose.yml)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_REPO_ROOT_ENV_FILE, extra="ignore")

    # The backend's single DB role (see scripts/bootstrap_db_role.py, which provisions it): read-only
    # on Immich's own database, full control on this app's own database. Never
    # DB_USERNAME/DB_PASSWORD - those are Immich's own admin connection, not used by this backend.
    db_app_username: str
    db_app_password: str

    # Immich's own database - this app only ever reads from it (see immich_db_url below).
    db_database_name: str
    # This app's own database, on the same Postgres instance but deliberately NOT inside Immich's:
    # Immich backs up with `pg_dump --clean --if-exists` over its own database, so anything living
    # there ends up in Immich's dumps and breaks its restore (see docs/ARCHITECTURE/BACKEND.md's
    # "Por qué una base de datos separada"). Defaulted rather than required so that upgrading an
    # existing install is zero-config - a missing value here would fail db-init, and the backend
    # would never start behind its `service_completed_successfully` dependency.
    db_app_database_name: str = "minigames"
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

    # Admin feature (ADMIN-FEATURE.md point #1) - promotion only, not account creation: if a user
    # already registered (via /signup) with this email, services/admin_bootstrap.py flips their
    # is_admin flag to True on every backend startup. If no such account exists yet, it's a no-op
    # (register normally first, then restart the backend). None/unset means no admin is managed.
    admin_email: str | None = None

    # Two databases, one role. Deliberately no single `db_url` property: an ambiguous name pointing
    # at one of two databases is exactly the class of mistake the split exists to rule out.
    def _db_url(self, database: str) -> str:
        return (
            f"postgresql+psycopg://{self.db_app_username}:{self.db_app_password}"
            f"@{self.db_host}:{self.db_port}/{database}"
        )

    @property
    def immich_db_url(self) -> str:
        """Immich's database - read-only (see persistence/immich_db.py)."""
        return self._db_url(self.db_database_name)

    @property
    def app_db_url(self) -> str:
        """This app's own database - read/write (see persistence/base.py)."""
        return self._db_url(self.db_app_database_name)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton - Settings() re-parses/re-reads the .env file from disk on every call, so
    hot paths (a request-scoped `settings or Settings()` default, engine construction) should use
    this instead of constructing their own. Callers that genuinely want a fresh read (e.g. tests
    isolating their own Settings instance) can still construct Settings() directly."""
    return Settings()

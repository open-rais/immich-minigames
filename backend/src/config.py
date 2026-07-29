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

    # Public URL the *browser* uses to open Immich directly ("Ver en Immich" buttons, roadmap #10) -
    # distinct from immich_server_url above, which is how the *backend* reaches Immich and is often an
    # internal Docker host, useless as a browser link. Falls back to immich_server_url when unset -
    # convenient for localhost dev, but produces a broken link if the backend reaches Immich through an
    # internal Docker host and this isn't set explicitly (see .env.example).
    immich_external_url: str | None = None

    # Signs/verifies this app's own login JWT (services/auth_service.py) - unrelated to Immich.
    # Generate with `openssl rand -hex 32`. Rotating it invalidates every existing session (no
    # server-side session table to selectively revoke, see docs/ARCHITECTURE/BACKEND.md).
    jwt_secret: str
    jwt_expire_days: int = 30
    # Whether the session cookie is marked Secure (HTTPS-only). False by default because the dev
    # stack and docker-compose.app.yml both serve plain HTTP - set to true if this is deployed
    # behind a TLS-terminating reverse proxy (the expected way to self-host this), or the JWT
    # cookie keeps going out without the Secure flag even over HTTPS.
    cookie_secure: bool = False

    # Roadmap #H, F5 - backing store for api/rate_limit.py's Limiter (and the per-email login
    # check it shares that storage with). "memory://" (default) is a single process's own memory -
    # fine for this app's single-backend-container deployment shape, and what every rate limit
    # test in this suite runs against. Accepts "redis://host:port" too (the `limits` library's own
    # URI scheme) for a multi-process deployment, where per-process in-memory counters would let
    # each process serve its own separate budget instead of one shared one.
    rate_limit_storage_uri: str = "memory://"

    # Admin feature (ADMIN-FEATURE.md point #1) - promotion only, not account creation: if a user
    # already registered (via /signup) with this email, services/admin_bootstrap.py flips their
    # is_admin flag to True on every backend startup. If no such account exists yet, it's a no-op
    # (register normally first, then restart the backend). None/unset means no admin is managed.
    admin_email: str | None = None

    # Roadmap #H, F1 - registration is invite-only (services/invite_service.py), but the very first
    # account can't have an invite yet. While the `users` table is empty, RegisterIn.invite_code is
    # accepted as valid if it matches this value instead (services/auth_service.py's
    # _authorize_registration) - a one-shot bootstrap door that closes itself the moment any
    # account exists. Generate with `openssl rand -hex 32`, same as JWT_SECRET. Leave unset to allow
    # the first registration freely (dev convenience, zero config for local dev) - the door still
    # closes after that first account either way.
    initial_invite_token: str | None = None

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

    @property
    def immich_public_url(self) -> str:
        return (self.immich_external_url or self.immich_server_url).rstrip("/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton - Settings() re-parses/re-reads the .env file from disk on every call, so
    hot paths (a request-scoped `settings or Settings()` default, engine construction) should use
    this instead of constructing their own. Callers that genuinely want a fresh read (e.g. tests
    isolating their own Settings instance) can still construct Settings() directly."""
    return Settings()

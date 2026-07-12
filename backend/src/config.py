"""App configuration, read from the repo-root .env (shared with docker-compose.yml)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_REPO_ROOT_ENV_FILE, extra="ignore")

    # Deliberately the read-only role (see docker/init-scripts/create_minigames_ro_role.sh), never
    # DB_USERNAME/DB_PASSWORD - those are Immich's own admin connection.
    db_ro_username: str
    db_ro_password: str
    db_database_name: str
    db_host: str = "localhost"
    db_port: int = 5432

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_ro_username}:{self.db_ro_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_database_name}"
        )

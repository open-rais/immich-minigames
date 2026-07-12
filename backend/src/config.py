"""App configuration, read from the repo-root .env (shared with docker-compose.yml)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_REPO_ROOT_ENV_FILE, extra="ignore")

    db_username: str
    db_password: str
    db_database_name: str
    db_host: str = "localhost"
    db_port: int = 5432

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_username}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_database_name}"
        )

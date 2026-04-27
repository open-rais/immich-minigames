from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "immich-minigames"
    app_version: str = "0.1.0"

    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str
    redis_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
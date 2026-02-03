"""Configuration from environment."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/iot_gateway"
    freeswitch_host: str = "localhost"
    freeswitch_port: int = 8021
    freeswitch_password: str = "ClueCon"
    freeswitch_use_rest: bool = True
    freeswitch_rest_url: str | None = None  # e.g. http://localhost:8080
    webhook_api_key: str = "change-me-in-production"
    api_port: int = 8000


settings = Settings()

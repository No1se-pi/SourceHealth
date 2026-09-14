"""Typed settings: создаются на границе процесса, не во время импорта core."""

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr = SecretStr("postgresql+psycopg://sourcehealth:sourcehealth@127.0.0.1:15432/sourcehealth")
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    sourcecraft_api_base_url: str = "https://api.sourcecraft.tech"
    sourcecraft_pat: SecretStr | None = None
    sourcecraft_timeout: float = Field(default=15, gt=0, le=60)
    sourcecraft_max_pages: int = Field(default=100, ge=1, le=1000)
    yandex_client_id: str = ""
    yandex_client_secret: SecretStr | None = None
    yandex_redirect_uri: str = "https://localhost/api/v1/auth/yandex/callback"
    session_secret: SecretStr | None = None
    public_origin: str = "https://localhost"
    cookie_secure: bool = True
    session_ttl: int = Field(default=86400, ge=60, le=604800)
    platform_cache_ttl: int = Field(default=300, ge=1)
    code_cache_ttl: int = Field(default=604800, ge=1)
    result_cache_ttl: int = Field(default=300, ge=1)
    analysis_timeout: int = Field(default=600, ge=30, le=3600)
    analysis_profile: str = "platform-v1"
    refresh_interval: int = Field(default=86400, ge=300)

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("PostgreSQL with psycopg is required")
        return value

    @field_validator("sourcecraft_api_base_url")
    @classmethod
    def trusted_sourcecraft_host(cls, value: str) -> str:
        if value.rstrip("/") != "https://api.sourcecraft.tech":
            raise ValueError("only official SourceCraft API host is allowed")
        return value.rstrip("/")

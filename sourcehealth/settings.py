"""Typed settings: создаются на границе процесса, не во время импорта core."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr = SecretStr("postgresql+psycopg://sourcehealth:sourcehealth@127.0.0.1:15432/sourcehealth")
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")
    sourcecraft_api_base_url: str = "https://api.sourcecraft.tech"
    sourcecraft_pat: SecretStr | None = None
    sourcecraft_credential_key: SecretStr | None = None
    sourcecraft_connection_ttl: int = Field(default=1800, ge=60, le=3600)
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
    analysis_profile: Literal["platform-v1", "code-v1", "mvp-v1"] = "platform-v1"
    code_runtime_enabled: bool = False
    code_runtime_image: str = "sourcehealth-sast"
    code_runtime_timeout: int = Field(default=180, ge=1, le=1200)
    refresh_interval: int = Field(default=86400, ge=300)

    @model_validator(mode="after")
    def runtime_budget(self):
        # The legacy workflow applies timeout separately to clone and analysis.
        # Reserve time for bounded platform requests, container setup and cleanup.
        if self.code_runtime_enabled and self.analysis_timeout < 2 * self.code_runtime_timeout + 180:
            raise ValueError("analysis_timeout must cover both runtime stages and orchestration")
        return self

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

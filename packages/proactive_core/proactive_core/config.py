"""Typed application configuration."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration shared by every service."""

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    service_name: str = "api"
    database_url: str = "postgresql+asyncpg://proactive:proactive@localhost:5432/proactive"
    redis_url: str = "redis://localhost:6379/0"
    public_base_url: str = "http://localhost:3000"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    jwt_issuer: str = "proactive-seo"
    jwt_audience: str = "proactive-seo-api"
    jwt_private_key: SecretStr | None = None
    jwt_public_key: SecretStr | None = None
    credential_encryption_key: SecretStr | None = None
    webhook_signing_secret: SecretStr | None = None
    live_actions_enabled: bool = False
    task_dispatch_enabled: bool = False
    openai_api_key: SecretStr | None = None
    dataforseo_login: SecretStr | None = None
    dataforseo_password: SecretStr | None = None
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    @model_validator(mode="after")
    def validate_secure_environment(self) -> Self:
        """Refuse non-local startup when mandatory cryptographic material is absent."""
        if self.env in {"staging", "production"}:
            required = {
                "APP_JWT_PRIVATE_KEY": self.jwt_private_key,
                "APP_JWT_PUBLIC_KEY": self.jwt_public_key,
                "APP_CREDENTIAL_ENCRYPTION_KEY": self.credential_encryption_key,
                "APP_WEBHOOK_SIGNING_SECRET": self.webhook_signing_secret,
            }
            missing = [name for name, value in required.items() if value is None]
            if missing:
                raise ValueError(f"Missing required secure settings: {', '.join(missing)}")
            if any(origin == "*" for origin in self.cors_origins):
                raise ValueError("Wildcard CORS origins are forbidden outside local development")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide validated settings instance."""
    return Settings()

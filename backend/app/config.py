"""Application configuration using pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QMF_",
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "development"
    port: int = 8000
    secret_key: str = "super-secret-key-change-in-production-32chars"
    jwt_secret: str = "quest-mf-jwt-dev-secret-key-replace-with-rsa256-in-prod"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # PostgreSQL DSN
    pg_dsn: str = "postgresql://postgres:password@localhost:5432/postgres"
    pg_pool_min: int = 2
    pg_pool_max: int = 20
    pg_statement_timeout_ms: int = 5000

    # Redis URL
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_url: str = "redis://localhost:6379/1"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]


settings = Settings()

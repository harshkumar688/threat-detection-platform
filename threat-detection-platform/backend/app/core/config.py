"""
Application Configuration

Loads all settings from environment variables using Pydantic Settings.
Provides a cached singleton via get_settings().
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Threat Detection Platform"
    app_version: str = "0.1.0"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_debug: bool = False
    backend_log_level: str = "INFO"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://threat_user:dev_password_change_in_production@localhost:5432/threat_detection"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- JWT ---
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # --- CORS ---
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:80"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # --- Rate Limiting ---
    rate_limit_per_minute: int = 100
    login_rate_limit_per_minute: int = 5

    # --- Evidence ---
    evidence_storage_path: str = "/app/evidence"
    evidence_retention_days: int = 90

    # --- Admin Seed (first-time setup) ---
    # Loaded from environment (.env). These defaults exist only for local
    # development convenience and MUST be overridden via environment
    # variables in any shared or production deployment.
    admin_email: str = "admin@threatplatform.local"
    admin_password: str = "admin123"
    admin_full_name: str = "System Administrator"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()

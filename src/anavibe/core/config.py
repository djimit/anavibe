"""Application configuration using Pydantic Settings.

This module provides centralized configuration management with:
- Environment variable loading
- Type validation
- Secure defaults
- Configuration validation at startup
"""

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import (
    AnyHttpUrl,
    BeforeValidator,
    Field,
    PostgresDsn,
    RedisDsn,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors_origins(v: Any) -> list[str]:
    """Parse CORS origins from string or list."""
    if isinstance(v, str):
        return [origin.strip() for origin in v.split(",") if origin.strip()]
    if isinstance(v, list):
        return v
    return []


CorsOrigins = Annotated[list[str], BeforeValidator(parse_cors_origins)]


class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Log level options."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All sensitive values should be provided via environment variables
    and NEVER committed to version control.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # Application Settings
    # =========================================================================
    app_name: str = Field(default="anavibe", description="Application name")
    app_env: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment",
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")

    # =========================================================================
    # Server Settings
    # =========================================================================
    host: str = Field(default="0.0.0.0", description="Server host")  # noqa: S104
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    workers: int = Field(default=4, ge=1, le=32, description="Number of workers")
    reload: bool = Field(default=False, description="Enable auto-reload")

    # =========================================================================
    # Security Settings
    # =========================================================================
    secret_key: str = Field(
        ...,
        min_length=32,
        description="Secret key for signing (minimum 32 characters)",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        ge=5,
        le=1440,
        description="Access token expiration in minutes",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Refresh token expiration in days",
    )
    api_key_header: str = Field(default="X-API-Key", description="API key header name")

    # =========================================================================
    # CORS Settings
    # =========================================================================
    cors_origins: CorsOrigins = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="Allow credentials in CORS",
    )

    # =========================================================================
    # Database Settings
    # =========================================================================
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL connection URL",
    )
    database_pool_size: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Database connection pool size",
    )
    database_max_overflow: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Max overflow connections",
    )
    database_pool_timeout: int = Field(
        default=30,
        ge=10,
        le=120,
        description="Connection pool timeout in seconds",
    )

    # =========================================================================
    # Redis Settings
    # =========================================================================
    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    redis_password: str | None = Field(default=None, description="Redis password")
    redis_ssl: bool = Field(default=False, description="Use SSL for Redis")

    # =========================================================================
    # Rate Limiting
    # =========================================================================
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests: int = Field(
        default=100,
        ge=10,
        le=10000,
        description="Max requests per window",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Rate limit window in seconds",
    )

    # =========================================================================
    # MCP A2A Settings
    # =========================================================================
    agent_registration_enabled: bool = Field(
        default=True,
        description="Allow agent registration",
    )
    agent_heartbeat_interval_seconds: int = Field(
        default=30,
        ge=10,
        le=300,
        description="Agent heartbeat interval",
    )
    agent_timeout_seconds: int = Field(
        default=120,
        ge=30,
        le=600,
        description="Agent timeout threshold",
    )
    message_queue_max_size: int = Field(
        default=1000,
        ge=100,
        le=100000,
        description="Max messages in queue",
    )
    message_retention_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Message retention in hours",
    )
    a2a_encryption_enabled: bool = Field(
        default=True,
        description="Enable A2A message encryption",
    )
    a2a_encryption_key: str | None = Field(
        default=None,
        description="Fernet key for A2A encryption",
    )

    # =========================================================================
    # Observability
    # =========================================================================
    metrics_enabled: bool = Field(default=True, description="Enable metrics")
    metrics_port: int = Field(default=9090, description="Metrics port")
    tracing_enabled: bool = Field(default=False, description="Enable tracing")
    tracing_endpoint: AnyHttpUrl | None = Field(
        default=None,
        description="Tracing endpoint",
    )
    log_file: Path | None = Field(default=None, description="Log file path")

    # =========================================================================
    # External Services
    # =========================================================================
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key",
    )
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key",
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate secret key strength."""
        if len(v) < 32:
            msg = "Secret key must be at least 32 characters"
            raise ValueError(msg)
        return v

    @field_validator("a2a_encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str | None) -> str | None:
        """Validate Fernet encryption key format."""
        if v is None:
            return v
        # Fernet keys are 32 bytes, base64-encoded = 44 characters
        if len(v) != 44:
            msg = "A2A encryption key must be a valid Fernet key (44 characters)"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Validate settings for production environment."""
        if self.app_env == Environment.PRODUCTION:
            if self.debug:
                msg = "Debug mode must be disabled in production"
                raise ValueError(msg)
            if self.reload:
                msg = "Auto-reload must be disabled in production"
                raise ValueError(msg)
            if "*" in self.cors_origins or "http://localhost" in str(self.cors_origins):
                msg = "Localhost CORS origins not allowed in production"
                raise ValueError(msg)
            if self.a2a_encryption_enabled and not self.a2a_encryption_key:
                msg = "A2A encryption key required when encryption is enabled"
                raise ValueError(msg)
        return self

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env == Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == Environment.PRODUCTION

    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.app_env == Environment.TESTING


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Returns:
        Settings instance loaded from environment.
    """
    return Settings()

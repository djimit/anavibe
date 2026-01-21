"""Authentication models for JWT tokens and API keys."""

from datetime import datetime

from pydantic import Field

from anavibe.models.base import AgentId, BaseSchema


class Token(BaseSchema):
    """JWT token response schema."""

    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Access token expiration in seconds")


class TokenPayload(BaseSchema):
    """Decoded JWT token payload."""

    sub: AgentId = Field(description="Token subject (agent ID)")
    exp: datetime = Field(description="Expiration timestamp")
    iat: datetime = Field(description="Issued at timestamp")
    type: str = Field(description="Token type (access/refresh)")
    jti: str | None = Field(default=None, description="JWT ID (for refresh tokens)")


class TokenRefresh(BaseSchema):
    """Request schema for token refresh."""

    refresh_token: str = Field(
        min_length=1,
        description="Refresh token",
    )


class ApiKeyCreate(BaseSchema):
    """Schema for creating an API key."""

    name: str = Field(
        min_length=1,
        max_length=64,
        description="API key name/description",
    )
    expires_in_days: int | None = Field(
        default=None,
        ge=1,
        le=365,
        description="Expiration in days (None = never)",
    )
    scopes: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Permission scopes",
    )


class ApiKeyResponse(BaseSchema):
    """Response for API key operations."""

    id: str = Field(description="API key ID")
    name: str = Field(description="API key name")
    prefix: str = Field(description="Key prefix for identification")
    created_at: datetime = Field(description="Creation timestamp")
    expires_at: datetime | None = Field(description="Expiration timestamp")
    last_used_at: datetime | None = Field(description="Last usage timestamp")
    scopes: list[str] = Field(description="Permission scopes")


class ApiKeyCreateResponse(ApiKeyResponse):
    """Response when creating a new API key (includes full key)."""

    key: str = Field(
        description="Full API key (only shown once)",
    )


class LoginRequest(BaseSchema):
    """Schema for agent login request."""

    agent_id: AgentId = Field(description="Agent identifier")
    api_key: str = Field(
        min_length=1,
        max_length=256,
        description="API key",
    )

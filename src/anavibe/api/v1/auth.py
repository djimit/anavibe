"""Authentication endpoints."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from anavibe.api.deps import CurrentAgent, Security, get_security_manager
from anavibe.core.config import get_settings
from anavibe.core.security import SecurityManager
from anavibe.exceptions import AuthenticationError, InvalidTokenError, TokenExpiredError
from anavibe.models.auth import LoginRequest, Token, TokenRefresh


router = APIRouter()


class TokenResponse(BaseModel):
    """Token response with expiration info."""

    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Access token expiration in seconds")


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    security: Security,
) -> TokenResponse:
    """Authenticate an agent and return tokens.

    This endpoint validates the agent's API key and returns
    JWT tokens for subsequent authenticated requests.
    """
    # In a real implementation, you would:
    # 1. Look up the agent by ID
    # 2. Verify the API key hash
    # 3. Check if the agent is active/not banned

    # Placeholder validation - replace with database lookup
    if not request.api_key.startswith("av_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    settings = get_settings()

    # Generate tokens
    access_token = security.create_access_token(
        subject=request.agent_id,
        additional_claims={"type": "access"},
    )
    refresh_token = security.create_refresh_token(
        subject=request.agent_id,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: TokenRefresh,
    security: Security,
) -> TokenResponse:
    """Refresh an access token using a refresh token.

    The refresh token must be valid and not expired.
    A new access token and refresh token are returned.
    """
    try:
        payload = security.verify_token(
            request.refresh_token,
            token_type="refresh",
        )
    except TokenExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        ) from e
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from e

    agent_id = payload.get("sub")
    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    settings = get_settings()

    # Generate new tokens
    new_access_token = security.create_access_token(
        subject=agent_id,
        additional_claims={"type": "access"},
    )
    new_refresh_token = security.create_refresh_token(
        subject=agent_id,
    )

    # TODO: Invalidate the old refresh token in the database

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/logout")
async def logout(
    agent_id: CurrentAgent,
) -> dict[str, str]:
    """Logout and invalidate tokens.

    In a stateless JWT setup, this is mainly for client-side
    token clearing. For true token invalidation, implement
    a token blacklist in Redis.
    """
    # TODO: Add token to blacklist in Redis
    return {"message": "Successfully logged out"}


@router.get("/me")
async def get_current_agent_info(
    agent_id: CurrentAgent,
) -> dict[str, str]:
    """Get information about the currently authenticated agent."""
    # TODO: Return full agent info from database
    return {
        "agent_id": agent_id,
        "authenticated": "true",
    }

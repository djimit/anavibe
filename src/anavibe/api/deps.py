"""FastAPI dependency injection functions.

Provides common dependencies for:
- Authentication and authorization
- Database sessions
- Security utilities
- Configuration access
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from anavibe.core.config import Settings, get_settings
from anavibe.core.security import SecurityManager
from anavibe.exceptions import AuthenticationError, InvalidTokenError, TokenExpiredError


# HTTP Bearer token security scheme
bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_security_manager() -> SecurityManager:
    """Get cached security manager instance.

    Returns:
        SecurityManager instance.
    """
    settings = get_settings()
    return SecurityManager(settings)


async def get_current_agent(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    security: Annotated[SecurityManager, Depends(get_security_manager)] = None,
) -> str:
    """Get current authenticated agent ID.

    Supports both JWT Bearer tokens and API key authentication.

    Args:
        credentials: Bearer token credentials.
        x_api_key: API key header.
        security: Security manager instance.

    Returns:
        Authenticated agent ID.

    Raises:
        HTTPException: If authentication fails.
    """
    if security is None:
        security = get_security_manager()

    # Try JWT authentication first
    if credentials and credentials.credentials:
        try:
            payload = security.verify_token(credentials.credentials)
            agent_id = payload.get("sub")
            if not agent_id:
                raise InvalidTokenError("Token missing subject")
            return agent_id
        except TokenExpiredError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e
        except InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    # Try API key authentication
    if x_api_key:
        # In a real implementation, you would look up the API key in the database
        # For now, we'll validate the format and return a placeholder
        if not x_api_key.startswith("av_"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key format",
            )
        # TODO: Look up API key in database and return associated agent ID
        # This is a placeholder - replace with actual database lookup
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key authentication requires database setup",
        )

    # No authentication provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_agent(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    security: Annotated[SecurityManager, Depends(get_security_manager)] = None,
) -> str | None:
    """Get current agent ID if authenticated, None otherwise.

    Args:
        credentials: Bearer token credentials.
        x_api_key: API key header.
        security: Security manager instance.

    Returns:
        Agent ID if authenticated, None otherwise.
    """
    if security is None:
        security = get_security_manager()

    if not credentials and not x_api_key:
        return None

    try:
        return await get_current_agent(credentials, x_api_key, security)
    except HTTPException:
        return None


def require_capability(required_capability: str):
    """Dependency factory for capability-based authorization.

    Args:
        required_capability: Capability required for the endpoint.

    Returns:
        Dependency function.
    """

    async def check_capability(
        agent_id: Annotated[str, Depends(get_current_agent)],
    ) -> str:
        """Check if agent has required capability.

        Args:
            agent_id: Authenticated agent ID.

        Returns:
            Agent ID if authorized.

        Raises:
            HTTPException: If agent lacks capability.
        """
        # TODO: Look up agent capabilities in database
        # For now, allow all authenticated agents
        return agent_id

    return check_capability


# Type aliases for cleaner dependency injection
CurrentAgent = Annotated[str, Depends(get_current_agent)]
OptionalAgent = Annotated[str | None, Depends(get_optional_agent)]
Security = Annotated[SecurityManager, Depends(get_security_manager)]
AppSettings = Annotated[Settings, Depends(get_settings)]

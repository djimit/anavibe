"""Custom exceptions for the Anavibe MCP A2A framework.

All exceptions follow a consistent pattern with error codes and
contextual information while avoiding exposure of sensitive data.
"""

from typing import Any


class AnavibeError(Exception):
    """Base exception for all Anavibe errors.

    Attributes:
        message: Human-readable error message.
        error_code: Machine-readable error code.
        details: Additional context (sanitized for external exposure).
    """

    error_code: str = "ANAVIBE_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message.
            details: Additional context for debugging.
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses.

        Returns:
            Dictionary with error information.
        """
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# =============================================================================
# Authentication & Authorization Exceptions
# =============================================================================


class AuthenticationError(AnavibeError):
    """Raised when authentication fails."""

    error_code = "AUTHENTICATION_FAILED"
    status_code = 401

    def __init__(
        self,
        message: str = "Authentication failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class AuthorizationError(AnavibeError):
    """Raised when authorization is denied."""

    error_code = "AUTHORIZATION_DENIED"
    status_code = 403

    def __init__(
        self,
        message: str = "Access denied",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class TokenExpiredError(AuthenticationError):
    """Raised when an authentication token has expired."""

    error_code = "TOKEN_EXPIRED"

    def __init__(
        self,
        message: str = "Token has expired",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class InvalidTokenError(AuthenticationError):
    """Raised when a token is invalid or malformed."""

    error_code = "INVALID_TOKEN"

    def __init__(
        self,
        message: str = "Invalid token",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


# =============================================================================
# Agent Exceptions
# =============================================================================


class AgentError(AnavibeError):
    """Base exception for agent-related errors."""

    error_code = "AGENT_ERROR"
    status_code = 400


class AgentNotFoundError(AgentError):
    """Raised when an agent is not found."""

    error_code = "AGENT_NOT_FOUND"
    status_code = 404

    def __init__(
        self,
        message: str = "Agent not found",
        *,
        agent_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if agent_id:
            details["agent_id"] = agent_id
        super().__init__(message, details=details)


class AgentExistsError(AgentError):
    """Raised when attempting to create an agent that already exists."""

    error_code = "AGENT_EXISTS"
    status_code = 409

    def __init__(
        self,
        message: str = "Agent already exists",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class AgentOfflineError(AgentError):
    """Raised when attempting to communicate with an offline agent."""

    error_code = "AGENT_OFFLINE"
    status_code = 503

    def __init__(
        self,
        message: str = "Agent is offline",
        *,
        agent_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if agent_id:
            details["agent_id"] = agent_id
        super().__init__(message, details=details)


class AgentCapabilityError(AgentError):
    """Raised when an agent lacks required capability."""

    error_code = "CAPABILITY_NOT_SUPPORTED"
    status_code = 400

    def __init__(
        self,
        message: str = "Agent does not support this capability",
        *,
        capability: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if capability:
            details["capability"] = capability
        super().__init__(message, details=details)


# =============================================================================
# Message Exceptions
# =============================================================================


class MessageError(AnavibeError):
    """Base exception for message-related errors."""

    error_code = "MESSAGE_ERROR"
    status_code = 400


class MessageNotFoundError(MessageError):
    """Raised when a message is not found."""

    error_code = "MESSAGE_NOT_FOUND"
    status_code = 404

    def __init__(
        self,
        message: str = "Message not found",
        *,
        message_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if message_id:
            details["message_id"] = message_id
        super().__init__(message, details=details)


class MessageDeliveryError(MessageError):
    """Raised when message delivery fails."""

    error_code = "MESSAGE_DELIVERY_FAILED"
    status_code = 503

    def __init__(
        self,
        message: str = "Failed to deliver message",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


class MessageValidationError(MessageError):
    """Raised when message validation fails."""

    error_code = "MESSAGE_VALIDATION_FAILED"
    status_code = 422

    def __init__(
        self,
        message: str = "Message validation failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


# =============================================================================
# Rate Limiting Exceptions
# =============================================================================


class RateLimitError(AnavibeError):
    """Raised when rate limit is exceeded."""

    error_code = "RATE_LIMIT_EXCEEDED"
    status_code = 429

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, details=details)
        self.retry_after = retry_after


# =============================================================================
# Validation Exceptions
# =============================================================================


class ValidationError(AnavibeError):
    """Raised when input validation fails."""

    error_code = "VALIDATION_ERROR"
    status_code = 422

    def __init__(
        self,
        message: str = "Validation failed",
        *,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(message, details=details)


# =============================================================================
# Configuration Exceptions
# =============================================================================


class ConfigurationError(AnavibeError):
    """Raised when configuration is invalid or missing."""

    error_code = "CONFIGURATION_ERROR"
    status_code = 500

    def __init__(
        self,
        message: str = "Configuration error",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)


# =============================================================================
# External Service Exceptions
# =============================================================================


class ExternalServiceError(AnavibeError):
    """Raised when an external service call fails."""

    error_code = "EXTERNAL_SERVICE_ERROR"
    status_code = 502

    def __init__(
        self,
        message: str = "External service error",
        *,
        service: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if service:
            details["service"] = service
        super().__init__(message, details=details)


class DatabaseError(ExternalServiceError):
    """Raised when a database operation fails."""

    error_code = "DATABASE_ERROR"

    def __init__(
        self,
        message: str = "Database operation failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, service="database", details=details)


class CacheError(ExternalServiceError):
    """Raised when a cache operation fails."""

    error_code = "CACHE_ERROR"

    def __init__(
        self,
        message: str = "Cache operation failed",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, service="cache", details=details)

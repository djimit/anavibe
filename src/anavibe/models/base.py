"""Base models and common utilities for Pydantic models."""

import re
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Type aliases for common patterns
AgentId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Agent identifier",
    ),
]

MessageId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Message identifier",
    ),
]

SafeString = Annotated[
    str,
    Field(
        min_length=1,
        max_length=1024,
        description="Sanitized string input",
    ),
]


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_default=True,
        use_enum_values=True,
    )


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Last update timestamp",
    )


class BaseResponse(BaseSchema):
    """Base response schema with common fields."""

    success: bool = Field(default=True, description="Request success status")
    message: str | None = Field(default=None, description="Response message")


class PaginatedResponse(BaseResponse):
    """Base schema for paginated responses."""

    total: int = Field(ge=0, description="Total number of items")
    page: int = Field(ge=1, description="Current page number")
    page_size: int = Field(ge=1, le=100, description="Items per page")
    pages: int = Field(ge=0, description="Total number of pages")


class ErrorResponse(BaseSchema):
    """Standard error response schema."""

    error: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error details",
    )


def sanitize_string(value: str) -> str:
    """Sanitize a string by removing potentially dangerous characters.

    Args:
        value: Input string to sanitize.

    Returns:
        Sanitized string.
    """
    # Remove null bytes and control characters (except newlines and tabs)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    return sanitized.strip()


def create_sanitized_validator(field_name: str) -> Any:
    """Create a field validator for sanitizing strings.

    Args:
        field_name: Name of the field to validate.

    Returns:
        Validator function.
    """

    @field_validator(field_name, mode="after")
    @classmethod
    def validate(cls, v: str) -> str:
        return sanitize_string(v)

    return validate

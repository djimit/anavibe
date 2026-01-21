"""Agent models for MCP A2A communication."""

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated

from pydantic import Field, field_validator

from anavibe.models.base import (
    AgentId,
    BaseSchema,
    SafeString,
    TimestampMixin,
    sanitize_string,
)


class AgentStatus(str, Enum):
    """Agent status enumeration."""

    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    MAINTENANCE = "maintenance"


class AgentCapability(str, Enum):
    """Standard agent capabilities."""

    CHAT = "chat"
    CODE = "code"
    ANALYSIS = "analysis"
    SEARCH = "search"
    FILE_OPERATIONS = "file_operations"
    WEB_BROWSE = "web_browse"
    DATA_PROCESSING = "data_processing"
    IMAGE_GENERATION = "image_generation"
    AUDIO_PROCESSING = "audio_processing"
    CUSTOM = "custom"


class AgentCreate(BaseSchema):
    """Schema for creating a new agent."""

    name: SafeString = Field(
        min_length=1,
        max_length=128,
        description="Human-readable agent name",
        examples=["my-assistant", "code-reviewer"],
    )
    description: str | None = Field(
        default=None,
        max_length=1024,
        description="Agent description",
    )
    capabilities: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="List of agent capabilities",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Additional agent metadata",
    )
    webhook_url: str | None = Field(
        default=None,
        max_length=2048,
        description="Webhook URL for notifications",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and sanitize agent name."""
        sanitized = sanitize_string(v)
        # Additional validation: must be alphanumeric with hyphens/underscores
        if not all(c.isalnum() or c in "-_" for c in sanitized):
            msg = "Name must contain only alphanumeric characters, hyphens, and underscores"
            raise ValueError(msg)
        return sanitized

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, v: list[str]) -> list[str]:
        """Validate and deduplicate capabilities."""
        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique = []
        for cap in v:
            sanitized = sanitize_string(cap).lower()
            if sanitized and sanitized not in seen:
                seen.add(sanitized)
                unique.append(sanitized)
        return unique

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate metadata keys and values."""
        if len(v) > 20:
            msg = "Maximum 20 metadata entries allowed"
            raise ValueError(msg)

        sanitized = {}
        for key, value in v.items():
            # Sanitize keys and values
            clean_key = sanitize_string(key)[:64]
            clean_value = sanitize_string(str(value))[:256]
            if clean_key:
                sanitized[clean_key] = clean_value
        return sanitized


class AgentUpdate(BaseSchema):
    """Schema for updating an agent."""

    name: SafeString | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Updated agent name",
    )
    description: str | None = Field(
        default=None,
        max_length=1024,
        description="Updated description",
    )
    capabilities: list[str] | None = Field(
        default=None,
        max_length=50,
        description="Updated capabilities",
    )
    status: AgentStatus | None = Field(
        default=None,
        description="Updated status",
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description="Updated metadata",
    )
    webhook_url: str | None = Field(
        default=None,
        max_length=2048,
        description="Updated webhook URL",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate and sanitize agent name."""
        if v is None:
            return None
        sanitized = sanitize_string(v)
        if not all(c.isalnum() or c in "-_" for c in sanitized):
            msg = "Name must contain only alphanumeric characters, hyphens, and underscores"
            raise ValueError(msg)
        return sanitized


class Agent(BaseSchema, TimestampMixin):
    """Full agent model."""

    id: AgentId = Field(description="Unique agent identifier")
    name: str = Field(description="Agent name")
    description: str | None = Field(default=None, description="Agent description")
    capabilities: list[str] = Field(
        default_factory=list,
        description="Agent capabilities",
    )
    status: AgentStatus = Field(
        default=AgentStatus.OFFLINE,
        description="Current status",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Agent metadata",
    )
    webhook_url: str | None = Field(default=None, description="Webhook URL")
    last_heartbeat: datetime | None = Field(
        default=None,
        description="Last heartbeat timestamp",
    )
    api_key_hash: str = Field(description="Hashed API key", exclude=True)

    @property
    def is_online(self) -> bool:
        """Check if agent is currently online."""
        return self.status == AgentStatus.ONLINE

    @property
    def is_available(self) -> bool:
        """Check if agent is available for communication."""
        return self.status in (AgentStatus.ONLINE, AgentStatus.BUSY)


class AgentResponse(BaseSchema):
    """Agent response schema for API responses."""

    id: AgentId = Field(description="Agent identifier")
    name: str = Field(description="Agent name")
    description: str | None = Field(default=None, description="Agent description")
    capabilities: list[str] = Field(description="Agent capabilities")
    status: AgentStatus = Field(description="Current status")
    metadata: dict[str, str] = Field(description="Agent metadata")
    created_at: datetime = Field(description="Creation timestamp")
    last_heartbeat: datetime | None = Field(description="Last heartbeat")


class AgentRegistrationResponse(BaseSchema):
    """Response for successful agent registration."""

    agent: AgentResponse = Field(description="Registered agent details")
    api_key: str = Field(
        description="API key (only shown once)",
        examples=["av_abc123..."],
    )


class AgentHeartbeat(BaseSchema):
    """Schema for agent heartbeat requests."""

    status: AgentStatus = Field(
        default=AgentStatus.ONLINE,
        description="Agent status",
    )
    load: Annotated[float, Field(ge=0, le=1)] = Field(
        default=0.0,
        description="Agent load (0.0 to 1.0)",
    )
    active_tasks: Annotated[int, Field(ge=0)] = Field(
        default=0,
        description="Number of active tasks",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Additional heartbeat data",
    )


class AgentList(BaseSchema):
    """Schema for listing agents."""

    agents: list[AgentResponse] = Field(description="List of agents")
    total: int = Field(ge=0, description="Total number of agents")
    online_count: int = Field(ge=0, description="Number of online agents")

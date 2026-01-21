"""Message models for agent-to-agent communication."""

import re
from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import Field, field_validator, model_validator

from anavibe.models.base import AgentId, BaseSchema, MessageId, sanitize_string


class MessagePriority(int, Enum):
    """Message priority levels."""

    LOW = 0
    NORMAL = 5
    HIGH = 8
    URGENT = 10


class MessageStatus(str, Enum):
    """Message delivery status."""

    PENDING = "pending"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    EXPIRED = "expired"


class MessageType(str, Enum):
    """Message type enumeration."""

    TEXT = "text"
    COMMAND = "command"
    RESPONSE = "response"
    EVENT = "event"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    BROADCAST = "broadcast"


class MessageCreate(BaseSchema):
    """Schema for creating a new message."""

    recipient_id: AgentId = Field(description="Recipient agent ID")
    content: str = Field(
        min_length=1,
        max_length=65536,
        description="Message content",
    )
    message_type: MessageType = Field(
        default=MessageType.TEXT,
        description="Type of message",
    )
    priority: MessagePriority = Field(
        default=MessagePriority.NORMAL,
        description="Message priority",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional message metadata",
    )
    reply_to: MessageId | None = Field(
        default=None,
        description="ID of message being replied to",
    )
    ttl_seconds: Annotated[int, Field(ge=60, le=86400)] = Field(
        default=3600,
        description="Time-to-live in seconds",
    )
    require_ack: bool = Field(
        default=False,
        description="Require delivery acknowledgment",
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Sanitize message content."""
        # Remove null bytes and most control characters
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", v)
        if not sanitized.strip():
            msg = "Message content cannot be empty"
            raise ValueError(msg)
        return sanitized

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate metadata size and content."""
        if len(v) > 50:
            msg = "Maximum 50 metadata entries allowed"
            raise ValueError(msg)

        # Validate total size (approximate JSON size)
        import json

        try:
            serialized = json.dumps(v)
            if len(serialized) > 16384:
                msg = "Metadata exceeds maximum size (16KB)"
                raise ValueError(msg)
        except (TypeError, ValueError) as e:
            msg = "Metadata must be JSON serializable"
            raise ValueError(msg) from e

        return v


class BroadcastMessage(BaseSchema):
    """Schema for broadcast messages to multiple agents."""

    recipient_ids: list[AgentId] = Field(
        min_length=1,
        max_length=100,
        description="List of recipient agent IDs",
    )
    content: str = Field(
        min_length=1,
        max_length=65536,
        description="Message content",
    )
    message_type: MessageType = Field(
        default=MessageType.BROADCAST,
        description="Type of message",
    )
    priority: MessagePriority = Field(
        default=MessagePriority.NORMAL,
        description="Message priority",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )
    ttl_seconds: Annotated[int, Field(ge=60, le=86400)] = Field(
        default=3600,
        description="Time-to-live in seconds",
    )

    @field_validator("recipient_ids")
    @classmethod
    def validate_recipients(cls, v: list[str]) -> list[str]:
        """Validate and deduplicate recipient IDs."""
        unique = list(dict.fromkeys(v))  # Preserve order, remove duplicates
        return unique


class AgentMessage(BaseSchema):
    """Full message model."""

    id: MessageId = Field(description="Unique message identifier")
    sender_id: AgentId = Field(description="Sender agent ID")
    recipient_id: AgentId = Field(description="Recipient agent ID")
    content: str = Field(description="Message content")
    message_type: MessageType = Field(description="Type of message")
    priority: MessagePriority = Field(description="Message priority")
    status: MessageStatus = Field(description="Delivery status")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Message metadata",
    )
    reply_to: MessageId | None = Field(
        default=None,
        description="ID of parent message",
    )
    created_at: datetime = Field(description="Creation timestamp")
    delivered_at: datetime | None = Field(
        default=None,
        description="Delivery timestamp",
    )
    read_at: datetime | None = Field(
        default=None,
        description="Read timestamp",
    )
    expires_at: datetime = Field(description="Expiration timestamp")
    signature: str | None = Field(
        default=None,
        description="Message signature for verification",
    )
    encrypted: bool = Field(
        default=False,
        description="Whether content is encrypted",
    )


class MessageResponse(BaseSchema):
    """Message response for API."""

    id: MessageId = Field(description="Message identifier")
    sender_id: AgentId = Field(description="Sender agent ID")
    recipient_id: AgentId = Field(description="Recipient agent ID")
    message_type: MessageType = Field(description="Type of message")
    priority: MessagePriority = Field(description="Message priority")
    status: MessageStatus = Field(description="Delivery status")
    created_at: datetime = Field(description="Creation timestamp")
    delivered_at: datetime | None = Field(description="Delivery timestamp")


class MessageAck(BaseSchema):
    """Message acknowledgment schema."""

    message_id: MessageId = Field(description="Message ID being acknowledged")
    status: MessageStatus = Field(description="New status")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Acknowledgment timestamp",
    )


class MessageQuery(BaseSchema):
    """Query parameters for listing messages."""

    sender_id: AgentId | None = Field(
        default=None,
        description="Filter by sender",
    )
    recipient_id: AgentId | None = Field(
        default=None,
        description="Filter by recipient",
    )
    status: MessageStatus | None = Field(
        default=None,
        description="Filter by status",
    )
    message_type: MessageType | None = Field(
        default=None,
        description="Filter by type",
    )
    min_priority: MessagePriority | None = Field(
        default=None,
        description="Minimum priority",
    )
    since: datetime | None = Field(
        default=None,
        description="Messages since timestamp",
    )
    until: datetime | None = Field(
        default=None,
        description="Messages until timestamp",
    )
    limit: Annotated[int, Field(ge=1, le=100)] = Field(
        default=50,
        description="Maximum results",
    )
    offset: Annotated[int, Field(ge=0)] = Field(
        default=0,
        description="Result offset",
    )

    @model_validator(mode="after")
    def validate_time_range(self) -> "MessageQuery":
        """Validate time range is valid."""
        if self.since and self.until and self.since > self.until:
            msg = "'since' must be before 'until'"
            raise ValueError(msg)
        return self


class MessageList(BaseSchema):
    """Paginated message list response."""

    messages: list[MessageResponse] = Field(description="List of messages")
    total: int = Field(ge=0, description="Total matching messages")
    has_more: bool = Field(description="Whether more messages exist")

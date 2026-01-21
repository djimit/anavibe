"""Unit tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from anavibe.models.agent import AgentCreate, AgentStatus, AgentUpdate
from anavibe.models.message import MessageCreate, MessagePriority, MessageType


class TestAgentCreate:
    """Tests for AgentCreate model."""

    def test_valid_agent_create(self) -> None:
        """Should create agent with valid data."""
        agent = AgentCreate(
            name="test-agent",
            description="A test agent",
            capabilities=["chat", "code"],
        )

        assert agent.name == "test-agent"
        assert agent.capabilities == ["chat", "code"]

    def test_name_sanitization(self) -> None:
        """Should sanitize agent name."""
        agent = AgentCreate(name="  test-agent  ")

        assert agent.name == "test-agent"

    def test_name_validation_invalid_chars(self) -> None:
        """Should reject invalid characters in name."""
        with pytest.raises(ValidationError):
            AgentCreate(name="test@agent!")

    def test_capabilities_deduplication(self) -> None:
        """Should deduplicate capabilities."""
        agent = AgentCreate(
            name="test-agent",
            capabilities=["chat", "chat", "code", "code"],
        )

        assert agent.capabilities == ["chat", "code"]

    def test_metadata_validation(self) -> None:
        """Should validate metadata."""
        agent = AgentCreate(
            name="test-agent",
            metadata={"key1": "value1", "key2": "value2"},
        )

        assert len(agent.metadata) == 2

    def test_metadata_max_entries(self) -> None:
        """Should reject too many metadata entries."""
        with pytest.raises(ValidationError):
            AgentCreate(
                name="test-agent",
                metadata={f"key{i}": f"value{i}" for i in range(25)},
            )

    def test_name_too_long(self) -> None:
        """Should reject name that's too long."""
        with pytest.raises(ValidationError):
            AgentCreate(name="a" * 200)


class TestAgentUpdate:
    """Tests for AgentUpdate model."""

    def test_partial_update(self) -> None:
        """Should allow partial updates."""
        update = AgentUpdate(name="new-name")

        assert update.name == "new-name"
        assert update.description is None
        assert update.status is None

    def test_status_update(self) -> None:
        """Should accept valid status."""
        update = AgentUpdate(status=AgentStatus.BUSY)

        assert update.status == AgentStatus.BUSY


class TestMessageCreate:
    """Tests for MessageCreate model."""

    def test_valid_message_create(self) -> None:
        """Should create message with valid data."""
        message = MessageCreate(
            recipient_id="agt_recipient123",
            content="Hello, World!",
        )

        assert message.content == "Hello, World!"
        assert message.priority == MessagePriority.NORMAL

    def test_content_sanitization(self) -> None:
        """Should sanitize message content."""
        message = MessageCreate(
            recipient_id="agt_recipient123",
            content="Hello\x00World",  # Null byte
        )

        assert "\x00" not in message.content

    def test_content_empty_after_sanitization(self) -> None:
        """Should reject empty content after sanitization."""
        with pytest.raises(ValidationError):
            MessageCreate(
                recipient_id="agt_recipient123",
                content="   ",  # Only whitespace
            )

    def test_priority_values(self) -> None:
        """Should accept valid priority values."""
        message = MessageCreate(
            recipient_id="agt_recipient123",
            content="Test",
            priority=MessagePriority.URGENT,
        )

        assert message.priority == MessagePriority.URGENT

    def test_message_type_values(self) -> None:
        """Should accept valid message types."""
        message = MessageCreate(
            recipient_id="agt_recipient123",
            content="Test",
            message_type=MessageType.COMMAND,
        )

        assert message.message_type == MessageType.COMMAND

    def test_metadata_size_limit(self) -> None:
        """Should reject oversized metadata."""
        with pytest.raises(ValidationError):
            MessageCreate(
                recipient_id="agt_recipient123",
                content="Test",
                metadata={f"key{i}": "x" * 1000 for i in range(100)},
            )

    def test_ttl_bounds(self) -> None:
        """Should enforce TTL bounds."""
        # Valid TTL
        message = MessageCreate(
            recipient_id="agt_recipient123",
            content="Test",
            ttl_seconds=3600,
        )
        assert message.ttl_seconds == 3600

        # TTL too low
        with pytest.raises(ValidationError):
            MessageCreate(
                recipient_id="agt_recipient123",
                content="Test",
                ttl_seconds=30,  # Below minimum of 60
            )

        # TTL too high
        with pytest.raises(ValidationError):
            MessageCreate(
                recipient_id="agt_recipient123",
                content="Test",
                ttl_seconds=100000,  # Above maximum of 86400
            )

    def test_recipient_id_format(self) -> None:
        """Should validate recipient ID format."""
        # Valid format
        message = MessageCreate(
            recipient_id="agt_valid123",
            content="Test",
        )
        assert message.recipient_id == "agt_valid123"

        # Invalid format (special characters)
        with pytest.raises(ValidationError):
            MessageCreate(
                recipient_id="agt@invalid!",
                content="Test",
            )

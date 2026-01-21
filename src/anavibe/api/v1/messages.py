"""Message endpoints for agent-to-agent communication."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from anavibe.api.deps import CurrentAgent, Security
from anavibe.core.logging import get_logger
from anavibe.models.message import (
    AgentMessage,
    BroadcastMessage,
    MessageAck,
    MessageCreate,
    MessageList,
    MessagePriority,
    MessageResponse,
    MessageStatus,
    MessageType,
)


router = APIRouter()
logger = get_logger(__name__)

# In-memory storage for demo purposes
# Replace with database in production
_messages: dict[str, AgentMessage] = {}


def _generate_message_id() -> str:
    """Generate a unique message ID."""
    return f"msg_{secrets.token_urlsafe(16)}"


@router.post(
    "",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    request: MessageCreate,
    agent_id: CurrentAgent,
    security: Security,
) -> MessageResponse:
    """Send a message to another agent.

    The message will be queued for delivery to the recipient.
    """
    # Validate recipient exists (in production, check database)
    # For demo, we skip this check

    # Generate message ID
    message_id = _generate_message_id()
    now = datetime.now(UTC)

    # Calculate expiration
    expires_at = now + timedelta(seconds=request.ttl_seconds)

    # Sign message content if encryption is enabled
    signature = None
    encrypted = False

    if security._fernet:
        try:
            content_bytes = request.content.encode("utf-8")
            signature = security.sign_message(content_bytes)
            # Optionally encrypt the content
            # encrypted_content = security.encrypt_message(content_bytes)
            # encrypted = True
        except Exception:
            logger.warning("message_signing_failed", message_id=message_id)

    # Create message
    message = AgentMessage(
        id=message_id,
        sender_id=agent_id,
        recipient_id=request.recipient_id,
        content=request.content,
        message_type=request.message_type,
        priority=request.priority,
        status=MessageStatus.PENDING,
        metadata=request.metadata,
        reply_to=request.reply_to,
        created_at=now,
        expires_at=expires_at,
        signature=signature,
        encrypted=encrypted,
    )

    _messages[message_id] = message

    logger.info(
        "message_sent",
        message_id=message_id,
        sender=agent_id,
        recipient=request.recipient_id,
        type=request.message_type.value,
        priority=request.priority.value,
    )

    return MessageResponse(
        id=message.id,
        sender_id=message.sender_id,
        recipient_id=message.recipient_id,
        message_type=message.message_type,
        priority=message.priority,
        status=message.status,
        created_at=message.created_at,
        delivered_at=message.delivered_at,
    )


@router.post(
    "/broadcast",
    response_model=list[MessageResponse],
    status_code=status.HTTP_201_CREATED,
)
async def broadcast_message(
    request: BroadcastMessage,
    agent_id: CurrentAgent,
    security: Security,
) -> list[MessageResponse]:
    """Broadcast a message to multiple agents.

    Sends the same message to all specified recipients.
    """
    responses = []
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=request.ttl_seconds)

    for recipient_id in request.recipient_ids:
        message_id = _generate_message_id()

        message = AgentMessage(
            id=message_id,
            sender_id=agent_id,
            recipient_id=recipient_id,
            content=request.content,
            message_type=request.message_type,
            priority=request.priority,
            status=MessageStatus.PENDING,
            metadata=request.metadata,
            created_at=now,
            expires_at=expires_at,
        )

        _messages[message_id] = message

        responses.append(
            MessageResponse(
                id=message.id,
                sender_id=message.sender_id,
                recipient_id=message.recipient_id,
                message_type=message.message_type,
                priority=message.priority,
                status=message.status,
                created_at=message.created_at,
                delivered_at=message.delivered_at,
            )
        )

    logger.info(
        "broadcast_sent",
        sender=agent_id,
        recipient_count=len(request.recipient_ids),
    )

    return responses


@router.get("", response_model=MessageList)
async def list_messages(
    agent_id: CurrentAgent,
    sent: Annotated[bool, Query()] = False,
    status_filter: Annotated[MessageStatus | None, Query(alias="status")] = None,
    message_type: Annotated[MessageType | None, Query(alias="type")] = None,
    min_priority: Annotated[MessagePriority | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MessageList:
    """List messages for the current agent.

    By default, lists received messages. Set sent=true for sent messages.
    """
    # Filter messages
    if sent:
        messages = [m for m in _messages.values() if m.sender_id == agent_id]
    else:
        messages = [m for m in _messages.values() if m.recipient_id == agent_id]

    # Apply additional filters
    if status_filter:
        messages = [m for m in messages if m.status == status_filter]
    if message_type:
        messages = [m for m in messages if m.message_type == message_type]
    if min_priority is not None:
        messages = [m for m in messages if m.priority >= min_priority]

    # Sort by priority (desc) then created_at (desc)
    messages.sort(key=lambda m: (-m.priority.value, -m.created_at.timestamp()))

    # Paginate
    total = len(messages)
    has_more = total > offset + limit
    messages = messages[offset : offset + limit]

    return MessageList(
        messages=[
            MessageResponse(
                id=m.id,
                sender_id=m.sender_id,
                recipient_id=m.recipient_id,
                message_type=m.message_type,
                priority=m.priority,
                status=m.status,
                created_at=m.created_at,
                delivered_at=m.delivered_at,
            )
            for m in messages
        ],
        total=total,
        has_more=has_more,
    )


@router.get("/{message_id}", response_model=AgentMessage)
async def get_message(
    message_id: str,
    agent_id: CurrentAgent,
) -> AgentMessage:
    """Get a specific message by ID.

    Only the sender or recipient can access the message.
    """
    message = _messages.get(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    # Check authorization
    if message.sender_id != agent_id and message.recipient_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this message",
        )

    # Mark as read if recipient is accessing
    if message.recipient_id == agent_id and message.status == MessageStatus.DELIVERED:
        message.status = MessageStatus.READ
        message.read_at = datetime.now(UTC)
        _messages[message_id] = message

    return message


@router.post("/{message_id}/ack", response_model=MessageResponse)
async def acknowledge_message(
    message_id: str,
    request: MessageAck,
    agent_id: CurrentAgent,
) -> MessageResponse:
    """Acknowledge receipt or reading of a message.

    Only the recipient can acknowledge a message.
    """
    message = _messages.get(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    if message.recipient_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recipient can acknowledge message",
        )

    # Update status
    now = datetime.now(UTC)

    if request.status == MessageStatus.DELIVERED:
        message.status = MessageStatus.DELIVERED
        message.delivered_at = now
    elif request.status == MessageStatus.READ:
        message.status = MessageStatus.READ
        message.delivered_at = message.delivered_at or now
        message.read_at = now

    _messages[message_id] = message

    logger.info(
        "message_acknowledged",
        message_id=message_id,
        status=request.status.value,
    )

    return MessageResponse(
        id=message.id,
        sender_id=message.sender_id,
        recipient_id=message.recipient_id,
        message_type=message.message_type,
        priority=message.priority,
        status=message.status,
        created_at=message.created_at,
        delivered_at=message.delivered_at,
    )


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: str,
    agent_id: CurrentAgent,
) -> None:
    """Delete a message.

    Only the sender can delete a message.
    """
    message = _messages.get(message_id)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    if message.sender_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only sender can delete message",
        )

    del _messages[message_id]
    logger.info("message_deleted", message_id=message_id)

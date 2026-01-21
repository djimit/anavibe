"""Agent management endpoints."""

import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from anavibe.api.deps import CurrentAgent, Security
from anavibe.core.logging import get_logger
from anavibe.models.agent import (
    Agent,
    AgentCreate,
    AgentHeartbeat,
    AgentList,
    AgentRegistrationResponse,
    AgentResponse,
    AgentStatus,
    AgentUpdate,
)


router = APIRouter()
logger = get_logger(__name__)

# In-memory storage for demo purposes
# Replace with database in production
_agents: dict[str, Agent] = {}


def _generate_agent_id() -> str:
    """Generate a unique agent ID."""
    return f"agt_{secrets.token_urlsafe(12)}"


@router.post(
    "/register",
    response_model=AgentRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_agent(
    request: AgentCreate,
    security: Security,
) -> AgentRegistrationResponse:
    """Register a new agent in the system.

    Creates a new agent with the provided details and returns
    an API key for authentication. The API key is only shown once.
    """
    # Check for duplicate name
    for agent in _agents.values():
        if agent.name == request.name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent with this name already exists",
            )

    # Generate agent ID and API key
    agent_id = _generate_agent_id()
    api_key = security.generate_api_key()
    api_key_hash = security.hash_api_key(api_key)

    # Create agent
    now = datetime.now(UTC)
    agent = Agent(
        id=agent_id,
        name=request.name,
        description=request.description,
        capabilities=request.capabilities,
        status=AgentStatus.OFFLINE,
        metadata=request.metadata,
        webhook_url=request.webhook_url,
        created_at=now,
        updated_at=now,
        api_key_hash=api_key_hash,
    )

    _agents[agent_id] = agent

    logger.info(
        "agent_registered",
        agent_id=agent_id,
        name=request.name,
        capabilities=request.capabilities,
    )

    return AgentRegistrationResponse(
        agent=AgentResponse(
            id=agent.id,
            name=agent.name,
            description=agent.description,
            capabilities=agent.capabilities,
            status=agent.status,
            metadata=agent.metadata,
            created_at=agent.created_at,
            last_heartbeat=agent.last_heartbeat,
        ),
        api_key=api_key,
    )


@router.get("", response_model=AgentList)
async def list_agents(
    agent_id: CurrentAgent,
    status_filter: Annotated[AgentStatus | None, Query(alias="status")] = None,
    capability: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AgentList:
    """List all registered agents.

    Supports filtering by status and capability.
    """
    agents = list(_agents.values())

    # Apply filters
    if status_filter:
        agents = [a for a in agents if a.status == status_filter]
    if capability:
        agents = [a for a in agents if capability in a.capabilities]

    # Count online agents
    online_count = sum(1 for a in agents if a.status == AgentStatus.ONLINE)

    # Paginate
    total = len(agents)
    agents = agents[offset : offset + limit]

    return AgentList(
        agents=[
            AgentResponse(
                id=a.id,
                name=a.name,
                description=a.description,
                capabilities=a.capabilities,
                status=a.status,
                metadata=a.metadata,
                created_at=a.created_at,
                last_heartbeat=a.last_heartbeat,
            )
            for a in agents
        ],
        total=total,
        online_count=online_count,
    )


@router.get("/{target_agent_id}", response_model=AgentResponse)
async def get_agent(
    target_agent_id: str,
    agent_id: CurrentAgent,
) -> AgentResponse:
    """Get details of a specific agent."""
    agent = _agents.get(target_agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        capabilities=agent.capabilities,
        status=agent.status,
        metadata=agent.metadata,
        created_at=agent.created_at,
        last_heartbeat=agent.last_heartbeat,
    )


@router.patch("/{target_agent_id}", response_model=AgentResponse)
async def update_agent(
    target_agent_id: str,
    request: AgentUpdate,
    agent_id: CurrentAgent,
) -> AgentResponse:
    """Update an agent's details.

    Only the owning agent can update its own details.
    """
    if target_agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only update your own agent",
        )

    agent = _agents.get(target_agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(agent, field) and value is not None:
            setattr(agent, field, value)

    agent.updated_at = datetime.now(UTC)
    _agents[target_agent_id] = agent

    logger.info("agent_updated", agent_id=target_agent_id, fields=list(update_data.keys()))

    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        capabilities=agent.capabilities,
        status=agent.status,
        metadata=agent.metadata,
        created_at=agent.created_at,
        last_heartbeat=agent.last_heartbeat,
    )


@router.post("/{target_agent_id}/heartbeat")
async def agent_heartbeat(
    target_agent_id: str,
    request: AgentHeartbeat,
    agent_id: CurrentAgent,
) -> dict[str, str]:
    """Send a heartbeat to indicate agent is alive.

    Must be called periodically to maintain online status.
    """
    if target_agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only send heartbeat for your own agent",
        )

    agent = _agents.get(target_agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # Update heartbeat
    agent.status = request.status
    agent.last_heartbeat = datetime.now(UTC)
    agent.updated_at = agent.last_heartbeat

    # Update metadata from heartbeat
    if request.metadata:
        agent.metadata.update(request.metadata)

    _agents[target_agent_id] = agent

    return {"status": "ok", "timestamp": agent.last_heartbeat.isoformat()}


@router.delete("/{target_agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    target_agent_id: str,
    agent_id: CurrentAgent,
) -> None:
    """Delete an agent.

    Only the owning agent can delete itself.
    """
    if target_agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only delete your own agent",
        )

    if target_agent_id not in _agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    del _agents[target_agent_id]
    logger.info("agent_deleted", agent_id=target_agent_id)

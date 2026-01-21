"""Pytest configuration and shared fixtures."""

import os
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# Set test environment before importing app
os.environ["APP_ENV"] = "testing"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-characters-long"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["DEBUG"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Configure anyio backend for async tests."""
    return "asyncio"


@pytest.fixture(scope="module")
def test_app():
    """Create test application instance."""
    from anavibe.server import create_application

    app = create_application()
    return app


@pytest.fixture(scope="module")
def client(test_app) -> Generator[TestClient, None, None]:
    """Create synchronous test client."""
    with TestClient(test_app) as client:
        yield client


@pytest.fixture
async def async_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Create asynchronous test client."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def security_manager():
    """Create security manager for testing."""
    from anavibe.core.config import get_settings
    from anavibe.core.security import SecurityManager

    settings = get_settings()
    return SecurityManager(settings)


@pytest.fixture
def valid_agent_token(security_manager) -> str:
    """Generate a valid agent token for testing."""
    return security_manager.create_access_token(
        subject="test-agent-001",
        additional_claims={"type": "access"},
    )


@pytest.fixture
def auth_headers(valid_agent_token: str) -> dict[str, str]:
    """Create authorization headers with valid token."""
    return {"Authorization": f"Bearer {valid_agent_token}"}


@pytest.fixture
def sample_agent_data() -> dict[str, Any]:
    """Sample agent creation data."""
    return {
        "name": "test-agent",
        "description": "A test agent for unit testing",
        "capabilities": ["chat", "code"],
        "metadata": {"version": "1.0"},
    }


@pytest.fixture
def sample_message_data() -> dict[str, Any]:
    """Sample message creation data."""
    return {
        "recipient_id": "agt_recipient123",
        "content": "Hello, this is a test message",
        "message_type": "text",
        "priority": 5,
        "metadata": {"test": "true"},
        "ttl_seconds": 3600,
    }

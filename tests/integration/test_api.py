"""Integration tests for API endpoints."""

from typing import Any

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self, client: TestClient) -> None:
        """Should return healthy status."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_readiness_check(self, client: TestClient) -> None:
        """Should return readiness status."""
        response = client.get("/api/v1/ready")

        assert response.status_code == 200
        data = response.json()
        assert "ready" in data
        assert "checks" in data

    def test_liveness_check(self, client: TestClient) -> None:
        """Should return alive status."""
        response = client.get("/api/v1/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    def test_login_invalid_credentials(self, client: TestClient) -> None:
        """Should reject invalid credentials."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "agent_id": "test-agent",
                "api_key": "invalid_key",  # Doesn't start with av_
            },
        )

        assert response.status_code == 401

    def test_login_valid_format(self, client: TestClient) -> None:
        """Should accept valid credential format."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "agent_id": "test-agent",
                "api_key": "av_test_key_12345",
            },
        )

        # In test mode, this should return tokens
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_get_me_unauthorized(self, client: TestClient) -> None:
        """Should require authentication."""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401

    def test_get_me_authorized(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Should return agent info when authenticated."""
        response = client.get("/api/v1/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "agent_id" in data


class TestAgentEndpoints:
    """Tests for agent management endpoints."""

    def test_register_agent(self, client: TestClient) -> None:
        """Should register new agent."""
        response = client.post(
            "/api/v1/agents/register",
            json={
                "name": "new-test-agent",
                "description": "A new test agent",
                "capabilities": ["chat"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "agent" in data
        assert "api_key" in data
        assert data["agent"]["name"] == "new-test-agent"
        assert data["api_key"].startswith("av_")

    def test_register_agent_duplicate_name(self, client: TestClient) -> None:
        """Should reject duplicate agent names."""
        # Register first agent
        client.post(
            "/api/v1/agents/register",
            json={"name": "duplicate-agent", "capabilities": []},
        )

        # Try to register with same name
        response = client.post(
            "/api/v1/agents/register",
            json={"name": "duplicate-agent", "capabilities": []},
        )

        assert response.status_code == 409

    def test_list_agents_unauthorized(self, client: TestClient) -> None:
        """Should require authentication to list agents."""
        response = client.get("/api/v1/agents")

        assert response.status_code == 401

    def test_list_agents_authorized(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Should list agents when authenticated."""
        response = client.get("/api/v1/agents", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "total" in data


class TestMessageEndpoints:
    """Tests for message endpoints."""

    def test_send_message_unauthorized(
        self,
        client: TestClient,
        sample_message_data: dict[str, Any],
    ) -> None:
        """Should require authentication to send message."""
        response = client.post("/api/v1/messages", json=sample_message_data)

        assert response.status_code == 401

    def test_send_message_authorized(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        sample_message_data: dict[str, Any],
    ) -> None:
        """Should send message when authenticated."""
        response = client.post(
            "/api/v1/messages",
            json=sample_message_data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["recipient_id"] == sample_message_data["recipient_id"]

    def test_list_messages_unauthorized(self, client: TestClient) -> None:
        """Should require authentication to list messages."""
        response = client.get("/api/v1/messages")

        assert response.status_code == 401

    def test_list_messages_authorized(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Should list messages when authenticated."""
        response = client.get("/api/v1/messages", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert "total" in data


class TestSecurityHeaders:
    """Tests for security headers."""

    def test_security_headers_present(self, client: TestClient) -> None:
        """Should include security headers in response."""
        response = client.get("/api/v1/health")

        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "Strict-Transport-Security" in response.headers
        assert "Content-Security-Policy" in response.headers

    def test_correlation_id_header(self, client: TestClient) -> None:
        """Should return correlation ID header."""
        response = client.get("/api/v1/health")

        assert "X-Correlation-ID" in response.headers

    def test_timing_header(self, client: TestClient) -> None:
        """Should return timing header."""
        response = client.get("/api/v1/health")

        assert "X-Response-Time" in response.headers
        assert "ms" in response.headers["X-Response-Time"]


class TestErrorHandling:
    """Tests for error handling."""

    def test_validation_error_format(self, client: TestClient) -> None:
        """Should return proper validation error format."""
        response = client.post(
            "/api/v1/agents/register",
            json={"name": ""},  # Empty name should fail validation
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "VALIDATION_ERROR"
        assert "details" in data
        assert "errors" in data["details"]

    def test_not_found_error(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Should return 404 for non-existent resources."""
        response = client.get(
            "/api/v1/agents/nonexistent123",
            headers=auth_headers,
        )

        assert response.status_code == 404

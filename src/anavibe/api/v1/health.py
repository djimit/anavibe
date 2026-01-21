"""Health check endpoints."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from anavibe import __version__


router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(description="Health status")
    version: str = Field(description="Application version")
    timestamp: datetime = Field(description="Current server time")
    checks: dict[str, Any] = Field(
        default_factory=dict,
        description="Individual health checks",
    )


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    ready: bool = Field(description="Whether the service is ready")
    checks: dict[str, bool] = Field(description="Individual readiness checks")


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check endpoint.

    Returns basic service health status.
    """
    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp=datetime.now(UTC),
        checks={
            "api": "ok",
        },
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    """Readiness check endpoint.

    Checks if the service is ready to accept traffic.
    In production, this would check database, Redis, etc.
    """
    checks = {
        "api": True,
        # TODO: Add database check
        # TODO: Add Redis check
    }

    all_ready = all(checks.values())

    return ReadinessResponse(
        ready=all_ready,
        checks=checks,
    )


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """Kubernetes liveness probe endpoint.

    Simple check that the service is running.
    """
    return {"status": "alive"}

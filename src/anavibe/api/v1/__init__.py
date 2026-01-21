"""API v1 routes."""

from fastapi import APIRouter

from anavibe.api.v1 import agents, auth, health, messages


router = APIRouter(prefix="/api/v1")

# Include sub-routers
router.include_router(health.router, tags=["Health"])
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(agents.router, prefix="/agents", tags=["Agents"])
router.include_router(messages.router, prefix="/messages", tags=["Messages"])

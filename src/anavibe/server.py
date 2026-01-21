"""Main FastAPI application server.

This module configures and runs the Anavibe MCP A2A server
with all middleware, routes, and security settings.
"""

import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from anavibe import __version__
from anavibe.api.v1 import router as api_v1_router
from anavibe.core.config import get_settings
from anavibe.core.logging import configure_logging, get_logger
from anavibe.exceptions import AnavibeError
from anavibe.middleware.security import (
    CorrelationIdMiddleware,
    RequestTimingMiddleware,
    RequestValidationMiddleware,
    SecurityHeadersMiddleware,
)


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Handles startup and shutdown events.
    """
    settings = get_settings()
    configure_logging(settings)

    logger.info(
        "application_starting",
        version=__version__,
        environment=settings.app_env.value,
        debug=settings.debug,
    )

    # Startup: Initialize connections, caches, etc.
    # TODO: Initialize database connection pool
    # TODO: Initialize Redis connection
    # TODO: Start background tasks (heartbeat monitor, message cleanup)

    yield

    # Shutdown: Clean up resources
    logger.info("application_shutting_down")
    # TODO: Close database connections
    # TODO: Close Redis connections
    # TODO: Stop background tasks


def create_application() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application.
    """
    settings = get_settings()

    app = FastAPI(
        title="Anavibe MCP A2A",
        description="Model Context Protocol Agent-to-Agent Communication Framework",
        version=__version__,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # Add middleware (order matters - first added = last executed)

    # Security headers
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts_max_age=31536000,
        include_subdomains=True,
        frame_options="DENY",
        csp_policy="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    )

    # Request validation
    app.add_middleware(RequestValidationMiddleware)

    # Request timing
    app.add_middleware(RequestTimingMiddleware)

    # Correlation ID
    app.add_middleware(CorrelationIdMiddleware)

    # Rate limiting (requires Redis)
    # if settings.rate_limit_enabled:
    #     from anavibe.middleware.rate_limit import RateLimitMiddleware, RateLimiter
    #     rate_limiter = RateLimiter(redis_client, ...)
    #     app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)

    # Register exception handlers
    register_exception_handlers(app)

    # Include API routes
    app.include_router(api_v1_router)

    return app


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers.

    Args:
        app: FastAPI application.
    """

    @app.exception_handler(AnavibeError)
    async def anavibe_exception_handler(
        request: Request,
        exc: AnavibeError,
    ) -> JSONResponse:
        """Handle Anavibe custom exceptions."""
        logger.warning(
            "anavibe_error",
            error_code=exc.error_code,
            message=exc.message,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        """Handle HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP_ERROR",
                "message": str(exc.detail),
                "details": {},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Handle request validation errors."""
        # Sanitize error details to avoid exposing internal info
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error.get("loc", [])),
                "message": error.get("msg", "Invalid value"),
                "type": error.get("type", "value_error"),
            })

        logger.warning(
            "validation_error",
            path=request.url.path,
            error_count=len(errors),
        )

        return JSONResponse(
            status_code=422,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": errors},
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        # Log the full exception for debugging
        logger.exception(
            "unexpected_error",
            path=request.url.path,
            error_type=type(exc).__name__,
        )

        # Return generic error to client (don't expose internal details)
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {},
            },
        )


# Create the application instance
app = create_application()


def run() -> None:
    """Run the server using uvicorn."""
    settings = get_settings()

    uvicorn.run(
        "anavibe.server:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=1 if settings.reload else settings.workers,
        log_level=settings.log_level.value.lower(),
        access_log=settings.is_development,
    )


if __name__ == "__main__":
    run()

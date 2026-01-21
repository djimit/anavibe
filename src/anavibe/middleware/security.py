"""Security middleware for request/response processing.

Implements:
- Security headers (HSTS, CSP, X-Frame-Options, etc.)
- Request correlation IDs
- Timing attack protection
- Request validation
"""

import secrets
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from anavibe.core.logging import correlation_id_var, get_logger


if TYPE_CHECKING:
    from starlette.types import ASGIApp


logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses.

    Adds headers recommended by OWASP and security best practices.
    """

    def __init__(
        self,
        app: "ASGIApp",
        *,
        hsts_max_age: int = 31536000,
        include_subdomains: bool = True,
        frame_options: str = "DENY",
        content_type_nosniff: bool = True,
        xss_protection: bool = True,
        referrer_policy: str = "strict-origin-when-cross-origin",
        csp_policy: str | None = None,
        permissions_policy: str | None = None,
    ) -> None:
        """Initialize security headers middleware.

        Args:
            app: ASGI application.
            hsts_max_age: Max age for HSTS header in seconds.
            include_subdomains: Include subdomains in HSTS.
            frame_options: X-Frame-Options value.
            content_type_nosniff: Enable X-Content-Type-Options.
            xss_protection: Enable X-XSS-Protection.
            referrer_policy: Referrer-Policy value.
            csp_policy: Content-Security-Policy value.
            permissions_policy: Permissions-Policy value.
        """
        super().__init__(app)
        self.hsts_max_age = hsts_max_age
        self.include_subdomains = include_subdomains
        self.frame_options = frame_options
        self.content_type_nosniff = content_type_nosniff
        self.xss_protection = xss_protection
        self.referrer_policy = referrer_policy
        self.csp_policy = csp_policy or "default-src 'self'"
        self.permissions_policy = permissions_policy

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request and add security headers to response.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler.

        Returns:
            HTTP response with security headers.
        """
        response = await call_next(request)

        # HSTS - HTTP Strict Transport Security
        hsts_value = f"max-age={self.hsts_max_age}"
        if self.include_subdomains:
            hsts_value += "; includeSubDomains"
        response.headers["Strict-Transport-Security"] = hsts_value

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = self.frame_options

        # Prevent MIME type sniffing
        if self.content_type_nosniff:
            response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS Protection (legacy but still useful)
        if self.xss_protection:
            response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer Policy
        response.headers["Referrer-Policy"] = self.referrer_policy

        # Content Security Policy
        response.headers["Content-Security-Policy"] = self.csp_policy

        # Permissions Policy (if configured)
        if self.permissions_policy:
            response.headers["Permissions-Policy"] = self.permissions_policy

        # Prevent caching of sensitive responses
        if request.url.path.startswith("/api/v1/auth"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        return response


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to handle request correlation IDs.

    Ensures every request has a unique correlation ID for tracing.
    """

    CORRELATION_ID_HEADER = "X-Correlation-ID"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request with correlation ID tracking.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler.

        Returns:
            HTTP response with correlation ID header.
        """
        # Get or generate correlation ID
        correlation_id = request.headers.get(
            self.CORRELATION_ID_HEADER,
            secrets.token_urlsafe(16),
        )

        # Set in context variable for logging
        correlation_id_var.set(correlation_id)

        # Process request
        response = await call_next(request)

        # Add correlation ID to response
        response.headers[self.CORRELATION_ID_HEADER] = correlation_id

        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware to track request timing.

    Adds timing information to responses and logs slow requests.
    """

    SLOW_REQUEST_THRESHOLD_MS = 1000  # 1 second

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request with timing tracking.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler.

        Returns:
            HTTP response with timing header.
        """
        start_time = time.perf_counter()

        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Add timing header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Log slow requests
        if duration_ms > self.SLOW_REQUEST_THRESHOLD_MS:
            logger.warning(
                "slow_request",
                path=request.url.path,
                method=request.method,
                duration_ms=duration_ms,
            )

        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for request validation and sanitization.

    Validates:
    - Content-Type headers
    - Request size limits
    - Path traversal attempts
    """

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    ALLOWED_CONTENT_TYPES = frozenset({
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    })

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Validate and process request.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler.

        Returns:
            HTTP response or error response.
        """
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_CONTENT_LENGTH:
            return Response(
                content='{"error": "REQUEST_TOO_LARGE", "message": "Request body too large"}',
                status_code=413,
                media_type="application/json",
            )

        # Validate content type for requests with body
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "").split(";")[0].strip()
            if content_type and content_type not in self.ALLOWED_CONTENT_TYPES:
                return Response(
                    content='{"error": "UNSUPPORTED_MEDIA_TYPE", "message": "Unsupported content type"}',
                    status_code=415,
                    media_type="application/json",
                )

        # Check for path traversal attempts
        if ".." in request.url.path:
            logger.warning(
                "path_traversal_attempt",
                path=request.url.path,
                client=request.client.host if request.client else "unknown",
            )
            return Response(
                content='{"error": "BAD_REQUEST", "message": "Invalid request path"}',
                status_code=400,
                media_type="application/json",
            )

        return await call_next(request)

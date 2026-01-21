"""Rate limiting middleware using sliding window algorithm.

Implements:
- Per-client rate limiting
- Per-endpoint rate limiting
- Sliding window algorithm for accurate limiting
- Redis-backed for distributed deployments
"""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from anavibe.core.logging import get_logger
from anavibe.exceptions import RateLimitError


if TYPE_CHECKING:
    from redis.asyncio import Redis
    from starlette.types import ASGIApp


logger = get_logger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit rule."""

    requests: int  # Maximum requests allowed
    window_seconds: int  # Time window in seconds


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    reset_at: int
    retry_after: int | None = None


class RateLimiter:
    """Rate limiter using sliding window algorithm with Redis backend."""

    def __init__(
        self,
        redis_client: "Redis[bytes]",
        *,
        default_limit: int = 100,
        default_window: int = 60,
        key_prefix: str = "ratelimit",
    ) -> None:
        """Initialize the rate limiter.

        Args:
            redis_client: Redis client for distributed rate limiting.
            default_limit: Default requests per window.
            default_window: Default window size in seconds.
            key_prefix: Prefix for Redis keys.
        """
        self._redis = redis_client
        self._default_limit = default_limit
        self._default_window = default_window
        self._key_prefix = key_prefix
        self._endpoint_configs: dict[str, RateLimitConfig] = {}

    def configure_endpoint(
        self,
        path: str,
        *,
        requests: int,
        window_seconds: int,
    ) -> None:
        """Configure rate limit for a specific endpoint.

        Args:
            path: API endpoint path (supports wildcards).
            requests: Maximum requests allowed.
            window_seconds: Time window in seconds.
        """
        self._endpoint_configs[path] = RateLimitConfig(
            requests=requests,
            window_seconds=window_seconds,
        )

    def _get_config(self, path: str) -> RateLimitConfig:
        """Get rate limit config for a path.

        Args:
            path: Request path.

        Returns:
            Rate limit configuration.
        """
        # Check for exact match
        if path in self._endpoint_configs:
            return self._endpoint_configs[path]

        # Check for prefix matches (e.g., "/api/v1/auth/*")
        for pattern, config in self._endpoint_configs.items():
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                if path.startswith(prefix):
                    return config

        # Return default config
        return RateLimitConfig(
            requests=self._default_limit,
            window_seconds=self._default_window,
        )

    def _get_key(self, identifier: str, path: str) -> str:
        """Generate Redis key for rate limiting.

        Args:
            identifier: Client identifier (IP, user ID, API key).
            path: Request path.

        Returns:
            Redis key string.
        """
        # Normalize path for rate limiting
        normalized_path = path.rstrip("/").replace("/", ":")
        return f"{self._key_prefix}:{identifier}:{normalized_path}"

    async def check_rate_limit(
        self,
        identifier: str,
        path: str,
    ) -> RateLimitResult:
        """Check if request is allowed under rate limit.

        Uses sliding window log algorithm for accurate rate limiting.

        Args:
            identifier: Client identifier.
            path: Request path.

        Returns:
            Rate limit result.
        """
        config = self._get_config(path)
        key = self._get_key(identifier, path)
        now = time.time()
        window_start = now - config.window_seconds

        # Lua script for atomic rate limiting operation
        # This ensures thread-safety in distributed environments
        lua_script = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local window_start = tonumber(ARGV[2])
        local max_requests = tonumber(ARGV[3])
        local window_seconds = tonumber(ARGV[4])

        -- Remove old entries outside the window
        redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

        -- Count current requests in window
        local current_count = redis.call('ZCARD', key)

        if current_count < max_requests then
            -- Allow request and add timestamp
            redis.call('ZADD', key, now, now .. '-' .. math.random())
            redis.call('EXPIRE', key, window_seconds)
            return {1, max_requests - current_count - 1, math.ceil(now + window_seconds)}
        else
            -- Get oldest entry for retry calculation
            local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
            local retry_after = 0
            if oldest and #oldest >= 2 then
                retry_after = math.ceil(tonumber(oldest[2]) + window_seconds - now)
            end
            return {0, 0, math.ceil(now + window_seconds), retry_after}
        end
        """

        result = await self._redis.eval(
            lua_script,
            1,
            key,
            str(now),
            str(window_start),
            str(config.requests),
            str(config.window_seconds),
        )

        allowed = bool(result[0])
        remaining = int(result[1])
        reset_at = int(result[2])
        retry_after = int(result[3]) if len(result) > 3 and result[3] else None

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=retry_after,
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for enforcing rate limits on API requests."""

    def __init__(
        self,
        app: "ASGIApp",
        rate_limiter: RateLimiter,
        *,
        enabled: bool = True,
        exclude_paths: set[str] | None = None,
    ) -> None:
        """Initialize rate limit middleware.

        Args:
            app: ASGI application.
            rate_limiter: Rate limiter instance.
            enabled: Whether rate limiting is enabled.
            exclude_paths: Paths to exclude from rate limiting.
        """
        super().__init__(app)
        self._rate_limiter = rate_limiter
        self._enabled = enabled
        self._exclude_paths = exclude_paths or {"/health", "/metrics", "/docs", "/openapi.json"}

    def _get_client_identifier(self, request: Request) -> str:
        """Get unique identifier for the client.

        Priority:
        1. API key (if authenticated)
        2. User ID (if authenticated)
        3. X-Forwarded-For header (for proxied requests)
        4. Client IP address

        Args:
            request: HTTP request.

        Returns:
            Client identifier string.
        """
        # Check for API key in header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Use first 16 chars as identifier (don't use full key)
            return f"key:{api_key[:16]}"

        # Check for authenticated user in state
        if hasattr(request.state, "agent_id"):
            return f"agent:{request.state.agent_id}"

        # Check X-Forwarded-For for proxied requests
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Get first IP in chain (original client)
            client_ip = forwarded_for.split(",")[0].strip()
            return f"ip:{client_ip}"

        # Fall back to direct client IP
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process request with rate limiting.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler.

        Returns:
            HTTP response or 429 error.
        """
        # Skip if disabled or excluded path
        if not self._enabled or request.url.path in self._exclude_paths:
            return await call_next(request)

        identifier = self._get_client_identifier(request)

        try:
            result = await self._rate_limiter.check_rate_limit(
                identifier,
                request.url.path,
            )
        except Exception:
            # If rate limiting fails, allow request but log error
            logger.exception("rate_limit_check_failed", identifier=identifier)
            return await call_next(request)

        if not result.allowed:
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                path=request.url.path,
                retry_after=result.retry_after,
            )

            error = RateLimitError(
                "Rate limit exceeded",
                retry_after=result.retry_after,
            )

            return Response(
                content=f'{{"error": "{error.error_code}", "message": "{error.message}", "retry_after": {result.retry_after}}}',
                status_code=429,
                media_type="application/json",
                headers={
                    "X-RateLimit-Limit": str(result.remaining + 1),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(result.reset_at),
                    "Retry-After": str(result.retry_after or 60),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_at)

        return response


class InMemoryRateLimiter:
    """In-memory rate limiter for development/testing.

    NOT suitable for production with multiple workers.
    """

    def __init__(
        self,
        *,
        default_limit: int = 100,
        default_window: int = 60,
    ) -> None:
        """Initialize in-memory rate limiter.

        Args:
            default_limit: Default requests per window.
            default_window: Default window size in seconds.
        """
        self._default_limit = default_limit
        self._default_window = default_window
        self._requests: dict[str, list[float]] = {}

    async def check_rate_limit(
        self,
        identifier: str,
        path: str,
    ) -> RateLimitResult:
        """Check if request is allowed.

        Args:
            identifier: Client identifier.
            path: Request path.

        Returns:
            Rate limit result.
        """
        key = f"{identifier}:{path}"
        now = time.time()
        window_start = now - self._default_window

        # Get or create request list
        if key not in self._requests:
            self._requests[key] = []

        # Remove old requests
        self._requests[key] = [
            ts for ts in self._requests[key] if ts > window_start
        ]

        current_count = len(self._requests[key])

        if current_count < self._default_limit:
            self._requests[key].append(now)
            return RateLimitResult(
                allowed=True,
                remaining=self._default_limit - current_count - 1,
                reset_at=int(now + self._default_window),
            )

        oldest = min(self._requests[key]) if self._requests[key] else now
        retry_after = int(oldest + self._default_window - now)

        return RateLimitResult(
            allowed=False,
            remaining=0,
            reset_at=int(now + self._default_window),
            retry_after=max(1, retry_after),
        )

"""In-memory sliding-window rate limiting and security headers."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.middleware.audit import client_ip

WHITELIST_PREFIXES = ("/health", "/api/v1/health", "/assets/", "/static/", "/docs", "/redoc", "/openapi.json")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding window limiter (in-process; use Redis for multi-worker)."""

    def __init__(self, app) -> None:  # noqa: ANN001
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _allow(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = int(window - (now - bucket[0])) + 1
                return False, retry_after
            bucket.append(now)
            return True, 0

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.rate_limit_enabled or request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(prefix) for prefix in WHITELIST_PREFIXES):
            return await call_next(request)

        ip = client_ip(request)
        is_auth = path.endswith("/auth/login") or path.endswith("/auth/refresh")
        limit = settings.rate_limit_login_per_minute if is_auth else settings.rate_limit_per_minute
        key = f"{ip}:{'auth' if is_auth else 'api'}"
        allowed, retry_after = self._allow(key, limit, settings.rate_limit_window_seconds)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Demasiadas solicitudes. Intente de nuevo más tarde.",
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Window"] = str(settings.rate_limit_window_seconds)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """OWASP-friendly response headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if not request.url.path.startswith("/docs") and not request.url.path.startswith("/redoc"):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data: blob: https://*.basemaps.cartocdn.com "
                "https://*.tile.openstreetmap.org; style-src 'self' 'unsafe-inline'; "
                "script-src 'self'; connect-src 'self' https:; font-src 'self' data:",
            )
        if request.url.scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

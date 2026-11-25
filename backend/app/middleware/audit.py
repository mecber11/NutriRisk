"""Audit middleware: logs every API request with entry/exit timestamps."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.rbac import module_for_path
from app.db.session import SessionLocal
from app.services.audit import write_audit

logger = logging.getLogger("nutririsk.audit")

SKIP_PREFIXES = (
    "/health",
    "/api/v1/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/assets/",
    "/static/",
    "/favicon",
)

EXECUTE_HINTS = (
    "/train",
    "/run",
    "/execute",
    "/score",
    "/predict",
    "/compute",
    "/bootstrap",
    "/seed",
    "/recompute",
    "/acknowledge",
    "/refresh",
)
EXPORT_HINTS = ("/export", "/download")
RESOURCE_RE = re.compile(r"^/api/v1/([a-z_-]+)(?:/(\d+))?")


def resolve_action(method: str, path: str) -> str:
    """Map HTTP method + path to a business action label."""
    lowered = path.lower()
    if any(hint in lowered for hint in EXPORT_HINTS):
        return "export"
    if any(hint in lowered for hint in EXECUTE_HINTS):
        return "execute"
    if lowered.endswith("/agent/chat") or lowered.endswith("/agent/query"):
        return "use"
    return {
        "GET": "read",
        "HEAD": "read",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }.get(method.upper(), "read")


def resolve_resource(path: str) -> tuple[str | None, str | None]:
    match = RESOURCE_RE.match(path)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def resolve_result(status_code: int) -> str:
    if status_code < 400:
        return "SUCCESS"
    if status_code in (401, 403):
        return "DENIED"
    if status_code >= 500:
        return "ERROR"
    return "FAILURE"


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


class AuditMiddleware(BaseHTTPMiddleware):
    """Writes one immutable audit row per API call (POST/GET/...)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        should_log = path.startswith("/api/") and not any(path.startswith(p) for p in SKIP_PREFIXES)

        if not should_log:
            return await call_next(request)

        started = time.perf_counter()
        started_at = datetime.now(timezone.utc)
        status_code = 500
        response: Response | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            logger.exception("Request failed: %s %s", request.method, path)
            raise
        finally:
            if should_log:
                duration_ms = int((time.perf_counter() - started) * 1000)
                state = request.state
                user_id = getattr(state, "audit_user_id", None)
                email = getattr(state, "audit_email", None)
                role_code = getattr(state, "audit_role", None)
                resource_type, resource_id = resolve_resource(path)
                detail = {
                    "query": dict(request.query_params),
                    "duration_ms": duration_ms,
                    "client": request.headers.get("x-client-name"),
                }
                if user_id is None and path.endswith("/auth/login"):
                    email = getattr(state, "audit_email", email)
                try:
                    with SessionLocal() as db:
                        write_audit(
                            db,
                            module=module_for_path(path),
                            action=resolve_action(request.method, path),
                            result=resolve_result(status_code),
                            user_id=user_id,
                            user_email=email,
                            role_code=role_code,
                            resource_type=resource_type,
                            resource_id=resource_id,
                            method=request.method,
                            path=path,
                            status_code=status_code,
                            ip_address=client_ip(request),
                            user_agent=request.headers.get("user-agent"),
                            session_id=request.headers.get("x-session-id"),
                            started_at=started_at,
                            detail=detail,
                        )
                except Exception:  # pragma: no cover - audit must never break the API
                    logger.exception("Could not persist audit entry for %s %s", request.method, path)

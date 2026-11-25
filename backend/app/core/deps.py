"""Shared FastAPI dependencies: authentication, RBAC and pagination."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.rbac import Action, has_permission
from app.core.security import TokenError, decode_token
from app.db.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False, description="JWT de acceso emitido por /auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized(detail: str = "No autenticado") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User:
    """Resolve the authenticated user from the bearer token."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Token de acceso requerido")
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except TokenError as exc:
        raise _unauthorized(str(exc)) from exc

    user = db.get(User, int(payload.get("sub", 0)))
    if user is None:
        raise _unauthorized("Usuario no encontrado")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")

    # Expose identity to the audit middleware through the shared request scope.
    request.state.audit_user_id = user.id
    request.state.audit_email = user.email
    request.state.audit_role = user.role.code
    request.state.audit_user = user
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(module: str, action: str | Action):
    """Dependency factory enforcing the RBAC matrix for module+action."""

    action_value = action.value if isinstance(action, Action) else action

    def _checker(user: CurrentUser) -> User:
        if not has_permission(user.role.code, module, action_value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"El rol {user.role.code} no tiene permiso '{action_value}' sobre '{module}'",
            )
        return user

    return _checker


def require_roles(*role_codes: str):
    """Dependency factory restricting access to an explicit role list."""

    allowed = set(role_codes)

    def _checker(user: CurrentUser) -> User:
        if user.role.code not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rol no autorizado para esta operación",
            )
        return user

    return _checker


class Pagination:
    """Query params for paginated endpoints."""

    def __init__(self, page: int = 1, page_size: int = 25) -> None:
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


PageParams = Annotated[Pagination, Depends()]


def paginated(items: list[Any], total: int, page: int, page_size: int) -> dict[str, Any]:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if page_size else 0,
    }

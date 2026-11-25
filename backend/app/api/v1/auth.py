"""Authentication endpoints: login, refresh, logout, profile and password recovery."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.rbac import allowed_modules
from app.core.security import (
    PasswordPolicyError,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_reset_token,
    hash_password,
    hash_token,
    needs_rehash,
    validate_password_strength,
    verify_password,
)
from app.db.base import ensure_utc
from app.models.user import PasswordResetToken, RefreshToken, User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LogoutRequest,
    ProfileUpdate,
    RefreshRequest,
    ResetPasswordRequest,
    TokenPair,
    UserWithPermissions,
)
from app.services.audit import write_audit

router = APIRouter(prefix="/auth", tags=["Autenticación"])
logger = logging.getLogger("nutririsk.auth")


def _user_payload(user: User) -> UserWithPermissions:
    payload = UserWithPermissions.model_validate(user)
    payload.permissions = allowed_modules(user.role.code)
    return payload


def _issue_tokens(db: Session, user: User, request: Request) -> TokenPair:
    access = create_access_token(user.id, user.role.code, user.email)
    refresh, expires_at = create_refresh_token(user.id, user.role.code)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
            user_agent=(request.headers.get("user-agent") or "")[:400],
            ip_address=request.client.host if request.client else None,
        )
    )
    user.last_login_at = datetime.now(timezone.utc)
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_expire_minutes * 60,
        user=_user_payload(user),
    )


@router.post("/login", response_model=TokenPair, summary="Iniciar sesión")
def login(payload: LoginRequest, request: Request, db: DbSession) -> TokenPair:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    now = datetime.now(timezone.utc)
    locked_until = ensure_utc(user.locked_until) if user is not None else None
    if locked_until and locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Cuenta bloqueada temporalmente por intentos fallidos. Intente más tarde.",
        )
    if user is None or not verify_password(payload.password, user.hashed_password):
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.max_failed_logins:
                user.locked_until = now + timedelta(minutes=settings.account_lock_minutes)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")

    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(payload.password)

    request.state.audit_email = user.email
    request.state.audit_role = user.role.code
    request.state.audit_user_id = user.id
    tokens = _issue_tokens(db, user, request)
    write_audit(
        db,
        module="users",
        action="login",
        result="SUCCESS",
        user=user,
        path="/api/v1/auth/login",
        method="POST",
        status_code=200,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        session_id=request.headers.get("x-session-id"),
        detail={"email": user.email},
    )
    return tokens


@router.post("/refresh", response_model=TokenPair, summary="Renovar token de acceso")
def refresh(payload: RefreshRequest, request: Request, db: DbSession) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(payload.refresh_token)))
    if stored is None or stored.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revocado")
    if ensure_utc(stored.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expirado")
    user = db.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no disponible")
    stored.revoked_at = datetime.now(timezone.utc)
    tokens = _issue_tokens(db, user, request)
    request.state.audit_user_id = user.id
    request.state.audit_email = user.email
    request.state.audit_role = user.role.code
    return tokens


@router.post("/logout", summary="Cerrar sesión")
def logout(payload: LogoutRequest, request: Request, db: DbSession, user: CurrentUser) -> dict[str, str]:
    if payload.refresh_token:
        stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(payload.refresh_token)))
        if stored is not None and stored.user_id == user.id:
            stored.revoked_at = datetime.now(timezone.utc)
            db.commit()
    write_audit(
        db,
        module="users",
        action="logout",
        user=user,
        path="/api/v1/auth/logout",
        method="POST",
        status_code=200,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"message": "Sesión cerrada"}


@router.get("/me", response_model=UserWithPermissions, summary="Perfil del usuario autenticado")
def me(user: CurrentUser) -> UserWithPermissions:
    return _user_payload(user)


@router.patch("/me", response_model=UserWithPermissions, summary="Actualizar perfil")
def update_profile(payload: ProfileUpdate, db: DbSession, user: CurrentUser) -> UserWithPermissions:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return _user_payload(user)


@router.post("/change-password", summary="Cambiar contraseña")
def change_password(payload: ChangePasswordRequest, db: DbSession, user: CurrentUser) -> dict[str, str]:
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta")
    try:
        validate_password_strength(payload.new_password)
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = False
    db.commit()
    return {"message": "Contraseña actualizada"}


@router.post("/forgot-password", response_model=ForgotPasswordResponse, summary="Solicitar recuperación de contraseña")
def forgot_password(payload: ForgotPasswordRequest, db: DbSession) -> ForgotPasswordResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    message = "Si el correo está registrado, recibirá instrucciones para restablecer su contraseña."
    if user is None:
        return ForgotPasswordResponse(message=message)
    token, token_hash, expires_at = generate_reset_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    # In demo mode the token is returned so the flow can be tested end-to-end.
    if settings.demo_mode:
        return ForgotPasswordResponse(
            message=message,
            reset_token=token,
            expires_in_minutes=settings.password_reset_expire_minutes,
        )
    return ForgotPasswordResponse(message=message)


@router.post("/reset-password", summary="Restablecer contraseña con token")
def reset_password(payload: ResetPasswordRequest, db: DbSession) -> dict[str, str]:
    stored = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(payload.token)))
    now = datetime.now(timezone.utc)
    if stored is None or stored.used_at is not None or ensure_utc(stored.expires_at) < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido o expirado")
    try:
        validate_password_strength(payload.new_password)
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    user = db.get(User, stored.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    user.hashed_password = hash_password(payload.new_password)
    user.failed_login_count = 0
    user.locked_until = None
    stored.used_at = now
    db.commit()
    return {"message": "Contraseña restablecida correctamente"}


"""Password hashing, JWT handling and anonymisation helpers."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

_argon2 = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)

BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


class PasswordPolicyError(ValueError):
    """Raised when a password does not satisfy the security policy."""


class TokenError(Exception):
    """Raised when a JWT is missing, malformed, expired or of the wrong type."""


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    """Hash a password with Argon2id (primary algorithm)."""
    return _argon2.hash(password)


def _verify_bcrypt(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against Argon2id or bcrypt (legacy support)."""
    if not hashed:
        return False
    if hashed.startswith(BCRYPT_PREFIXES):
        return _verify_bcrypt(password, hashed)
    try:
        return _argon2.verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    """True when the stored hash should be upgraded to Argon2id."""
    if hashed.startswith(BCRYPT_PREFIXES):
        return True
    try:
        return _argon2.check_needs_rehash(hashed)
    except InvalidHashError:
        return True


def validate_password_strength(password: str) -> None:
    """Enforce the password policy (OWASP-aligned, configurable length)."""
    problems: list[str] = []
    if len(password) < settings.password_min_length:
        problems.append(f"al menos {settings.password_min_length} caracteres")
    if not any(char.islower() for char in password):
        problems.append("una minúscula")
    if not any(char.isupper() for char in password):
        problems.append("una mayúscula")
    if not any(char.isdigit() for char in password):
        problems.append("un dígito")
    if not any(not char.isalnum() for char in password):
        problems.append("un símbolo")
    if problems:
        raise PasswordPolicyError("La contraseña debe incluir " + ", ".join(problems) + ".")


# --------------------------------------------------------------------------- #
# Tokens
# --------------------------------------------------------------------------- #
def _encode(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int, role: str, email: str, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "email": email,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if extra:
        payload.update(extra)
    return _encode(payload)


def create_refresh_token(user_id: int, role: str) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    token = _encode(
        {
            "sub": str(user_id),
            "role": role,
            "type": "refresh",
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": uuid.uuid4().hex,
        }
    )
    return token, expires_at


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """Decode and validate a JWT, enforcing its token type."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Token expirado") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Token inválido") from exc
    if payload.get("type") != expected_type:
        raise TokenError("Tipo de token inválido")
    return payload


def hash_token(token: str) -> str:
    """Irreversible hash used to persist refresh/reset tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_reset_token() -> tuple[str, str, datetime]:
    """Return (plain token, sha256 hash, expiry)."""
    token = secrets.token_urlsafe(48)
    return token, hash_token(token), datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_expire_minutes
    )


# --------------------------------------------------------------------------- #
# Anonymisation
# --------------------------------------------------------------------------- #
def pseudonymize(value: str) -> str:
    """Stable pseudonym (HMAC-like) for sensitive identifiers."""
    return hashlib.sha256(f"{settings.anonymization_salt}:{value}".encode("utf-8")).hexdigest()[:24]


def anonymized_identifier(prefix: str, value: str) -> str:
    return f"{prefix}-{pseudonymize(value).upper()}"

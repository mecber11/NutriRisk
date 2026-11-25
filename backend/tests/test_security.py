"""Pruebas de seguridad: hashing, política de contraseñas y JWT."""

from __future__ import annotations

import pytest

from app.core.security import (
    PasswordPolicyError,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_reset_token,
    hash_password,
    hash_token,
    needs_rehash,
    pseudonymize,
    validate_password_strength,
    verify_password,
)


def test_argon2_hash_and_verify():
    hashed = hash_password("Segura#2026!")
    assert hashed.startswith("$argon2")
    assert verify_password("Segura#2026!", hashed) is True
    assert verify_password("incorrecta", hashed) is False


def test_bcrypt_legacy_hash_is_supported():
    import bcrypt

    legacy = bcrypt.hashpw(b"Legado#2026!", bcrypt.gensalt()).decode()
    assert verify_password("Legado#2026!", legacy) is True
    assert needs_rehash(legacy) is True


def test_password_policy_rejects_weak_passwords():
    with pytest.raises(PasswordPolicyError):
        validate_password_strength("corta")
    with pytest.raises(PasswordPolicyError):
        validate_password_strength("sinmayusculas1!")
    with pytest.raises(PasswordPolicyError):
        validate_password_strength("SinSimbolos2026")
    validate_password_strength("Valida#2026")


def test_access_token_roundtrip():
    token = create_access_token(42, "ADMIN", "admin@nutririsk.ai")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "42"
    assert payload["role"] == "ADMIN"
    assert payload["type"] == "access"


def test_refresh_token_type_is_enforced():
    token, expires_at = create_refresh_token(7, "AUDITOR")
    assert decode_token(token, expected_type="refresh")["role"] == "AUDITOR"
    with pytest.raises(TokenError):
        decode_token(token, expected_type="access")
    assert expires_at is not None


def test_invalid_token_raises():
    with pytest.raises(TokenError):
        decode_token("not-a-token")


def test_reset_token_hashing():
    token, token_hash, expires_at = generate_reset_token()
    assert len(token) > 20
    assert token_hash == hash_token(token)
    assert expires_at is not None


def test_pseudonymization_is_stable_and_salted():
    first = pseudonymize("CH-2023-T01-0001")
    second = pseudonymize("CH-2023-T01-0001")
    other = pseudonymize("CH-2023-T01-0002")
    assert first == second
    assert first != other
    assert len(first) == 24

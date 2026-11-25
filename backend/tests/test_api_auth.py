"""Pruebas de autenticación, sesión y recuperación de contraseña."""

from __future__ import annotations

from fastapi.testclient import TestClient

API = "/api/v1"


def _create_user(client: TestClient, headers: dict[str, str], email: str) -> None:
    response = client.post(
        f"{API}/users",
        headers=headers,
        json={
            "email": email,
            "full_name": "Usuario de Prueba",
            "password": "Prueba#2026!",
            "role_code": "PUBLIC_HEALTH_ANALYST",
            "organization": "QA",
        },
    )
    assert response.status_code == 201, response.text


def test_login_success_and_me(client: TestClient):
    response = client.post(f"{API}/auth/login", json={"email": "admin@nutririsk.ai", "password": "Admin#2026!"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["user"]["role"]["code"] == "ADMIN"
    permissions = payload["user"]["permissions"]
    assert "dashboard" in permissions or "*" in permissions

    headers = {"Authorization": f"Bearer {payload['access_token']}"}
    me = client.get(f"{API}/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "admin@nutririsk.ai"


def test_login_wrong_password_is_401(client: TestClient):
    response = client.post(f"{API}/auth/login", json={"email": "admin@nutririsk.ai", "password": "incorrecta"})
    assert response.status_code == 401


def test_me_requires_token(client: TestClient):
    assert client.get(f"{API}/auth/me").status_code == 401


def test_refresh_rotates_token(client: TestClient):
    login = client.post(f"{API}/auth/login", json={"email": "gestor@nutririsk.ai", "password": "Gestor#2026!"}).json()
    refreshed = client.post(f"{API}/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["access_token"] != login["access_token"]
    reused = client.post(f"{API}/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert reused.status_code == 401


def test_logout_revokes_refresh_token(client: TestClient):
    login = client.post(f"{API}/auth/login", json={"email": "analista@nutririsk.ai", "password": "Analista#2026!"}).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    response = client.post(f"{API}/auth/logout", headers=headers, json={"refresh_token": login["refresh_token"]})
    assert response.status_code == 200
    refresh = client.post(f"{API}/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert refresh.status_code == 401


def test_lockout_after_failed_attempts(client: TestClient, admin_headers: dict[str, str]):
    email = "bloqueo@nutririsk.ai"
    _create_user(client, admin_headers, email)
    for _ in range(6):
        client.post(f"{API}/auth/login", json={"email": email, "password": "Incorrecta#2026!"})
    blocked = client.post(f"{API}/auth/login", json={"email": email, "password": "Prueba#2026!"})
    assert blocked.status_code == 423


def test_change_password_flow(client: TestClient, admin_headers: dict[str, str]):
    email = "cambio@nutririsk.ai"
    _create_user(client, admin_headers, email)
    login = client.post(f"{API}/auth/login", json={"email": email, "password": "Prueba#2026!"}).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    changed = client.post(
        f"{API}/auth/change-password",
        headers=headers,
        json={"current_password": "Prueba#2026!", "new_password": "Nueva#2026!"},
    )
    assert changed.status_code == 200
    assert client.post(f"{API}/auth/login", json={"email": email, "password": "Nueva#2026!"}).status_code == 200
    weak = client.post(
        f"{API}/auth/change-password",
        headers=headers,
        json={"current_password": "Nueva#2026!", "new_password": "corta"},
    )
    assert weak.status_code == 422


def test_password_recovery_flow(client: TestClient, admin_headers: dict[str, str]):
    email = "recupera@nutririsk.ai"
    _create_user(client, admin_headers, email)
    forgot = client.post(f"{API}/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 200
    token = forgot.json()["reset_token"]
    assert token
    reset = client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "Recuperada#2026!"})
    assert reset.status_code == 200
    assert client.post(f"{API}/auth/login", json={"email": email, "password": "Recuperada#2026!"}).status_code == 200
    invalid = client.post(f"{API}/auth/reset-password", json={"token": "invalido", "new_password": "Otra#2026!"})
    assert invalid.status_code == 400


def test_profile_update(client: TestClient, admin_headers: dict[str, str]):
    response = client.patch(
        f"{API}/auth/me",
        headers=admin_headers,
        json={"position": "Directora de sistemas", "organization": "Ministerio de Salud"},
    )
    assert response.status_code == 200
    assert response.json()["position"] == "Directora de sistemas"


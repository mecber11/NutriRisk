"""Pruebas de la bitácora inmutable y del middleware de auditoría."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.models.audit import AuditLog
from app.services.audit import sanitize_payload, write_audit

API = "/api/v1"


def test_audit_table_is_append_only(db_session):
    entry = AuditLog(module="tests", action="read", result="SUCCESS", user_email="qa@nutririsk.ai")
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    with pytest.raises(IntegrityError):
        db_session.execute(text("UPDATE audit_logs SET action='delete' WHERE id=:id"), {"id": entry.id})
        db_session.commit()
    db_session.rollback()

    with pytest.raises(IntegrityError):
        db_session.execute(text("DELETE FROM audit_logs WHERE id=:id"), {"id": entry.id})
        db_session.commit()
    db_session.rollback()


def test_navigation_events_are_append_only(db_session):
    from app.models.audit import NavigationEvent

    event = NavigationEvent(module="dashboard", event_type="ENTER")
    db_session.add(event)
    db_session.commit()
    with pytest.raises(IntegrityError):
        db_session.execute(text("DELETE FROM navigation_events WHERE id=:id"), {"id": event.id})
        db_session.commit()
    db_session.rollback()


def test_middleware_records_api_calls(client: TestClient, admin_headers: dict[str, str], db_session):
    before = db_session.scalar(select(func.count(AuditLog.id))) or 0
    response = client.get(f"{API}/dashboard/options", headers={**admin_headers, "X-Session-Id": "pytest-session"})
    assert response.status_code == 200
    after = db_session.scalar(select(func.count(AuditLog.id))) or 0
    assert after > before
    last = db_session.execute(select(AuditLog).order_by(AuditLog.id.desc())).scalars().first()
    assert last is not None
    assert last.module == "dashboard"
    assert last.path == f"{API}/dashboard/options"
    assert last.result == "SUCCESS"
    assert last.session_id == "pytest-session"
    assert last.duration_ms >= 0


def test_middleware_records_denied_requests(client: TestClient, auditor_headers: dict[str, str], db_session):
    response = client.get(f"{API}/users", headers=auditor_headers)
    assert response.status_code == 403
    last = db_session.execute(select(AuditLog).order_by(AuditLog.id.desc())).scalars().first()
    assert last is not None
    assert last.result == "DENIED"
    assert last.status_code == 403


def test_write_audit_masks_sensitive_payload(db_session):
    entry = write_audit(
        db_session,
        module="tests",
        action="create",
        detail={"password": "secreto", "nested": {"token": "abc"}, "ok": "visible"},
        result="SUCCESS",
    )
    payload = json.loads(entry.detail)
    assert payload["password"] == "***"
    assert payload["nested"]["token"] == "***"
    assert payload["ok"] == "visible"


def test_sanitize_payload_handles_lists():
    sanitized = sanitize_payload([{"api_key": "123"}, {"value": 1}])
    assert sanitized[0]["api_key"] == "***"
    assert sanitized[1]["value"] == 1


def test_audit_filters_and_search(client: TestClient, admin_headers: dict[str, str]):
    logs = client.get(f"{API}/audit/logs?module=datasets&page_size=5", headers=admin_headers)
    assert logs.status_code == 200
    items = logs.json()["items"]
    assert all(item["module"] == "datasets" for item in items)
    search = client.get(f"{API}/audit/logs?search=audit&page_size=5", headers=admin_headers)
    assert search.status_code == 200

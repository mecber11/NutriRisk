"""Audit trail service: append-only writes, filtered queries and summaries."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog, NavigationEvent
from app.models.user import User

SENSITIVE_QUERY_KEYS = {"password", "token", "authorization", "secret", "api_key", "refresh_token"}


def sanitize_payload(payload: Any) -> Any:
    """Remove credentials from logged payloads."""
    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if any(marker in str(key).lower() for marker in SENSITIVE_QUERY_KEYS):
                cleaned[key] = "***"
            else:
                cleaned[key] = sanitize_payload(value)
        return cleaned
    if isinstance(payload, list):
        return [sanitize_payload(item) for item in payload[:50]]
    if isinstance(payload, (datetime,)):
        return payload.isoformat()
    return payload


def write_audit(
    db: Session,
    *,
    module: str,
    action: str,
    result: str = "SUCCESS",
    user: User | None = None,
    user_id: int | None = None,
    user_email: str | None = None,
    role_code: str | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    method: str | None = None,
    path: str | None = None,
    status_code: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    session_id: str | None = None,
    started_at: datetime | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    """Append one audit row (never updates existing rows)."""
    now = datetime.now(timezone.utc)
    start = started_at or now
    duration = max(0, int((now - start).total_seconds() * 1000))
    entry = AuditLog(
        user_id=user.id if user else user_id,
        user_email=user.email if user else user_email,
        role_code=user.role.code if user else role_code,
        module=module,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        method=method,
        path=path,
        status_code=status_code,
        result=result,
        detail=json.dumps(sanitize_payload(detail), ensure_ascii=False)[:8000] if detail else None,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:400] or None,
        session_id=session_id,
        started_at=start,
        finished_at=now,
        duration_ms=duration,
    )
    db.add(entry)
    db.commit()
    return entry


def record_navigation(
    db: Session,
    *,
    user: User | None,
    module: str,
    event_type: str,
    path: str | None = None,
    session_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> NavigationEvent:
    event = NavigationEvent(
        user_id=user.id if user else None,
        session_id=session_id,
        module=module,
        event_type=event_type.upper(),
        path=path,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:400] or None,
    )
    db.add(event)
    db.commit()
    return event


def build_audit_query(
    *,
    search: str | None = None,
    module: str | None = None,
    action: str | None = None,
    result: str | None = None,
    role_code: str | None = None,
    user_email: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    session_id: str | None = None,
) -> Select[tuple[AuditLog]]:
    stmt = select(AuditLog)
    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(AuditLog.user_email).like(pattern),
                func.lower(AuditLog.path).like(pattern),
                func.lower(AuditLog.resource_type).like(pattern),
                func.lower(AuditLog.module).like(pattern),
                func.lower(AuditLog.action).like(pattern),
                func.lower(AuditLog.ip_address).like(pattern),
            )
        )
    if module:
        stmt = stmt.where(AuditLog.module == module)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if result:
        stmt = stmt.where(AuditLog.result == result)
    if role_code:
        stmt = stmt.where(AuditLog.role_code == role_code)
    if user_email:
        stmt = stmt.where(AuditLog.user_email == user_email)
    if session_id:
        stmt = stmt.where(AuditLog.session_id == session_id)
    if date_from:
        stmt = stmt.where(AuditLog.started_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.started_at <= date_to)
    return stmt.order_by(AuditLog.started_at.desc(), AuditLog.id.desc())


def audit_summary(db: Session, days: int = 30) -> dict[str, Any]:
    """KPIs for the audit dashboard."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    total = db.scalar(select(func.count(AuditLog.id)).where(AuditLog.started_at >= since)) or 0
    failures = (
        db.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.started_at >= since, AuditLog.result != "SUCCESS")
        )
        or 0
    )
    by_module = db.execute(
        select(AuditLog.module, func.count(AuditLog.id))
        .where(AuditLog.started_at >= since)
        .group_by(AuditLog.module)
        .order_by(func.count(AuditLog.id).desc())
    ).all()
    by_user = db.execute(
        select(AuditLog.user_email, func.count(AuditLog.id))
        .where(AuditLog.started_at >= since)
        .group_by(AuditLog.user_email)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    ).all()
    by_day = db.execute(
        select(func.date(AuditLog.started_at), func.count(AuditLog.id))
        .where(AuditLog.started_at >= since)
        .group_by(func.date(AuditLog.started_at))
        .order_by(func.date(AuditLog.started_at))
    ).all()
    return {
        "period_days": days,
        "total_events": total,
        "failed_events": failures,
        "success_rate": round((total - failures) / total * 100, 2) if total else 100.0,
        "by_module": [{"module": module, "count": count} for module, count in by_module],
        "top_users": [{"email": email or "anónimo", "count": count} for email, count in by_user],
        "by_day": [{"date": str(day), "count": count} for day, count in by_day],
    }

"""Audit trail endpoints: immutable log, navigation marks, summary and exports."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.core.deps import CurrentUser, DbSession, PageParams, paginated, require_permission
from app.core.rbac import Action, Module
from app.models.audit import AuditLog, NavigationEvent
from app.models.user import User
from app.schemas.system import (
    AuditLogOut,
    AuditSummary,
    NavigationEventCreate,
    NavigationEventOut,
)
from app.services.audit import audit_summary, build_audit_query, record_navigation
from app.services.reporting import FORMAT_LABELS, generate_report

router = APIRouter(prefix="/audit", tags=["Bitácora y auditoría"])


def _serialize(entry: AuditLog) -> AuditLogOut:
    detail: dict[str, Any] | None = None
    if entry.detail:
        try:
            detail = json.loads(entry.detail)
        except json.JSONDecodeError:
            detail = {"raw": entry.detail}
    return AuditLogOut(
        id=entry.id,
        user_id=entry.user_id,
        user_email=entry.user_email,
        role_code=entry.role_code,
        module=entry.module,
        action=entry.action,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        method=entry.method,
        path=entry.path,
        status_code=entry.status_code,
        result=entry.result,
        detail=detail,
        ip_address=entry.ip_address,
        user_agent=entry.user_agent,
        session_id=entry.session_id,
        started_at=entry.started_at,
        finished_at=entry.finished_at,
        duration_ms=entry.duration_ms,
    )


@router.get("/logs", summary="Consultar bitácora")
def list_logs(
    db: DbSession,
    _: User = Depends(require_permission(Module.AUDIT, Action.READ)),
    page: PageParams = None,  # type: ignore[assignment]
    search: str | None = Query(default=None),
    module: str | None = Query(default=None),
    action: str | None = Query(default=None),
    result: str | None = Query(default=None),
    role_code: str | None = Query(default=None),
    user_email: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
) -> dict:
    page = page or PageParams()
    stmt = build_audit_query(
        search=search,
        module=module,
        action=action,
        result=result,
        role_code=role_code,
        user_email=user_email,
        date_from=date_from,
        date_to=date_to,
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    entries = db.execute(stmt.offset(page.offset).limit(page.limit)).scalars().all()
    return paginated([_serialize(entry).model_dump() for entry in entries], total, page.page, page.page_size)


@router.get("/summary", response_model=AuditSummary, summary="Resumen de actividad")
def summary(db: DbSession, days: int = Query(default=30, ge=1, le=365), _: User = Depends(require_permission(Module.AUDIT, Action.READ))) -> AuditSummary:
    return AuditSummary(**audit_summary(db, days))


@router.get("/navigation", response_model=dict, summary="Eventos de entrada/salida por módulo")
def navigation_events(
    db: DbSession,
    _: User = Depends(require_permission(Module.AUDIT, Action.READ)),
    page: PageParams = None,  # type: ignore[assignment]
    module: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
) -> dict:
    page = page or PageParams()
    stmt = select(NavigationEvent)
    count_stmt = select(func.count(NavigationEvent.id))
    conditions = []
    if module:
        conditions.append(NavigationEvent.module == module)
    if event_type:
        conditions.append(NavigationEvent.event_type == event_type.upper())
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)
    total = db.scalar(count_stmt) or 0
    events = db.execute(
        stmt.order_by(NavigationEvent.occurred_at.desc()).offset(page.offset).limit(page.limit)
    ).scalars().all()
    return paginated(
        [NavigationEventOut.model_validate(event).model_dump() for event in events], total, page.page, page.page_size
    )


@router.post("/navigation", response_model=NavigationEventOut, summary="Registrar entrada/salida de módulo")
def create_navigation(payload: NavigationEventCreate, request: Request, db: DbSession, user: CurrentUser) -> NavigationEventOut:
    event = record_navigation(
        db,
        user=user,
        module=payload.module,
        event_type=payload.event_type,
        path=payload.path,
        session_id=payload.session_id or request.headers.get("x-session-id"),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return NavigationEventOut.model_validate(event)


@router.get("/logs/{log_id}", response_model=AuditLogOut, summary="Detalle de evento")
def get_log(log_id: int, db: DbSession, _: User = Depends(require_permission(Module.AUDIT, Action.READ))) -> AuditLogOut:
    entry = db.get(AuditLog, log_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
    return _serialize(entry)


@router.get("/me", summary="Mi actividad reciente")
def my_activity(db: DbSession, user: CurrentUser, limit: int = Query(default=50, ge=1, le=200)) -> dict:
    entries = db.execute(
        select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.started_at.desc()).limit(limit)
    ).scalars().all()
    return {"items": [_serialize(entry).model_dump() for entry in entries], "total": len(entries)}


@router.get("/export", summary="Exportar bitácora (PDF, Word, Excel)")
def export_logs(
    db: DbSession,
    fmt: str = Query(default="xlsx", pattern="^(pdf|docx|xlsx)$"),
    search: str | None = Query(default=None),
    module: str | None = Query(default=None),
    action: str | None = Query(default=None),
    result: str | None = Query(default=None),
    user_email: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    _: User = Depends(require_permission(Module.AUDIT, Action.EXPORT)),
) -> FileResponse:
    report = generate_report(
        db,
        kind="audit_log",
        fmt=fmt,
        params={
            "search": search,
            "module": module,
            "action": action,
            "result": result,
            "user_email": user_email,
            "date_from": date_from,
            "date_to": date_to,
        },
        title="Bitácora de auditoría",
    )
    if not report.file_path or not Path(report.file_path).exists():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo generar el archivo")
    return FileResponse(
        report.file_path,
        filename=report.file_name or f"bitacora.{fmt}",
        media_type={
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }[fmt],
        headers={"X-Report-Format": FORMAT_LABELS[fmt]},
    )

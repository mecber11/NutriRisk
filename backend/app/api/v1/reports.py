"""Report generation and download endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.core.config import settings
from app.core.deps import DbSession, PageParams, paginated, require_permission
from app.core.integrations import require_service_token
from app.core.rbac import Action, Module
from app.models.system import Report
from app.models.user import User
from app.schemas.system import ReportKindInfo, ReportOut, ReportRequest
from app.services.reporting import FORMAT_LABELS, REPORT_KINDS, generate_report, serialize_report

router = APIRouter(prefix="/reports", tags=["Reportes"])

REPORT_READ = Depends(require_permission(Module.REPORTS, Action.READ))
REPORT_CREATE = Depends(require_permission(Module.REPORTS, Action.CREATE))

MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.get("/kinds", response_model=list[ReportKindInfo], summary="Tipos de reporte disponibles")
def kinds(_: User = REPORT_READ) -> list[ReportKindInfo]:
    return [
        ReportKindInfo(
            code=code,
            label=meta["label"],
            description=meta["description"],
            formats=list(FORMAT_LABELS),
            params=meta.get("params", []),
        )
        for code, meta in REPORT_KINDS.items()
    ]


@router.get("", summary="Historial de reportes")
def list_reports(
    db: DbSession,
    page: PageParams,
    kind: str | None = Query(default=None),
    fmt: str | None = Query(default=None),
    _: User = REPORT_READ,
) -> dict:
    stmt = select(Report)
    count_stmt = select(func.count(Report.id))
    conditions = []
    if kind:
        conditions.append(Report.kind == kind)
    if fmt:
        conditions.append(Report.fmt == fmt)
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)
    total = db.scalar(count_stmt) or 0
    reports = db.execute(stmt.order_by(Report.id.desc()).offset(page.offset).limit(page.limit)).scalars().all()
    return paginated([serialize_report(report) for report in reports], total, page.page, page.page_size)


@router.post("/generate", response_model=ReportOut, status_code=status.HTTP_201_CREATED, summary="Generar reporte")
def generate(payload: ReportRequest, db: DbSession, user: User = REPORT_CREATE) -> ReportOut:
    try:
        report = generate_report(
            db,
            kind=payload.kind,
            fmt=payload.fmt,
            params=payload.params,
            title=payload.title,
            user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ReportOut(**serialize_report(report))


@router.post("/schedule", summary="Programar reportes automáticos vía n8n")
def schedule(_: User = REPORT_CREATE) -> dict:
    return {
        "message": "La programación se gestiona en n8n mediante el flujo 'NutriRisk - Reportes programados'.",
        "webhook": f"{settings.n8n_base_url}/webhook/nutririsk-reports",
        "api_endpoint": f"{settings.api_public_url}/api/v1/reports/generate",
        "cron_examples": ["0 7 * * 1 (semanal)", "0 6 1 * * (mensual)"],
        "import_file": "n8n/workflows/03_reportes_programados.json",
    }


@router.post("/n8n/generate", response_model=ReportOut, status_code=status.HTTP_201_CREATED, summary="Generar reporte (n8n)")
def generate_n8n(payload: ReportRequest, db: DbSession, _token: None = Depends(require_service_token)) -> ReportOut:
    try:
        report = generate_report(db, kind=payload.kind, fmt=payload.fmt, params=payload.params, title=payload.title, user_id=None)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ReportOut(**serialize_report(report))


@router.get("/{report_id}", response_model=ReportOut, summary="Detalle del reporte")
def get_report(report_id: int, db: DbSession, _: User = REPORT_READ) -> ReportOut:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reporte no encontrado")
    return ReportOut(**serialize_report(report))


@router.get("/{report_id}/download", summary="Descargar reporte")
def download(report_id: int, db: DbSession, _: User = REPORT_READ) -> FileResponse:
    report = db.get(Report, report_id)
    if report is None or report.status != "READY" or not report.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reporte no disponible")
    path = Path(report.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="El archivo ya no está disponible")
    return FileResponse(
        path,
        filename=report.file_name or f"reporte_{report.id}.{report.fmt}",
        media_type=MEDIA_TYPES.get(report.fmt, "application/octet-stream"),
    )


@router.delete("/{report_id}", summary="Eliminar reporte")
def delete_report(
    report_id: int,
    db: DbSession,
    _: User = Depends(require_permission(Module.REPORTS, Action.DELETE)),
) -> dict[str, str]:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reporte no encontrado")
    if report.file_path:
        Path(report.file_path).unlink(missing_ok=True)
    db.delete(report)
    db.commit()
    return {"message": "Reporte eliminado"}


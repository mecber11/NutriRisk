"""Scheduled ingestion endpoints (UI + n8n service token)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, PageParams, paginated, require_permission
from app.core.integrations import require_service_token
from app.core.rbac import Action, Module
from app.models.data import Dataset, IngestionRun
from app.models.user import User
from app.schemas.data import IngestionRunOut
from app.services.ingestion import IngestionError, ingest_file

logger = logging.getLogger("nutririsk.ingestion")
router = APIRouter(prefix="/ingestion", tags=["Ingesta programada"])

INGEST_READ = Depends(require_permission(Module.INGESTION, Action.READ))





@router.get("/runs", summary="Historial de ingestas")
def list_runs(
    db: DbSession,
    page: PageParams,
    dataset_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    _: User = INGEST_READ,
) -> dict:
    stmt = select(IngestionRun)
    count_stmt = select(func.count(IngestionRun.id))
    conditions = []
    if dataset_id:
        conditions.append(IngestionRun.dataset_id == dataset_id)
    if status_filter:
        conditions.append(IngestionRun.status == status_filter)
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)
    total = db.scalar(count_stmt) or 0
    runs = db.execute(stmt.order_by(IngestionRun.id.desc()).offset(page.offset).limit(page.limit)).scalars().all()
    return paginated([IngestionRunOut.model_validate(run).model_dump() for run in runs], total, page.page, page.page_size)


@router.get("/schedule", summary="Configuración de ingesta programada")
def schedule(_: User = INGEST_READ) -> dict[str, Any]:
    return {
        "scheduler": "n8n",
        "workflow": "n8n/workflows/01_ingesta_programada.json",
        "webhook": f"{settings.n8n_base_url}/webhook/nutririsk-ingestion",
        "api_endpoint": f"{settings.api_public_url}/api/v1/ingestion/n8n/sync",
        "auth_header": "X-N8N-Token",
        "recommended_cron": "0 5 * * *",
        "description": "Reprocesa los datasets con archivo disponible y notifica el resultado.",
    }


def _reprocess(db, dataset: Dataset, *, trigger: str, user_id: int | None) -> dict[str, Any]:
    if not dataset.file_path or not Path(dataset.file_path).exists():
        return {"dataset_id": dataset.id, "status": "SKIPPED", "reason": "Archivo no disponible"}
    try:
        outcome = ingest_file(db, dataset=dataset, path=Path(dataset.file_path), trigger=trigger, user_id=user_id)
        return {
            "dataset_id": dataset.id,
            "name": dataset.name,
            "status": outcome.run.status,
            "rows_loaded": outcome.run.rows_loaded,
            "rows_rejected": outcome.run.rows_rejected,
            "duration_ms": outcome.run.duration_ms,
        }
    except IngestionError as exc:
        return {"dataset_id": dataset.id, "status": "FAILED", "error": str(exc)}


@router.post("/trigger", summary="Reprocesar un dataset")
def trigger(
    dataset_id: int,
    db: DbSession,
    user: User = Depends(require_permission(Module.INGESTION, Action.EXECUTE)),
) -> dict[str, Any]:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado")
    return _reprocess(db, dataset, trigger="MANUAL", user_id=user.id)


@router.post("/n8n/sync", summary="Sincronización programada (n8n)")
def n8n_sync(
    db: DbSession,
    dataset_id: int | None = Query(default=None),
    _token: None = Depends(require_service_token),
) -> dict[str, Any]:
    stmt = select(Dataset).where(Dataset.status.in_(["READY", "PARTIAL", "FAILED"]))
    if dataset_id:
        stmt = stmt.where(Dataset.id == dataset_id)
    datasets = db.execute(stmt.order_by(Dataset.id)).scalars().all()
    results = [_reprocess(db, dataset, trigger="SCHEDULE", user_id=None) for dataset in datasets]
    return {
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "datasets": len(results),
        "processed": sum(1 for item in results if item.get("rows_loaded")),
        "results": results,
    }


_ = CurrentUser


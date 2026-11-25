"""System information, health checks and demo-data administration."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import DbSession, require_permission
from app.core.rbac import Action, Module, RoleCode
from app.db.session import SessionLocal
from app.models.data import AnthropometricIndicator, Child, Dataset, Household, IngestionRun, Territory, VariableDefinition
from app.models.ml import (
    Alert,
    FairnessReport,
    MLModel,
    ModelExperiment,
    Prediction,
    PredictionExplanation,
    TerritoryRisk,
)
from app.models.system import Report
from app.models.user import Role, User
from app.models.audit import AuditLog
from app.schemas.common import HealthResponse
from app.schemas.system import SystemInfo
from app.services.modeling import score_model, train_bundle

router = APIRouter(prefix="/system", tags=["Sistema"])
logger = logging.getLogger("nutririsk.system")

SYSTEM_READ = Depends(require_permission(Module.SYSTEM, Action.READ))


@router.get("/health", response_model=HealthResponse, summary="Verificación de salud")
def health(db: DbSession) -> HealthResponse:
    database = "ok"
    try:
        db.execute(select(func.count(Role.id)))
    except Exception:  # noqa: BLE001
        database = "error"
    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database=database,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/info", response_model=SystemInfo, summary="Información del sistema")
def info(db: DbSession, _: User = SYSTEM_READ) -> SystemInfo:
    from app.models.ml import MLModel as Model

    counts = {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "territories": db.scalar(select(func.count(Territory.id))) or 0,
        "households": db.scalar(select(func.count(Household.id))) or 0,
        "children": db.scalar(select(func.count(Child.id))) or 0,
        "datasets": db.scalar(select(func.count(Dataset.id))) or 0,
        "models": db.scalar(select(func.count(Model.id))) or 0,
        "alerts": db.scalar(select(func.count(Alert.id))) or 0,
        "reports": db.scalar(select(func.count(Report.id))) or 0,
        "audit_events": db.scalar(select(func.count(AuditLog.id))) or 0,
    }
    active = db.scalar(select(Model).where(Model.is_active.is_(True)))
    return SystemInfo(
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        api_prefix=settings.api_v1_prefix,
        database="PostgreSQL + PostGIS" if settings.is_postgres else "SQLite (modo demostración)",
        demo_mode=settings.demo_mode,
        llm_provider=settings.llm_provider,
        reference_version="WHO-2006",
        counts=counts,
        active_model={
            "id": active.id,
            "name": active.name,
            "algorithm": active.algorithm,
            "version": active.version,
            "auc": (active.metrics or {}).get("auc"),
        }
        if active
        else None,
        features={
            "shap": True,
            "fairlearn": True,
            "spatial_regression": True,
            "cnn_lstm": True,
            "n8n": True,
            "langflow": True,
            "langchain_agent": True,
        },
        server_time=datetime.now(timezone.utc),
    )


def _reset_demo_data(db: Session) -> None:
    """Delete derived demo data in FK-safe order (keeps users, roles, settings)."""
    db.execute(delete(PredictionExplanation))
    db.execute(delete(Prediction))
    db.execute(delete(TerritoryRisk))
    db.execute(delete(FairnessReport))
    db.execute(delete(Alert))
    db.execute(delete(MLModel))
    db.execute(delete(ModelExperiment))
    db.execute(delete(AnthropometricIndicator))
    db.execute(delete(Child))
    db.execute(delete(Household))
    db.execute(delete(VariableDefinition))
    db.execute(delete(IngestionRun))
    db.execute(delete(Dataset))
    db.commit()


def _reseed_and_train() -> None:
    from app.db.bootstrap import bootstrap
    from app.services.synthetic import write_artifacts

    settings.ensure_directories()
    write_artifacts(settings.synthetic_dir)
    with SessionLocal() as db:
        _reset_demo_data(db)
    bootstrap()
    with SessionLocal() as db:
        train_bundle(
            db,
            algorithms=["random_forest", "xgboost", "catboost", "spatial_xgboost"],
            task="classification",
            target="stunting",
            cv_strategy="group_kfold_region",
            seed=settings.random_seed,
            hyperparams=None,
            user_id=None,
            dataset_id=None,
            notes="Regeneración desde el panel de administración",
            include_spatial=True,
            include_cnn_lstm=True,
        )


@router.post("/demo-data", status_code=status.HTTP_202_ACCEPTED, summary="Regenerar datos sintéticos y reentrenar")
def regenerate_demo(
    background: BackgroundTasks,
    db: DbSession,
    user: User = Depends(require_permission(Module.SYSTEM, Action.EXECUTE)),
) -> dict[str, Any]:
    if user.role.code != RoleCode.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo administradores")
    background.add_task(_reseed_and_train)
    return {
        "message": "Regeneración encolada: se recrearán datos sintéticos y se reentrenarán los modelos.",
        "estimated_minutes": 4,
    }


@router.post("/train", status_code=status.HTTP_202_ACCEPTED, summary="Reentrenar modelos base")
def retrain(
    background: BackgroundTasks,
    user: User = Depends(require_permission(Module.SYSTEM, Action.EXECUTE)),
) -> dict[str, Any]:
    if user.role.code != RoleCode.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo administradores")

    def _run() -> None:
        with SessionLocal() as db:
            train_bundle(
                db,
                algorithms=["random_forest", "xgboost", "catboost"],
                task="classification",
                target="stunting",
                cv_strategy="group_kfold_region",
                seed=settings.random_seed,
                hyperparams=None,
                user_id=None,
                dataset_id=None,
                notes="Reentrenamiento manual",
                include_spatial=True,
                include_cnn_lstm=False,
            )

    background.add_task(_run)
    return {"message": "Reentrenamiento encolado", "estimated_minutes": 2}


@router.get("/monitoring", summary="Métricas operativas")
def monitoring(db: DbSession, _: User = SYSTEM_READ) -> dict[str, Any]:
    from app.models.audit import AuditLog as Log

    total_events = db.scalar(select(func.count(Log.id))) or 0
    failures = db.scalar(select(func.count(Log.id)).where(Log.result != "SUCCESS")) or 0
    slow = db.scalar(select(func.count(Log.id)).where(Log.duration_ms > 1000)) or 0
    latest = db.execute(select(Log).order_by(Log.started_at.desc()).limit(10)).scalars().all()
    return {
        "audit_events": total_events,
        "failed_events": failures,
        "slow_events": slow,
        "success_rate": round((total_events - failures) / total_events * 100, 2) if total_events else 100.0,
        "latest_events": [
            {
                "id": event.id,
                "module": event.module,
                "action": event.action,
                "result": event.result,
                "duration_ms": event.duration_ms,
                "started_at": event.started_at.isoformat() if event.started_at else None,
            }
            for event in latest
        ],
        "storage_dir": str(settings.storage_dir),
        "artifacts_dir": str(settings.artifacts_dir),
        "database": "postgresql" if settings.is_postgres else "sqlite",
    }


_ = (score_model, MLModel)


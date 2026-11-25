"""Trained model registry: activation, scoring and metrics."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.deps import DbSession, PageParams, paginated, require_permission
from app.core.rbac import Action, Module, RoleCode
from app.db.session import SessionLocal
from app.models.ml import MLModel
from app.models.user import User
from app.schemas.ml import ModelComparisonRow, ModelOut
from app.services.modeling import (
    activate_model,
    get_active_model,
    load_artifact,
    model_metrics_table,
    score_model,
)

router = APIRouter(prefix="/models", tags=["Modelos"])
logger = logging.getLogger("nutririsk.models")

MODEL_READ = Depends(require_permission(Module.MODELS, Action.READ))
MODEL_EXECUTE = Depends(require_permission(Module.MODELS, Action.EXECUTE))


def _score_in_background(model_id: int) -> None:
    with SessionLocal() as db:
        model = db.get(MLModel, model_id)
        if model is None:
            return
        try:
            score_model(db, model)
        except Exception:  # noqa: BLE001
            logger.exception("Fallo al puntuar el modelo %s", model_id)


@router.get("", summary="Listar modelos")
def list_models(
    db: DbSession,
    page: PageParams,
    algorithm: str | None = Query(default=None),
    _: User = MODEL_READ,
) -> dict:
    stmt = select(MLModel)
    count_stmt = select(func.count(MLModel.id))
    if algorithm:
        stmt = stmt.where(MLModel.algorithm == algorithm)
        count_stmt = count_stmt.where(MLModel.algorithm == algorithm)
    total = db.scalar(count_stmt) or 0
    models = db.execute(stmt.order_by(MLModel.id.desc()).offset(page.offset).limit(page.limit)).scalars().all()
    return paginated([ModelOut.model_validate(model).model_dump() for model in models], total, page.page, page.page_size)


@router.get("/active", response_model=ModelOut, summary="Modelo activo")
def active_model(db: DbSession, _: User = MODEL_READ) -> ModelOut:
    model = get_active_model(db)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay modelo activo")
    return ModelOut.model_validate(model)


@router.get("/comparison", response_model=list[ModelComparisonRow], summary="Comparación de modelos")
def comparison(db: DbSession, _: User = MODEL_READ) -> list[ModelComparisonRow]:
    return [ModelComparisonRow(**row) for row in model_metrics_table(db)]


@router.post("/{model_id}/activate", response_model=ModelOut, summary="Activar modelo")
def activate(
    model_id: int,
    db: DbSession,
    user: User = Depends(require_permission(Module.MODELS, Action.UPDATE)),
) -> ModelOut:
    _ = user
    try:
        model = activate_model(db, model_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ModelOut.model_validate(model)


@router.post("/{model_id}/score", status_code=status.HTTP_202_ACCEPTED, summary="Repuntuar población y mapa de riesgo")
def score(
    model_id: int,
    background: BackgroundTasks,
    db: DbSession,
    user: User = Depends(require_permission(Module.MODELS, Action.EXECUTE)),
) -> dict:
    if user.role.code == RoleCode.AUDITOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El auditor no puede ejecutar puntuaciones")
    model = db.get(MLModel, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modelo no encontrado")
    if model.task != "classification":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Solo modelos de clasificación")
    background.add_task(_score_in_background, model_id)
    return {"message": "Puntuación encolada", "model_id": model_id}


@router.get("/{model_id}", response_model=ModelOut, summary="Detalle del modelo")
def get_model(model_id: int, db: DbSession, _: User = MODEL_READ) -> ModelOut:
    model = db.get(MLModel, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modelo no encontrado")
    return ModelOut.model_validate(model)


@router.get("/{model_id}/metrics", summary="Métricas completas")
def metrics(model_id: int, db: DbSession, _: User = MODEL_READ) -> dict:
    model = db.get(MLModel, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modelo no encontrado")
    experiment = model.experiment
    return {
        "model": ModelOut.model_validate(model).model_dump(),
        "metrics": model.metrics or {},
        "per_region": (experiment.per_region_metrics if experiment else {}) or {},
        "per_group": (experiment.per_group_metrics if experiment else {}) or {},
        "spatial_diagnostics": (experiment.spatial_diagnostics if experiment else {}) or {},
    }


@router.get("/{model_id}/feature-importance", summary="Importancia de variables")
def feature_importance(model_id: int, db: DbSession, _: User = MODEL_READ) -> dict:
    model = db.get(MLModel, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modelo no encontrado")
    return {
        "model_id": model.id,
        "algorithm": model.algorithm,
        "importance": model.feature_importance or {},
        "shap": model.shap_summary or {},
    }


@router.delete("/{model_id}", summary="Eliminar modelo")
def delete_model(
    model_id: int,
    db: DbSession,
    _: User = Depends(require_permission(Module.MODELS, Action.DELETE)),
) -> dict[str, str]:
    model = db.get(MLModel, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modelo no encontrado")
    if model.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active otro modelo antes de eliminar el actual")
    try:
        load_artifact(model)
    except FileNotFoundError:
        pass
    db.delete(model)
    db.commit()
    return {"message": "Modelo eliminado"}

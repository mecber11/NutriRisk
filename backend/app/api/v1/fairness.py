"""Fairness endpoints backed by Fairlearn group metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.deps import DbSession, require_permission
from app.core.rbac import Action, Module
from app.ml.features import SENSITIVE_ATTRIBUTES
from app.models.ml import MLModel
from app.models.user import User
from app.schemas.ml import FairnessResult, FairnessRunRequest, FairnessSummary
from app.services.fairness import compute_fairness, summary as fairness_summary
from app.services.modeling import get_active_model

router = APIRouter(prefix="/fairness", tags=["Equidad"])

FAIR_READ = Depends(require_permission(Module.FAIRNESS, Action.READ))
FAIR_EXECUTE = Depends(require_permission(Module.FAIRNESS, Action.EXECUTE))


@router.get("/attributes", summary="Atributos sensibles disponibles")
def attributes(_: User = FAIR_READ) -> dict:
    return {
        "attributes": [{"code": code, "label": label} for code, label in SENSITIVE_ATTRIBUTES.items()],
        "threshold": 0.2,
    }


@router.get("/{model_id}", response_model=FairnessSummary, summary="Resumen de equidad del modelo")
def get_fairness(
    model_id: int,
    db: DbSession,
    attribute: str | None = Query(default=None),
    _: User = FAIR_READ,
) -> FairnessSummary:
    model = db.get(MLModel, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modelo no encontrado")
    data = fairness_summary(db, model_id)
    if attribute:
        data["attributes"] = [item for item in data["attributes"] if item["sensitive_attribute"] == attribute]
    return FairnessSummary(
        model_id=model_id,
        attributes=[FairnessResult(**item) for item in data["attributes"]],
        overall_acceptable=data["overall_acceptable"],
        notes=data["notes"],
    )


@router.post("/run", response_model=list[FairnessResult], summary="Recalcular equidad")
def run_fairness(
    payload: FairnessRunRequest,
    db: DbSession,
    user: User = FAIR_EXECUTE,
) -> list[FairnessResult]:
    model = db.get(MLModel, payload.model_id) or get_active_model(db)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Modelo no encontrado")
    results = compute_fairness(
        db,
        model.id,
        attributes=payload.attributes,
        threshold=payload.threshold,
        persist=True,
        user_id=user.id,
    )
    if not results:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No hay predicciones para evaluar")
    return [FairnessResult(**item) for item in results]

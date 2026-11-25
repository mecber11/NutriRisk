"""Explainability endpoints: global SHAP, local child/territory explanations."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import DbSession, require_permission
from app.core.rbac import Action, Module
from app.ml.features import FEATURE_LABELS, FEATURES, SPATIAL_FEATURES, add_features, add_spatial_features, build_analytical_frame
from app.models.data import Child, Territory
from app.models.ml import MLModel, Prediction
from app.models.user import User
from app.schemas.ml import (
    DependenceResponse,
    GlobalExplanation,
    LocalExplanation,
    ShapContribution,
    ShapFeature,
    TerritoryExplanation,
)
from app.services.modeling import get_active_model, load_artifact
from app.services.xai import (
    build_explainer,
    to_probability_space,
    dependence_points,
    global_explanation,
    intervention_hint,
    local_explanation,
    narrative,
    _shap_values,
)

router = APIRouter(prefix="/xai", tags=["Explicabilidad (XAI)"])

XAI_READ = Depends(require_permission(Module.XAI, Action.READ))


def _resolve_model(db, model_id: int | None) -> MLModel:  # noqa: ANN001
    model = db.get(MLModel, model_id) if model_id else get_active_model(db)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay modelo disponible")
    if model.task != "classification":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Solo modelos de clasificación")
    return model


def _feature_frame(db, model: MLModel):  # noqa: ANN001, ANN202
    payload = load_artifact(model)
    frame = add_features(build_analytical_frame(db))
    features = payload.get("features", FEATURES)
    if any(feature in SPATIAL_FEATURES for feature in features):
        frame = add_spatial_features(db, frame)
    return payload, frame, features


@router.get("/models", summary="Modelos con explicabilidad disponible")
def models_with_xai(db: DbSession, _: User = XAI_READ) -> dict:
    models = db.execute(select(MLModel).where(MLModel.task == "classification")).scalars().all()
    return {
        "models": [
            {
                "id": model.id,
                "name": model.name,
                "algorithm": model.algorithm,
                "is_active": model.is_active,
                "version": model.version,
                "has_shap": bool((model.shap_summary or {}).get("features")),
            }
            for model in models
        ]
    }


@router.get("/global", response_model=GlobalExplanation, summary="Importancia global SHAP")
def global_xai(db: DbSession, model_id: int | None = Query(default=None), top_n: int = Query(default=12, ge=3, le=30), _: User = XAI_READ) -> GlobalExplanation:
    model = _resolve_model(db, model_id)
    stored = model.shap_summary or {}
    if stored.get("features") and len(stored["features"]) >= top_n:
        return GlobalExplanation(
            model_id=model.id,
            model_name=model.name,
            algorithm=model.algorithm,
            base_value=float(stored.get("base_value", 0.0)),
            n_samples=int(stored.get("n_samples", 0)),
            features=[ShapFeature(**item) for item in stored["features"][:top_n]],
            beeswarm=stored.get("beeswarm", [])[:600],
        )
    payload, frame, features = _feature_frame(db, model)
    result = global_explanation(
        payload["estimator"],
        frame[features],
        top_n=top_n,
        model_id=model.id,
        model_name=model.name,
        algorithm=model.algorithm,
    )
    return GlobalExplanation(
        model_id=model.id,
        model_name=model.name,
        algorithm=model.algorithm,
        base_value=result["base_value"],
        n_samples=result["n_samples"],
        features=[ShapFeature(**item) for item in result["features"]],
        beeswarm=result["beeswarm"],
    )


@router.get("/child/{child_id}", response_model=LocalExplanation, summary="Explicación local por niño")
def explain_child(
    child_id: int,
    db: DbSession,
    model_id: int | None = Query(default=None),
    _: User = XAI_READ,
) -> LocalExplanation:
    model = _resolve_model(db, model_id)
    child = db.get(Child, child_id)
    if child is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niño no encontrado")
    payload, frame, features = _feature_frame(db, model)
    row_frame = frame[frame["child_id"] == child.id]
    if row_frame.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El niño no tiene indicadores")
    X = row_frame[features]
    prediction, base, contributions = local_explanation(payload["estimator"], X)
    stored_prediction = db.scalar(
        select(Prediction).where(Prediction.model_id == model.id, Prediction.child_id == child.id)
    )
    text = narrative(
        prediction,
        child_code=child.code,
        contributions=contributions,
        context={"territory": row_frame.iloc[0]["territory_name"], "region": row_frame.iloc[0]["region"]},
    )
    hint = intervention_hint(contributions)
    if hint:
        text += f" Recomendación: {hint}"
    return LocalExplanation(
        child_id=child.id,
        child_code=child.code,
        model_id=model.id,
        prediction=round(float(prediction), 4),
        base_value=round(float(base), 4),
        risk_band=stored_prediction.risk_band if stored_prediction else "UNKNOWN",
        contributions=[ShapContribution(**item) for item in contributions],
        narrative=text,
        positive=[ShapContribution(**item) for item in contributions if item["contribution"] > 0][:4],
        negative=[ShapContribution(**item) for item in contributions if item["contribution"] < 0][:4],
    )


@router.get("/territory/{territory_id}", response_model=TerritoryExplanation, summary="Explicación agregada por territorio")
def explain_territory(
    territory_id: int,
    db: DbSession,
    model_id: int | None = Query(default=None),
    year: int | None = Query(default=None),
    _: User = XAI_READ,
) -> TerritoryExplanation:
    model = _resolve_model(db, model_id)
    territory = db.get(Territory, territory_id)
    if territory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Territorio no encontrado")
    payload, frame, features = _feature_frame(db, model)
    subset = frame[frame["territory_id"] == territory.id]
    if year:
        subset = subset[subset["period_year"] == year]
    if subset.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sin datos para el territorio")
    sample = subset.sample(min(len(subset), 250), random_state=42)
    X = sample[features]
    explainer = build_explainer(payload["estimator"], X)
    values = _shap_values(explainer, X)
    base_raw = float(np.atleast_1d(explainer.expected_value)[-1]) if hasattr(explainer, "expected_value") else 0.0
    _, values = to_probability_space(base_raw, values)
    mean_abs = abs(values).mean(axis=0)
    order = mean_abs.argsort()[::-1][:8]
    total = float(mean_abs.sum()) or 1.0
    items = [
        ShapFeature(
            feature=features[index],
            label=FEATURE_LABELS.get(features[index], features[index]),
            mean_abs_shap=round(float(mean_abs[index]), 5),
            share=round(float(mean_abs[index] / total), 4),
            direction="positive",
        )
        for index in order
    ]
    risk = None
    from app.models.ml import TerritoryRisk

    risk = db.scalar(
        select(TerritoryRisk).where(
            TerritoryRisk.model_id == model.id,
            TerritoryRisk.territory_id == territory.id,
            TerritoryRisk.period_year == (year or int(subset["period_year"].max())),
        )
    )
    mean_risk = float(risk.mean_risk) if risk else float(subset["risk"].mean() if "risk" in subset else 0.0)
    stunting = float(subset["stunting"].mean())
    top_labels = ", ".join(item.label for item in items[:4])
    text = (
        f"En {territory.name} ({territory.region}) el riesgo medio predicho es {mean_risk * 100:.1f} % "
        f"con una prevalencia observada de retraso del crecimiento de {stunting * 100:.1f} % "
        f"en {len(subset)} niños evaluados. Los determinantes que más pesan son: {top_labels}."
    )
    return TerritoryExplanation(
        territory_id=territory.id,
        territory_code=territory.code,
        territory_name=territory.name,
        region=territory.region,
        model_id=model.id,
        mean_risk=round(mean_risk, 4),
        stunting_prevalence=round(stunting, 4),
        children_screened=int(len(subset)),
        features=items,
        narrative=text,
    )


@router.get("/dependence", response_model=DependenceResponse, summary="Gráfico de dependencia SHAP")
def dependence(
    db: DbSession,
    feature: str = Query(...),
    model_id: int | None = Query(default=None),
    _: User = XAI_READ,
) -> DependenceResponse:
    model = _resolve_model(db, model_id)
    payload, frame, features = _feature_frame(db, model)
    if feature not in features:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Variable no disponible en el modelo")
    points = dependence_points(payload["estimator"], frame[features], feature)
    return DependenceResponse(
        feature=feature,
        label=FEATURE_LABELS.get(feature, feature),
        model_id=model.id,
        points=[{"value": point["value"], "shap": point["shap"], "group": point["group"]} for point in points],
    )


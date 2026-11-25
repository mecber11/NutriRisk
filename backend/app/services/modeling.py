"""Training orchestration, experiment registry, scoring and risk mapping."""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml import cnn_lstm
from app.ml.features import (
    FEATURE_LABELS,
    FEATURES,
    SPATIAL_FEATURES,
    add_features,
    add_spatial_features,
    build_analytical_frame,
    feature_matrix,
    target_series,
)
from app.ml.models import (
    ALGORITHM_LABELS,
    build_estimator,
    classification_metrics,
    optimal_thresholds,
    out_of_fold_scores,
    per_group_metrics,
    per_region_metrics,
    predict_scores,
    regression_metrics,
    spatial_group_splits,
    top_feature_importance,
)
from app.ml.spatial import (
    build_neighbor_map,
    evaluate_corrected,
    morans_i,
    spatial_lag_correction,
    spatial_regression,
    spatial_summary,
    territory_frame,
)
from app.models.data import Territory
from app.models.ml import MLModel, ModelExperiment, Prediction, TerritoryRisk

logger = logging.getLogger("nutririsk.modeling")

RISK_BANDS = ((0.15, "LOW"), (0.30, "MODERATE"), (0.50, "HIGH"), (1.01, "CRITICAL"))


def risk_band(score: float) -> str:
    for threshold, band in RISK_BANDS:
        if score < threshold:
            return band
    return "CRITICAL"


def artifacts_dir() -> Path:
    path = settings.artifacts_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def next_version(db: Session, algorithm: str) -> str:
    count = db.scalar(select(func.count(MLModel.id)).where(MLModel.algorithm == algorithm)) or 0
    return f"1.0.{count + 1}"


def load_artifact(model: MLModel) -> dict[str, Any]:
    path = Path(model.artifact_path)
    if not path.exists():
        raise FileNotFoundError(f"Artefacto no encontrado: {path}")
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return joblib.load(path)


def _training_frame(db: Session, dataset_id: int | None = None) -> pd.DataFrame:
    frame = build_analytical_frame(db)
    if frame.empty:
        raise ValueError("No hay datos analíticos. Cargue un dataset y calcule indicadores antropométricos.")
    if dataset_id:
        logger.info("Entrenando con dataset_id=%s (se usa el conjunto analítico completo)", dataset_id)
    return add_features(frame)


def train_experiment(
    db: Session,
    *,
    algorithm: str,
    task: str = "classification",
    target: str = "stunting",
    cv_strategy: str = "group_kfold_region",
    seed: int = 42,
    hyperparams: dict[str, Any] | None = None,
    user_id: int | None = None,
    dataset_id: int | None = None,
    notes: str | None = None,
    include_spatial: bool = True,
    experiment_id: int | None = None,
) -> ModelExperiment:
    """Train one algorithm with spatial CV, metrics, SHAP and versioned artifact."""
    started = time.perf_counter()
    experiment = db.get(ModelExperiment, experiment_id) if experiment_id else None
    if experiment is None:
        experiment = ModelExperiment(
            name=f"{ALGORITHM_LABELS.get(algorithm, algorithm)} · {target}",
            algorithm=algorithm,
            task=task,
            target=target,
            dataset_id=dataset_id,
            cv_strategy=cv_strategy,
            seed=seed,
            hyperparams=hyperparams or {},
            status="RUNNING",
            notes=notes,
            started_at=datetime.now(timezone.utc),
            created_by=user_id,
        )
        db.add(experiment)
        db.commit()
    else:
        experiment.status = "RUNNING"
        experiment.started_at = datetime.now(timezone.utc)
        experiment.notes = notes
        db.commit()

    try:
        frame = _training_frame(db, dataset_id)
        model_features = list(FEATURES)
        if algorithm == "spatial_xgboost":
            frame = add_spatial_features(db, frame)
            model_features = list(FEATURES) + list(SPATIAL_FEATURES)
        X = feature_matrix(frame, model_features)
        y = target_series(frame, target)
        groups = frame["region"]

        if algorithm == "cnn_lstm":
            return _train_cnn(db, experiment, frame, seed=seed, user_id=user_id)

        factory = lambda: build_estimator(algorithm, task, seed=seed, params=hyperparams)  # noqa: E731
        splits = spatial_group_splits(groups, cv_strategy, seed=seed)
        oof, folds = out_of_fold_scores(factory, X, y, groups, splits)
        mask = ~np.isnan(oof)
        if not mask.any():
            raise RuntimeError("La validación no produjo predicciones fuera de pliegue")

        if task == "classification":
            metrics = classification_metrics(y[mask].to_numpy(), oof[mask])
            operating = optimal_thresholds(y[mask].to_numpy(), oof[mask])
            at_optimal = classification_metrics(y[mask].to_numpy(), oof[mask], threshold=operating["threshold"])
            at_screening = classification_metrics(
                y[mask].to_numpy(), oof[mask], threshold=operating["screening_threshold"]
            )
            metrics["operating_points"] = operating
            metrics["threshold_optimal"] = operating["threshold"]
            metrics["screening_threshold"] = operating["screening_threshold"]
            metrics["f1_optimal"] = at_optimal["f1"]
            metrics["precision_optimal"] = at_optimal["precision"]
            metrics["recall_optimal"] = at_optimal["recall"]
            metrics["f1_screening"] = at_screening["f1"]
            metrics["recall_screening"] = at_screening["recall"]
            metrics["precision_screening"] = at_screening["precision"]
            per_region = per_region_metrics(frame[mask], y[mask].to_numpy(), oof[mask], task)
            per_group = per_group_metrics(frame[mask], y[mask].to_numpy(), oof[mask], task)
            threshold_for_scoring = operating["threshold"]
        else:
            metrics = regression_metrics(y[mask].to_numpy(), oof[mask])
            per_region = per_region_metrics(frame[mask], y[mask].to_numpy(), oof[mask], task)
            per_group = per_group_metrics(frame[mask], y[mask].to_numpy(), oof[mask], task)
            threshold_for_scoring = 0.5
        metrics["folds"] = folds
        metrics["cv_strategy"] = cv_strategy
        metrics["train_rows"] = int(mask.sum())
        metrics["features"] = len(model_features)
        metrics["duration_seconds"] = round(time.perf_counter() - started, 2)

        diagnostics: dict[str, Any] = {"moran": {"available": False}}
        correction: dict[str, Any] = {"available": False}
        if include_spatial and task == "classification":
            residuals = y.to_numpy(dtype=float) - np.nan_to_num(oof, nan=float(np.mean(y)))
            aggregated = territory_frame(frame, residuals)
            neighbor_map = build_neighbor_map(db)
            weights_available = [code for code, neighbors in neighbor_map.items() if neighbors]
            if len(weights_available) >= 6:
                try:
                    from app.ml.spatial import build_weights

                    weights, codes = build_weights(neighbor_map)
                    subset = aggregated.set_index("territory_code").loc[
                        [code for code in codes if code in set(aggregated["territory_code"])]
                    ]
                    diagnostics = {
                        "moran": morans_i(subset["mean_residual"].to_numpy(), weights),
                        "models": spatial_regression(aggregated, neighbor_map),
                        "n_territories": int(len(subset)),
                    }
                    diagnostics["summary"] = spatial_summary(aggregated, diagnostics["models"])
                    correction = spatial_lag_correction(
                        dict(zip(aggregated["territory_code"], aggregated["mean_residual"])), neighbor_map
                    )
                    diagnostics["correction"] = evaluate_corrected(
                        frame.assign(territory_code=frame["territory_code"])[mask],
                        y[mask].to_numpy(),
                        oof[mask],
                        correction,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Diagnósticos espaciales no disponibles: %s", exc)
                    diagnostics["error"] = str(exc)

        final_model = factory()
        final_model.fit(X, y)
        importance = top_feature_importance(final_model, model_features)

        shap_summary: dict[str, Any] = {}
        try:
            from app.services.xai import global_explanation

            shap_summary = global_explanation(
                final_model,
                X,
                top_n=12,
                model_name=experiment.name,
                algorithm=algorithm,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("SHAP no disponible: %s", exc)
            shap_summary = {"error": str(exc), "features": []}

        version = next_version(db, algorithm)
        artifact_path = artifacts_dir() / f"{algorithm}_{target}_{version}_{uuid.uuid4().hex[:8]}.joblib"
        payload = {
            "estimator": final_model,
            "features": model_features,
            "feature_labels": FEATURE_LABELS,
            "task": task,
            "target": target,
            "algorithm": algorithm,
            "seed": seed,
            "version": version,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "spatial_offsets": correction.get("offsets", {}),
            "spatial_rho": correction.get("rho", 0.0),
            "threshold": threshold_for_scoring,
        }
        joblib.dump(payload, artifact_path, compress=3)

        experiment.metrics = metrics
        experiment.per_region_metrics = per_region
        experiment.per_group_metrics = per_group
        experiment.spatial_diagnostics = diagnostics
        experiment.feature_importance = importance
        experiment.status = "COMPLETED"
        experiment.finished_at = datetime.now(timezone.utc)
        experiment.duration_seconds = round(time.perf_counter() - started, 2)

        model = MLModel(
            experiment_id=experiment.id,
            name=f"NutriRisk {ALGORITHM_LABELS.get(algorithm, algorithm)}",
            version=version,
            algorithm=algorithm,
            task=task,
            target=target,
            artifact_path=str(artifact_path),
            feature_names=model_features,
            metrics=metrics,
            feature_importance=importance,
            shap_summary=shap_summary,
            hyperparams={"params": (hyperparams or {}), "seed": seed, "spatial_rho": correction.get("rho", 0.0)},
            is_active=False,
            is_synthetic=True,
        )
        db.add(model)
        db.commit()
        db.refresh(experiment)
        return experiment

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        experiment = db.get(ModelExperiment, experiment.id) or experiment
        experiment.status = "FAILED"
        experiment.notes = f"{notes or ''}\nERROR: {exc}".strip()
        experiment.finished_at = datetime.now(timezone.utc)
        experiment.duration_seconds = round(time.perf_counter() - started, 2)
        db.commit()
        logger.exception("Training failed for %s", algorithm)
        raise


def _train_cnn(db: Session, experiment: ModelExperiment, frame: pd.DataFrame, *, seed: int, user_id: int | None) -> ModelExperiment:
    """Train the CNN-LSTM and register it as a spatio-temporal experiment."""
    result = cnn_lstm.train_cnn_lstm(frame, FEATURES, seed=seed)
    artifact_path = artifacts_dir() / f"cnn_lstm_{uuid.uuid4().hex[:8]}.pt"
    cnn_lstm.save_model(frame, FEATURES, artifact_path, seed=seed)

    version = next_version(db, "cnn_lstm")
    experiment.status = "COMPLETED"
    experiment.metrics = result["metrics"]
    experiment.per_region_metrics = result["per_region"]
    experiment.spatial_diagnostics = {
        "sequence_shape": result["sequence_shape"],
        "territories": result["territories"],
        "years": result["years"],
        "curves": result["curves"],
    }
    experiment.feature_importance = {}
    experiment.finished_at = datetime.now(timezone.utc)
    experiment.duration_seconds = 1.0
    model = MLModel(
        experiment_id=experiment.id,
        name="NutriRisk CNN-LSTM espaciotemporal",
        version=version,
        algorithm="cnn_lstm",
        task="regression",
        target="stunting",
        artifact_path=str(artifact_path),
        feature_names=FEATURES,
        metrics=result["metrics"],
        feature_importance={},
        shap_summary={},
        hyperparams={"seed": seed, "epochs": result["metrics"].get("epochs")},
        is_active=False,
        is_synthetic=True,
        created_by=user_id,
    )
    db.add(model)
    db.commit()
    db.refresh(experiment)
    return experiment


def train_bundle(
    db: Session,
    *,
    algorithms: list[str],
    task: str,
    target: str,
    cv_strategy: str,
    seed: int,
    hyperparams: dict[str, dict[str, Any]] | None,
    user_id: int | None,
    dataset_id: int | None,
    notes: str | None,
    include_spatial: bool,
    include_cnn_lstm: bool,
) -> dict[str, Any]:
    """Train several algorithms, activate the best one and score the population."""
    results: list[ModelExperiment] = []
    errors: list[dict[str, str]] = []
    queue = list(algorithms)
    if include_cnn_lstm and "cnn_lstm" not in queue:
        queue.append("cnn_lstm")

    for algorithm in queue:
        try:
            experiment = train_experiment(
                db,
                algorithm=algorithm,
                task="regression" if algorithm == "cnn_lstm" else task,
                target=target,
                cv_strategy=cv_strategy,
                seed=seed,
                hyperparams=(hyperparams or {}).get(algorithm),
                user_id=user_id,
                dataset_id=dataset_id,
                notes=notes,
                include_spatial=include_spatial,
            )
            results.append(experiment)
        except Exception as exc:  # noqa: BLE001
            errors.append({"algorithm": algorithm, "error": str(exc)})

    best_model = select_best_model(db, [experiment.id for experiment in results])
    scoring: dict[str, Any] = {}
    if best_model:
        activate_model(db, best_model.id)
        try:
            scoring = score_model(db, best_model)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Scoring failed")
            scoring = {"error": str(exc)}
    return {
        "experiments": [experiment.id for experiment in results],
        "errors": errors,
        "best_model_id": best_model.id if best_model else None,
        "scoring": scoring,
    }


def select_best_model(db: Session, experiment_ids: list[int]) -> MLModel | None:
    """Pick the best deployable classification model by AUC, then F1."""
    if not experiment_ids:
        return None
    models = db.execute(select(MLModel).where(MLModel.experiment_id.in_(experiment_ids))).scalars().all()
    classification = [
        model for model in models if model.task == "classification" and (model.metrics or {}).get("auc") is not None
    ]
    if classification:
        return max(
            classification,
            key=lambda model: ((model.metrics or {}).get("auc", 0), (model.metrics or {}).get("f1", 0)),
        )
    return models[0] if models else None


def activate_model(db: Session, model_id: int) -> MLModel:
    model = db.get(MLModel, model_id)
    if model is None:
        raise ValueError("Modelo no encontrado")
    db.execute(MLModel.__table__.update().values(is_active=False))
    model.is_active = True
    db.commit()
    db.refresh(model)
    return model


def get_active_model(db: Session) -> MLModel | None:
    return db.scalar(select(MLModel).where(MLModel.is_active.is_(True)))


def score_model(db: Session, model: MLModel, *, years: list[int] | None = None) -> dict[str, Any]:
    """Score every child with a classification model, persist predictions and risk map."""
    if model.task != "classification":
        raise ValueError("Solo los modelos de clasificación generan puntuaciones por niño")
    payload = load_artifact(model)
    estimator = payload["estimator"]
    features = payload.get("features", FEATURES)
    offsets = payload.get("spatial_offsets") or {}
    threshold = float(payload.get("threshold", 0.5))

    frame = add_features(build_analytical_frame(db))
    if frame.empty:
        raise ValueError("No hay datos para puntuar")
    if any(feature in SPATIAL_FEATURES for feature in features):
        frame = add_spatial_features(db, frame)
    if years:
        frame = frame[frame["period_year"].isin(years)]
    X = frame[features]
    scores = predict_scores(estimator, X)
    if offsets:
        scores = np.clip(scores + np.array([offsets.get(code, 0.0) for code in frame["territory_code"]]), 1e-4, 1 - 1e-4)
    frame["score"] = scores
    frame["risk_band"] = [risk_band(float(score)) for score in scores]

    db.execute(delete(Prediction).where(Prediction.model_id == model.id))
    db.execute(delete(TerritoryRisk).where(TerritoryRisk.model_id == model.id))
    db.commit()

    prediction_rows = [
        {
            "model_id": model.id,
            "child_id": int(row.child_id),
            "territory_id": int(row.territory_id),
            "score": float(row.score),
            "predicted_label": int(row.score >= threshold),
            "risk_band": row.risk_band,
            "period_year": int(row.period_year),
            "created_at": datetime.now(timezone.utc),
        }
        for row in frame.itertuples(index=False)
    ]
    db.execute(Prediction.__table__.insert(), prediction_rows)
    db.commit()

    # Territory-level SHAP is computed on a stratified sample (fast and sufficient
    # for the risk-map tooltips); per-child explanations are generated on demand.
    explanations: dict[int, dict[str, Any]] = {}
    try:
        explanations = _explain_sample(payload["estimator"], frame, features, per_territory=25)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudieron calcular explicaciones por territorio: %s", exc)

    territory_rows = _aggregate_territories(frame, model.id, explanations)
    db.execute(TerritoryRisk.__table__.insert(), territory_rows)
    db.commit()

    from app.services import alerts as alerts_service

    alert_result = alerts_service.evaluate_alerts(db)

    model.metrics = {**(model.metrics or {}), "scored_children": len(prediction_rows), "scored_at": datetime.now(timezone.utc).isoformat()}
    db.commit()
    return {
        "model_id": model.id,
        "scored_children": len(prediction_rows),
        "territories": len(territory_rows),
        "explained_children": len(explanations),
        "alerts": alert_result,
        "mean_risk": round(float(frame["score"].mean()), 4),
    }


def _explain_sample(
    estimator: Any,
    frame: pd.DataFrame,
    features: list[str],
    *,
    per_territory: int = 25,
) -> dict[int, dict[str, Any]]:
    """Stratified SHAP sample (per territory-year) for territory-level drivers."""
    import shap

    rng = np.random.default_rng(settings.random_seed)
    indices: list[int] = []
    for _, subset in frame.groupby(["territory_id", "period_year"]):
        positions = subset.index.to_numpy()
        take = min(per_territory, len(positions))
        indices.extend(rng.choice(positions, size=take, replace=False).tolist())
    sample = frame.loc[sorted(set(indices))]
    X = sample[features]
    from app.services.xai import to_probability_space

    try:
        explainer = shap.TreeExplainer(estimator)
        values = np.asarray(explainer.shap_values(X))
        if values.ndim == 3:
            values = values[:, :, 1]
        base_raw = float(np.atleast_1d(explainer.expected_value)[-1])
    except Exception:  # noqa: BLE001
        from app.services.xai import _shap_values, build_explainer

        explainer = build_explainer(estimator, X)
        values = _shap_values(explainer, X)
        base_raw = float(np.atleast_1d(getattr(explainer, "expected_value", 0.0))[-1])
    base, values = to_probability_space(base_raw, values)

    labels = [FEATURE_LABELS.get(column, column) for column in features]
    top_indices = np.argsort(np.abs(values), axis=1)[:, -5:][:, ::-1]
    result: dict[int, dict[str, Any]] = {}
    for position, (child_id, score) in enumerate(zip(sample["child_id"].to_numpy(), sample["score"].to_numpy())):
        contributions = [
            {
                "feature": features[index],
                "label": labels[index],
                "value": round(float(X.iloc[position][features[index]]), 4),
                "contribution": round(float(values[position, index]), 5),
                "direction": "positive" if values[position, index] > 0 else "negative",
            }
            for index in top_indices[position]
        ]
        result[int(child_id)] = {
            "base_value": round(base, 5),
            "contributions": contributions,
            "narrative": "",
            "score": float(score),
        }
    return result


def _territory_top_features(
    frame: pd.DataFrame, explanations: dict[int, dict[str, Any]], top_n: int = 5
) -> dict[tuple[int, int], list[dict[str, Any]]]:
    """Aggregate the top local SHAP drivers to the territory-year level."""
    totals: dict[tuple[int, int], dict[str, float]] = {}
    labels: dict[str, str] = {}
    for row in frame[["child_id", "territory_id", "period_year"]].itertuples(index=False):
        explanation = explanations.get(int(row.child_id))
        if not explanation:
            continue
        key = (int(row.territory_id), int(row.period_year))
        bucket = totals.setdefault(key, {})
        for item in explanation["contributions"]:
            bucket[item["feature"]] = bucket.get(item["feature"], 0.0) + abs(item["contribution"])
            labels[item["feature"]] = item["label"]
    counts = frame.groupby(["territory_id", "period_year"]).size().to_dict()
    result: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for key, bucket in totals.items():
        count = max(1, int(counts.get((key[0], key[1]), 1)))
        ordered = sorted(bucket.items(), key=lambda item: item[1], reverse=True)[:top_n]
        result[key] = [
            {"feature": feature, "label": labels.get(feature, feature), "mean_abs_shap": round(value / count, 5)}
            for feature, value in ordered
        ]
    return result


def _aggregate_territories(
    frame: pd.DataFrame,
    model_id: int,
    explanations: dict[int, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Aggregate child scores into territory risk rows with priority ranking."""
    grouped = (
        frame.groupby(["territory_id", "territory_code", "period_year"])
        .agg(
            mean_risk=("score", "mean"),
            stunting_prevalence=("stunting", "mean"),
            children_screened=("child_id", "size"),
            population_u5=("population_u5", "first"),
        )
        .reset_index()
    )
    top_features = _territory_top_features(frame, explanations or {})
    rows: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for year, subset in grouped.groupby("period_year"):
        ordered = subset.sort_values("mean_risk", ascending=False).reset_index(drop=True)
        for rank, row in ordered.iterrows():
            rows.append(
                {
                    "model_id": model_id,
                    "territory_id": int(row["territory_id"]),
                    "period_year": int(year),
                    "mean_risk": round(float(row["mean_risk"]), 5),
                    "risk_band": risk_band(float(row["mean_risk"])),
                    "stunting_prevalence": round(float(row["stunting_prevalence"]), 5),
                    "children_screened": int(row["children_screened"]),
                    "population_at_risk": int(round(float(row["population_u5"]) * float(row["mean_risk"]))),
                    "priority_rank": int(rank + 1),
                    "top_features": top_features.get((int(row["territory_id"]), int(year)), []),
                    "created_at": now,
                }
            )
    return rows


def refresh_territory_top_features(db: Session, model: MLModel) -> int:
    """Attach the dominant SHAP drivers to each territory risk row."""
    from app.services.xai import territory_explanation

    payload = load_artifact(model)
    frame = add_features(build_analytical_frame(db))
    if frame.empty:
        return 0
    X = frame[payload.get("features", FEATURES)]
    explanations = territory_explanation(payload["estimator"], X, frame["territory_code"])
    updated = 0
    for code, features in explanations.items():
        rows = db.execute(
            select(TerritoryRisk)
            .join(Territory, TerritoryRisk.territory_id == Territory.id)
            .where(TerritoryRisk.model_id == model.id, Territory.code == code)
        ).scalars().all()
        for row in rows:
            row.top_features = features
            updated += 1
    db.commit()
    return updated


def model_metrics_table(db: Session) -> list[dict[str, Any]]:
    """Comparison rows for the model performance screen."""
    models = db.execute(select(MLModel).order_by(MLModel.id.desc())).scalars().all()
    rows = []
    best_auc = max(
        ((model.metrics or {}).get("auc") or 0 for model in models if model.task == "classification"), default=0
    )
    for model in models:
        metrics = model.metrics or {}
        rows.append(
            {
                "model_id": model.id,
                "name": model.name,
                "version": model.version,
                "algorithm": model.algorithm,
                "auc": metrics.get("auc"),
                "f1": metrics.get("f1"),
                "f1_optimal": metrics.get("f1_optimal"),
                "precision": metrics.get("precision"),
                "recall": metrics.get("recall"),
                "accuracy": metrics.get("accuracy"),
                "brier": metrics.get("brier"),
                "threshold": metrics.get("threshold_optimal"),
                "rmse": metrics.get("rmse"),
                "mae": metrics.get("mae"),
                "r2": metrics.get("r2"),
                "train_seconds": metrics.get("duration_seconds"),
                "is_best": bool(model.task == "classification" and metrics.get("auc") == best_auc and best_auc > 0),
            }
        )
    return rows


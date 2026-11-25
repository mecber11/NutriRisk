"""Fairness analysis with Fairlearn group metrics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.features import SENSITIVE_ATTRIBUTES, build_analytical_frame
from app.models.ml import FairnessReport, MLModel, Prediction

FAIRNESS_THRESHOLD = 0.2


def _model_predictions(db: Session, model: MLModel) -> pd.DataFrame:
    rows = db.execute(
        select(Prediction.child_id, Prediction.score, Prediction.predicted_label).where(
            Prediction.model_id == model.id
        )
    ).all()
    predictions = pd.DataFrame(rows, columns=["child_id", "score", "predicted_label"])
    frame = build_analytical_frame(db)
    return frame.merge(predictions, on="child_id", how="inner")


def group_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray) -> dict[str, Any]:
    """Confusion-based metrics for one subgroup."""
    from sklearn.metrics import roc_auc_score

    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    y_score = np.asarray(y_score, dtype=float)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    positives = tp + fn
    negatives = fp + tn
    auc = None
    if len(np.unique(y_true)) > 1:
        auc = round(float(roc_auc_score(y_true, y_score)), 4)
    return {
        "n": int(len(y_true)),
        "selection_rate": round(float(y_pred.mean()), 4) if len(y_pred) else 0.0,
        "tpr": round(tp / positives, 4) if positives else None,
        "fpr": round(fp / negatives, 4) if negatives else None,
        "precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
        "recall": round(tp / positives, 4) if positives else None,
        "accuracy": round((tp + tn) / len(y_true), 4) if len(y_true) else None,
        "auc": auc,
        "mean_score": round(float(y_score.mean()), 4) if len(y_score) else None,
        "stunting_rate": round(float(y_true.mean()), 4) if len(y_true) else None,
    }


def compute_fairness(
    db: Session,
    model_id: int,
    *,
    attributes: list[str] | None = None,
    threshold: float = FAIRNESS_THRESHOLD,
    persist: bool = True,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    """Per-attribute group metrics, disparity and acceptance flag."""
    from fairlearn.metrics import MetricFrame, false_positive_rate, selection_rate, true_positive_rate
    from sklearn.metrics import accuracy_score

    model = db.get(MLModel, model_id)
    if model is None:
        raise ValueError("Modelo no encontrado")
    frame = _model_predictions(db, model)
    if frame.empty:
        return []
    attributes = attributes or list(SENSITIVE_ATTRIBUTES)
    y_true = frame["stunting"].astype(int).to_numpy()
    y_pred = frame["predicted_label"].astype(int).to_numpy()
    y_score = frame["score"].to_numpy(dtype=float)
    results: list[dict[str, Any]] = []

    for attribute in attributes:
        if attribute not in frame.columns:
            continue
        sensitive = frame[attribute].astype(str)
        group_frames: list[dict[str, Any]] = []
        for group in sorted(sensitive.unique()):
            mask = (sensitive == group).to_numpy()
            if int(mask.sum()) < 20:
                continue
            metrics = group_metrics(y_true[mask], y_pred[mask], y_score[mask])
            label = group
            if attribute == "sex":
                label = "Femenino" if group == "F" else "Masculino"
            elif attribute == "wealth_quintile":
                label = f"Quintil {group}"
            elif attribute == "urban_rural":
                label = "Urbano" if group == "URBAN" else "Rural"
            group_frames.append({"group": label, "raw_group": group, **metrics})

        if len(group_frames) < 2:
            continue

        mf = MetricFrame(
            metrics={
                "selection_rate": selection_rate,
                "tpr": true_positive_rate,
                "fpr": false_positive_rate,
                "accuracy": accuracy_score,
            },
            y_true=y_true,
            y_pred=y_pred,
            sensitive_features=sensitive,
        )
        by_group = mf.by_group
        selection_rates = [row["selection_rate"] for row in group_frames if row["selection_rate"] is not None]
        disparity = round(float(max(selection_rates) - min(selection_rates)), 4) if selection_rates else 0.0
        tpr_values = [row["tpr"] for row in group_frames if row["tpr"] is not None]
        tpr_gap = round(float(max(tpr_values) - min(tpr_values)), 4) if len(tpr_values) > 1 else 0.0
        ratio = (
            round(float(min(selection_rates) / max(selection_rates)), 4)
            if selection_rates and max(selection_rates) > 0
            else None
        )
        result = {
            "model_id": model.id,
            "sensitive_attribute": attribute,
            "metric": "demographic_parity_and_equalized_odds",
            "groups": group_frames,
            "max_disparity": disparity,
            "tpr_gap": tpr_gap,
            "ratio": ratio,
            "is_acceptable": disparity <= threshold,
            "threshold": threshold,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "fairlearn_by_group": {
                group: {
                    metric: (None if pd.isna(value) else round(float(value), 4))
                    for metric, value in row.items()
                }
                for group, row in by_group.iterrows()
            },
        }
        results.append(result)

        if persist:
            db.add(
                FairnessReport(
                    model_id=model.id,
                    sensitive_attribute=attribute,
                    metric=result["metric"],
                    results={"groups": group_frames, "fairlearn_by_group": result["fairlearn_by_group"]},
                    disparity=disparity,
                    is_acceptable=result["is_acceptable"],
                    created_by=user_id,
                )
            )
    if persist and results:
        db.commit()
    return results


def summary(db: Session, model_id: int) -> dict[str, Any]:
    """Latest stored fairness results for a model (computed on demand if missing)."""
    reports = db.execute(select(FairnessReport).where(FairnessReport.model_id == model_id)).scalars().all()
    if not reports:
        results = compute_fairness(db, model_id)
        return {
            "model_id": model_id,
            "attributes": results,
            "overall_acceptable": all(item["is_acceptable"] for item in results) if results else True,
            "notes": ["Resultados calculados en esta consulta."],
        }
    attributes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for report in sorted(reports, key=lambda item: item.created_at, reverse=True):
        if report.sensitive_attribute in seen:
            continue
        seen.add(report.sensitive_attribute)
        groups = (report.results or {}).get("groups", [])
        attributes.append(
            {
                "model_id": report.model_id,
                "sensitive_attribute": report.sensitive_attribute,
                "metric": report.metric,
                "groups": groups,
                "max_disparity": report.disparity,
                "ratio": None,
                "is_acceptable": report.is_acceptable,
                "threshold": FAIRNESS_THRESHOLD,
                "generated_at": report.created_at.isoformat() if report.created_at else None,
            }
        )
    return {
        "model_id": model_id,
        "attributes": attributes,
        "overall_acceptable": all(item["is_acceptable"] for item in attributes),
        "notes": [
            "Disparidad de paridad demográfica = diferencia máxima de tasa de selección entre grupos.",
            "Umbral de aceptación: 0,20 (regla de cuatro quintos de referencia).",
        ],
    }


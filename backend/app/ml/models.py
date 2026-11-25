"""Model factories, metrics and spatial cross-validation helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    matthews_corrcoef,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold

ALGORITHM_LABELS = {
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
    "catboost": "CatBoost",
    "spatial_xgboost": "XGBoost + Spatial Regression",
    "cnn_lstm": "CNN-LSTM",
}

ALGORITHM_DESCRIPTIONS = {
    "random_forest": "Ensemble de árboles con bagging, robusto y con importancia nativa.",
    "xgboost": "Gradient boosting regularizado, alto desempeño tabular.",
    "catboost": "Gradient boosting con manejo nativo de categóricas y poca necesidad de ajuste.",
    "spatial_xgboost": "XGBoost aumentado con rezagos espaciales y corrección de residuos SAR/SEM.",
    "cnn_lstm": "Red convolucional + LSTM sobre series territoriales anuales.",
}

DEFAULT_PARAMS: dict[str, dict[str, Any]] = {
    "random_forest": {
        "classification": {"n_estimators": 300, "max_depth": 14, "min_samples_leaf": 6, "max_features": "sqrt"},
        "regression": {"n_estimators": 300, "max_depth": 16, "min_samples_leaf": 4, "max_features": 0.7},
    },
    "xgboost": {
        "classification": {
            "n_estimators": 400,
            "max_depth": 4,
            "learning_rate": 0.06,
            "subsample": 0.9,
            "colsample_bytree": 0.85,
            "reg_lambda": 1.2,
            "min_child_weight": 3,
        },
        "regression": {
            "n_estimators": 400,
            "max_depth": 5,
            "learning_rate": 0.06,
            "subsample": 0.9,
            "colsample_bytree": 0.85,
            "reg_lambda": 1.0,
        },
    },
    "catboost": {
        "classification": {"iterations": 450, "depth": 5, "learning_rate": 0.06, "l2_leaf_reg": 4.0},
        "regression": {"iterations": 450, "depth": 6, "learning_rate": 0.06, "l2_leaf_reg": 3.0},
    },
}


def build_estimator(
    algorithm: str,
    task: str,
    *,
    seed: int = 42,
    params: dict[str, Any] | None = None,
) -> Any:  # noqa: ANN401
    """Instantiate an unfitted estimator for the requested algorithm/task."""
    overrides = params or {}
    base = dict(DEFAULT_PARAMS.get(algorithm, {}).get(task, {}))
    base.update(overrides)

    if algorithm == "random_forest":
        if task == "regression":
            return RandomForestRegressor(random_state=seed, n_jobs=-1, **base)
        return RandomForestClassifier(random_state=seed, n_jobs=-1, **base)

    if algorithm in ("xgboost", "spatial_xgboost"):
        from xgboost import XGBClassifier, XGBRegressor

        if task == "regression":
            return XGBRegressor(random_state=seed, n_jobs=-1, tree_method="hist", **base)
        return XGBClassifier(
            random_state=seed,
            n_jobs=-1,
            tree_method="hist",
            eval_metric="logloss",
            **base,
        )

    if algorithm == "catboost":
        from catboost import CatBoostClassifier, CatBoostRegressor

        if task == "regression":
            return CatBoostRegressor(random_seed=seed, verbose=False, allow_writing_files=False, **base)
        return CatBoostClassifier(
            random_seed=seed,
            verbose=False,
            allow_writing_files=False,
            eval_metric="AUC",
            **base,
        )

    raise ValueError(f"Algoritmo no soportado: {algorithm}")


def predict_scores(estimator: Any, features: pd.DataFrame) -> np.ndarray:  # noqa: ANN401
    """Return probabilities (classification) or predictions (regression)."""
    if hasattr(estimator, "predict_proba"):
        return np.asarray(estimator.predict_proba(features))[:, 1]
    return np.asarray(estimator.predict(features), dtype=float)


def classification_metrics(y_true: np.ndarray, y_score: np.ndarray, threshold: float = 0.5) -> dict[str, Any]:
    """Standard classification metrics with safe handling of single-class folds."""
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score, dtype=float)
    y_pred = (y_score >= threshold).astype(int)
    metrics: dict[str, Any] = {
        "n": int(len(y_true)),
        "positives": int(y_true.sum()),
        "prevalence": round(float(y_true.mean()), 4) if len(y_true) else 0.0,
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
    }
    if len(np.unique(y_true)) > 1:
        metrics["auc"] = round(float(roc_auc_score(y_true, y_score)), 4)
        metrics["average_precision"] = round(float(average_precision_score(y_true, y_score)), 4)
        metrics["brier"] = round(float(brier_score_loss(y_true, np.clip(y_score, 1e-6, 1 - 1e-6))), 4)
        metrics["log_loss"] = round(
            float(log_loss(y_true, np.clip(y_score, 1e-6, 1 - 1e-6), labels=[0, 1])), 4
        )
    else:
        metrics.update({"auc": None, "average_precision": None, "brier": None, "log_loss": None})
    metrics["confusion_matrix"] = confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist()
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    metrics['specificity'] = float(tn / (tn + fp)) if tn + fp else None
    metrics['sensitivity'] = metrics['recall']
    metrics['mcc'] = float(matthews_corrcoef(y_true, y_pred))
    return metrics


def optimal_thresholds(y_true: np.ndarray, y_score: np.ndarray, screening_recall: float = 0.75) -> dict[str, Any]:
    """Operating points: max-F1 threshold and a screening threshold with target recall."""
    from sklearn.metrics import precision_recall_curve

    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score, dtype=float)
    if len(np.unique(y_true)) < 2:
        return {"threshold": 0.5, "f1": None, "precision": None, "recall": None, "screening_threshold": 0.5}
    precision, recall, thresholds = precision_recall_curve(y_true, y_score)
    f1_scores = 2 * precision * recall / np.clip(precision + recall, 1e-9, None)
    best_index = int(np.argmax(f1_scores[:-1])) if len(thresholds) else 0
    best = {
        "threshold": round(float(thresholds[best_index]), 4) if len(thresholds) else 0.5,
        "f1": round(float(f1_scores[best_index]), 4),
        "precision": round(float(precision[best_index]), 4),
        "recall": round(float(recall[best_index]), 4),
    }
    candidates = np.where(recall[:-1] >= screening_recall)[0]
    if len(candidates):
        screening = float(thresholds[candidates.max()])
    else:
        screening = float(thresholds[0]) if len(thresholds) else 0.5
    best["screening_threshold"] = round(screening, 4)
    return best


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    metrics = {
        "n": int(len(y_true)),
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        # R² is unstable with very small group sizes; only reported from n>=8.
        "r2": round(float(r2_score(y_true, y_pred)), 4) if len(y_true) >= 8 else None,
    }
    if len(y_true) > 1 and np.std(y_true) > 0 and np.std(y_pred) > 0:
        metrics["pearson"] = round(float(np.corrcoef(y_true, y_pred)[0, 1]), 4)
    return metrics


def spatial_group_splits(
    groups: pd.Series,
    strategy: str,
    n_splits: int = 5,
    seed: int = 42,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """GroupKFold / leave-one-region-out splits by region."""
    groups = pd.Series(groups).reset_index(drop=True)
    unique = sorted(groups.dropna().unique())
    if strategy == "leave_one_region_out" or len(unique) <= 2:
        splits = []
        for region in unique:
            test_mask = groups == region
            if test_mask.sum() == 0 or (~test_mask).sum() == 0:
                continue
            splits.append((np.where(~test_mask)[0], np.where(test_mask)[0]))
        return splits
    kfold = GroupKFold(n_splits=min(n_splits, len(unique)))
    return list(kfold.split(np.zeros(len(groups)), groups=groups))


def out_of_fold_scores(
    estimator_factory: Callable[[], Any],
    features: pd.DataFrame,
    target: pd.Series,
    groups: pd.Series,
    splits: list[tuple[np.ndarray, np.ndarray]],
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Fit each fold and return out-of-fold scores plus fold metadata."""
    scores = np.full(len(target), np.nan)
    fold_metrics: list[dict[str, Any]] = []
    for index, (train_idx, test_idx) in enumerate(splits, start=1):
        estimator = estimator_factory()
        estimator.fit(features.iloc[train_idx], target.iloc[train_idx])
        fold_scores = predict_scores(estimator, features.iloc[test_idx])
        scores[test_idx] = fold_scores
        held_regions = sorted(pd.Series(groups.iloc[test_idx]).unique().tolist())
        fold_metrics.append(
            {
                "fold": index,
                "train_n": int(len(train_idx)),
                "test_n": int(len(test_idx)),
                "held_out_regions": held_regions,
            }
        )
    return scores, fold_metrics


def per_region_metrics(
    frame: pd.DataFrame,
    y_true: np.ndarray,
    y_score: np.ndarray,
    task: str,
) -> dict[str, Any]:
    """Metrics per region (spatial transferability)."""
    result: dict[str, Any] = {}
    for region in sorted(frame["region"].dropna().unique()):
        mask = (frame["region"] == region).to_numpy()
        if mask.sum() < 30:
            continue
        subset_true = y_true[mask]
        subset_score = y_score[mask]
        if np.isnan(subset_score).any():
            continue
        metrics = (
            classification_metrics(subset_true, subset_score)
            if task == "classification"
            else regression_metrics(subset_true, subset_score)
        )
        result[str(region)] = metrics
    return result


def per_group_metrics(
    frame: pd.DataFrame,
    y_true: np.ndarray,
    y_score: np.ndarray,
    task: str,
    attributes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Metrics per sensitive subgroup (fairness-oriented view)."""
    from app.ml.features import SENSITIVE_ATTRIBUTES

    attributes = attributes or SENSITIVE_ATTRIBUTES
    result: dict[str, Any] = {}
    for column, label in attributes.items():
        if column not in frame.columns:
            continue
        groups: dict[str, Any] = {}
        for value in sorted(frame[column].dropna().astype(str).unique()):
            mask = frame[column].astype(str) == value
            if mask.sum() < 25:
                continue
            subset_true = y_true[mask.to_numpy()]
            subset_score = y_score[mask.to_numpy()]
            if np.isnan(subset_score).any():
                continue
            metrics = (
                classification_metrics(subset_true, subset_score)
                if task == "classification"
                else regression_metrics(subset_true, subset_score)
            )
            groups[value] = metrics
        if groups:
            result[column] = {"label": label, "groups": groups}
    return result


def top_feature_importance(estimator: Any, feature_names: list[str], top_n: int = 15) -> dict[str, float]:  # noqa: ANN401
    """Native or permutation-free feature importance, sorted."""
    values: np.ndarray | None = None
    if hasattr(estimator, "feature_importances_"):
        values = np.asarray(estimator.feature_importances_, dtype=float)
    elif hasattr(estimator, "get_feature_importance"):
        values = np.asarray(estimator.get_feature_importance(), dtype=float)
    if values is None or len(values) != len(feature_names):
        return {}
    total = values.sum() or 1.0
    ranked = sorted(zip(feature_names, values / total), key=lambda item: item[1], reverse=True)
    return {name: round(float(value), 6) for name, value in ranked[:top_n]}

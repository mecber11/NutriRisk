"""SHAP explainability: global, local and territory-level explanations."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.ml.features import FEATURE_LABELS

MAX_EXPLAIN_ROWS = 400


def _sigmoid(value: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(value, dtype=float)))


def to_probability_space(base_value: float, values: np.ndarray) -> tuple[float, np.ndarray]:
    """Express margin-space SHAP values as additive probability-point contributions.

    XGBoost and CatBoost return SHAP values in log-odds space, while Random Forest
    already returns them in probability space. For the tree boosters we apply the
    logistic transform sequentially (largest absolute contribution first), which
    yields contributions in percentage points that still add up exactly to
    ``prediction - base_probability``.
    """
    array = np.asarray(values, dtype=float)
    if 0.0 <= base_value <= 1.0:
        return float(base_value), array
    base_probability = float(_sigmoid(base_value))
    if array.ndim == 1:
        order = np.argsort(-np.abs(array))
        cumulative = base_value + np.cumsum(array[order])
        probabilities = _sigmoid(cumulative)
        impacts = np.diff(np.concatenate([[base_probability], probabilities]))
        result = np.zeros_like(array)
        result[order] = impacts
        return base_probability, result
    result = np.empty_like(array)
    for row in range(array.shape[0]):
        _, transformed = to_probability_space(base_value, array[row])
        result[row] = transformed
    return base_probability, result


def _shap_values(explainer: Any, data: pd.DataFrame) -> np.ndarray:  # noqa: ANN401
    values = explainer.shap_values(data)
    array = np.asarray(values)
    if array.ndim == 3:  # (n, features, classes)
        array = array[:, :, 1]
    return np.asarray(array, dtype=float)


def build_explainer(model: Any, background: pd.DataFrame) -> Any:  # noqa: ANN401
    """Create a SHAP explainer suited to the estimator type."""
    import shap

    try:
        return shap.TreeExplainer(model)
    except Exception:  # noqa: BLE001
        background_sample = background.sample(
            min(len(background), 120), random_state=42
        ) if len(background) > 120 else background
        return shap.Explainer(model.predict, background_sample)


def base_value(model: Any, explainer: Any) -> float:  # noqa: ANN401
    try:
        expected = np.asarray(explainer.expected_value, dtype=float).ravel()
        return float(expected[-1]) if expected.size else 0.0
    except Exception:  # noqa: BLE001
        if hasattr(model, "predict_proba"):
            return float(np.mean(model.predict_proba(np.zeros((1, 1)))[:, 1]))
        return 0.0


def global_explanation(
    model: Any,
    features: pd.DataFrame,
    *,
    top_n: int = 15,
    model_id: int = 0,
    model_name: str = "",
    algorithm: str = "",
) -> dict[str, Any]:
    """Global mean(|SHAP|) importance with feature shares."""
    sample = features.sample(min(len(features), MAX_EXPLAIN_ROWS), random_state=42)
    explainer = build_explainer(model, features)
    values = _shap_values(explainer, sample)
    base_raw = float(np.atleast_1d(explainer.expected_value)[-1]) if hasattr(explainer, "expected_value") else 0.0
    base_value, values = to_probability_space(base_raw, values)
    mean_abs = np.abs(values).mean(axis=0)
    total = float(mean_abs.sum()) or 1.0
    direction = np.sign(values).mean(axis=0)
    order = np.argsort(mean_abs)[::-1][:top_n]
    items = [
        {
            "feature": sample.columns[index],
            "label": FEATURE_LABELS.get(sample.columns[index], sample.columns[index]),
            "mean_abs_shap": round(float(mean_abs[index]), 5),
            "share": round(float(mean_abs[index] / total), 4),
            "direction": "positive" if direction[index] >= 0 else "negative",
        }
        for index in order
    ]
    beeswarm = []
    for index in order[:6]:
        for value, shap_value in zip(sample.iloc[:, index].to_numpy()[:120], values[:, index][:120]):
            beeswarm.append(
                {
                    "feature": str(sample.columns[index]),
                    "value": round(float(value), 4),
                    "shap": round(float(shap_value), 5),
                }
            )
    return {
        "model_id": model_id,
        "model_name": model_name,
        "algorithm": algorithm,
        "base_value": round(float(base_value), 5),
        "n_samples": int(len(sample)),
        "features": items,
        "beeswarm": beeswarm,
    }


def local_explanation(
    model: Any,
    row: pd.DataFrame,
    *,
    top_n: int = 8,
) -> tuple[float, float, list[dict[str, Any]]]:
    """Return (prediction, base_value, top contributions) for one child."""
    estimator = model
    explainer = build_explainer(model, row)
    values = _shap_values(explainer, row)[0]
    base_raw = float(np.atleast_1d(getattr(explainer, "expected_value", 0.0))[-1])
    base, values = to_probability_space(base_raw, values)
    if hasattr(estimator, "predict_proba"):
        prediction = float(estimator.predict_proba(row)[0, 1])
    else:
        prediction = float(np.asarray(estimator.predict(row))[0])
    contributions = [
        {
            "feature": column,
            "label": FEATURE_LABELS.get(column, column),
            "value": round(float(row.iloc[0][column]), 4),
            "contribution": round(float(value), 5),
            "direction": "positive" if value > 0 else "negative",
        }
        for column, value in zip(row.columns, values)
    ]
    contributions.sort(key=lambda item: abs(item["contribution"]), reverse=True)
    return prediction, base, contributions[:top_n]


def territory_explanation(
    model: Any,
    features: pd.DataFrame,
    territory_codes: pd.Series,
    *,
    top_n: int = 6,
) -> dict[str, list[dict[str, Any]]]:
    """Aggregate mean |SHAP| per territory for the risk map tooltips."""
    sample_mask = np.random.default_rng(42).random(len(features)) < 0.5
    sample = features.loc[sample_mask]
    codes = territory_codes.loc[sample_mask]
    explainer = build_explainer(model, features)
    values = _shap_values(explainer, sample)
    base_raw = float(np.atleast_1d(explainer.expected_value)[-1]) if hasattr(explainer, "expected_value") else 0.0
    _, values = to_probability_space(base_raw, values)
    result: dict[str, list[dict[str, Any]]] = {}
    for code in sorted(codes.unique()):
        mask = (codes == code).to_numpy()
        if mask.sum() < 5:
            continue
        mean_abs = np.abs(values[mask]).mean(axis=0)
        order = np.argsort(mean_abs)[::-1][:top_n]
        result[str(code)] = [
            {
                "feature": sample.columns[index],
                "label": FEATURE_LABELS.get(sample.columns[index], sample.columns[index]),
                "mean_abs_shap": round(float(mean_abs[index]), 5),
            }
            for index in order
        ]
    return result


def dependence_points(
    model: Any,
    features: pd.DataFrame,
    feature: str,
    *,
    max_points: int = 300,
) -> list[dict[str, Any]]:
    """SHAP dependence plot data for one feature."""
    sample = features.sample(min(len(features), max_points), random_state=42)
    explainer = build_explainer(model, features)
    values = _shap_values(explainer, sample)
    base_raw = float(np.atleast_1d(explainer.expected_value)[-1]) if hasattr(explainer, "expected_value") else 0.0
    _, values = to_probability_space(base_raw, values)
    if feature not in sample.columns:
        raise KeyError(f"Variable no disponible: {feature}")
    index = list(sample.columns).index(feature)
    return [
        {"value": round(float(value), 4), "shap": round(float(shap_value), 5), "group": None}
        for value, shap_value in zip(sample[feature].to_numpy(), values[:, index])
    ]


def narrative(
    prediction: float,
    *,
    child_code: str,
    contributions: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
) -> str:
    """Natural-language interpretation of a local explanation (Spanish)."""
    positives = [item for item in contributions if item["contribution"] > 0][:3]
    negatives = [item for item in contributions if item["contribution"] < 0][:3]
    risk_pct = prediction * 100
    band = "alto" if prediction >= 0.6 else ("medio" if prediction >= 0.35 else "bajo")
    parts = [f"El niño {child_code} presenta un riesgo predicho de desnutrición {band} ({risk_pct:.1f}%)."]
    if positives:
        listed = ", ".join(f"{item['label']} ({item['contribution']:+.3f})" for item in positives)
        parts.append(f"Los factores que más incrementan el riesgo son: {listed}.")
    if negatives:
        listed = ", ".join(f"{item['label']} ({item['contribution']:+.3f})" for item in negatives)
        parts.append(f"Los factores protectores más relevantes son: {listed}.")
    if context:
        if context.get("territory"):
            parts.append(f"Territorio: {context['territory']} ({context.get('region', 'sin región')}).")
        if context.get("intervention"):
            parts.append(context["intervention"])
    parts.append(
        "Interpretación basada en valores SHAP del modelo activo; no constituye diagnóstico clínico."
    )
    return " ".join(parts)


def intervention_hint(contributions: list[dict[str, Any]]) -> str:
    """Map the dominant driver to a programmatic recommendation."""
    if not contributions:
        return ""
    top = contributions[0]["feature"]
    hints = {
        "water_improved": "Priorizar acceso a agua segura y tratamiento intradomiciliario.",
        "sanitation_improved": "Ampliar saneamiento mejorado y eliminación segura de excretas.",
        "food_insecurity_score": "Activar transferencias alimentarias y consejería nutricional.",
        "territory_food_insecurity": "Reforzar la seguridad alimentaria del territorio.",
        "minimum_diet_diversity": "Promover diversidad dietética y alimentación complementaria.",
        "maternal_education_years": "Vincular al hogar a programas de educación materna.",
        "wealth_quintile": "Incluir el hogar en esquemas de protección social focalizados.",
        "vaccination_complete": "Completar esquema de vacunación y controles de crecimiento.",
        "diarrhea_14d": "Manejo integrado de diarrea y suplementación con zinc.",
        "urban": "Ajustar la estrategia al contexto urbano/rural del hogar.",
    }
    return hints.get(top, "Revisar el determinante principal con el equipo territorial.")


"""Spatial statistics: weights, Moran's I, SAR/SEM (PySAL), GWR and residual calibration."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.ml.models import classification_metrics


def build_neighbor_map(db) -> dict[str, list[str]]:  # noqa: ANN001
    """Load territory adjacency from the database."""
    from sqlalchemy import select

    from app.models.data import Territory

    rows = db.execute(select(Territory.code, Territory.neighbor_codes)).all()
    return {code: list(neighbors or []) for code, neighbors in rows}


def build_weights(neighbor_map: dict[str, list[str]]) -> tuple[Any, list[str]]:  # noqa: ANN401
    """Build a row-standardised PySAL W from an adjacency map."""
    from libpysal.weights import W

    codes = sorted(code for code, neighbors in neighbor_map.items() if neighbors)
    neighbors = {code: [n for n in neighbor_map[code] if n in neighbor_map] for code in codes}
    weights = W(neighbors, silence_warnings=True, ids=codes)
    weights.transform = "r"
    return weights, codes


def morans_i(values: np.ndarray, weights: Any, permutations: int = 999) -> dict[str, Any]:  # noqa: ANN401
    """Global Moran's I with a conditional-permutation pseudo p-value."""
    from esda.moran import Moran

    clean = np.nan_to_num(np.asarray(values, dtype=float), nan=0.0)
    if len(clean) < 5 or np.std(clean) == 0:
        return {"available": False, "reason": "Insuficientes unidades o varianza nula"}
    moran = Moran(clean, weights, permutations=permutations)
    p_value = round(float(moran.p_sim), 4) if moran.p_sim is not None else None
    if p_value is not None and p_value > 0.05:
        interpretation = "sin evidencia de autocorrelación espacial significativa en los residuos"
    elif moran.I > moran.EI:
        interpretation = "autocorrelación espacial positiva (clústeres de riesgo)"
    else:
        interpretation = "autocorrelación espacial negativa (patrón alternante)"
    return {
        "available": True,
        "i": round(float(moran.I), 4),
        "expected_i": round(float(moran.EI), 4),
        "z_score": round(float(moran.z_sim), 3) if moran.z_sim is not None else None,
        "p_value": p_value,
        "interpretation": interpretation,
        "units": int(len(clean)),
    }


def territory_frame(frame: pd.DataFrame, residual: np.ndarray) -> pd.DataFrame:
    """Aggregate child-level rows to territory level for area-level models."""
    data = frame.copy()
    data["residual"] = residual
    aggregated = (
        data.groupby("territory_code")
        .agg(
            territory_name=("territory_name", "first"),
            region=("region", "first"),
            n=("child_id", "size"),
            stunting_rate=("stunting", "mean"),
            mean_residual=("residual", "mean"),
            wealth=("wealth_quintile", "mean"),
            water_coverage=("water_coverage", "first"),
            sanitation_coverage=("sanitation_coverage", "first"),
            food_insecurity=("territory_food_insecurity", "first"),
            ndvi=("ndvi", "first"),
            altitude=("altitude_m", "first"),
            population_u5=("population_u5", "first"),
            latitude=("latitude", "first"),
            longitude=("longitude", "first"),
        )
        .reset_index()
    )
    return aggregated


def _pysal_matrix(values: np.ndarray) -> np.ndarray:
    return np.asarray(values, dtype=float).reshape(-1, 1)


def spatial_regression(aggregated: pd.DataFrame, neighbor_map: dict[str, list[str]]) -> dict[str, Any]:
    """Fit OLS, SAR (lag) and SEM (error) models plus a local GWR on territory rates."""
    try:
        from spreg import ML_Error, ML_Lag, OLS
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"PySAL no disponible: {exc}"}

    weights, codes = build_weights(neighbor_map)
    subset = aggregated.set_index("territory_code").loc[[c for c in codes if c in aggregated["territory_code"].values]]
    if len(subset) < 10:
        return {"available": False, "reason": "Se requieren al menos 10 territorios con vecinos"}

    y = _pysal_matrix(subset["stunting_rate"].to_numpy() * 100.0)
    predictors = np.column_stack(
        [
            subset["wealth"].to_numpy(dtype=float),
            subset["water_coverage"].to_numpy(dtype=float),
            subset["sanitation_coverage"].to_numpy(dtype=float),
            subset["food_insecurity"].to_numpy(dtype=float),
            subset["ndvi"].to_numpy(dtype=float),
            subset["altitude"].to_numpy(dtype=float) / 1000.0,
        ]
    )
    x = np.column_stack([np.ones(len(subset)), predictors])
    names = ["const", "wealth", "water_coverage", "sanitation_coverage", "food_insecurity", "ndvi", "altitude_km"]
    result: dict[str, Any] = {"available": True, "n": int(len(subset)), "names": names}

    try:
        ols = OLS(y, x, w=weights, spat_diag=True, moran=True, name_y="stunting_rate")
        result["ols"] = {
            "r2": round(float(ols.r2), 4),
            "coefficients": {name: round(float(value), 4) for name, value in zip(names, ols.betas.flatten())},
            "moran_residuals": {
                "i": round(float(ols.moran_res[0]), 4),
                "p_value": round(float(ols.moran_res[2]), 4),
            }
            if getattr(ols, "moran_res", None) is not None
            else None,
        }
    except Exception as exc:  # noqa: BLE001
        result["ols"] = {"error": str(exc)}

    try:
        sar = ML_Lag(y, x, w=weights, name_y="stunting_rate", name_x=names)
        result["sar"] = {
            "rho": round(float(sar.rho), 4),
            "pseudo_r2": round(float(sar.pr2), 4),
            "log_likelihood": round(float(sar.logll), 2),
            "coefficients": {name: round(float(value), 4) for name, value in zip(names, sar.betas.flatten())},
        }
    except Exception as exc:  # noqa: BLE001
        result["sar"] = {"error": str(exc)}

    try:
        sem = ML_Error(y, x, w=weights, name_y="stunting_rate", name_x=names)
        result["sem"] = {
            "lambda": round(float(sem.lam), 4),
            "pseudo_r2": round(float(sem.pr2), 4),
            "log_likelihood": round(float(sem.logll), 2),
            "coefficients": {name: round(float(value), 4) for name, value in zip(names, sem.betas.flatten())},
        }
    except Exception as exc:  # noqa: BLE001
        result["sem"] = {"error": str(exc)}

    result["gwr"] = geographically_weighted_regression(
        subset.reset_index(), names, predictors, subset["stunting_rate"].to_numpy() * 100.0
    )
    return result


def _haversine_km(lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    radius = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return 2 * radius * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def geographically_weighted_regression(
    territory_rows: pd.DataFrame,
    names: list[str],
    predictors: np.ndarray,
    y: np.ndarray,
) -> dict[str, Any]:
    """Gaussian-kernel GWR with local coefficients (implemented in NumPy)."""
    try:
        lat = territory_rows["latitude"].to_numpy(dtype=float)
        lon = territory_rows["longitude"].to_numpy(dtype=float)
    except KeyError:
        return {"available": False, "reason": "Sin coordenadas de territorio"}
    n = len(y)
    if n < 10:
        return {"available": False, "reason": "Insuficientes territorios"}
    distances = _haversine_km(lat[:, None], lon[:, None], lat[None, :], lon[None, :])
    nearest = np.sort(np.where(distances > 0, distances, np.inf), axis=1)[:, 0]
    bandwidth = float(np.median(nearest) * 2.2)
    x = np.column_stack([np.ones(n), predictors])
    betas = np.zeros((n, x.shape[1]))
    local_r2 = np.zeros(n)
    for index in range(n):
        weights = np.exp(-0.5 * (distances[index] / max(bandwidth, 1e-6)) ** 2)
        root = np.sqrt(weights)
        design = x * root[:, None]
        response = y * root
        try:
            beta, *_ = np.linalg.lstsq(design, response, rcond=None)
        except np.linalg.LinAlgError:
            continue
        betas[index] = beta
        fitted = x @ beta
        residual = y - fitted
        weighted_mean = np.sum(weights * y) / max(np.sum(weights), 1e-9)
        total = np.sum(weights * (y - weighted_mean) ** 2)
        local_r2[index] = 1 - (np.sum(weights * residual**2) / total) if total > 0 else 0.0

    coefficient_summary = {}
    for position, name in enumerate(names):
        values = betas[:, position]
        coefficient_summary[name] = {
            "mean": round(float(values.mean()), 4),
            "min": round(float(values.min()), 4),
            "max": round(float(values.max()), 4),
            "sd": round(float(values.std()), 4),
        }
    return {
        "available": True,
        "bandwidth_km": round(bandwidth, 1),
        "n": int(n),
        "mean_local_r2": round(float(np.clip(local_r2, 0, 1).mean()), 4),
        "coefficients": coefficient_summary,
        "note": "GWR con kernel gaussiano y ancho de banda adaptado al vecino más cercano.",
    }


def spatial_lag_correction(
    residuals_by_territory: dict[str, float],
    neighbor_map: dict[str, list[str]],
) -> dict[str, Any]:
    """One-step SAR calibration of area-level residuals.

    Estimates ``r = alpha + rho * W r + e`` by OLS and returns the spatially
    structured component ``rho * (W r)`` as a per-territory probability offset.
    """
    codes = [code for code in residuals_by_territory if neighbor_map.get(code)]
    if len(codes) < 5:
        return {"available": False, "offsets": {}, "rho": 0.0, "reason": "Insuficientes territorios"}
    index = {code: position for position, code in enumerate(codes)}
    residual = np.array([residuals_by_territory[code] for code in codes], dtype=float)
    lagged = np.zeros_like(residual)
    for code in codes:
        neighbors = [neighbor for neighbor in neighbor_map[code] if neighbor in index]
        if neighbors:
            lagged[index[code]] = float(np.mean([residual[index[neighbor]] for neighbor in neighbors]))
    design = np.column_stack([np.ones(len(codes)), lagged])
    try:
        beta, *_ = np.linalg.lstsq(design, residual, rcond=None)
        rho = float(beta[1])
    except np.linalg.LinAlgError:
        rho = 0.0
    offsets = {code: float(rho * lagged[index[code]]) for code in codes}
    return {
        "available": True,
        "rho": round(rho, 4),
        "offsets": offsets,
        "note": "Corrección espacial de una etapa: rho * rezago espacial del residuo medio.",
    }


def evaluate_corrected(
    frame: pd.DataFrame,
    y_true: np.ndarray,
    scores: np.ndarray,
    corrections: dict[str, Any],
) -> dict[str, Any]:
    """Compare metrics before/after the spatial residual calibration."""
    if not corrections.get("available"):
        return {"available": False}
    offsets = corrections["offsets"]
    adjusted = np.clip(
        scores + np.array([offsets.get(code, 0.0) for code in frame["territory_code"]], dtype=float), 1e-4, 1 - 1e-4
    )
    return {
        "available": True,
        "rho": corrections["rho"],
        "before": classification_metrics(y_true, scores),
        "after": classification_metrics(y_true, adjusted),
        "delta_auc": round(
            float(
                (classification_metrics(y_true, adjusted).get("auc") or 0)
                - (classification_metrics(y_true, scores).get("auc") or 0)
            ),
            4,
        ),
    }


def spatial_summary(aggregated: pd.DataFrame, diagnostics: dict[str, Any]) -> list[str]:
    """Human-readable sentences for reports and the agent."""
    lines: list[str] = []
    moran = diagnostics.get("moran", {})
    if moran.get("available"):
        lines.append(
            f"Moran's I de residuos = {moran['i']} (p={moran['p_value']}), lo que indica {moran['interpretation']}."
        )
    sar = diagnostics.get("sar", {})
    if sar and "rho" in sar:
        lines.append(f"Modelo SAR: rho = {sar['rho']} (pseudo R² = {sar['pseudo_r2']}).")
    sem = diagnostics.get("sem", {})
    if sem and "lambda" in sem:
        lines.append(f"Modelo SEM: lambda = {sem['lambda']} (pseudo R² = {sem['pseudo_r2']}).")
    gwr = diagnostics.get("gwr", {})
    if gwr.get("available"):
        lines.append(
            f"GWR: R² local medio = {gwr['mean_local_r2']} con ancho de banda {gwr['bandwidth_km']} km."
        )
    return lines


def safe_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return float(_haversine_km(np.array([lat1]), np.array([lon1]), np.array([lat2]), np.array([lon2]))[0])



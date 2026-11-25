"""Dashboard aggregations: KPIs, trends, comparisons, risk distribution and ranking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.features import build_analytical_frame
from app.models.data import Child, Territory
from app.models.ml import MLModel, Prediction, TerritoryRisk

RISK_LABELS = {"LOW": "Bajo", "MODERATE": "Moderado", "HIGH": "Alto", "CRITICAL": "Crítico"}
AGE_GROUPS = ["0-5 m", "6-11 m", "12-23 m", "24-35 m", "36-59 m"]


def risk_band(score: float) -> str:
    if score < 0.15:
        return "LOW"
    if score < 0.30:
        return "MODERATE"
    if score < 0.50:
        return "HIGH"
    return "CRITICAL"


def active_model(db: Session) -> MLModel | None:
    return db.scalar(select(MLModel).where(MLModel.is_active.is_(True)))


def load_frame(db: Session, model: MLModel | None = None) -> pd.DataFrame:
    """Analytical frame enriched with the active model's predicted risk."""
    frame = build_analytical_frame(db)
    if frame.empty:
        return frame
    model = model or active_model(db)
    if model is not None:
        rows = db.execute(
            select(Prediction.child_id, Prediction.score, Prediction.risk_band).where(Prediction.model_id == model.id)
        ).all()
        if rows:
            predictions = pd.DataFrame(rows, columns=["child_id", "risk", "risk_band"])
            frame = frame.merge(predictions, on="child_id", how="left")
            frame["risk"] = frame["risk"].fillna(frame["stunting"].astype(float) * 0.35)
        else:
            frame["risk"] = frame["stunting"].astype(float) * 0.35
    else:
        frame["risk"] = frame["stunting"].astype(float) * 0.35
    frame["risk_band"] = frame["risk"].map(risk_band)
    return frame


def apply_filters(
    frame: pd.DataFrame,
    *,
    year: int | None = None,
    region: str | None = None,
    sex: str | None = None,
    age_group: str | None = None,
    territory_id: int | None = None,
    wealth_quintile: int | None = None,
    urban_rural: str | None = None,
) -> pd.DataFrame:
    data = frame
    if year:
        data = data[data["period_year"] == year]
    if region:
        data = data[data["region"] == region]
    if sex:
        data = data[data["sex"] == sex]
    if age_group:
        data = data[data["age_group"] == age_group]
    if territory_id:
        data = data[data["territory_id"] == territory_id]
    if wealth_quintile:
        data = data[data["wealth_quintile"] == wealth_quintile]
    if urban_rural:
        data = data[data["urban_rural"] == urban_rural]
    return data


def _pct(value: float | None) -> float:
    return round(float(value or 0) * 100, 2)


def kpis(frame: pd.DataFrame, previous: pd.DataFrame | None = None, model: MLModel | None = None) -> list[dict[str, Any]]:
    """KPI cards with year-over-year deltas."""
    total = len(frame)
    stunting = float(frame["stunting"].mean()) if total else 0.0
    wasting = float(frame["wasting"].mean()) if total else 0.0
    underweight = float(frame["underweight"].mean()) if total else 0.0
    severe = float(frame["severe_stunting"].mean()) if "severe_stunting" in frame.columns and total else 0.0
    mean_risk = float(frame["risk"].mean()) if total else 0.0
    high_risk_share = float((frame["risk"] >= 0.5).mean()) if total else 0.0

    prev_stunting = float(previous["stunting"].mean()) if previous is not None and len(previous) else None
    prev_risk = float(previous["risk"].mean()) if previous is not None and len(previous) else None

    def delta(current: float, before: float | None) -> float | None:
        if before is None or before == 0:
            return None
        return round((current - before) / before * 100, 2)

    territory_risk = (
        frame.groupby("territory_id")["risk"].mean().sort_values(ascending=False) if total else pd.Series(dtype=float)
    )
    critical_territories = int((territory_risk >= 0.5).sum()) if len(territory_risk) else 0
    population_at_risk = 0
    if total:
        territory_rows = frame.groupby("territory_id").agg(
            risk=("risk", "mean"), population_u5=("population_u5", "first")
        )
        population_at_risk = int(round((territory_rows["risk"] * territory_rows["population_u5"]).sum()))

    auc = (model.metrics or {}).get("auc") if model else None
    return [
        {
            "key": "children_screened",
            "label": "Niños evaluados",
            "value": float(total),
            "unit": "",
            "delta": None,
            "trend": "flat",
            "description": "Registros con antropometría válida en el filtro actual.",
            "severity": "neutral",
        },
        {
            "key": "stunting_prevalence",
            "label": "Prevalencia de retraso en crecimiento",
            "value": _pct(stunting),
            "unit": "%",
            "delta": delta(stunting, prev_stunting),
            "trend": "down" if prev_stunting is not None and stunting < prev_stunting else "up",
            "description": "HAZ < -2 DE (OMS 2006).",
            "severity": "critical" if stunting >= 0.3 else ("warning" if stunting >= 0.2 else "ok"),
        },
        {
            "key": "wasting_prevalence",
            "label": "Prevalencia de emaciación",
            "value": _pct(wasting),
            "unit": "%",
            "delta": None,
            "trend": "flat",
            "description": "WHZ < -2 DE (OMS 2006).",
            "severity": "critical" if wasting >= 0.15 else ("warning" if wasting >= 0.08 else "ok"),
        },
        {
            "key": "underweight_prevalence",
            "label": "Prevalencia de bajo peso",
            "value": _pct(underweight),
            "unit": "%",
            "delta": None,
            "trend": "flat",
            "description": "WAZ < -2 DE (OMS 2006).",
            "severity": "warning" if underweight >= 0.12 else "ok",
        },
        {
            "key": "mean_risk",
            "label": "Riesgo medio predicho",
            "value": _pct(mean_risk),
            "unit": "%",
            "delta": delta(mean_risk, prev_risk),
            "trend": "down" if prev_risk is not None and mean_risk < prev_risk else "up",
            "description": "Probabilidad media del modelo activo.",
            "severity": "warning" if mean_risk >= 0.3 else "ok",
        },
        {
            "key": "high_risk_share",
            "label": "Niños en riesgo alto o crítico",
            "value": _pct(high_risk_share),
            "unit": "%",
            "delta": None,
            "trend": "flat",
            "description": "Proporción con riesgo predicho ≥ 50 %.",
            "severity": "critical" if high_risk_share >= 0.15 else "warning",
        },
        {
            "key": "priority_territories",
            "label": "Territorios críticos",
            "value": float(critical_territories),
            "unit": "",
            "delta": None,
            "trend": "flat",
            "description": "Territorios con riesgo medio ≥ 50 %.",
            "severity": "critical" if critical_territories > 0 else "ok",
        },
        {
            "key": "population_at_risk",
            "label": "Población menor de 5 años en riesgo",
            "value": float(population_at_risk),
            "unit": "",
            "delta": None,
            "trend": "flat",
            "description": "WorldPop sintético × riesgo medio territorial.",
            "severity": "warning",
        },
        {
            "key": "model_auc",
            "label": "AUC del modelo activo",
            "value": round(float(auc) * 100, 2) if auc is not None else 0.0,
            "unit": "%",
            "delta": None,
            "trend": "flat",
            "description": "Validación espacial (GroupKFold por región).",
            "severity": "ok" if (auc or 0) >= 0.75 else "warning",
        },
        {
            "key": "severe_stunting",
            "label": "Retraso severo",
            "value": _pct(severe),
            "unit": "%",
            "delta": None,
            "trend": "flat",
            "description": "HAZ < -3 DE.",
            "severity": "critical" if severe >= 0.05 else "ok",
        },
    ]


def trend(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    grouped = frame.groupby("period_year").agg(
        stunting=("stunting", "mean"),
        wasting=("wasting", "mean"),
        underweight=("underweight", "mean"),
        mean_risk=("risk", "mean"),
        n=("child_id", "size"),
    )
    grouped = grouped.sort_index()
    series = []
    for year, row in grouped.iterrows():
        series.append(
            {
                "period": str(int(year)),
                "stunting": _pct(row["stunting"]),
                "wasting": _pct(row["wasting"]),
                "underweight": _pct(row["underweight"]),
                "mean_risk": _pct(row["mean_risk"]),
                "population_at_risk": int(row["n"]),
            }
        )
    return series


def comparison(frame: pd.DataFrame, dimension: str) -> list[dict[str, Any]]:
    """Compare prevalence/risk across a dimension."""
    columns = {
        "region": ("region", None),
        "sex": ("sex", None),
        "age_group": ("age_group", None),
        "wealth_quintile": ("wealth_quintile", None),
        "urban_rural": ("urban_rural", None),
    }
    if dimension not in columns or frame.empty:
        return []
    column = columns[dimension][0]
    grouped = frame.groupby(column).agg(
        stunting=("stunting", "mean"),
        wasting=("wasting", "mean"),
        underweight=("underweight", "mean"),
        mean_risk=("risk", "mean"),
        n=("child_id", "size"),
    )
    rows = []
    for key, row in grouped.sort_values("stunting", ascending=False).iterrows():
        label = str(key)
        if dimension == "wealth_quintile":
            label = f"Quintil {int(key)}"
        elif dimension == "sex":
            label = "Femenino" if key == "F" else "Masculino"
        elif dimension == "urban_rural":
            label = "Urbano" if key == "URBAN" else "Rural"
        rows.append(
            {
                "key": str(key),
                "label": label,
                "stunting": _pct(row["stunting"]),
                "wasting": _pct(row["wasting"]),
                "underweight": _pct(row["underweight"]),
                "mean_risk": _pct(row["mean_risk"]),
                "n": int(row["n"]),
            }
        )
    return rows


def risk_distribution(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    totals = len(frame)
    territory_population = frame.groupby("territory_id")["population_u5"].first()
    population_map = {
        band: float(
            (frame[frame["risk_band"] == band].groupby("territory_id")["population_u5"].first().sum())
        )
        for band in RISK_LABELS
    }
    rows = []
    for band, label in RISK_LABELS.items():
        subset = frame[frame["risk_band"] == band]
        rows.append(
            {
                "band": band,
                "label": label,
                "count": int(len(subset)),
                "population": int(population_map.get(band, 0)),
                "share": round(len(subset) / totals * 100, 2) if totals else 0.0,
            }
        )
    _ = territory_population
    return rows


def top_territories(db: Session, year: int | None, limit: int = 8) -> list[dict[str, Any]]:
    model = active_model(db)
    if model is None:
        return []
    stmt = (
        select(TerritoryRisk, Territory)
        .join(Territory, TerritoryRisk.territory_id == Territory.id)
        .where(TerritoryRisk.model_id == model.id)
        .order_by(TerritoryRisk.period_year.desc(), TerritoryRisk.priority_rank.asc())
    )
    if year:
        stmt = stmt.where(TerritoryRisk.period_year == year)
    rows = db.execute(stmt).all()
    results = []
    for risk, territory in rows:
        if len(results) >= limit:
            break
        results.append(
            {
                "territory_id": territory.id,
                "code": territory.code,
                "name": territory.name,
                "region": territory.region,
                "year": risk.period_year,
                "mean_risk": round(float(risk.mean_risk), 4),
                "risk_band": risk.risk_band,
                "stunting_prevalence": round(float(risk.stunting_prevalence), 4),
                "children_screened": risk.children_screened,
                "population_at_risk": risk.population_at_risk,
                "priority_rank": risk.priority_rank,
                "top_features": risk.top_features or [],
            }
        )
    return results


def model_performance(db: Session) -> list[dict[str, Any]]:
    models = db.execute(select(MLModel).order_by(MLModel.id.desc())).scalars().all()
    rows = []
    for model in models:
        metrics = model.metrics or {}
        rows.append(
            {
                "model_id": model.id,
                "name": model.name,
                "algorithm": model.algorithm,
                "auc": metrics.get("auc"),
                "f1": metrics.get("f1_optimal") or metrics.get("f1"),
                "precision": metrics.get("precision_optimal") or metrics.get("precision"),
                "recall": metrics.get("recall_optimal") or metrics.get("recall"),
                "accuracy": metrics.get("accuracy"),
                "is_active": model.is_active,
                "trained_at": model.trained_at,
            }
        )
    return rows


def overview(db: Session, *, year: int | None = None, region: str | None = None, sex: str | None = None,
             age_group: str | None = None) -> dict[str, Any]:
    model = active_model(db)
    frame = load_frame(db, model)
    years = sorted(frame["period_year"].unique().tolist()) if not frame.empty else []
    selected_year = year or (max(years) if years else None)
    filtered = apply_filters(frame, year=selected_year, region=region, sex=sex, age_group=age_group)
    previous = apply_filters(frame, year=(selected_year - 1) if selected_year else None, region=region, sex=sex,
                             age_group=age_group)
    if previous.empty:
        previous = None

    from app.services.alerts import summarize_alerts

    alerts_summary = summarize_alerts(db)
    return {
        "kpis": kpis(filtered, previous, model),
        "trend": trend(apply_filters(frame, region=region, sex=sex, age_group=age_group)),
        "regions": comparison(apply_filters(frame, year=selected_year), "region"),
        "top_territories": top_territories(db, selected_year),
        "model_performance": model_performance(db),
        "risk_distribution": risk_distribution(filtered),
        "alerts": [
            {
                "id": alert.id,
                "title": alert.title,
                "message": alert.message,
                "severity": alert.severity,
                "status": alert.status,
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
            }
            for alert in alerts_summary["latest"][:5]
        ],
        "filters": {"year": selected_year, "region": region, "sex": sex, "age_group": age_group},
        "meta": {
            "active_model_id": model.id if model else None,
            "active_model_algorithm": model.algorithm if model else None,
            "years": years,
            "regions": sorted(frame["region"].dropna().unique().tolist()) if not frame.empty else [],
            "age_groups": AGE_GROUPS,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "children_total": int(len(frame)),
            "synthetic": True,
        },
    }


def filter_options(db: Session) -> dict[str, Any]:
    frame = build_analytical_frame(db)
    territories = db.execute(select(Territory.id, Territory.code, Territory.name, Territory.region)).all()
    return {
        "regions": sorted(frame["region"].dropna().unique().tolist()) if not frame.empty else [],
        "years": sorted(int(year) for year in frame["period_year"].dropna().unique()) if not frame.empty else [],
        "sexes": ["F", "M"],
        "age_groups": AGE_GROUPS,
        "territories": [
            {"id": terr[0], "code": terr[1], "name": terr[2], "region": terr[3]} for terr in territories
        ],
    }


def data_coverage(db: Session) -> dict[str, Any]:
    total = db.scalar(select(Child.id).limit(1))
    return {"has_data": total is not None}

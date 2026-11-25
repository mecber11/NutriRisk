"""Rule-based operational alerts for territories, models and data quality."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.data import Child, Dataset
from app.models.ml import Alert, MLModel, TerritoryRisk


def _exists(db: Session, rule_code: str, territory_id: int | None = None) -> bool:
    stmt = select(func.count(Alert.id)).where(Alert.rule_code == rule_code, Alert.status == "OPEN")
    if territory_id is not None:
        stmt = stmt.where(Alert.territory_id == territory_id)
    return bool(db.scalar(stmt))


def create_alert(
    db: Session,
    *,
    rule_code: str,
    severity: str,
    title: str,
    message: str,
    territory_id: int | None = None,
    value: float | None = None,
    threshold: float | None = None,
    context: dict[str, Any] | None = None,
    deduplicate: bool = True,
) -> Alert | None:
    """Insert an alert unless an equivalent open one already exists."""
    if deduplicate and _exists(db, rule_code, territory_id):
        return None
    alert = Alert(
        rule_code=rule_code,
        severity=severity,
        title=title,
        message=message,
        territory_id=territory_id,
        value=value,
        threshold=threshold,
        context=context or {},
        status="OPEN",
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    db.commit()
    return alert


def evaluate_alerts(db: Session, *, risk_threshold: float = 0.30, prevalence_threshold: float = 0.25) -> dict[str, Any]:
    """Run all operational rules and report what was created."""
    created: list[dict[str, Any]] = []
    skipped = 0

    active_model = db.scalar(select(MLModel).where(MLModel.is_active.is_(True)))
    if active_model:
        latest_year = db.scalar(select(func.max(TerritoryRisk.period_year)).where(TerritoryRisk.model_id == active_model.id))
        rows = db.execute(
            select(TerritoryRisk).where(
                TerritoryRisk.model_id == active_model.id,
                TerritoryRisk.period_year == latest_year,
                TerritoryRisk.mean_risk >= risk_threshold,
            )
        ).scalars().all()
        for risk in rows:
            from app.models.data import Territory

            territory = db.get(Territory, risk.territory_id)
            alert = create_alert(
                db,
                rule_code="HIGH_TERRITORY_RISK",
                severity="CRITICAL" if risk.mean_risk >= 0.5 else "WARNING",
                title=f"Riesgo territorial alto en {territory.name if territory else risk.territory_id}",
                message=(
                    f"Riesgo medio predicho {risk.mean_risk:.2f} (umbral {risk_threshold:.2f}); "
                    f"prevalencia observada de retraso del crecimiento {risk.stunting_prevalence:.1%} "
                    f"en {risk.children_screened} niños evaluados ({latest_year})."
                ),
                territory_id=risk.territory_id,
                value=risk.mean_risk,
                threshold=risk_threshold,
                context={"period_year": latest_year, "model_id": active_model.id, "priority_rank": risk.priority_rank},
            )
            if alert:
                created.append({"rule": "HIGH_TERRITORY_RISK", "territory_id": risk.territory_id})
            else:
                skipped += 1

        auc = (active_model.metrics or {}).get("auc")
        if auc is not None and auc < 0.70:
            alert = create_alert(
                db,
                rule_code="LOW_MODEL_AUC",
                severity="WARNING",
                title="Desempeño del modelo por debajo del umbral",
                message=f"El modelo activo '{active_model.name}' presenta AUC={auc:.3f} (<0.70). Revise datos o reentrene.",
                value=float(auc),
                threshold=0.70,
                context={"model_id": active_model.id},
            )
            if alert:
                created.append({"rule": "LOW_MODEL_AUC"})
            else:
                skipped += 1
    else:
        skipped += 1

    datasets = db.execute(select(Dataset).where(Dataset.status == "READY")).scalars().all()
    for dataset in datasets:
        score = (dataset.quality_report or {}).get("score")
        if score is not None and score < 70:
            alert = create_alert(
                db,
                rule_code="LOW_DATA_QUALITY",
                severity="WARNING",
                title=f"Calidad de datos baja en {dataset.name}",
                message=f"El dataset '{dataset.name}' obtuvo {score}/100 en el control de calidad.",
                value=float(score),
                threshold=70.0,
                context={"dataset_id": dataset.id},
            )
            if alert:
                created.append({"rule": "LOW_DATA_QUALITY", "dataset_id": dataset.id})
            else:
                skipped += 1

    total_children = db.scalar(select(func.count(Child.id))) or 0
    if total_children == 0:
        alert = create_alert(
            db,
            rule_code="NO_DATA",
            severity="INFO",
            title="Sin datos cargados",
            message="No hay niños en la base. Cargue un dataset o genere datos sintéticos de demostración.",
            deduplicate=True,
        )
        if alert:
            created.append({"rule": "NO_DATA"})

    return {"created": len(created), "skipped": skipped, "rules": created}


def summarize_alerts(db: Session) -> dict[str, Any]:
    rows = db.execute(select(Alert)).scalars().all()
    counts: dict[str, int] = {}
    severities: dict[str, int] = {}
    for alert in rows:
        counts[alert.status] = counts.get(alert.status, 0) + 1
        severities[alert.severity] = severities.get(alert.severity, 0) + 1
    latest = sorted(rows, key=lambda alert: alert.created_at, reverse=True)[:5]
    return {
        "open": counts.get("OPEN", 0),
        "acknowledged": counts.get("ACKNOWLEDGED", 0),
        "resolved": counts.get("RESOLVED", 0),
        "critical": severities.get("CRITICAL", 0),
        "by_severity": severities,
        "latest": latest,
    }

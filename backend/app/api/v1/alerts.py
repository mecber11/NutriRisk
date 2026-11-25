"""Operational alerts endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.deps import DbSession, PageParams, paginated, require_permission
from app.core.integrations import require_service_token
from app.core.rbac import Action, Module
from app.models.ml import Alert
from app.models.user import User
from app.schemas.ml import AlertCreate, AlertEvaluationResult, AlertOut, AlertSummary
from app.services.alerts import create_alert, evaluate_alerts, summarize_alerts

router = APIRouter(prefix="/alerts", tags=["Alertas y notificaciones"])

ALERT_READ = Depends(require_permission(Module.ALERTS, Action.READ))


@router.get("", summary="Listar alertas")
def list_alerts(
    db: DbSession,
    page: PageParams,
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    _: User = ALERT_READ,
) -> dict:
    stmt = select(Alert)
    count_stmt = select(func.count(Alert.id))
    conditions = []
    if status_filter:
        conditions.append(Alert.status == status_filter)
    if severity:
        conditions.append(Alert.severity == severity)
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)
    total = db.scalar(count_stmt) or 0
    alerts = db.execute(stmt.order_by(Alert.created_at.desc()).offset(page.offset).limit(page.limit)).scalars().all()
    return paginated([AlertOut.model_validate(alert).model_dump() for alert in alerts], total, page.page, page.page_size)


@router.get("/summary", response_model=AlertSummary, summary="Resumen de alertas")
def summary(db: DbSession, _: User = ALERT_READ) -> AlertSummary:
    data = summarize_alerts(db)
    return AlertSummary(
        open=data["open"],
        acknowledged=data["acknowledged"],
        resolved=data["resolved"],
        critical=data["critical"],
        by_severity=data["by_severity"],
        latest=[AlertOut.model_validate(alert) for alert in data["latest"]],
    )


@router.post("", response_model=AlertOut, status_code=status.HTTP_201_CREATED, summary="Crear alerta manual")
def create(
    payload: AlertCreate,
    db: DbSession,
    user: User = Depends(require_permission(Module.ALERTS, Action.CREATE)),
) -> AlertOut:
    alert = create_alert(
        db,
        rule_code=payload.rule_code,
        severity=payload.severity,
        title=payload.title,
        message=payload.message,
        territory_id=payload.territory_id,
        value=payload.value,
        threshold=payload.threshold,
        context={"created_by": user.email},
        deduplicate=False,
    )
    return AlertOut.model_validate(alert)


@router.post("/evaluate", response_model=AlertEvaluationResult, summary="Ejecutar reglas de alerta")
def evaluate(db: DbSession, _: User = Depends(require_permission(Module.ALERTS, Action.CREATE))) -> AlertEvaluationResult:
    result = evaluate_alerts(db)
    return AlertEvaluationResult(created=result["created"], skipped=result["skipped"], rules=result["rules"])


@router.post("/n8n/evaluate", response_model=AlertEvaluationResult, summary="Evaluar reglas (n8n)")
def evaluate_n8n(db: DbSession, _token: None = Depends(require_service_token)) -> AlertEvaluationResult:
    result = evaluate_alerts(db)
    return AlertEvaluationResult(created=result["created"], skipped=result["skipped"], rules=result["rules"])


@router.post("/{alert_id}/acknowledge", response_model=AlertOut, summary="Reconocer alerta")
def acknowledge(
    alert_id: int,
    db: DbSession,
    user: User = Depends(require_permission(Module.ALERTS, Action.UPDATE)),
) -> AlertOut:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta no encontrada")
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_by = user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return AlertOut.model_validate(alert)


@router.post("/{alert_id}/resolve", response_model=AlertOut, summary="Resolver alerta")
def resolve(
    alert_id: int,
    db: DbSession,
    user: User = Depends(require_permission(Module.ALERTS, Action.UPDATE)),
) -> AlertOut:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta no encontrada")
    alert.status = "RESOLVED"
    alert.acknowledged_by = user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return AlertOut.model_validate(alert)


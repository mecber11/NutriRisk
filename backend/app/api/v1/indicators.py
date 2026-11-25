"""Anthropometric indicators, WHO references and indicator maintenance."""

from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.deps import CurrentUser, DbSession, PageParams, paginated, require_permission
from app.core.rbac import Action, Module
from app.ml.features import build_analytical_frame
from app.models.data import AnthropometricIndicator, Child, Household, Territory
from app.models.user import User
from app.schemas.data import (
    ChildOut,
    ChildRecord,
    DistributionResponse,
    HistogramBin,
    IndicatorOut,
    IndicatorSummary,
    OptionSets,
    PrevalenceRow,
    RecomputeRequest,
    RecomputeResult,
    TerritoryOut,
    HouseholdOut,
)
from app.services.anthropometry import AnthropometryError, compute_indicators, reference_coverage, self_check

router = APIRouter(prefix="/indicators", tags=["Indicadores antropométricos"])

IND_READ = Depends(require_permission(Module.INDICATORS, Action.READ))


def _prevalence_rows(frame, key: str, label_map: dict[str, str] | None = None) -> list[PrevalenceRow]:
    rows: list[PrevalenceRow] = []
    if frame.empty:
        return rows
    for value, subset in frame.groupby(key):
        label = (label_map or {}).get(str(value), str(value))
        rows.append(
            PrevalenceRow(
                key=str(value),
                label=label,
                n=int(len(subset)),
                stunting=round(float(subset["stunting"].mean()), 4),
                wasting=round(float(subset["wasting"].mean()), 4),
                underweight=round(float(subset["underweight"].mean()), 4),
                severe_stunting=round(float(subset["severe_stunting"].mean()), 4)
                if "severe_stunting" in subset.columns
                else 0.0,
                mean_haz=round(float(subset["haz"].mean()), 4),
            )
        )
    return rows


@router.get("/summary", response_model=IndicatorSummary, summary="Resumen de prevalencias")
def summary(
    db: DbSession,
    year: int | None = Query(default=None),
    region: str | None = Query(default=None),
    sex: str | None = Query(default=None),
    age_group: str | None = Query(default=None),
    _: User = IND_READ,
) -> IndicatorSummary:
    frame = build_analytical_frame(db)
    if frame.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay indicadores calculados")
    if year:
        frame = frame[frame["period_year"] == year]
    if region:
        frame = frame[frame["region"] == region]
    if sex:
        frame = frame[frame["sex"] == sex]
    if age_group:
        frame = frame[frame["age_group"] == age_group]
    return IndicatorSummary(
        total_children=int(len(frame)),
        stunting_prevalence=round(float(frame["stunting"].mean()), 4),
        wasting_prevalence=round(float(frame["wasting"].mean()), 4),
        underweight_prevalence=round(float(frame["underweight"].mean()), 4),
        severe_stunting_prevalence=round(
            float((frame["haz"] < -3).mean()) if "haz" in frame.columns else 0.0, 4
        ),
        mean_haz=round(float(frame["haz"].mean()), 4),
        mean_waz=round(float(frame["waz"].mean()), 4),
        mean_whz=round(float(frame["whz"].mean()), 4),
        by_year=_prevalence_rows(frame, "period_year"),
        by_region=_prevalence_rows(frame, "region"),
        by_sex=_prevalence_rows(frame, "sex", {"F": "Femenino", "M": "Masculino"}),
        by_age_group=_prevalence_rows(frame, "age_group"),
        by_wealth_quintile=_prevalence_rows(
            frame, "wealth_quintile", {str(index): f"Quintil {index}" for index in range(1, 6)}
        ),
    )


@router.get("/children", summary="Listar niños con indicadores")
def list_children(
    db: DbSession,
    page: PageParams,
    year: int | None = Query(default=None),
    region: str | None = Query(default=None),
    sex: str | None = Query(default=None),
    territory_id: int | None = Query(default=None),
    stunting: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    _: User = IND_READ,
) -> dict:
    stmt = (
        select(Child, AnthropometricIndicator, Territory, Household)
        .join(AnthropometricIndicator, AnthropometricIndicator.child_id == Child.id)
        .join(Territory, Child.territory_id == Territory.id)
        .join(Household, Child.household_id == Household.id)
    )
    count_stmt = (
        select(func.count(Child.id))
        .join(AnthropometricIndicator, AnthropometricIndicator.child_id == Child.id)
        .join(Territory, Child.territory_id == Territory.id)
    )
    conditions = []
    if year:
        conditions.append(Child.period_year == year)
    if region:
        conditions.append(Territory.region == region)
    if sex:
        conditions.append(Child.sex == sex)
    if territory_id:
        conditions.append(Child.territory_id == territory_id)
    if stunting is not None:
        conditions.append(AnthropometricIndicator.stunting.is_(stunting))
    if search:
        conditions.append(Child.code.ilike(f"%{search}%"))
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)
    total = db.scalar(count_stmt) or 0
    rows = db.execute(stmt.order_by(Child.id).offset(page.offset).limit(page.limit)).all()
    items = []
    for child, indicator, territory, household in rows:
        items.append(
            {
                "child": ChildOut.model_validate(child).model_dump(),
                "indicator": IndicatorOut.model_validate(indicator).model_dump(),
                "territory": {
                    "id": territory.id,
                    "code": territory.code,
                    "name": territory.name,
                    "region": territory.region,
                },
                "household": {
                    "id": household.id,
                    "wealth_quintile": household.wealth_quintile,
                    "maternal_education": household.maternal_education,
                    "urban_rural": household.urban_rural,
                },
            }
        )
    return paginated(items, total, page.page, page.page_size)


@router.get("/children/{child_id}", response_model=ChildRecord, summary="Detalle de un niño")
def get_child(child_id: int, db: DbSession, _: User = IND_READ) -> ChildRecord:
    child = db.get(Child, child_id)
    if child is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Niño no encontrado")
    indicator = db.scalar(select(AnthropometricIndicator).where(AnthropometricIndicator.child_id == child.id))
    household = db.get(Household, child.household_id)
    territory = db.get(Territory, child.territory_id)
    return ChildRecord(
        child=ChildOut.model_validate(child),
        household=HouseholdOut.model_validate(household) if household else None,
        territory=TerritoryOut.model_validate(territory) if territory else None,
        indicator=IndicatorOut.model_validate(indicator) if indicator else None,
    )


@router.post("/recompute", response_model=RecomputeResult, summary="Recalcular z-scores OMS")
def recompute(
    payload: RecomputeRequest,
    db: DbSession,
    user: User = Depends(require_permission(Module.INDICATORS, Action.EXECUTE)),
) -> RecomputeResult:
    stmt = select(Child)
    if payload.territory_id:
        stmt = stmt.where(Child.territory_id == payload.territory_id)
    if payload.year:
        stmt = stmt.where(Child.period_year == payload.year)
    children = db.execute(stmt).scalars().all()
    processed = 0
    failed = 0
    errors: list[dict[str, Any]] = []
    for child in children:
        try:
            result = compute_indicators(
                sex=child.sex,
                age_months=child.age_months,
                weight_kg=child.weight_kg,
                height_cm=child.height_cm,
                edema=child.edema,
            )
        except AnthropometryError as exc:
            failed += 1
            if len(errors) < 50:
                errors.append({"child_id": child.id, "code": child.code, "error": str(exc)})
            continue
        indicator = db.scalar(select(AnthropometricIndicator).where(AnthropometricIndicator.child_id == child.id))
        if indicator is None:
            indicator = AnthropometricIndicator(child_id=child.id)
            db.add(indicator)
        indicator.haz = result.haz
        indicator.waz = result.waz
        indicator.whz = result.whz
        indicator.baz = result.baz
        indicator.stunting = result.stunting
        indicator.severe_stunting = result.severe_stunting
        indicator.wasting = result.wasting
        indicator.severe_wasting = result.severe_wasting
        indicator.underweight = result.underweight
        indicator.severe_underweight = result.severe_underweight
        indicator.overweight = result.overweight
        indicator.edematous = result.edematous
        indicator.reference_version = result.reference_version
        processed += 1
    db.commit()
    return RecomputeResult(processed=processed, failed=failed, errors=errors)


@router.get("/reference", summary="Referencia OMS 2006 y autochequeo")
def reference(_: User = IND_READ) -> dict[str, Any]:
    return {**reference_coverage(), "self_check": self_check()}


@router.get("/distribution", response_model=DistributionResponse, summary="Distribución de un indicador")
def distribution(
    db: DbSession,
    indicator: str = Query(default="haz", pattern="^(haz|waz|whz|baz)$"),
    bins: int = Query(default=30, ge=5, le=80),
    year: int | None = Query(default=None),
    region: str | None = Query(default=None),
    _: User = IND_READ,
) -> DistributionResponse:
    frame = build_analytical_frame(db)
    if frame.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay datos")
    if year:
        frame = frame[frame["period_year"] == year]
    if region:
        frame = frame[frame["region"] == region]
    values = frame[indicator].dropna().to_numpy()
    if values.size == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sin valores para el indicador")
    counts, edges = _histogram(values, bins)
    bins_list = [
        HistogramBin(bin_start=round(float(edges[index]), 3), bin_end=round(float(edges[index + 1]), 3), count=int(counts[index]))
        for index in range(len(counts))
    ]
    mean = float(values.mean())
    sd = float(values.std(ddof=0)) if values.size > 1 else 0.0
    return DistributionResponse(
        indicator=indicator,
        reference_line=-2.0,
        bins=bins_list,
        mean=round(mean, 4),
        sd=round(sd, 4),
        total=int(values.size),
    )


def _histogram(values, bins: int):  # noqa: ANN001, ANN202
    import numpy as np

    counts, edges = np.histogram(values, bins=bins, range=(-5, 5))
    return counts, edges


@router.get("/options", response_model=OptionSets, summary="Opciones de filtrado")
def options(db: DbSession, _: User = IND_READ) -> OptionSets:
    frame = build_analytical_frame(db)
    territories = db.execute(select(Territory.id, Territory.code, Territory.name, Territory.region)).all()
    return OptionSets(
        regions=sorted(frame["region"].dropna().unique().tolist()) if not frame.empty else [],
        years=sorted(int(year) for year in frame["period_year"].dropna().unique()) if not frame.empty else [],
        sexes=["F", "M"],
        age_groups=sorted(frame["age_group"].dropna().unique().tolist()) if not frame.empty else [],
        territories=[{"id": item[0], "code": item[1], "name": item[2], "region": item[3]} for item in territories],
    )


_ = (CurrentUser, math)

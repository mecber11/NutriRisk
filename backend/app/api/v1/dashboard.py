"""Dashboard endpoints: KPIs, trends, comparisons and filter options."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.deps import DbSession, require_permission
from app.core.rbac import Action, Module
from app.ml.features import build_analytical_frame
from app.models.user import User
from app.schemas.ml import (
    ComparisonResponse,
    DashboardKpis,
    DashboardOverview,
    ModelPerformanceResponse,
    RiskDistributionResponse,
    TrendResponse,
)
from app.services import dashboard as service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

DASH_READ = Depends(require_permission(Module.DASHBOARD, Action.READ))


@router.get("/overview", response_model=DashboardOverview, summary="Vista agregada del tablero")
def overview(
    db: DbSession,
    year: int | None = Query(default=None),
    region: str | None = Query(default=None),
    sex: str | None = Query(default=None),
    age_group: str | None = Query(default=None),
    _: User = DASH_READ,
) -> DashboardOverview:
    return DashboardOverview(**service.overview(db, year=year, region=region, sex=sex, age_group=age_group))


@router.get("/kpis", response_model=DashboardKpis, summary="Indicadores clave")
def kpis(
    db: DbSession,
    year: int | None = Query(default=None),
    region: str | None = Query(default=None),
    sex: str | None = Query(default=None),
    age_group: str | None = Query(default=None),
    _: User = DASH_READ,
) -> DashboardKpis:
    model = service.active_model(db)
    frame = service.load_frame(db, model)
    years = sorted(frame["period_year"].unique().tolist()) if not frame.empty else []
    selected_year = year or (max(years) if years else None)
    current = service.apply_filters(frame, year=selected_year, region=region, sex=sex, age_group=age_group)
    previous = service.apply_filters(
        frame, year=(selected_year - 1) if selected_year else None, region=region, sex=sex, age_group=age_group
    )
    return DashboardKpis(
        kpis=service.kpis(current, previous if not previous.empty else None, model),
        filters={"year": selected_year, "region": region, "sex": sex, "age_group": age_group},
    )


@router.get("/trends", response_model=TrendResponse, summary="Series temporales")
def trends(
    db: DbSession,
    region: str | None = Query(default=None),
    sex: str | None = Query(default=None),
    _: User = DASH_READ,
) -> TrendResponse:
    frame = service.apply_filters(service.load_frame(db), region=region, sex=sex)
    return TrendResponse(series=service.trend(frame))


@router.get("/comparison", response_model=ComparisonResponse, summary="Comparativos por dimensión")
def comparison(
    db: DbSession,
    dimension: str = Query(default="region", pattern="^(region|sex|age_group|wealth_quintile|urban_rural)$"),
    year: int | None = Query(default=None),
    _: User = DASH_READ,
) -> ComparisonResponse:
    frame = service.apply_filters(service.load_frame(db), year=year)
    return ComparisonResponse(dimension=dimension, rows=service.comparison(frame, dimension))


@router.get("/risk-distribution", response_model=RiskDistributionResponse, summary="Distribución de bandas de riesgo")
def risk_distribution(db: DbSession, year: int | None = Query(default=None), _: User = DASH_READ) -> RiskDistributionResponse:
    frame = service.apply_filters(service.load_frame(db), year=year)
    population = int(frame.groupby("territory_id")["population_u5"].first().sum()) if not frame.empty else 0
    from app.schemas.ml import RiskDistributionItem

    return RiskDistributionResponse(
        bands=[RiskDistributionItem(**item) for item in service.risk_distribution(frame)],
        total_children=int(len(frame)),
        total_population=population,
    )


@router.get("/model-performance", response_model=ModelPerformanceResponse, summary="Desempeño de modelos")
def model_performance(db: DbSession, _: User = DASH_READ) -> ModelPerformanceResponse:
    from app.schemas.ml import ModelPerformanceRow

    return ModelPerformanceResponse(
        models=[ModelPerformanceRow(**row) for row in service.model_performance(db)]
    )


@router.get("/options", summary="Opciones de filtros y metadatos")
def options(db: DbSession, _: User = DASH_READ) -> dict:
    frame = build_analytical_frame(db)
    return {
        **service.filter_options(db),
        "total_children": int(len(frame)),
        "regions_meta": [
            {"name": region, "children": int((frame["region"] == region).sum())}
            for region in sorted(frame["region"].dropna().unique().tolist())
        ]
        if not frame.empty
        else [],
    }

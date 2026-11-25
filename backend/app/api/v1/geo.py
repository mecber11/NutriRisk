"""Geospatial endpoints: risk map, territory ranking and environmental layers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import DbSession, require_permission
from app.core.rbac import Action, Module
from app.models.data import Territory
from app.models.ml import MLModel, TerritoryRisk
from app.models.user import User
from app.schemas.ml import (
    GeoLayersResponse,
    GeoLayerPoint,
    MapCollection,
    MapFeature,
    MapProperties,
    RankingResponse,
    RiskDistributionItem,
    RiskDistributionResponse,
    TerritoryRiskOut,
)
from app.services.modeling import get_active_model

router = APIRouter(prefix="/geo", tags=["Cartografía de riesgo"])

GEO_READ = Depends(require_permission(Module.GEO, Action.READ))

BAND_COLORS = {
    "LOW": "#0e7490",
    "MODERATE": "#f59e0b",
    "HIGH": "#f97316",
    "CRITICAL": "#dc2626",
}

LAYERS: dict[str, dict[str, Any]] = {
    "risk": {"label": "Riesgo predicho", "unit": "%"},
    "stunting": {"label": "Retraso en crecimiento observado", "unit": "%"},
    "population": {"label": "Población menor de 5 años", "unit": "niños"},
    "ndvi": {"label": "Índice de vegetación (NDVI)", "unit": "índice"},
    "rainfall": {"label": "Precipitación anual", "unit": "mm"},
    "water": {"label": "Cobertura de agua", "unit": "%"},
    "sanitation": {"label": "Cobertura de saneamiento", "unit": "%"},
    "altitude": {"label": "Altitud", "unit": "m"},
    "food_insecurity": {"label": "Inseguridad alimentaria", "unit": "índice"},
}


@router.get("/layers", summary="Capas disponibles")
def available_layers(_: User = GEO_READ) -> dict[str, Any]:
    return {"layers": [{"code": code, **meta} for code, meta in LAYERS.items()]}


@router.get("/map", response_model=MapCollection, summary="Mapa coroplético de riesgo")
def risk_map(
    db: DbSession,
    year: int | None = Query(default=None),
    model_id: int | None = Query(default=None),
    _: User = GEO_READ,
) -> MapCollection:
    model = db.get(MLModel, model_id) if model_id else get_active_model(db)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay modelo activo")
    years = [row[0] for row in db.execute(select(TerritoryRisk.period_year).where(TerritoryRisk.model_id == model.id).distinct()).all()]
    selected_year = year or (max(years) if years else None)
    rows = db.execute(
        select(TerritoryRisk, Territory)
        .join(Territory, TerritoryRisk.territory_id == Territory.id)
        .where(TerritoryRisk.model_id == model.id)
    ).all()
    features: list[MapFeature] = []
    for risk, territory in rows:
        if selected_year and risk.period_year != selected_year:
            continue
        if not territory.geometry:
            continue
        features.append(
            MapFeature(
                geometry=territory.geometry,
                properties=MapProperties(
                    territory_id=territory.id,
                    code=territory.code,
                    name=territory.name,
                    region=territory.region,
                    urban_rural=territory.urban_rural,
                    population=territory.population,
                    population_u5=territory.population_u5,
                    mean_risk=round(float(risk.mean_risk), 4),
                    risk_band=risk.risk_band,
                    stunting_prevalence=round(float(risk.stunting_prevalence), 4),
                    priority_rank=risk.priority_rank,
                    children_screened=risk.children_screened,
                    population_at_risk=risk.population_at_risk,
                    altitude_m=territory.altitude_m,
                    food_insecurity_index=territory.food_insecurity_index,
                    water_coverage=territory.water_coverage,
                    sanitation_coverage=territory.sanitation_coverage,
                ),
            )
        )
    legend = [
        {"band": band, "color": color, "label": label, "min": minimum, "max": maximum}
        for band, color, label, minimum, maximum in (
            ("LOW", BAND_COLORS["LOW"], "Bajo", 0.0, 0.15),
            ("MODERATE", BAND_COLORS["MODERATE"], "Moderado", 0.15, 0.30),
            ("HIGH", BAND_COLORS["HIGH"], "Alto", 0.30, 0.50),
            ("CRITICAL", BAND_COLORS["CRITICAL"], "Crítico", 0.50, 1.0),
        )
    ]
    return MapCollection(features=features, year=selected_year or 0, model_id=model.id, legend=legend)


@router.get("/territories", summary="Listado de territorios")
def territories(db: DbSession, _: User = GEO_READ) -> dict[str, Any]:
    rows = db.execute(select(Territory).order_by(Territory.code)).scalars().all()
    return {
        "items": [
            {
                "id": territory.id,
                "code": territory.code,
                "name": territory.name,
                "region": territory.region,
                "population": territory.population,
                "population_u5": territory.population_u5,
                "neighbors": territory.neighbor_codes,
                "latitude": territory.latitude,
                "longitude": territory.longitude,
            }
            for territory in rows
        ],
        "total": len(rows),
    }


@router.get("/territories/{code}", summary="Detalle territorial")
def territory_detail(code: str, db: DbSession, _: User = GEO_READ) -> dict[str, Any]:
    territory = db.scalar(select(Territory).where(Territory.code == code.upper()))
    if territory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Territorio no encontrado")
    risks = db.execute(
        select(TerritoryRisk).where(TerritoryRisk.territory_id == territory.id).order_by(TerritoryRisk.period_year)
    ).scalars().all()
    return {
        "territory": {
            "id": territory.id,
            "code": territory.code,
            "name": territory.name,
            "region": territory.region,
            "urban_rural": territory.urban_rural,
            "population": territory.population,
            "population_u5": territory.population_u5,
            "area_km2": territory.area_km2,
            "altitude_m": territory.altitude_m,
            "climate_zone": territory.climate_zone,
            "rainfall_mm": territory.rainfall_mm,
            "temperature_c": territory.temperature_c,
            "ndvi": territory.ndvi,
            "food_insecurity_index": territory.food_insecurity_index,
            "water_coverage": territory.water_coverage,
            "sanitation_coverage": territory.sanitation_coverage,
            "neighbor_codes": territory.neighbor_codes,
            "geometry": territory.geometry,
        },
        "risk_history": [
            {
                "year": risk.period_year,
                "model_id": risk.model_id,
                "mean_risk": risk.mean_risk,
                "risk_band": risk.risk_band,
                "stunting_prevalence": risk.stunting_prevalence,
                "priority_rank": risk.priority_rank,
                "population_at_risk": risk.population_at_risk,
                "children_screened": risk.children_screened,
                "top_features": risk.top_features,
            }
            for risk in risks
        ],
    }


@router.get("/ranking", response_model=RankingResponse, summary="Ranking de territorios prioritarios")
def ranking(
    db: DbSession,
    year: int | None = Query(default=None),
    limit: int = Query(default=24, ge=1, le=100),
    model_id: int | None = Query(default=None),
    _: User = GEO_READ,
) -> RankingResponse:
    model = db.get(MLModel, model_id) if model_id else get_active_model(db)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay modelo activo")
    rows = db.execute(
        select(TerritoryRisk, Territory)
        .join(Territory, TerritoryRisk.territory_id == Territory.id)
        .where(TerritoryRisk.model_id == model.id)
        .order_by(TerritoryRisk.period_year.desc(), TerritoryRisk.priority_rank)
    ).all()
    selected_year = year or (rows[0][0].period_year if rows else 0)
    items = []
    for risk, territory in rows:
        if risk.period_year != selected_year:
            continue
        items.append(
            TerritoryRiskOut(
                territory_id=territory.id,
                code=territory.code,
                name=territory.name,
                region=territory.region,
                year=risk.period_year,
                mean_risk=round(float(risk.mean_risk), 4),
                risk_band=risk.risk_band,
                stunting_prevalence=round(float(risk.stunting_prevalence), 4),
                children_screened=risk.children_screened,
                population_at_risk=risk.population_at_risk,
                priority_rank=risk.priority_rank,
                top_features=risk.top_features or [],
            )
        )
        if len(items) >= limit:
            break
    return RankingResponse(year=selected_year, model_id=model.id, total=len(items), rows=items)


@router.get("/risk/{territory_id}", response_model=TerritoryRiskOut, summary="Riesgo de un territorio")
def territory_risk(territory_id: int, db: DbSession, year: int | None = Query(default=None), _: User = GEO_READ) -> TerritoryRiskOut:
    territory = db.get(Territory, territory_id)
    if territory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Territorio no encontrado")
    stmt = (
        select(TerritoryRisk)
        .where(TerritoryRisk.territory_id == territory_id)
        .order_by(TerritoryRisk.period_year.desc())
    )
    if year:
        stmt = stmt.where(TerritoryRisk.period_year == year)
    risk = db.scalar(stmt)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sin riesgo calculado")
    return TerritoryRiskOut(
        territory_id=territory.id,
        code=territory.code,
        name=territory.name,
        region=territory.region,
        year=risk.period_year,
        mean_risk=risk.mean_risk,
        risk_band=risk.risk_band,
        stunting_prevalence=risk.stunting_prevalence,
        children_screened=risk.children_screened,
        population_at_risk=risk.population_at_risk,
        priority_rank=risk.priority_rank,
        top_features=risk.top_features or [],
    )


@router.get("/layer/{layer_code}", response_model=GeoLayersResponse, summary="Capa ambiental o poblacional")
def layer(layer_code: str, db: DbSession, _: User = GEO_READ) -> GeoLayersResponse:
    if layer_code not in LAYERS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capa no disponible")
    rows = db.execute(select(Territory).order_by(Territory.code)).scalars().all()
    attribute_map = {
        "population": "population_u5",
        "ndvi": "ndvi",
        "rainfall": "rainfall_mm",
        "water": "water_coverage",
        "sanitation": "sanitation_coverage",
        "altitude": "altitude_m",
        "food_insecurity": "food_insecurity_index",
    }
    points = []
    for territory in rows:
        if layer_code in ("risk", "stunting"):
            risk = db.scalar(
                select(TerritoryRisk)
                .where(TerritoryRisk.territory_id == territory.id)
                .order_by(TerritoryRisk.period_year.desc())
            )
            value = None
            if risk:
                value = risk.mean_risk if layer_code == "risk" else risk.stunting_prevalence
        else:
            value = getattr(territory, attribute_map[layer_code], None)
        points.append(
            GeoLayerPoint(
                code=territory.code,
                name=territory.name,
                value=round(float(value), 4) if value is not None else None,
                population=territory.population_u5,
            )
        )
    meta = LAYERS[layer_code]
    return GeoLayersResponse(layer=layer_code, label=meta["label"], unit=meta.get("unit"), points=points)


@router.get("/risk-distribution", response_model=RiskDistributionResponse, summary="Distribución de riesgo")
def risk_distribution(db: DbSession, year: int | None = Query(default=None), _: User = GEO_READ) -> RiskDistributionResponse:
    from app.services.dashboard import load_frame, risk_distribution as compute_distribution

    frame = load_frame(db)
    if frame.empty:
        return RiskDistributionResponse(bands=[], total_children=0, total_population=0)
    years = sorted(frame["period_year"].unique().tolist())
    selected_year = year or max(years)
    subset = frame[frame["period_year"] == selected_year]
    bands = [RiskDistributionItem(**item) for item in compute_distribution(subset)]
    population = int(subset.groupby("territory_id")["population_u5"].first().sum())
    return RiskDistributionResponse(bands=bands, total_children=int(len(subset)), total_population=population)


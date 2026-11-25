"""Analytical feature engineering for the malnutrition risk models.

Features are limited to *determinants* (socioeconomic, WASH, dietary and
environmental) — never anthropometric outcomes — so the models remain usable for
early identification before a child is measured.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.data import AnthropometricIndicator, Child, Household, Territory

EDUCATION_YEARS = {"NONE": 0, "PRIMARY": 6, "SECONDARY": 12, "TERTIARY": 16}
IMPROVED_WATER = {"PIPED", "IMPROVED"}

FEATURES: list[str] = [
    "age_months",
    "sex_female",
    "wealth_quintile",
    "maternal_education_years",
    "maternal_age",
    "water_improved",
    "sanitation_improved",
    "electricity",
    "assets_count",
    "household_size",
    "food_insecurity_score",
    "urban",
    "minimum_diet_diversity",
    "vaccination_complete",
    "diarrhea_14d",
    "fever_14d",
    "birth_weight_g",
    "breastfeeding_months",
    "altitude_m",
    "rainfall_mm",
    "temperature_c",
    "ndvi",
    "water_coverage",
    "sanitation_coverage",
    "territory_food_insecurity",
    "population_density",
]

FEATURE_LABELS: dict[str, str] = {
    "age_months": "Edad (meses)",
    "sex_female": "Sexo femenino",
    "wealth_quintile": "Quintil de riqueza",
    "maternal_education_years": "Educación materna (años)",
    "maternal_age": "Edad materna",
    "water_improved": "Agua mejorada",
    "sanitation_improved": "Saneamiento mejorado",
    "electricity": "Electricidad",
    "assets_count": "Activos del hogar",
    "household_size": "Tamaño del hogar",
    "food_insecurity_score": "Inseguridad alimentaria (hogar)",
    "urban": "Área urbana",
    "minimum_diet_diversity": "Dieta mínima diversa",
    "vaccination_complete": "Vacunación completa",
    "diarrhea_14d": "Diarrea reciente",
    "fever_14d": "Fiebre reciente",
    "birth_weight_g": "Peso al nacer (g)",
    "breastfeeding_months": "Lactancia (meses)",
    "altitude_m": "Altitud (m)",
    "rainfall_mm": "Precipitación (mm)",
    "temperature_c": "Temperatura (°C)",
    "ndvi": "NDVI",
    "water_coverage": "Cobertura de agua (territorio)",
    "sanitation_coverage": "Cobertura de saneamiento (territorio)",
    "territory_food_insecurity": "Inseguridad alimentaria (territorio)",
    "population_density": "Densidad de menores de 5 años",
    "neighbor_wealth": "Riqueza media de territorios vecinos",
    "neighbor_water_coverage": "Cobertura de agua (vecinos)",
    "neighbor_sanitation_coverage": "Saneamiento (vecinos)",
    "neighbor_food_insecurity": "Inseguridad alimentaria (vecinos)",
}

SPATIAL_FEATURES: list[str] = [
    "neighbor_wealth",
    "neighbor_water_coverage",
    "neighbor_sanitation_coverage",
    "neighbor_food_insecurity",
]

SENSITIVE_ATTRIBUTES = {
    "sex": "Sexo",
    "wealth_quintile": "Quintil de riqueza",
    "urban_rural": "Área urbano/rural",
    "region": "Región",
    "age_group": "Grupo de edad",
}


def age_group(age_months: int) -> str:
    if age_months < 6:
        return "0-5 m"
    if age_months < 12:
        return "6-11 m"
    if age_months < 24:
        return "12-23 m"
    if age_months < 36:
        return "24-35 m"
    return "36-59 m"


def build_analytical_frame(db: Session, year: int | None = None) -> pd.DataFrame:
    """Join children, households, territories and indicators into a flat table."""
    stmt = (
        select(
            Child.id.label("child_id"),
            Child.code.label("child_code"),
            Child.period_year,
            Child.age_months,
            Child.sex,
            Child.weight_kg,
            Child.height_cm,
            Child.muac_cm,
            Child.birth_weight_g,
            Child.breastfeeding_months,
            Child.minimum_diet_diversity,
            Child.vaccination_complete,
            Child.diarrhea_14d,
            Child.fever_14d,
            Household.id.label("household_id"),
            Household.wealth_quintile,
            Household.wealth_index,
            Household.maternal_education,
            Household.maternal_age,
            Household.water_source,
            Household.sanitation,
            Household.electricity,
            Household.assets_count,
            Household.household_size,
            Household.food_insecurity_score,
            Household.urban_rural,
            Territory.id.label("territory_id"),
            Territory.code.label("territory_code"),
            Territory.name.label("territory_name"),
            Territory.region,
            Territory.population,
            Territory.population_u5,
            Territory.area_km2,
            Territory.latitude,
            Territory.longitude,
            Territory.altitude_m,
            Territory.rainfall_mm,
            Territory.temperature_c,
            Territory.ndvi,
            Territory.water_coverage,
            Territory.sanitation_coverage,
            Territory.food_insecurity_index,
            AnthropometricIndicator.haz,
            AnthropometricIndicator.waz,
            AnthropometricIndicator.whz,
            AnthropometricIndicator.baz,
            AnthropometricIndicator.stunting,
            AnthropometricIndicator.wasting,
            AnthropometricIndicator.underweight,
            AnthropometricIndicator.overweight,
        )
        .join(Household, Child.household_id == Household.id)
        .join(Territory, Child.territory_id == Territory.id)
        .join(AnthropometricIndicator, AnthropometricIndicator.child_id == Child.id)
    )
    if year:
        stmt = stmt.where(Child.period_year == year)
    rows = db.execute(stmt).all()
    frame = pd.DataFrame(rows, columns=list(stmt.selected_columns.keys()))
    if frame.empty:
        return frame
    frame = frame.rename(columns={"food_insecurity_index": "territory_food_insecurity"})
    for column in ("stunting", "wasting", "underweight", "overweight", "electricity", "minimum_diet_diversity",
                   "vaccination_complete", "diarrhea_14d", "fever_14d"):
        frame[column] = frame[column].astype(bool)
    frame["age_group"] = frame["age_months"].map(age_group)
    return frame


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Derive the numeric model matrix (deterministic and explainable)."""
    result = frame.copy()
    result["sex_female"] = (result["sex"].astype(str).str.upper() == "F").astype(float)
    result["maternal_education_years"] = (
        result["maternal_education"].map(EDUCATION_YEARS).fillna(6).astype(float)
    )
    result["water_improved"] = result["water_source"].isin(IMPROVED_WATER).astype(float)
    result["sanitation_improved"] = (result["sanitation"].astype(str) == "IMPROVED").astype(float)
    result["electricity"] = result["electricity"].astype(float)
    result["urban"] = (result["urban_rural"].astype(str) == "URBAN").astype(float)
    result["minimum_diet_diversity"] = result["minimum_diet_diversity"].astype(float)
    result["vaccination_complete"] = result["vaccination_complete"].astype(float)
    result["diarrhea_14d"] = result["diarrhea_14d"].astype(float)
    result["fever_14d"] = result["fever_14d"].astype(float)
    area = result["area_km2"].replace(0, np.nan)
    result["population_density"] = np.log1p(
        (result["population_u5"].astype(float) / area).fillna(0).clip(lower=0)
    )
    result["maternal_age"] = result["maternal_age"].fillna(result["maternal_age"].median() if result["maternal_age"].notna().any() else 27)
    result["birth_weight_g"] = result["birth_weight_g"].fillna(
        result["birth_weight_g"].median() if result["birth_weight_g"].notna().any() else 3200
    )
    result["breastfeeding_months"] = result["breastfeeding_months"].fillna(
        result["breastfeeding_months"].median() if result["breastfeeding_months"].notna().any() else 9
    )
    for feature in FEATURES:
        if feature not in result.columns:
            result[feature] = 0.0
        result[feature] = pd.to_numeric(result[feature], errors="coerce").fillna(0.0).astype(float)
    return result


def add_spatial_features(db: Session, frame: pd.DataFrame) -> pd.DataFrame:
    """Attach neighbour-territory averages (spatial lags) for the hybrid model."""
    from app.models.data import Territory

    result = frame.copy()
    rows = db.execute(
        select(Territory.code, Territory.neighbor_codes, Territory.water_coverage, Territory.sanitation_coverage,
               Territory.food_insecurity_index, Territory.population_u5, Territory.area_km2)
    ).all()
    territory_table = {
        code: {
            "neighbors": list(neighbors or []),
            "water_coverage": water,
            "sanitation_coverage": sanitation,
            "food_insecurity": food,
            "population_u5": population,
            "area_km2": area,
        }
        for code, neighbors, water, sanitation, food, population, area in rows
    }
    wealth_by_territory = frame.groupby("territory_code")["wealth_quintile"].mean().to_dict()
    lag_wealth: dict[str, float] = {}
    lag_water: dict[str, float] = {}
    lag_sanitation: dict[str, float] = {}
    lag_food: dict[str, float] = {}
    for code, info in territory_table.items():
        neighbors = [neighbor for neighbor in info["neighbors"] if neighbor in territory_table]
        if not neighbors:
            lag_wealth[code] = wealth_by_territory.get(code, 3.0)
            lag_water[code] = info["water_coverage"] or 0.5
            lag_sanitation[code] = info["sanitation_coverage"] or 0.5
            lag_food[code] = info["food_insecurity"] or 0.5
            continue
        lag_wealth[code] = float(np.mean([wealth_by_territory.get(neighbor, 3.0) for neighbor in neighbors]))
        lag_water[code] = float(np.mean([territory_table[neighbor]["water_coverage"] or 0.5 for neighbor in neighbors]))
        lag_sanitation[code] = float(
            np.mean([territory_table[neighbor]["sanitation_coverage"] or 0.5 for neighbor in neighbors])
        )
        lag_food[code] = float(np.mean([territory_table[neighbor]["food_insecurity"] or 0.5 for neighbor in neighbors]))

    codes = result["territory_code"].astype(str)
    result["neighbor_wealth"] = codes.map(lag_wealth).astype(float)
    result["neighbor_water_coverage"] = codes.map(lag_water).astype(float)
    result["neighbor_sanitation_coverage"] = codes.map(lag_sanitation).astype(float)
    result["neighbor_food_insecurity"] = codes.map(lag_food).astype(float)
    for feature in SPATIAL_FEATURES:
        result[feature] = pd.to_numeric(result[feature], errors="coerce").fillna(0.0).astype(float)
    return result


def feature_matrix(frame: pd.DataFrame, features: list[str] | None = None) -> pd.DataFrame:
    """Return the model matrix with a stable feature order."""
    data = add_features(frame)
    columns = list(features) if features else list(FEATURES)
    return data[columns]


def target_series(frame: pd.DataFrame, target: str) -> pd.Series:
    if target not in frame.columns:
        raise ValueError(f"Target desconocido: {target}")
    if target in ("stunting", "wasting", "underweight", "overweight"):
        return frame[target].astype(int)
    return pd.to_numeric(frame[target], errors="coerce")


def dataset_summary(frame: pd.DataFrame) -> dict[str, Any]:
    """Small descriptive summary used by the UI and the agent."""
    if frame.empty:
        return {"rows": 0}
    return {
        "rows": int(len(frame)),
        "children": int(frame["child_id"].nunique()),
        "territories": int(frame["territory_code"].nunique()),
        "regions": sorted(frame["region"].dropna().unique().tolist()),
        "years": sorted(int(year) for year in frame["period_year"].dropna().unique()),
        "stunting_prevalence": round(float(frame["stunting"].mean()), 4),
        "wasting_prevalence": round(float(frame["wasting"].mean()), 4),
        "underweight_prevalence": round(float(frame["underweight"].mean()), 4),
        "mean_haz": round(float(frame["haz"].mean()), 4),
    }

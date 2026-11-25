"""Synthetic demo data generator (clearly labelled SYNTHETIC).

The generator fabricates a fictional country ("República de Andara") partitioned
into 24 hexagonal territories across 5 regions. Anthropometric measurements are
drawn *through the WHO 2006 LMS curves* so the resulting z-scores are internally
consistent with the official standards, while the underlying risk model uses the
same socioeconomic, WASH and environmental determinants that the ML pipeline sees.

No real prevalence, population or place is represented here.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.services.anthropometry import load_reference

SEED = 42
YEARS = (2021, 2022, 2023)
CHILDREN_PER_TERRITORY_YEAR = 200
HEX_RADIUS = 0.55
GRID_COLS = 6
GRID_ROWS = 4

REGIONS: dict[str, dict[str, Any]] = {
    "Norte": {
        "altitude": (200, 900),
        "rainfall": (380, 650),
        "temperature": (27, 32),
        "ndvi": (0.28, 0.45),
        "food_insecurity": (0.55, 0.78),
        "water": (0.48, 0.68),
        "sanitation": (0.35, 0.58),
        "wealth": -0.65,
        "urban_share": 0.35,
        "risk": 0.75,
    },
    "Centro": {
        "altitude": (900, 1800),
        "rainfall": (900, 1400),
        "temperature": (19, 24),
        "ndvi": (0.50, 0.68),
        "food_insecurity": (0.22, 0.40),
        "water": (0.78, 0.93),
        "sanitation": (0.70, 0.88),
        "wealth": 0.35,
        "urban_share": 0.72,
        "risk": -0.35,
    },
    "Sur": {
        "altitude": (2400, 3600),
        "rainfall": (500, 800),
        "temperature": (10, 15),
        "ndvi": (0.35, 0.52),
        "food_insecurity": (0.38, 0.58),
        "water": (0.62, 0.80),
        "sanitation": (0.50, 0.72),
        "wealth": -0.10,
        "urban_share": 0.48,
        "risk": 0.20,
    },
    "Oriente": {
        "altitude": (120, 500),
        "rainfall": (1800, 2800),
        "temperature": (25, 30),
        "ndvi": (0.62, 0.82),
        "food_insecurity": (0.42, 0.62),
        "water": (0.55, 0.75),
        "sanitation": (0.30, 0.55),
        "wealth": -0.40,
        "urban_share": 0.30,
        "risk": 0.45,
    },
    "Occidente": {
        "altitude": (600, 1500),
        "rainfall": (700, 1100),
        "temperature": (21, 26),
        "ndvi": (0.44, 0.62),
        "food_insecurity": (0.30, 0.50),
        "water": (0.70, 0.86),
        "sanitation": (0.58, 0.78),
        "wealth": 0.05,
        "urban_share": 0.55,
        "risk": 0.0,
    },
}

NAME_ROOTS = [
    "Valle", "Sierra", "Loma", "Costa", "Río", "Monte", "Llano", "Pampa",
    "Campo", "Alta", "Bajo", "Puerto", "Cañón", "Sabana", "Cumbre", "Vega",
    "Tierra", "Bosque", "Marisma", "Quebrada", "Altiplano", "Ribera", "Mesa", "Cruz",
]
NAME_SUFFIXES = [
    "Verde", "Claro", "Nuevo", "Hondo", "Grande", "Florido", "Serrano", "Central",
    "del Sol", "de Agua", "Alto", "Bonito", "Fértil", "del Este", "Real", "Pacífico",
    "Andino", "Tropical", "del Valle", "Escondido", "Dorado", "del Norte", "Austral", "Unido",
]

CLIMATE_BY_REGION = {
    "Norte": "Árido cálido",
    "Centro": "Templado subhúmedo",
    "Sur": "Altiplano frío",
    "Oriente": "Tropical húmedo",
    "Occidente": "Templado húmedo",
}

# --------------------------------------------------------------------------- #
# Calibrated latent growth coefficients (z-score units, synthetic country).
# Chosen so the demo reproduces WHO-documented prevalence ranges: stunting ~20 %,
# wasting ~7 %, underweight ~14 %, with 6-35 % variation across territories.
# --------------------------------------------------------------------------- #
HAZ_INTERCEPT = -1.05
HAZ_TERRITORY = -0.60
HAZ_ENV_SCALE = 0.95
HAZ_WEALTH = 0.55
HAZ_EDUCATION = 0.40
HAZ_WATER = 0.24
HAZ_SANITATION = 0.22
HAZ_DIET = 0.32
HAZ_VACCINATION = 0.18
HAZ_DIARRHEA = -0.28
HAZ_TEEN_MOTHER = -0.12

WAZ_INTERCEPT = -0.70
WAZ_TERRITORY = -0.35
WAZ_ENV_SCALE = 0.80
WAZ_WEALTH = 0.45
WAZ_EDUCATION = 0.30
WAZ_WATER = 0.20
WAZ_SANITATION = 0.18
WAZ_DIET = 0.28
WAZ_VACCINATION = 0.14
WAZ_DIARRHEA = -0.30
WAZ_FEVER = -0.16
ACUTE_SD = 0.22
BETA_HAZ_WAZ = 0.50


@dataclass
class TerritoryProfile:
    code: str
    name: str
    region: str
    col: int
    row: int
    latitude: float
    longitude: float
    population: int
    population_u5: int
    area_km2: float
    altitude_m: float
    rainfall_mm: float
    temperature_c: float
    ndvi: float
    food_insecurity_index: float
    water_coverage: float
    sanitation_coverage: float
    wealth_level: float
    urban_share: float
    risk_latent: float
    geometry: dict[str, Any]
    neighbors: list[str]

    def properties(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "region": self.region,
            "level": "DEPARTMENT",
            "parent_code": None,
            "urban_rural": "MIXED",
            "population": self.population,
            "population_u5": self.population_u5,
            "area_km2": round(self.area_km2, 1),
            "altitude_m": round(self.altitude_m, 0),
            "climate_zone": CLIMATE_BY_REGION[self.region],
            "rainfall_mm": round(self.rainfall_mm, 0),
            "temperature_c": round(self.temperature_c, 1),
            "ndvi": round(self.ndvi, 3),
            "food_insecurity_index": round(self.food_insecurity_index, 3),
            "water_coverage": round(self.water_coverage, 3),
            "sanitation_coverage": round(self.sanitation_coverage, 3),
            "latitude": round(self.latitude, 4),
            "longitude": round(self.longitude, 4),
            "neighbor_codes": self.neighbors,
            "is_synthetic": True,
        }


def _hexagon(lon: float, lat: float, radius: float) -> dict[str, Any]:
    points = []
    for index in range(6):
        angle = math.radians(60 * index)
        points.append([round(lon + radius * math.cos(angle), 5), round(lat + radius * math.sin(angle), 5)])
    points.append(points[0])
    return {"type": "Polygon", "coordinates": [points]}


def _spherical_area_km2(coords: list[list[float]]) -> float:
    """Approximate polygon area on the sphere (km²)."""
    radius = 6371.0088
    total = 0.0
    for i in range(len(coords) - 1):
        lon1, lat1 = map(math.radians, coords[i])
        lon2, lat2 = map(math.radians, coords[i + 1])
        total += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
    return abs(total * radius * radius / 2.0)


def _region_for(row: int, col: int) -> str:
    if row == 0:
        return "Norte"
    if row == 1:
        return "Centro"
    if row == 2:
        return "Sur"
    return "Occidente" if col <= 2 else "Oriente"


def build_territories(seed: int = SEED) -> list[TerritoryProfile]:
    """Deterministically build the 24 synthetic territories with hex footprints."""
    rng = np.random.default_rng(seed)
    lat0, lon0 = 3.2, -76.4
    profiles: list[TerritoryProfile] = []
    index = 0
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            index += 1
            region = _region_for(row, col)
            cfg = REGIONS[region]
            lon = lon0 + col * 1.5 * HEX_RADIUS
            lat = lat0 + row * math.sqrt(3) * HEX_RADIUS + (col % 2) * math.sqrt(3) * HEX_RADIUS / 2
            name = f"{NAME_ROOTS[(index - 1) % len(NAME_ROOTS)]} {NAME_SUFFIXES[(index - 1) % len(NAME_SUFFIXES)]}"
            population = int(rng.integers(70_000, 780_000) * (1.0 if region != "Centro" else 1.35))
            geometry = _hexagon(lon, lat, HEX_RADIUS)
            area = _spherical_area_km2(geometry["coordinates"][0])
            altitude = float(rng.uniform(*cfg["altitude"]))
            territory = TerritoryProfile(
                code=f"T{index:02d}",
                name=name,
                region=region,
                col=col,
                row=row,
                latitude=lat,
                longitude=lon,
                population=population,
                population_u5=int(population * float(rng.uniform(0.085, 0.115))),
                area_km2=area,
                altitude_m=altitude,
                rainfall_mm=float(rng.uniform(*cfg["rainfall"])),
                temperature_c=float(rng.uniform(*cfg["temperature"])) - altitude / 900.0,
                ndvi=float(rng.uniform(*cfg["ndvi"])),
                food_insecurity_index=float(rng.uniform(*cfg["food_insecurity"])),
                water_coverage=float(rng.uniform(*cfg["water"])),
                sanitation_coverage=float(rng.uniform(*cfg["sanitation"])),
                wealth_level=cfg["wealth"] + float(rng.normal(0, 0.22)),
                urban_share=float(np.clip(cfg["urban_share"] + rng.normal(0, 0.07), 0.12, 0.9)),
                risk_latent=cfg["risk"] + float(rng.normal(0, 0.22)),
                geometry=geometry,
                neighbors=[],
            )
            profiles.append(territory)

    # Adjacency: nearest hexagon centres (flat-top hex grid has 6 neighbours).
    distances: list[tuple[float, str, str]] = []
    for i, left in enumerate(profiles):
        for right in profiles[i + 1 :]:
            distance = math.hypot(left.longitude - right.longitude, left.latitude - right.latitude)
            distances.append((distance, left.code, right.code))
    minimum = min(distance for distance, _, _ in distances)
    by_code = {profile.code: profile for profile in profiles}
    for distance, code_a, code_b in distances:
        if distance <= minimum * 1.05:
            by_code[code_a].neighbors.append(code_b)
            by_code[code_b].neighbors.append(code_a)
    for profile in profiles:
        profile.neighbors.sort()
    return profiles


def territories_geojson(profiles: list[TerritoryProfile]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "name": "andara_departments_synthetic",
        "features": [
            {"type": "Feature", "id": profile.code, "geometry": profile.geometry, "properties": profile.properties()}
            for profile in profiles
        ],
    }


EDUCATION_LEVELS = ["NONE", "PRIMARY", "SECONDARY", "TERTIARY"]
EDUCATION_WEIGHTS = {
    "NONE": [0.24, 0.15, 0.07, 0.02, 0.01],
    "PRIMARY": [0.52, 0.45, 0.31, 0.18, 0.08],
    "SECONDARY": [0.20, 0.32, 0.42, 0.40, 0.25],
    "TERTIARY": [0.04, 0.08, 0.20, 0.40, 0.66],
}
WATER_SOURCES = ["PIPED", "IMPROVED", "UNIMPROVED", "SURFACE"]
SANITATION_TYPES = ["IMPROVED", "SHARED", "UNIMPROVED", "OPEN"]
COOKING_FUELS = ["GAS", "ELECTRICITY", "KEROSENE", "WOOD", "CHARCOAL"]


def _ordered_category(probs: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Sample one category per row from a (n, k) probability matrix."""
    cumulative = np.cumsum(probs, axis=1)
    draws = rng.random((probs.shape[0], 1))
    return (draws > cumulative).sum(axis=1)


def _invert_lms(measure_type: str, table: dict[str, dict[str, float]], z: np.ndarray) -> np.ndarray:
    """Invert the LMS equation to obtain a measurement from a target z-score."""
    l_values = np.fromiter((table[key]["L"] for key in table), dtype=float)
    m = np.fromiter((table[key]["M"] for key in table), dtype=float)
    s = np.fromiter((table[key]["S"] for key in table), dtype=float)
    if measure_type == "height":
        return m * (1.0 + l_values * s * z) ** (1.0 / np.where(np.abs(l_values) < 1e-9, 1.0, l_values))
    safe_l = np.where(np.abs(l_values) < 1e-9, 1e-9, l_values)
    return m * np.power(np.maximum(1.0 + safe_l * s * z, 0.05), 1.0 / safe_l)


def generate_children(
    profiles: list[TerritoryProfile],
    *,
    years: tuple[int, ...] = YEARS,
    per_territory_year: int = CHILDREN_PER_TERRITORY_YEAR,
    seed: int = SEED,
) -> pd.DataFrame:
    """Generate a DHS-like flat child table using the WHO curves."""
    rng = np.random.default_rng(seed + 7)
    reference = load_reference()
    rows: list[dict[str, Any]] = []

    for year in years:
        year_trend = (year - 2021) * 0.035  # slow national improvement
        year_shock = {2021: 0.0, 2022: -0.10, 2023: 0.04}.get(year, 0.0)
        for profile in profiles:
            n = per_territory_year
            ages = rng.integers(0, 60, size=n)
            sexes = rng.choice(["M", "F"], size=n)
            urban = rng.random(n) < profile.urban_share

            wealth_score = (
                profile.wealth_level
                + np.where(urban, 0.35, -0.2)
                + rng.normal(0, 0.75, size=n)
            )
            wealth_quintile = np.clip(
                np.digitize(wealth_score, np.quantile(wealth_score, [0.2, 0.4, 0.6, 0.8])) + 1, 1, 5
            )
            education_probs = np.zeros((n, len(EDUCATION_LEVELS)))
            for level_index, level in enumerate(EDUCATION_LEVELS):
                base = np.array(EDUCATION_WEIGHTS[level])
                education_probs[:, level_index] = base[wealth_quintile - 1]
            education_probs /= education_probs.sum(axis=1, keepdims=True)
            education = _ordered_category(education_probs, rng)
            maternal_age = np.clip(rng.normal(27.5, 5.6, size=n), 15, 46).round()
            household_size = np.clip(rng.poisson(4.6, size=n), 1, 14)
            assets_count = np.clip(rng.poisson(wealth_quintile * 1.5, size=n), 0, 12)

            water_score = profile.water_coverage + np.where(urban, 0.14, -0.12) + (wealth_quintile - 3) * 0.05
            water_random = rng.random(n)
            water_source = np.where(
                water_random < np.clip(water_score - 0.25, 0.05, 0.95),
                "PIPED",
                np.where(
                    water_random < np.clip(water_score, 0.15, 0.97),
                    "IMPROVED",
                    np.where(water_random < 0.93, "UNIMPROVED", "SURFACE"),
                ),
            )
            sanitation_score = (
                profile.sanitation_coverage + np.where(urban, 0.12, -0.10) + (wealth_quintile - 3) * 0.06
            )
            sanitation_random = rng.random(n)
            sanitation = np.where(
                sanitation_random < np.clip(sanitation_score - 0.3, 0.05, 0.9),
                "IMPROVED",
                np.where(
                    sanitation_random < np.clip(sanitation_score, 0.15, 0.92),
                    "SHARED",
                    np.where(sanitation_random < 0.94, "UNIMPROVED", "OPEN"),
                ),
            )
            electricity = rng.random(n) < np.clip(
                0.35 + wealth_quintile * 0.11 + np.where(urban, 0.2, 0.0), 0.1, 0.98
            )
            cooking_fuel = np.where(
                electricity & (wealth_quintile >= 4),
                np.where(rng.random(n) < 0.7, "GAS", "ELECTRICITY"),
                np.where(rng.random(n) < 0.55, "WOOD", np.where(rng.random(n) < 0.7, "GAS", "CHARCOAL")),
            )

            water_improved = np.isin(water_source, ["PIPED", "IMPROVED"]).astype(float)
            sanitation_improved = (sanitation == "IMPROVED").astype(float)
            education_score = education / 3.0
            wealth_centered = (wealth_quintile - 3) / 2.0

            food_insecurity = np.clip(
                profile.food_insecurity_index + rng.normal(0, 0.10, size=n) - wealth_centered * 0.09, 0, 1
            )
            diet_diversity = rng.random(n) < np.clip(
                0.18 + wealth_centered * 0.16 + education_score * 0.1 - food_insecurity * 0.18, 0.03, 0.92
            )
            vaccination = rng.random(n) < np.clip(
                0.55 + education_score * 0.18 + np.where(urban, 0.1, -0.05) - food_insecurity * 0.12, 0.15, 0.97
            )
            diarrhea = rng.random(n) < np.clip(
                0.08 + (1 - water_improved) * 0.12 + (1 - sanitation_improved) * 0.14
                + (1 - diet_diversity) * 0.05 + (1 - vaccination) * 0.04, 0.02, 0.55
            )
            fever = rng.random(n) < np.clip(0.14 + food_insecurity * 0.10 + diarrhea * 0.12, 0.03, 0.5)

            # --- Latent growth model (determinants observable by the ML pipeline) ---
            environmental = (
                -0.55 * (profile.food_insecurity_index - 0.45)
                - 1.10 * (profile.water_coverage - 0.65)
                - 0.85 * (profile.sanitation_coverage - 0.60)
                + 0.55 * (profile.ndvi - 0.5)
                - 0.00022 * (profile.altitude_m - 1200)
                + float(rng.normal(0, 0.10))
            )
            mu_haz = (
                HAZ_INTERCEPT
                + HAZ_TERRITORY * profile.risk_latent
                + HAZ_ENV_SCALE * environmental
                + HAZ_WEALTH * wealth_centered
                + HAZ_EDUCATION * (education_score - 0.45)
                + HAZ_WATER * water_improved
                + HAZ_SANITATION * sanitation_improved
                + HAZ_DIET * diet_diversity.astype(float)
                + HAZ_VACCINATION * vaccination.astype(float)
                + HAZ_DIARRHEA * diarrhea.astype(float)
                + HAZ_TEEN_MOTHER * (maternal_age < 20)
                + year_trend
                + year_shock
            )
            haz_raw = rng.normal(mu_haz, 0.92, size=n)
            haz = np.clip(haz_raw, -4.2, 3.2)

            mu_waz = (
                WAZ_INTERCEPT
                + WAZ_TERRITORY * profile.risk_latent
                + WAZ_ENV_SCALE * environmental
                + WAZ_WEALTH * wealth_centered
                + WAZ_EDUCATION * (education_score - 0.45)
                + WAZ_WATER * water_improved
                + WAZ_SANITATION * sanitation_improved
                + WAZ_DIET * diet_diversity.astype(float)
                + WAZ_VACCINATION * vaccination.astype(float)
                + WAZ_DIARRHEA * diarrhea.astype(float)
                + WAZ_FEVER * fever.astype(float)
                + year_trend
                + year_shock * 0.7
            )
            # Weight residuals inherit part of the height residual: stunted children
            # tend to be lighter, which keeps WHZ variance close to the WHO reference.
            waz = np.clip(
                mu_waz + BETA_HAZ_WAZ * (haz_raw - mu_haz) + rng.normal(0, 0.72, size=n), -4.5, 3.0
            )
            # Independent acute shock so wasting is not a deterministic mirror of HAZ.
            acute = rng.normal(0, ACUTE_SD, size=n)
            waz_effective = np.clip(waz + acute, -4.8, 3.2)

            heights = np.empty(n)
            weights = np.empty(n)
            for month in np.unique(ages):
                mask = ages == month
                for sex in ("M", "F"):
                    sex_mask = mask & (sexes == sex)
                    if not sex_mask.any():
                        continue
                    table_h = reference["hfa"][sex][str(int(month))]
                    table_w = reference["wfa"][sex][str(int(month))]
                    heights[sex_mask] = _invert_lms(
                        "height",
                        {str(month): table_h},
                        haz[sex_mask],
                    )
                    weights[sex_mask] = _invert_lms(
                        "weight",
                        {str(month): table_w},
                        waz_effective[sex_mask],
                    )

            heights = heights + rng.normal(0, 0.28, size=n)
            weights = np.clip(weights + rng.normal(0, 0.12, size=n), 1.6, 32)
            heights = np.clip(heights, 45, 122)

            bmi = weights / np.square(heights / 100.0)
            muac = np.clip(
                13.2 + 0.55 * (weights - np.exp(np.log(weights).mean())) * 0.35 - (bmi < 13) * 0.6
                + rng.normal(0, 0.55, size=n),
                9.0,
                17.5,
            )
            birth_weight = np.clip(
                3250 + 90 * wealth_centered - 120 * (1 - education_score) + rng.normal(0, 420, size=n),
                1200,
                4800,
            )
            edema = rng.random(n) < 0.004
            breastfeeding = np.clip(rng.normal(9.5, 5.5, size=n) - wealth_centered * 0.8, 0, 24).round()

            for i in range(n):
                rows.append(
                    {
                        "child_code": f"CH-{year}-{profile.code}-{i + 1:04d}",
                        "household_code": f"HH-{year}-{profile.code}-{i + 1:05d}",
                        "territory_code": profile.code,
                        "region": profile.region,
                        "period_year": year,
                        "age_months": int(ages[i]),
                        "sex": sexes[i],
                        "weight_kg": round(float(weights[i]), 2),
                        "height_cm": round(float(heights[i]), 1),
                        "muac_cm": round(float(muac[i]), 2),
                        "edema": bool(edema[i]),
                        "birth_weight_g": int(birth_weight[i]),
                        "breastfeeding_months": int(breastfeeding[i]),
                        "wealth_quintile": int(wealth_quintile[i]),
                        "wealth_index": round(float(wealth_score[i]), 3),
                        "maternal_education": EDUCATION_LEVELS[int(education[i])],
                        "maternal_age": int(maternal_age[i]),
                        "water_source": str(water_source[i]),
                        "sanitation": str(sanitation[i]),
                        "electricity": bool(electricity[i]),
                        "cooking_fuel": str(cooking_fuel[i]),
                        "assets_count": int(assets_count[i]),
                        "household_size": int(household_size[i]),
                        "food_insecurity_score": round(float(food_insecurity[i]), 3),
                        "urban_rural": "URBAN" if urban[i] else "RURAL",
                        "minimum_diet_diversity": bool(diet_diversity[i]),
                        "vaccination_complete": bool(vaccination[i]),
                        "diarrhea_14d": bool(diarrhea[i]),
                        "fever_14d": bool(fever[i]),
                        "altitude_m": round(profile.altitude_m, 0),
                        "rainfall_mm": round(profile.rainfall_mm, 0),
                        "temperature_c": round(profile.temperature_c, 1),
                        "ndvi": round(profile.ndvi, 3),
                    }
                )

    frame = pd.DataFrame(rows)
    return frame


VARIABLE_DICTIONARY: list[dict[str, Any]] = [
    {
        "name": "child_code",
        "label": "Identificador del niño",
        "dtype": "string",
        "description": "Código sintético único del niño (seudonimizado).",
        "is_required": True,
        "is_identifier": True,
    },
    {
        "name": "household_code",
        "label": "Identificador del hogar",
        "dtype": "string",
        "description": "Código sintético del hogar.",
        "is_required": True,
        "is_identifier": True,
    },
    {
        "name": "territory_code",
        "label": "Código de territorio",
        "dtype": "string",
        "description": "Departamento sintético (T01-T24).",
        "is_required": True,
    },
    {"name": "region", "label": "Región", "dtype": "string", "description": "Región administrativa sintética.", "is_required": True},
    {"name": "period_year", "label": "Año del levantamiento", "dtype": "integer", "unit": "año", "description": "Año de la encuesta.", "is_required": True, "min_value": 1990, "max_value": 2100},
    {"name": "age_months", "label": "Edad en meses", "dtype": "integer", "unit": "meses", "description": "Edad del niño al momento de la medición (0-59).", "is_required": True, "min_value": 0, "max_value": 59},
    {"name": "sex", "label": "Sexo", "dtype": "category", "description": "M = masculino, F = femenino.", "is_required": True, "allowed_values": ["M", "F"]},
    {"name": "weight_kg", "label": "Peso", "dtype": "float", "unit": "kg", "description": "Peso medido en kilogramos.", "is_required": True, "min_value": 1.0, "max_value": 35.0},
    {"name": "height_cm", "label": "Talla / longitud", "dtype": "float", "unit": "cm", "description": "Longitud (<24 m) o talla (>=24 m) en centímetros.", "is_required": True, "min_value": 35.0, "max_value": 130.0},
    {"name": "muac_cm", "label": "Perímetro braquial", "dtype": "float", "unit": "cm", "description": "MUAC en centímetros.", "min_value": 9.0, "max_value": 20.0},
    {"name": "edema", "label": "Edema bilateral", "dtype": "boolean", "description": "Presencia de edema bilateral.", "is_required": False},
    {"name": "birth_weight_g", "label": "Peso al nacer", "dtype": "float", "unit": "g", "description": "Peso al nacer en gramos.", "min_value": 500, "max_value": 6000},
    {"name": "breastfeeding_months", "label": "Meses de lactancia", "dtype": "integer", "unit": "meses", "description": "Duración de lactancia materna.", "min_value": 0, "max_value": 36},
    {"name": "wealth_quintile", "label": "Quintil de riqueza", "dtype": "integer", "description": "1 = más pobre, 5 = más rico.", "is_required": True, "min_value": 1, "max_value": 5},
    {"name": "wealth_index", "label": "Índice de riqueza", "dtype": "float", "description": "Índice continuo de riqueza del hogar."},
    {"name": "maternal_education", "label": "Educación materna", "dtype": "category", "description": "Nivel educativo de la madre.", "is_required": True, "allowed_values": EDUCATION_LEVELS},
    {"name": "maternal_age", "label": "Edad materna", "dtype": "integer", "unit": "años", "min_value": 12, "max_value": 55},
    {"name": "water_source", "label": "Fuente de agua", "dtype": "category", "description": "Fuente principal de agua del hogar.", "is_required": True, "allowed_values": WATER_SOURCES},
    {"name": "sanitation", "label": "Saneamiento", "dtype": "category", "description": "Tipo de saneamiento del hogar.", "is_required": True, "allowed_values": SANITATION_TYPES},
    {"name": "electricity", "label": "Electricidad", "dtype": "boolean", "description": "Acceso a electricidad."},
    {"name": "cooking_fuel", "label": "Combustible de cocina", "dtype": "category", "description": "Combustible principal para cocinar.", "allowed_values": COOKING_FUELS},
    {"name": "assets_count", "label": "Activos del hogar", "dtype": "integer", "description": "Número de activos durables."},
    {"name": "household_size", "label": "Tamaño del hogar", "dtype": "integer", "unit": "personas", "description": "Número de miembros del hogar."},
    {"name": "food_insecurity_score", "label": "Inseguridad alimentaria", "dtype": "float", "description": "Escala 0-1 de inseguridad alimentaria del hogar.", "min_value": 0.0, "max_value": 1.0},
    {"name": "urban_rural", "label": "Área", "dtype": "category", "description": "URBAN o RURAL.", "allowed_values": ["URBAN", "RURAL"]},
    {"name": "minimum_diet_diversity", "label": "Dieta mínima diversa", "dtype": "boolean", "description": "Cumple diversidad dietética mínima."},
    {"name": "vaccination_complete", "label": "Vacunación completa", "dtype": "boolean", "description": "Esquema de vacunación completo para la edad."},
    {"name": "diarrhea_14d", "label": "Diarrea (14 días)", "dtype": "boolean", "description": "Episodio de diarrea en las últimas 2 semanas."},
    {"name": "fever_14d", "label": "Fiebre (14 días)", "dtype": "boolean", "description": "Episodio de fiebre en las últimas 2 semanas."},
    {"name": "altitude_m", "label": "Altitud", "dtype": "float", "unit": "m", "description": "Altitud del territorio."},
    {"name": "rainfall_mm", "label": "Precipitación", "dtype": "float", "unit": "mm/año", "description": "Precipitación media anual."},
    {"name": "temperature_c", "label": "Temperatura", "dtype": "float", "unit": "°C", "description": "Temperatura media anual."},
    {"name": "ndvi", "label": "NDVI", "dtype": "float", "description": "Índice de vegetación (0-1).", "min_value": 0.0, "max_value": 1.0},
]


def write_artifacts(out_dir: Path, seed: int = SEED) -> dict[str, Any]:
    """Generate the synthetic artefacts and return a manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    profiles = build_territories(seed)
    geojson = territories_geojson(profiles)
    (out_dir / "territories.geojson").write_text(json.dumps(geojson, ensure_ascii=False, indent=1), encoding="utf-8")

    frame = generate_children(profiles, seed=seed)
    frame.to_csv(out_dir / "children_synthetic.csv", index=False, encoding="utf-8")

    territories_frame = pd.DataFrame([profile.properties() for profile in profiles])
    territories_frame.to_csv(out_dir / "territories_synthetic.csv", index=False, encoding="utf-8")

    dictionary = {
        "dataset": "andara_child_survey_synthetic",
        "source": "SYNTHETIC",
        "note": "Datos completamente sintéticos generados para demostración. No representan prevalencias reales.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "years": list(YEARS),
        "rows": int(len(frame)),
        "variables": VARIABLE_DICTIONARY,
    }
    (out_dir / "dataset_dictionary.json").write_text(json.dumps(dictionary, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "seed": seed,
        "years": list(YEARS),
        "territories": len(profiles),
        "children": int(len(frame)),
        "files": ["territories.geojson", "children_synthetic.csv", "territories_synthetic.csv", "dataset_dictionary.json"],
        "generated_at": dictionary["generated_at"],
        "run_id": uuid.uuid4().hex[:12],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[3] / "data" / "synthetic"
    print(json.dumps(write_artifacts(target), indent=2))






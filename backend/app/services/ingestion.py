"""Dataset ingestion: file parsing, schema validation, quality control and loading.

Supports CSV, Excel and Parquet with DHS-like flat child tables. Column names are
normalised to the canonical model and validated against the variable dictionary.
"""

from __future__ import annotations

import hashlib
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.models.data import AnthropometricIndicator, Child, Dataset, Household, IngestionRun, Territory, VariableDefinition
from app.services.anthropometry import AnthropometryError, compute_indicators

SUPPORTED_EXTENSIONS = {".csv": "CSV", ".txt": "CSV", ".xlsx": "XLSX", ".xls": "XLSX", ".parquet": "PARQUET"}

COLUMN_ALIASES: dict[str, str] = {
    # identifiers
    "child_id": "child_code", "childid": "child_code", "codigo_nino": "child_code", "id_nino": "child_code",
    "caseid": "child_code", "case_id": "child_code",
    "household_id": "household_code", "householdid": "household_code", "id_hogar": "household_code",
    "hhid": "household_code", "hh_id": "household_code",
    "territory": "territory_code", "territory_id": "territory_code", "department": "territory_code",
    "departamento": "territory_code", "codigo_departamento": "territory_code", "dpto": "territory_code",
    "region_name": "region", "region": "region",
    "year": "period_year", "anio": "period_year", "survey_year": "period_year", "periodo": "period_year",
    "surveyid": "survey_id",
    # child
    "age": "age_months", "edad": "age_months", "edad_meses": "age_months", "agem": "age_months",
    "age_month": "age_months", "age_in_months": "age_months",
    "gender": "sex", "sexo": "sex", "sex": "sex",
    "weight": "weight_kg", "peso": "weight_kg", "peso_kg": "weight_kg", "weight_kg": "weight_kg",
    "weight_kilograms": "weight_kg",
    "height": "height_cm", "talla": "height_cm", "talla_cm": "height_cm", "height_cm": "height_cm",
    "length_cm": "height_cm", "longitud_cm": "height_cm", "stature": "height_cm",
    "muac": "muac_cm", "perimetro_braquial": "muac_cm", "muac_cm": "muac_cm",
    "edema": "edema", "edema_bilateral": "edema",
    "birth_weight": "birth_weight_g", "peso_nacer": "birth_weight_g", "birth_weight_g": "birth_weight_g",
    "breastfeeding": "breastfeeding_months", "lactancia": "breastfeeding_months",
    "minimum_diet_diversity": "minimum_diet_diversity", "diet_diversity": "minimum_diet_diversity",
    "diversidad_dietetica": "minimum_diet_diversity",
    "vaccination_complete": "vaccination_complete", "vacunacion_completa": "vaccination_complete",
    "diarrhea": "diarrhea_14d", "diarrea": "diarrhea_14d", "diarrhea_14d": "diarrhea_14d",
    "fever": "fever_14d", "fiebre": "fever_14d", "fever_14d": "fever_14d",
    # household / socioeconomic
    "wealth": "wealth_quintile", "wealth_quintile": "wealth_quintile", "quintil_riqueza": "wealth_quintile",
    "wealth_index": "wealth_index", "indice_riqueza": "wealth_index",
    "mother_education": "maternal_education", "maternal_education": "maternal_education",
    "educacion_materna": "maternal_education", "mother_edu": "maternal_education",
    "maternal_age": "maternal_age", "edad_madre": "maternal_age",
    "water": "water_source", "water_source": "water_source", "fuente_agua": "water_source",
    "sanitation": "sanitation", "saneamiento": "sanitation",
    "electricity": "electricity", "electricidad": "electricity",
    "cooking_fuel": "cooking_fuel", "combustible": "cooking_fuel",
    "assets": "assets_count", "assets_count": "assets_count", "activos": "assets_count",
    "household_size": "household_size", "tamano_hogar": "household_size", "hh_size": "household_size",
    "food_insecurity": "food_insecurity_score", "food_insecurity_score": "food_insecurity_score",
    "inseguridad_alimentaria": "food_insecurity_score",
    "urban_rural": "urban_rural", "area": "urban_rural", "residence": "urban_rural",
    # environment (territory level)
    "altitude": "altitude_m", "altitud": "altitude_m", "altitude_m": "altitude_m",
    "rainfall": "rainfall_mm", "precipitacion": "rainfall_mm", "rainfall_mm": "rainfall_mm",
    "temperature": "temperature_c", "temperatura": "temperature_c", "temperature_c": "temperature_c",
    "ndvi": "ndvi",
}

REQUIRED_COLUMNS: dict[str, list[str]] = {
    "CHILD": ["age_months", "sex", "weight_kg", "height_cm"],
    "HOUSEHOLD": ["household_code", "wealth_quintile"],
    "TERRITORY": ["territory_code"],
    "MIXED": ["age_months", "sex", "weight_kg", "height_cm"],
}

NUMERIC_RANGES: dict[str, tuple[float, float]] = {
    "age_months": (0, 60),
    "weight_kg": (1.0, 35.0),
    "height_cm": (35.0, 130.0),
    "muac_cm": (9.0, 20.0),
    "wealth_quintile": (1, 5),
    "maternal_age": (12, 55),
    "household_size": (1, 30),
    "assets_count": (0, 30),
    "food_insecurity_score": (0.0, 1.0),
    "ndvi": (0.0, 1.0),
    "period_year": (1990, 2100),
    "birth_weight_g": (500, 6000),
}

BOOL_COLUMNS = {"edema", "electricity", "minimum_diet_diversity", "vaccination_complete", "diarrhea_14d", "fever_14d"}
INT_COLUMNS = {"age_months", "wealth_quintile", "maternal_age", "household_size", "assets_count", "period_year", "breastfeeding_months"}
FLOAT_COLUMNS = {
    "weight_kg", "height_cm", "muac_cm", "birth_weight_g", "wealth_index", "food_insecurity_score",
    "altitude_m", "rainfall_mm", "temperature_c", "ndvi",
}
CATEGORY_COLUMNS = {"sex", "maternal_education", "water_source", "sanitation", "urban_rural", "cooking_fuel"}

SEX_MAP = {"m": "M", "male": "M", "masculino": "M", "h": "M", "hombre": "M", "1": "M",
           "f": "F", "female": "F", "femenino": "F", "mujer": "F", "2": "F"}
EDUCATION_MAP = {
    "none": "NONE", "ninguna": "NONE", "sin educacion": "NONE", "sin educación": "NONE", "0": "NONE",
    "primary": "PRIMARY", "primaria": "PRIMARY", "1": "PRIMARY",
    "secondary": "SECONDARY", "secundaria": "SECONDARY", "2": "SECONDARY",
    "tertiary": "TERTIARY", "superior": "TERTIARY", "universidad": "TERTIARY", "3": "TERTIARY",
}
WATER_MAP = {
    "piped": "PIPED", "tuberia": "PIPED", "tubería": "PIPED", "red publica": "PIPED", "red pública": "PIPED",
    "improved": "IMPROVED", "mejorada": "IMPROVED", "pozo": "IMPROVED", "well": "IMPROVED",
    "unimproved": "UNIMPROVED", "no mejorada": "UNIMPROVED", "carro": "UNIMPROVED",
    "surface": "SURFACE", "superficial": "SURFACE", "rio": "SURFACE", "río": "SURFACE",
}
SANITATION_MAP = {
    "improved": "IMPROVED", "mejorado": "IMPROVED", "alcantarillado": "IMPROVED", "inodoro": "IMPROVED",
    "shared": "SHARED", "compartido": "SHARED", "letrina compartida": "SHARED",
    "unimproved": "UNIMPROVED", "no mejorado": "UNIMPROVED", "letrina": "UNIMPROVED",
    "open": "OPEN", "aire libre": "OPEN", "campo abierto": "OPEN",
}
URBAN_MAP = {"urban": "URBAN", "urbano": "URBAN", "u": "URBAN", "1": "URBAN",
             "rural": "RURAL", "r": "RURAL", "2": "RURAL"}
TRUTHY = {"true", "1", "yes", "si", "sí", "y", "t", "verdadero"}
FALSY = {"false", "0", "no", "n", "f", "falso"}


class IngestionError(ValueError):
    """Raised when a file cannot be ingested."""


@dataclass
class IngestionOutcome:
    dataset: Dataset
    run: IngestionRun
    preview: list[dict[str, Any]] = field(default_factory=list)
    quality: dict[str, Any] = field(default_factory=dict)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_format(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise IngestionError(f"Formato no soportado: {suffix}. Use CSV, XLSX o Parquet.")
    return SUPPORTED_EXTENSIONS[suffix]


def read_table(path: Path, fmt: str) -> pd.DataFrame:
    """Read a dataset file into a DataFrame."""
    try:
        if fmt == "CSV":
            try:
                return pd.read_csv(path, encoding="utf-8")
            except UnicodeDecodeError:
                return pd.read_csv(path, encoding="latin-1")
        if fmt == "XLSX":
            return pd.read_excel(path)
        if fmt == "PARQUET":
            return pd.read_parquet(path)
    except Exception as exc:  # noqa: BLE001
        raise IngestionError(f"No se pudo leer el archivo: {exc}") from exc
    raise IngestionError(f"Formato no soportado: {fmt}")


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Lowercase/slugify headers and map known aliases to canonical names."""
    renamed: dict[str, str] = {}
    for column in frame.columns:
        key = slugify(str(column))
        renamed[column] = COLUMN_ALIASES.get(key, COLUMN_ALIASES.get(key.replace("_", ""), key))
    result = frame.rename(columns=renamed)
    # Drop exact duplicate canonical columns (keep the first).
    result = result.loc[:, ~result.columns.duplicated()]
    return result


def coerce_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Coerce dtypes and collect row-level errors; returns (clean_frame, errors)."""
    errors: list[dict[str, Any]] = []
    result = frame.copy()
    if "period_year" not in result.columns:
        result["period_year"] = datetime.now(timezone.utc).year
    result["period_year"] = pd.to_numeric(result["period_year"], errors="coerce").fillna(
        datetime.now(timezone.utc).year
    ).astype(int)

    if "sex" in result.columns:
        result["sex"] = (
            result["sex"].astype(str).str.strip().str.lower().map(SEX_MAP).fillna(result["sex"].astype(str).str.upper())
        )
    if "maternal_education" in result.columns:
        result["maternal_education"] = (
            result["maternal_education"].astype(str).str.strip().str.lower().map(EDUCATION_MAP)
        )
    if "water_source" in result.columns:
        result["water_source"] = result["water_source"].astype(str).str.strip().str.lower().map(WATER_MAP)
    if "sanitation" in result.columns:
        result["sanitation"] = result["sanitation"].astype(str).str.strip().str.lower().map(SANITATION_MAP)
    if "urban_rural" in result.columns:
        result["urban_rural"] = result["urban_rural"].astype(str).str.strip().str.lower().map(URBAN_MAP)
    for column in BOOL_COLUMNS & set(result.columns):
        result[column] = result[column].map(
            lambda value: True
            if str(value).strip().lower() in TRUTHY
            else (False if str(value).strip().lower() in FALSY else np.nan)
        )
        result[column] = result[column].astype("boolean").fillna(False).astype(bool)
    for column in INT_COLUMNS & set(result.columns):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    for column in FLOAT_COLUMNS & set(result.columns):
        result[column] = pd.to_numeric(result[column], errors="coerce")

    required_numeric = ["age_months", "weight_kg", "height_cm"]
    mask = pd.Series(False, index=result.index)
    for column in required_numeric:
        if column in result.columns:
            mask |= result[column].isna()
    invalid_rows = result[mask]
    for index, row in invalid_rows.head(100).iterrows():
        errors.append(
            {
                "row": int(index) + 2,
                "code": "MISSING_ANTHROPOMETRY",
                "message": "Fila sin edad, peso o talla válidos",
                "child_code": str(row.get("child_code", ""))[:60],
            }
        )
    result = result[~mask].copy()

    if "sex" in result.columns:
        bad_sex = ~result["sex"].isin(["M", "F"])
        if bad_sex.any():
            errors.append(
                {"row": None, "code": "INVALID_SEX", "message": f"{int(bad_sex.sum())} filas con sexo no reconocido"}
            )
            result = result[~bad_sex].copy()
    return result, errors


def build_quality_report(frame: pd.DataFrame, *, kind: str = "CHILD") -> dict[str, Any]:
    """Compute the data-quality report (missingness, duplicates, outliers, ranges)."""
    issues: list[dict[str, Any]] = []
    rows, columns = frame.shape
    duplicates = int(frame.duplicated().sum())
    missing_cells = int(frame.isna().sum().sum())
    missing_ratio = round(missing_cells / max(rows * max(columns, 1), 1), 4)

    column_stats: dict[str, dict[str, Any]] = {}
    outliers = 0
    for column in frame.columns:
        series = frame[column]
        stats: dict[str, Any] = {
            "dtype": str(series.dtype),
            "missing": int(series.isna().sum()),
            "missing_ratio": round(float(series.isna().mean()), 4),
            "unique": int(series.nunique(dropna=True)),
        }
        if pd.api.types.is_bool_dtype(series):
            stats["true_ratio"] = round(float(series.mean()), 4)
        elif pd.api.types.is_numeric_dtype(series):
            valid = series.dropna()
            if not valid.empty:
                stats.update(
                    {
                        "min": round(float(valid.min()), 4),
                        "max": round(float(valid.max()), 4),
                        "mean": round(float(valid.mean()), 4),
                        "median": round(float(valid.median()), 4),
                        "sd": round(float(valid.std(ddof=0)), 4) if len(valid) > 1 else 0.0,
                    }
                )
                q1, q3 = valid.quantile([0.25, 0.75])
                iqr = q3 - q1
                if iqr > 0:
                    column_outliers = int(((valid < q1 - 3 * iqr) | (valid > q3 + 3 * iqr)).sum())
                    stats["outliers"] = column_outliers
                    outliers += column_outliers
                low, high = NUMERIC_RANGES.get(column, (None, None))
                if low is not None and high is not None:
                    invalid = int(((valid < low) | (valid > high)).sum())
                    if invalid:
                        stats["out_of_range"] = invalid
                        severity = "error" if column in ("age_months", "weight_kg", "height_cm") else "warning"
                        issues.append(
                            {
                                "code": "OUT_OF_RANGE",
                                "severity": severity,
                                "message": f"{invalid} valores de '{column}' fuera del rango [{low}, {high}]",
                                "count": invalid,
                                "column": column,
                            }
                        )
        else:
            top = series.astype(str).value_counts().head(5)
            stats["top_values"] = {str(key): int(value) for key, value in top.items()}
        missing = stats["missing"]
        if missing and stats["missing_ratio"] > 0.2:
            issues.append(
                {
                    "code": "HIGH_MISSINGNESS",
                    "severity": "warning",
                    "message": f"'{column}' tiene {stats['missing_ratio'] * 100:.1f}% de valores faltantes",
                    "count": missing,
                    "column": column,
                }
            )
        column_stats[column] = stats

    if duplicates:
        issues.append(
            {"code": "DUPLICATE_ROWS", "severity": "warning", "message": f"{duplicates} filas duplicadas", "count": duplicates}
        )
    identity_column = "child_code" if "child_code" in frame.columns else None
    if identity_column:
        duplicated_ids = int(frame[identity_column].duplicated().sum())
        if duplicated_ids:
            issues.append(
                {
                    "code": "DUPLICATE_IDENTIFIERS",
                    "severity": "error",
                    "message": f"{duplicated_ids} identificadores de niño repetidos",
                    "count": duplicated_ids,
                    "column": identity_column,
                }
            )

    penalties = min(missing_ratio * 60, 40) + min(outliers / max(rows, 1) * 100, 20)
    penalties += 10 if duplicates else 0
    penalties += sum(12 for issue in issues if issue["severity"] == "error")
    score = max(0.0, round(100 - penalties, 1))
    return {
        "rows": rows,
        "columns": columns,
        "duplicate_rows": duplicates,
        "missing_cells": missing_cells,
        "missing_ratio": missing_ratio,
        "outliers": outliers,
        "issues": issues,
        "column_stats": column_stats,
        "score": score,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_columns(frame: pd.DataFrame, kind: str) -> list[dict[str, Any]]:
    required = REQUIRED_COLUMNS.get(kind, REQUIRED_COLUMNS["CHILD"])
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise IngestionError(
            "Faltan columnas obligatorias: " + ", ".join(missing) + ". Consulte el diccionario de datos."
        )
    return []


def humanize(name: str) -> str:
    return name.replace("_", " ").strip().capitalize()


def build_variable_definitions(frame: pd.DataFrame, quality: dict[str, Any]) -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    for column in frame.columns:
        stats = quality["column_stats"].get(column, {})
        dtype = "string"
        if pd.api.types.is_bool_dtype(frame[column]):
            dtype = "boolean"
        elif pd.api.types.is_integer_dtype(frame[column]):
            dtype = "integer"
        elif pd.api.types.is_numeric_dtype(frame[column]):
            dtype = "float"
        definitions.append(
            {
                "name": column,
                "label": humanize(column),
                "dtype": dtype,
                "unit": None,
                "description": None,
                "allowed_values": sorted(map(str, frame[column].dropna().unique()[:20]))
                if dtype == "string" and frame[column].nunique() <= 20
                else None,
                "min_value": stats.get("min"),
                "max_value": stats.get("max"),
                "is_required": column in REQUIRED_COLUMNS.get("CHILD", []),
                "is_identifier": column.endswith("_code") or column in ("child_id", "household_id"),
                "missing_count": stats.get("missing", 0),
                "stats": stats,
            }
        )
    return definitions


def _resolve_territories(db: Session, frame: pd.DataFrame, default_region: str) -> dict[str, int]:
    """Map territory codes to ids, creating lightweight territories when needed."""
    existing = {code: ident for code, ident in db.execute(select(Territory.code, Territory.id)).all()}
    if "territory_code" not in frame.columns:
        return existing
    missing_codes = sorted(set(frame["territory_code"].dropna().astype(str)) - set(existing))
    for index, code in enumerate(missing_codes, start=1):
        region_series = frame.loc[frame["territory_code"].astype(str) == code, "region"] if "region" in frame else None
        region = str(region_series.iloc[0]) if region_series is not None and not region_series.empty else default_region
        territory = Territory(
            code=code,
            name=f"Territorio {code}",
            region=region,
            level="DEPARTMENT",
            population=0,
            population_u5=0,
            is_synthetic=True,
            neighbor_codes=[],
        )
        db.add(territory)
        _ = index
    if missing_codes:
        db.flush()
        existing = {code: ident for code, ident in db.execute(select(Territory.code, Territory.id)).all()}
    return existing


def _value(row: pd.Series, key: str, default: Any = None) -> Any:  # noqa: ANN401
    value = row.get(key, default)
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return default
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def load_children(db: Session, dataset: Dataset, frame: pd.DataFrame) -> dict[str, int]:
    """Bulk-load households, children and anthropometric indicators."""
    territory_map = _resolve_territories(db, frame, dataset.country or "Sin región")
    fallback_territory = next(iter(territory_map.values())) if territory_map else None
    if fallback_territory is None:
        territory = Territory(code="T00", name="Territorio base", region="Sin región", population=0, population_u5=0)
        db.add(territory)
        db.flush()
        territory_map = {"T00": territory.id}
        fallback_territory = territory.id

    now_iso = datetime.now(timezone.utc)
    frame = frame.copy()
    if "child_code" not in frame.columns:
        frame["child_code"] = [f"{dataset.slug}-{index:06d}" for index in range(len(frame))]
    if "household_code" not in frame.columns:
        frame["household_code"] = frame["child_code"].astype(str) + "-HH"

    # Drop rows whose child_code already exists in the database.
    existing_codes = set(
        db.execute(select(Child.code).where(Child.code.in_(frame["child_code"].astype(str).tolist()))).scalars().all()
    )
    skipped = len(existing_codes)

    household_rows: dict[str, dict[str, Any]] = {}
    child_rows: list[dict[str, Any]] = []
    indicator_inputs: list[dict[str, Any]] = []
    rejected = 0
    errors: list[dict[str, Any]] = []

    for _, row in frame.iterrows():
        code = str(row["child_code"])
        if code in existing_codes:
            continue
        territory_code = str(row.get("territory_code", "")) if "territory_code" in frame.columns else ""
        territory_id = territory_map.get(territory_code, fallback_territory)
        household_code = str(row["household_code"])
        if household_code not in household_rows:
            household_rows[household_code] = {
                "code": household_code,
                "territory_id": territory_id,
                "period_year": int(_value(row, "period_year", now_iso.year)),
                "wealth_quintile": int(np.clip(_value(row, "wealth_quintile", 3), 1, 5)),
                "wealth_index": float(_value(row, "wealth_index", 0.0) or 0.0),
                "maternal_education": str(_value(row, "maternal_education", "PRIMARY") or "PRIMARY"),
                "maternal_age": _value(row, "maternal_age"),
                "water_source": str(_value(row, "water_source", "IMPROVED") or "IMPROVED"),
                "sanitation": str(_value(row, "sanitation", "IMPROVED") or "IMPROVED"),
                "electricity": bool(_value(row, "electricity", False)),
                "cooking_fuel": str(_value(row, "cooking_fuel", "GAS") or "GAS"),
                "assets_count": int(_value(row, "assets_count", 0) or 0),
                "household_size": int(_value(row, "household_size", 4) or 4),
                "food_insecurity_score": float(_value(row, "food_insecurity_score", 0.0) or 0.0),
                "urban_rural": str(_value(row, "urban_rural", "RURAL") or "RURAL"),
                "is_synthetic": bool(dataset.is_synthetic),
                "metadata_extra": {},
            }
        try:
            result = compute_indicators(
                sex=str(_value(row, "sex", "M")),
                age_months=float(_value(row, "age_months", 0)),
                weight_kg=float(_value(row, "weight_kg", 0)),
                height_cm=float(_value(row, "height_cm", 0)),
                edema=bool(_value(row, "edema", False)),
            )
        except (AnthropometryError, TypeError, ValueError) as exc:
            rejected += 1
            if len(errors) < 100:
                errors.append({"row": None, "code": "ANTHROPOMETRY_ERROR", "message": str(exc), "child_code": code})
            continue

        child_rows.append(
            {
                "code": code,
                "household_code": household_code,
                "territory_id": territory_id,
                "period_year": int(_value(row, "period_year", now_iso.year)),
                "age_months": int(_value(row, "age_months", 0)),
                "sex": str(_value(row, "sex", "M")),
                "weight_kg": float(_value(row, "weight_kg", 0)),
                "height_cm": float(_value(row, "height_cm", 0)),
                "muac_cm": _value(row, "muac_cm"),
                "edema": bool(_value(row, "edema", False)),
                "birth_weight_g": _value(row, "birth_weight_g"),
                "breastfeeding_months": _value(row, "breastfeeding_months"),
                "minimum_diet_diversity": bool(_value(row, "minimum_diet_diversity", False)),
                "vaccination_complete": bool(_value(row, "vaccination_complete", False)),
                "diarrhea_14d": bool(_value(row, "diarrhea_14d", False)),
                "fever_14d": bool(_value(row, "fever_14d", False)),
                "is_synthetic": bool(dataset.is_synthetic),
                "metadata_extra": {},
            }
        )
        indicator_inputs.append({"code": code, "result": result})

    if not child_rows:
        return {"loaded": 0, "skipped": skipped, "rejected": rejected, "errors": errors}

    db.execute(insert(Household), list(household_rows.values()))
    household_map = {
        code: ident
        for code, ident in db.execute(
            select(Household.code, Household.id).where(Household.code.in_(list(household_rows.keys())))
        ).all()
    }
    for row in child_rows:
        row["household_id"] = household_map[row.pop("household_code")]

    db.execute(insert(Child), child_rows)
    child_map = {
        code: ident
        for code, ident in db.execute(
            select(Child.code, Child.id).where(Child.code.in_([item["code"] for item in indicator_inputs]))
        ).all()
    }
    indicator_rows = []
    for item in indicator_inputs:
        child_id = child_map.get(item["code"])
        if child_id is None:
            continue
        result = item["result"]
        indicator_rows.append(
            {
                "child_id": child_id,
                "haz": result.haz,
                "waz": result.waz,
                "whz": result.whz,
                "baz": result.baz,
                "stunting": result.stunting,
                "severe_stunting": result.severe_stunting,
                "wasting": result.wasting,
                "severe_wasting": result.severe_wasting,
                "underweight": result.underweight,
                "severe_underweight": result.severe_underweight,
                "overweight": result.overweight,
                "edematous": result.edematous,
                "reference_version": result.reference_version,
                "computed_at": datetime.now(timezone.utc),
            }
        )
    db.execute(insert(AnthropometricIndicator), indicator_rows)
    return {
        "loaded": len(child_rows),
        "skipped": skipped,
        "rejected": rejected,
        "errors": errors,
        "households": len(household_rows),
    }


def ingest_file(
    db: Session,
    *,
    dataset: Dataset,
    path: Path,
    trigger: str = "UPLOAD",
    user_id: int | None = None,
    preview_rows: int = 10,
) -> IngestionOutcome:
    """Full ingestion pipeline for one file: validate, score, load, audit."""
    started = time.perf_counter()
    run = IngestionRun(dataset_id=dataset.id, status="RUNNING", trigger=trigger, triggered_by=user_id, started_at=datetime.now(timezone.utc))
    db.add(run)
    db.flush()

    try:
        frame = read_table(path, dataset.file_format or detect_format(path.name))
        frame = normalize_columns(frame)
        validate_columns(frame, dataset.kind)
        frame, coercion_errors = coerce_frame(frame)
        quality = build_quality_report(frame, kind=dataset.kind)
        preview = frame.head(preview_rows).replace({np.nan: None}).to_dict(orient="records")

        dataset.schema_definition = [
            {"name": column, "dtype": str(dtype)} for column, dtype in frame.dtypes.items()
        ]
        dataset.quality_report = quality
        dataset.rows = len(frame)
        dataset.columns = len(frame.columns)

        for definition in build_variable_definitions(frame, quality):
            db.merge(VariableDefinition(dataset_id=dataset.id, **definition))

        if dataset.kind in ("CHILD", "MIXED"):
            outcome = load_children(db, dataset, frame)
        else:
            outcome = {"loaded": len(frame), "skipped": 0, "rejected": 0, "errors": []}

        errors = coercion_errors + outcome.get("errors", [])
        run.rows_in = len(frame)
        run.rows_loaded = outcome.get("loaded", 0)
        run.rows_rejected = outcome.get("rejected", 0) + outcome.get("skipped", 0)
        run.errors = errors[:100]
        run.warnings = [issue for issue in quality.get("issues", []) if issue["severity"] == "warning"][:50]
        run.quality_report = quality
        run.status = "PARTIAL" if errors else "SUCCESS"
        run.finished_at = datetime.now(timezone.utc)
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        dataset.status = "READY"
        dataset.period_year = dataset.period_year or int(frame["period_year"].mode().iloc[0])
        db.commit()
        return IngestionOutcome(dataset=dataset, run=run, preview=preview, quality=quality)

    except IngestionError as exc:
        run.status = "FAILED"
        run.errors = [{"code": "INGESTION_ERROR", "message": str(exc)}]
        run.finished_at = datetime.now(timezone.utc)
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        dataset.status = "FAILED"
        dataset.quality_report = {"issues": [{"code": "INGESTION_ERROR", "severity": "error", "message": str(exc)}]}
        db.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        run = db.get(IngestionRun, run.id) or run
        run.status = "FAILED"
        run.errors = [{"code": "UNEXPECTED_ERROR", "message": str(exc)}]
        run.finished_at = datetime.now(timezone.utc)
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        dataset = db.get(Dataset, dataset.id) or dataset
        dataset.status = "FAILED"
        db.commit()
        raise IngestionError(f"Error inesperado durante la ingesta: {exc}") from exc

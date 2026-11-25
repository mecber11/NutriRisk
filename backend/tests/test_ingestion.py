"""Pruebas de ingesta, normalización y control de calidad."""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.ingestion import (
    IngestionError,
    build_quality_report,
    build_variable_definitions,
    coerce_frame,
    detect_format,
    normalize_columns,
    slugify,
    validate_columns,
)


def test_detect_format_supported_and_rejected():
    assert detect_format("datos.csv") == "CSV"
    assert detect_format("datos.XLSX") == "XLSX"
    assert detect_format("datos.parquet") == "PARQUET"
    with pytest.raises(IngestionError):
        detect_format("datos.zip")


def test_slugify_handles_accents():
    assert slugify("Encuesta de Niñez 2023") == "encuesta_de_ninez_2023"


def test_normalize_columns_maps_spanish_aliases():
    frame = pd.DataFrame(
        {
            "Código Niño": ["A1"],
            "Edad (meses)": [24],
            "Sexo": ["F"],
            "Peso kg": [11.5],
            "Talla cm": [86.0],
            "Quintil de riqueza": [2],
        }
    )
    normalized = normalize_columns(frame)
    assert "child_code" in normalized.columns
    assert "age_months" in normalized.columns
    assert "weight_kg" in normalized.columns


def test_validate_columns_requires_anthropometry():
    frame = pd.DataFrame({"age_months": [12], "sex": ["M"]})
    with pytest.raises(IngestionError) as error:
        validate_columns(frame, "CHILD")
    assert "weight_kg" in str(error.value)


def test_quality_report_detects_problems():
    frame = pd.DataFrame(
        {
            "age_months": [12, 24, 120, 36],
            "weight_kg": [9.5, 12.0, 15.0, 13.5],
            "sex": ["M", "F", "M", "F"],
        }
    )
    report = build_quality_report(frame)
    assert report["rows"] == 4
    assert report["score"] < 100
    assert any(issue["code"] == "OUT_OF_RANGE" for issue in report["issues"])
    assert report["column_stats"]["age_months"]["max"] == 120


def test_quality_report_flags_duplicate_identifiers():
    frame = pd.DataFrame(
        {
            "child_code": ["A", "A", "B"],
            "age_months": [12, 12, 24],
            "weight_kg": [9.0, 9.0, 12.0],
            "height_cm": [75.0, 75.0, 86.0],
        }
    )
    report = build_quality_report(frame)
    assert report["duplicate_rows"] == 1
    assert any(issue["code"] == "DUPLICATE_ROWS" for issue in report["issues"])


def test_coerce_frame_maps_categories_and_drops_invalid_rows():
    frame = pd.DataFrame(
        {
            "age_months": [12, None, 24],
            "sex": ["Femenino", "M", "M"],
            "weight_kg": [9.0, 10.0, None],
            "height_cm": [75.0, 80.0, 86.0],
            "maternal_education": ["primaria", "secundaria", "superior"],
            "water_source": ["tuberia", "pozo", "rio"],
            "urban_rural": ["urbano", "rural", "urbano"],
        }
    )
    cleaned, errors = coerce_frame(frame)
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["sex"] == "F"
    assert cleaned.iloc[0]["maternal_education"] == "PRIMARY"
    assert cleaned.iloc[0]["water_source"] == "PIPED"
    assert cleaned.iloc[0]["urban_rural"] == "URBAN"
    assert errors


def test_variable_definitions_include_stats():
    frame = pd.DataFrame({"age_months": [12, 24], "sex": ["M", "F"]})
    quality = build_quality_report(frame)
    definitions = build_variable_definitions(frame, quality)
    names = {definition["name"] for definition in definitions}
    assert {"age_months", "sex"} <= names
    age_definition = next(item for item in definitions if item["name"] == "age_months")
    assert age_definition["stats"]["max"] == 24

"""WHO 2006 child growth standards: LMS z-scores and nutritional classification.

Reference values live in ``backend/data/reference/who_lms.json`` and were built by
``scripts/build_who_reference.py`` from the official WHO Child Growth Standards
(2006) LMS parameters. Age-based indicators use monthly tables 0-60 months;
weight-for-length (0-24 m) and weight-for-height (24-60 m) interpolate linearly
between the integer centimetre rows of the WHO tables.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings

REFERENCE_VERSION = "WHO-2006"
Z_SCORE_LIMIT = 5.0
MIN_AGE_MONTHS = 0
MAX_AGE_MONTHS = 60


class AnthropometryError(ValueError):
    """Raised when a measurement cannot be scored (implausible or out of range)."""


@lru_cache
def load_reference(path: str | None = None) -> dict[str, Any]:
    """Load and cache the WHO LMS reference JSON."""
    reference_path = Path(path) if path else settings.reference_dir / "who_lms.json"
    if not reference_path.exists():
        raise AnthropometryError(f"Who reference file not found: {reference_path}")
    with reference_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def normalize_sex(sex: str) -> str:
    """Map common encodings to the WHO 'M'/'F' keys."""
    value = str(sex).strip().upper()
    if value in {"M", "MALE", "1", "H", "HOMBRE", "MASCULINO"}:
        return "M"
    if value in {"F", "FEMALE", "2", "MUJER", "FEMENINO"}:
        return "F"
    raise AnthropometryError(f"Sexo no válido: {sex!r}")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def lms_zscore(measure: float, L: float, M: float, S: float) -> float:
    """WHO LMS formula (Box-Cox normal transform), using WHO's L/M/S notation."""
    if measure <= 0 or M <= 0 or S <= 0:
        raise AnthropometryError("Medida fuera de rango fisiológico")
    if abs(L) < 1e-9:
        return math.log(measure / M) / S
    return ((measure / M) ** L - 1.0) / (L * S)


def _interpolate_lms(table: dict[str, dict[str, float]], value: float, minimum: int, maximum: int) -> dict[str, float]:
    """Linear interpolation of L, M, S between integer centimetre rows."""
    clamped = _clamp(value, minimum, maximum)
    lower = int(math.floor(clamped))
    upper = min(lower + 1, maximum)
    low_row = table.get(str(lower))
    high_row = table.get(str(upper), low_row)
    if low_row is None:
        raise AnthropometryError(f"Medida fuera de la tabla WHO ({value})")
    if low_row is high_row or lower == upper:
        return {"L": low_row["L"], "M": low_row["M"], "S": low_row["S"]}
    weight = clamped - lower
    return {
        "L": low_row["L"] + (high_row["L"] - low_row["L"]) * weight,
        "M": low_row["M"] + (high_row["M"] - low_row["M"]) * weight,
        "S": low_row["S"] + (high_row["S"] - low_row["S"]) * weight,
    }


@dataclass(slots=True)
class AnthropometricResult:
    """Computed z-scores, flags and classification for one child."""

    haz: float | None
    waz: float | None
    whz: float | None
    baz: float | None
    stunting: bool
    severe_stunting: bool
    wasting: bool
    severe_wasting: bool
    underweight: bool
    severe_underweight: bool
    overweight: bool
    edematous: bool
    flags: list[str]
    reference_version: str = REFERENCE_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _score(z: float, flags: list[str], label: str) -> float:
    if math.isnan(z) or math.isinf(z):
        raise AnthropometryError(f"z-score inválido para {label}")
    if abs(z) > Z_SCORE_LIMIT:
        flags.append(f"{label}_out_of_range")
        return round(_clamp(z, -Z_SCORE_LIMIT, Z_SCORE_LIMIT), 4)
    return round(z, 4)


def compute_indicators(
    *,
    sex: str,
    age_months: float,
    weight_kg: float,
    height_cm: float,
    edema: bool = False,
) -> AnthropometricResult:
    """Compute HAZ, WAZ, WHZ, BAZ and the WHO classification for one child."""
    reference = load_reference()
    sex_key = normalize_sex(sex)
    flags: list[str] = []

    if not (MIN_AGE_MONTHS <= age_months <= MAX_AGE_MONTHS + 1):
        raise AnthropometryError(f"Edad fuera del rango WHO 0-60 meses: {age_months}")
    if not (1.0 <= weight_kg <= 35.0):
        raise AnthropometryError(f"Peso fuera de rango plausible: {weight_kg}")
    if not (35.0 <= height_cm <= 130.0):
        raise AnthropometryError(f"Talla fuera de rango plausible: {height_cm}")

    month = int(_clamp(round(age_months), MIN_AGE_MONTHS, MAX_AGE_MONTHS))
    # WHO convention: length (< 24 m) vs height (>= 24 m).
    is_young = month < 24

    hfa_row = reference["hfa"][sex_key][str(month)]
    wfa_row = reference["wfa"][sex_key][str(month)]

    haz = _score(lms_zscore(height_cm, **hfa_row), flags, "haz")
    waz = _score(lms_zscore(weight_kg, **wfa_row), flags, "waz")

    if is_young:
        wfh_table = reference["wfl"][sex_key]
        wfh_row = _interpolate_lms(wfh_table, height_cm, 45, 110)
    else:
        wfh_table = reference["wfh"][sex_key]
        wfh_row = _interpolate_lms(wfh_table, height_cm, 65, 120)
    whz = _score(lms_zscore(weight_kg, **wfh_row), flags, "whz")

    bmi = weight_kg / ((height_cm / 100.0) ** 2)
    bfa_row = reference["bfa"][sex_key][str(month)]
    baz = _score(lms_zscore(bmi, **bfa_row), flags, "baz")

    if edema:
        flags.append("edematous")

    return AnthropometricResult(
        haz=haz,
        waz=waz,
        whz=whz,
        baz=baz,
        stunting=haz < -2.0,
        severe_stunting=haz < -3.0,
        wasting=(whz < -2.0) or edema,
        severe_wasting=(whz < -3.0) or edema,
        underweight=waz < -2.0,
        severe_underweight=waz < -3.0,
        overweight=whz > 2.0,
        edematous=edema,
        flags=flags,
    )


def classify_from_zscores(haz: float | None, waz: float | None, whz: float | None) -> dict[str, bool]:
    """Derive classification flags from precomputed z-scores."""
    return {
        "stunting": haz is not None and haz < -2.0,
        "severe_stunting": haz is not None and haz < -3.0,
        "wasting": whz is not None and whz < -2.0,
        "severe_wasting": whz is not None and whz < -3.0,
        "underweight": waz is not None and waz < -2.0,
        "severe_underweight": waz is not None and waz < -3.0,
        "overweight": whz is not None and whz > 2.0,
    }


def reference_coverage() -> dict[str, Any]:
    """Metadata about the loaded reference tables (exposed by the API)."""
    reference = load_reference()
    return {
        "version": reference.get("version", REFERENCE_VERSION),
        "source": reference.get("source"),
        "age_months_range": [MIN_AGE_MONTHS, MAX_AGE_MONTHS],
        "indicators": {
            key: {
                "male_rows": len(reference[key]["M"]),
                "female_rows": len(reference[key]["F"]),
            }
            for key in ("hfa", "wfa", "wfl", "wfh", "bfa")
        },
        "zscore_limit": Z_SCORE_LIMIT,
    }


def self_check(tolerance: float = 0.15) -> dict[str, Any]:
    """Recompute WHO published -2 SD cut-offs and report the max deviation.

    Used by the test-suite to prove the LMS engine matches the official tables.
    """
    reference = load_reference()
    anchors = reference.get("validation_minus2sd", {})
    deviations: dict[str, float] = {}
    for indicator in ("hfa", "wfa"):
        for sex_key, label in (("M", "boys"), ("F", "girls")):
            for month, expected_measure in anchors.get(f"{indicator}_{label}", {}).items():
                row = reference[indicator][sex_key][month]
                z = lms_zscore(expected_measure, **row)
                deviations[f"{indicator}_{label}_{month}"] = round(abs(z + 2.0), 4)
    worst = max(deviations.values()) if deviations else 0.0
    return {
        "checked_cutoffs": len(deviations),
        "max_deviation_z": worst,
        "tolerance": tolerance,
        "passed": worst <= tolerance,
    }


"""Pruebas del motor antropométrico OMS 2006."""

from __future__ import annotations

import pytest

from app.services.anthropometry import (
    AnthropometryError,
    classify_from_zscores,
    compute_indicators,
    load_reference,
    lms_zscore,
    normalize_sex,
    reference_coverage,
    self_check,
)


def test_reference_covers_all_indicators():
    reference = load_reference()
    for indicator in ("hfa", "wfa", "wfl", "wfh", "bfa"):
        assert len(reference[indicator]["M"]) >= 50
        assert len(reference[indicator]["F"]) >= 50
    assert reference["version"] == "WHO-2006"


def test_self_check_matches_who_cutoffs():
    result = self_check(tolerance=0.15)
    assert result["passed"] is True
    assert result["checked_cutoffs"] > 100


def test_lms_zscore_cutoff_is_minus_two():
    reference = load_reference()
    row = reference["wfa"]["M"]["12"]
    z = lms_zscore(reference["validation_minus2sd"]["wfa_boys"]["12"], **row)
    assert -2.15 < z < -1.85


def test_normalize_sex_accepts_spanish_and_codes():
    assert normalize_sex("F") == "F"
    assert normalize_sex("femenino") == "F"
    assert normalize_sex(1) == "M"
    assert normalize_sex("Hombre") == "M"
    with pytest.raises(AnthropometryError):
        normalize_sex("X")


def test_compute_indicators_healthy_child():
    result = compute_indicators(sex="M", age_months=24, weight_kg=12.2, height_cm=87.1, edema=False)
    assert result.haz is not None and -1 < result.haz < 1
    assert result.waz is not None
    assert result.whz is not None
    assert result.baz is not None
    assert result.stunting is False
    assert result.wasting is False
    assert result.reference_version == "WHO-2006"


def test_stunting_and_wasting_classification():
    stunted = compute_indicators(sex="F", age_months=30, weight_kg=11.0, height_cm=82.0)
    assert stunted.haz < -2
    assert stunted.stunting is True
    wasted = compute_indicators(sex="M", age_months=18, weight_kg=7.0, height_cm=82.0)
    assert wasted.whz < -2
    assert wasted.wasting is True


def test_edema_forces_wasting():
    result = compute_indicators(sex="F", age_months=40, weight_kg=13.0, height_cm=95.0, edema=True)
    assert result.wasting is True
    assert result.edematous is True


def test_implausible_measurements_raise():
    with pytest.raises(AnthropometryError):
        compute_indicators(sex="M", age_months=24, weight_kg=0.4, height_cm=87.0)
    with pytest.raises(AnthropometryError):
        compute_indicators(sex="M", age_months=24, weight_kg=12.0, height_cm=10.0)
    with pytest.raises(AnthropometryError):
        compute_indicators(sex="M", age_months=90, weight_kg=12.0, height_cm=100.0)


def test_extreme_z_scores_are_clamped_and_flagged():
    result = compute_indicators(sex="F", age_months=6, weight_kg=20.0, height_cm=60.0)
    assert abs(result.waz) <= 5.0
    assert any("out_of_range" in flag for flag in result.flags)


def test_classify_from_zscores():
    flags = classify_from_zscores(-2.5, -1.0, -2.8)
    assert flags["stunting"] is True
    assert flags["wasting"] is True
    assert flags["underweight"] is False


def test_reference_coverage_metadata():
    coverage = reference_coverage()
    assert coverage["age_months_range"] == [0, 60]
    assert coverage["indicators"]["hfa"]["male_rows"] == 61

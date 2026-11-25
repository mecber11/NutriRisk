"""Pruebas del generador de datos sintéticos y de su coherencia con la OMS."""

from __future__ import annotations

import json

import pandas as pd

from app.services.anthropometry import compute_indicators
from app.services.synthetic import (
    VARIABLE_DICTIONARY,
    build_territories,
    generate_children,
    territories_geojson,
    write_artifacts,
)


def test_territories_are_deterministic_and_complete():
    first = build_territories()
    second = build_territories()
    assert len(first) == 24
    assert [item.code for item in first] == [item.code for item in second]
    assert len({item.name for item in first}) == 24
    assert all(item.geometry["type"] == "Polygon" for item in first)
    assert all(item.population_u5 < item.population for item in first)


def test_neighbors_are_symmetric():
    profiles = build_territories()
    by_code = {profile.code: profile for profile in profiles}
    for profile in profiles:
        for neighbor in profile.neighbors:
            assert profile.code in by_code[neighbor].neighbors


def test_geojson_structure():
    collection = territories_geojson(build_territories())
    assert collection["type"] == "FeatureCollection"
    assert len(collection["features"]) == 24
    feature = collection["features"][0]
    assert feature["properties"]["is_synthetic"] is True
    assert feature["geometry"]["coordinates"][0][0] == feature["geometry"]["coordinates"][0][-1]


def test_generate_children_ranges_and_codes():
    frame = generate_children(build_territories(), years=(2023,), per_territory_year=8)
    assert isinstance(frame, pd.DataFrame)
    assert len(frame) == 24 * 8
    assert frame["child_code"].is_unique
    assert frame["sex"].isin(["M", "F"]).all()
    assert frame["age_months"].between(0, 59).all()
    assert frame["weight_kg"].between(1, 35).all()
    assert frame["height_cm"].between(35, 130).all()
    assert {"name", "label", "dtype", "description"} <= set(VARIABLE_DICTIONARY[0])


def test_generated_anthropometry_is_who_consistent():
    frame = generate_children(build_territories(), years=(2023,), per_territory_year=20)
    hazards = []
    for row in frame.head(200).itertuples(index=False):
        result = compute_indicators(
            sex=row.sex, age_months=row.age_months, weight_kg=row.weight_kg, height_cm=row.height_cm
        )
        hazards.append(result.haz)
    mean_haz = sum(hazards) / len(hazards)
    stunting_share = sum(1 for value in hazards if value < -2) / len(hazards)
    assert -1.8 < mean_haz < -0.2
    assert 0.05 < stunting_share < 0.45


def test_write_artifacts_creates_expected_files(tmp_path):
    manifest = write_artifacts(tmp_path)
    assert manifest["territories"] == 24
    for name in manifest["files"]:
        path = tmp_path / name
        assert path.exists() and path.stat().st_size > 0
    dictionary = json.loads((tmp_path / "dataset_dictionary.json").read_text(encoding="utf-8"))
    assert dictionary["source"] == "SYNTHETIC"
    assert dictionary["variables"]


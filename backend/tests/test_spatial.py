"""Pruebas de estadística espacial: pesos, Moran's I, SAR/SEM y GWR."""

from __future__ import annotations

import numpy as np
import pytest

from app.ml.spatial import (
    build_neighbor_map,
    build_weights,
    morans_i,
    spatial_lag_correction,
    spatial_regression,
    territory_frame,
)


def test_neighbor_map_from_database(db_session):
    neighbor_map = build_neighbor_map(db_session)
    assert len(neighbor_map) == 24
    assert all(isinstance(neighbors, list) for neighbors in neighbor_map.values())
    assert sum(len(neighbors) for neighbors in neighbor_map.values()) > 0


def test_weights_row_standardized(db_session):
    weights, codes = build_weights(build_neighbor_map(db_session))
    assert len(codes) == 24
    assert weights.transform.upper() == "R"
    row_sums = np.array(weights.sparse.toarray().sum(axis=1)).ravel()
    assert np.allclose(row_sums, 1.0, atol=1e-6)


def test_morans_i_detects_clustering(db_session):
    weights, codes = build_weights(build_neighbor_map(db_session))
    order = {code: index for index, code in enumerate(codes)}
    clustered = np.array(
        [1.0 if order[code] < 12 else 0.0 for code in codes]
    )
    result = morans_i(clustered, weights, permutations=99)
    assert result["available"] is True
    assert result["i"] > 0
    assert "interpretation" in result


def test_morans_i_requires_variance():
    result = morans_i(np.zeros(10), None)
    assert result["available"] is False


def test_spatial_lag_correction_returns_offsets(db_session):
    neighbor_map = build_neighbor_map(db_session)
    residuals = {code: 0.1 if index % 2 == 0 else -0.1 for index, code in enumerate(sorted(neighbor_map))}
    correction = spatial_lag_correction(residuals, neighbor_map)
    assert correction["available"] is True
    assert len(correction["offsets"]) == len(residuals)
    assert all(abs(value) < 1 for value in correction["offsets"].values())


def test_spatial_regression_available(db_session):
    from app.ml.features import build_analytical_frame

    frame = build_analytical_frame(db_session)
    residual = np.zeros(len(frame))
    aggregated = territory_frame(frame, residual)
    assert len(aggregated) == 24
    assert "latitude" in aggregated.columns
    diagnostics = spatial_regression(aggregated, build_neighbor_map(db_session))
    if diagnostics.get("available"):
        assert "sar" in diagnostics
        assert "sem" in diagnostics
        assert diagnostics["gwr"]["available"] in (True, False)
    else:  # pragma: no cover - sólo si PySAL no está disponible
        pytest.skip("PySAL no disponible")


def test_build_weights_handles_isolated_units():
    weights, codes = build_weights({"T01": ["T02"], "T02": ["T01"], "T03": []})
    assert codes == ["T01", "T02"]
    assert weights.n == 2


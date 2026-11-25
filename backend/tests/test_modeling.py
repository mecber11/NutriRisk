"""Pruebas del pipeline de modelado, métricas y explicabilidad."""

from __future__ import annotations

import numpy as np
import pytest
from sqlalchemy import func, select

from app.ml.cnn_lstm import build_sequences, torch_available
from app.ml.features import FEATURES, SPATIAL_FEATURES, add_features, feature_matrix
from app.ml.models import build_estimator, classification_metrics, optimal_thresholds, regression_metrics
from app.models.ml import MLModel, ModelExperiment, Prediction, TerritoryRisk
from app.services.modeling import (
    load_artifact,
    model_metrics_table,
    score_model,
    train_experiment,
)


def test_feature_matrix_has_stable_columns(db_session):
    from app.ml.features import build_analytical_frame

    frame = build_analytical_frame(db_session)
    matrix = feature_matrix(frame)
    assert list(matrix.columns) == FEATURES
    assert matrix.isna().sum().sum() == 0
    enriched = add_features(frame)
    assert enriched["sex_female"].isin([0.0, 1.0]).all()


def test_estimator_factory_and_metrics():
    estimator = build_estimator("random_forest", "classification", seed=1, params={"n_estimators": 5})
    assert estimator.__class__.__name__ == "RandomForestClassifier"
    with pytest.raises(ValueError):
        build_estimator("inexistente", "classification")

    y_true = np.array([0, 0, 1, 1, 0, 1])
    y_score = np.array([0.1, 0.2, 0.8, 0.7, 0.4, 0.6])
    metrics = classification_metrics(y_true, y_score)
    assert metrics["auc"] == 1.0
    assert metrics["confusion_matrix"] == [[3, 0], [0, 3]]

    thresholds = optimal_thresholds(y_true, y_score)
    assert 0 <= thresholds["threshold"] <= 1
    assert thresholds["screening_threshold"] >= thresholds["threshold"]

    regression = regression_metrics(np.array([1.0, 2.0, 3.0]), np.array([1.1, 1.9, 3.2]))
    assert regression["rmse"] > 0
    assert regression["r2"] is None or regression["r2"] <= 1


def test_train_experiment_registers_model(db_session):
    experiment = train_experiment(
        db_session,
        algorithm="xgboost",
        task="regression",
        target="haz",
        seed=11,
        hyperparams={"n_estimators": 40, "max_depth": 3},
        include_spatial=False,
    )
    assert experiment.status == "COMPLETED"
    assert experiment.metrics["rmse"] is not None
    assert experiment.per_region_metrics
    model = db_session.scalar(select(MLModel).where(MLModel.experiment_id == experiment.id))
    assert model is not None
    payload = load_artifact(model)
    assert payload["target"] == "haz"
    assert len(payload["features"]) == len(FEATURES)


def test_scoring_is_idempotent(db_session):
    model = db_session.scalar(select(MLModel).where(MLModel.is_active.is_(True)))
    first = score_model(db_session, model)
    second = score_model(db_session, model)
    assert first["scored_children"] == second["scored_children"]
    count = db_session.scalar(select(func.count(Prediction.id)).where(Prediction.model_id == model.id))
    assert count == second["scored_children"]
    risk_rows = db_session.scalar(select(func.count(TerritoryRisk.id)).where(TerritoryRisk.model_id == model.id))
    assert risk_rows == second["territories"]
    assert second["mean_risk"] > 0


def test_territory_risk_rank_is_contiguous(db_session):
    model = db_session.scalar(select(MLModel).where(MLModel.is_active.is_(True)))
    rows = db_session.execute(
        select(TerritoryRisk).where(TerritoryRisk.model_id == model.id, TerritoryRisk.period_year == 2023)
    ).scalars().all()
    ranks = sorted(row.priority_rank for row in rows)
    assert ranks == list(range(1, len(ranks) + 1))
    assert all(row.population_at_risk >= 0 for row in rows)


def test_model_metrics_table(db_session):
    rows = model_metrics_table(db_session)
    assert rows
    assert any(row["is_best"] for row in rows)


def test_cnn_sequences_shape(db_session):
    from app.ml.features import build_analytical_frame

    frame = build_analytical_frame(db_session)
    sequences = build_sequences(frame, FEATURES)
    assert sequences["x"].shape[0] == 24
    assert sequences["x"].shape[1] >= 2
    assert sequences["x"].shape[2] == len(FEATURES)
    assert sequences["years"] == sorted(sequences["years"])


def test_models_dataset_spatial_features_defined():
    assert len(SPATIAL_FEATURES) == 4
    assert "neighbor_wealth" in SPATIAL_FEATURES


def test_experiment_failure_is_recorded(db_session):
    with pytest.raises(ValueError):
        train_experiment(db_session, algorithm="random_forest", target="inexistente", include_spatial=False)
    failed = db_session.execute(
        select(ModelExperiment).where(ModelExperiment.target == "inexistente")
    ).scalars().all()
    assert failed and failed[-1].status == "FAILED"


@pytest.mark.skipif(not torch_available(), reason="PyTorch no instalado")
def test_cnn_lstm_training_smoke(db_session):
    from app.ml.cnn_lstm import train_cnn_lstm
    from app.ml.features import build_analytical_frame

    frame = build_analytical_frame(db_session)
    result = train_cnn_lstm(frame, FEATURES, epochs=5)
    assert result["metrics"]["rmse"] is not None
    assert result["territories"] == 24


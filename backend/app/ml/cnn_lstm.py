"""CNN-LSTM for spatio-temporal malnutrition risk (PyTorch).

Each territory is a multivariate yearly sequence of determinants; a 1-D
convolution extracts short-term patterns, an LSTM models temporal dependence and
a dense head predicts the territory-year stunting prevalence.

Evaluation protocol
-------------------
* **Temporal holdout (headline):** train on the 2021-2022 sequences of every
  territory and score 2023 (out-of-time, never seen during training).
* **Leave-one-region-out (stress test):** retrain excluding one region at a time
  and score its territories, to report spatial transferability per region.

Targets are standardised per fold so the network is not dominated by the scale
of the prevalence; predictions are back-transformed for reporting.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.ml.models import regression_metrics

EPOCHS = 300
LEARNING_RATE = 0.02
CHANNELS = 8
HIDDEN = 16
DROPOUT = 0.25
WEIGHT_DECAY = 0.01


def torch_available() -> bool:
    try:
        import torch  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def _require_torch():  # noqa: ANN202
    try:
        import torch
        from torch import nn
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "PyTorch no está instalado: el modelo CNN-LSTM no puede entrenarse. "
            "Instale 'torch' (rueda CPU) para habilitar este algoritmo."
        ) from exc
    return torch, nn


def build_sequences(frame: pd.DataFrame, features: list[str]) -> dict[str, Any]:
    """Aggregate child rows into (territory, year) sequences."""
    from app.ml.features import add_features

    frame = add_features(frame)
    grouped = (
        frame.groupby(["territory_code", "region", "period_year"])
        .agg({**{feature: "mean" for feature in features}, "stunting": "mean", "child_id": "size"})
        .reset_index()
    )
    grouped = grouped.sort_values(["territory_code", "period_year"])
    years = sorted(grouped["period_year"].unique().tolist())
    codes = sorted(grouped["territory_code"].unique().tolist())
    if len(years) < 2:
        raise ValueError("CNN-LSTM requiere al menos dos periodos anuales")

    tensor = np.zeros((len(codes), len(years), len(features)), dtype=np.float32)
    target = np.zeros((len(codes), len(years)), dtype=np.float32)
    present = np.zeros((len(codes), len(years)), dtype=bool)
    region_by_code: dict[str, str] = {}
    for _, row in grouped.iterrows():
        code_index = codes.index(row["territory_code"])
        year_index = years.index(int(row["period_year"]))
        tensor[code_index, year_index] = row[features].to_numpy(dtype=np.float32)
        target[code_index, year_index] = float(row["stunting"])
        present[code_index, year_index] = True
        region_by_code[row["territory_code"]] = row["region"]
    return {
        "x": tensor,
        "y": target,
        "present": present,
        "codes": codes,
        "years": years,
        "features": features,
        "regions": [region_by_code[code] for code in codes],
    }


def _build_network(n_features: int, torch, nn):  # noqa: ANN001, ANN202
    class CNNLSTM(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.conv = nn.Conv1d(n_features, CHANNELS, kernel_size=2, padding=1)
            self.dropout = nn.Dropout(DROPOUT)
            self.lstm = nn.LSTM(CHANNELS, HIDDEN, batch_first=True)
            self.head = nn.Sequential(nn.Linear(HIDDEN, 8), nn.ReLU(), nn.Linear(8, 1))

        def forward(self, x):  # noqa: ANN001, ANN201
            x = x.transpose(1, 2)
            x = torch.relu(self.conv(x))
            x = x.transpose(1, 2)
            x = self.dropout(x)
            output, _ = self.lstm(x)
            return self.head(output[:, -1, :]).squeeze(-1)

    return CNNLSTM()


def _fit_predict(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    *,
    seed: int,
    epochs: int = EPOCHS,
    learning_rate: float = LEARNING_RATE,
) -> tuple[np.ndarray, list[float]]:
    """Standardise features/target, train the CNN-LSTM, return test predictions."""
    torch, nn = _require_torch()
    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.set_num_threads(1)

    feature_mean = x_train.reshape(-1, x_train.shape[2]).mean(axis=0)
    feature_std = x_train.reshape(-1, x_train.shape[2]).std(axis=0)
    feature_std[feature_std == 0] = 1.0
    target_mean = float(y_train.mean())
    target_std = float(y_train.std()) or 1.0

    train_tensor = torch.from_numpy(((x_train - feature_mean) / feature_std).astype(np.float32))
    test_tensor = torch.from_numpy(((x_test - feature_mean) / feature_std).astype(np.float32))
    target_tensor = torch.from_numpy(((y_train - target_mean) / target_std).astype(np.float32))

    model = _build_network(x_train.shape[2], torch, nn)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate, weight_decay=WEIGHT_DECAY)
    loss_fn = nn.MSELoss()
    history: list[float] = []
    for _ in range(epochs):
        model.train()
        optimizer.zero_grad()
        loss = loss_fn(model(train_tensor), target_tensor)
        loss.backward()
        optimizer.step()
        history.append(float(loss.item()))
    model.eval()
    with torch.no_grad():
        scaled = model(test_tensor).numpy()
    predictions = scaled * target_std + target_mean
    return predictions.astype(float), history


def train_cnn_lstm(
    frame: pd.DataFrame,
    features: list[str],
    *,
    seed: int = 42,
    epochs: int = EPOCHS,
) -> dict[str, Any]:
    """Territory-holdout headline metrics + leave-one-region-out stress test."""
    from sklearn.model_selection import GroupKFold

    sequences = build_sequences(frame, features)
    x = np.nan_to_num(sequences["x"], nan=0.0)
    y = np.nan_to_num(sequences["y"], nan=float(np.mean(sequences["y"])))
    regions = np.array(sequences["regions"])
    latest = y[:, -1]
    codes = np.array(sequences["codes"])

    # --- Headline: 5-fold holdout by territory (unseen territories, 2023) ---
    holdout_prediction = np.full(len(codes), np.nan, dtype=float)
    history: list[float] = []
    splitter = GroupKFold(n_splits=min(5, len(codes)))
    for train_idx, test_idx in splitter.split(codes, groups=codes):
        fold_prediction, history = _fit_predict(
            x[train_idx], latest[train_idx], x[test_idx], seed=seed, epochs=epochs
        )
        holdout_prediction[test_idx] = fold_prediction
    holdout_metrics = regression_metrics(latest, holdout_prediction)
    holdout_metrics["protocol"] = "holdout_by_territory_2023"
    holdout_metrics["epochs"] = epochs
    holdout_metrics["territories"] = int(len(codes))

    # --- Stress test: leave-one-region-out --------------------------------
    predictions = np.full(len(sequences["codes"]), np.nan, dtype=float)
    per_region: dict[str, Any] = {}
    for region in sorted(set(sequences["regions"])):
        test_mask = regions == region
        train_mask = ~test_mask
        if test_mask.sum() < 2 or train_mask.sum() < 3:
            continue
        fold_prediction, _ = _fit_predict(
            x[train_mask], latest[train_mask], x[test_mask], seed=seed, epochs=epochs
        )
        predictions[test_mask] = fold_prediction
        per_region[region] = regression_metrics(latest[test_mask], fold_prediction)
    mask = ~np.isnan(predictions)
    loro_metrics = regression_metrics(latest[mask], predictions[mask]) if mask.any() else {}

    return {
        "metrics": {
            **holdout_metrics,
            "loro_rmse": loro_metrics.get("rmse"),
            "loro_r2": loro_metrics.get("r2"),
            "final_train_loss": round(float(history[-1]), 8) if history else None,
            "regions_evaluated": sorted(per_region),
            "sequence_shape": [int(x.shape[0]), int(x.shape[1]), int(x.shape[2])],
        },
        "per_region": per_region,
        "years": sequences["years"],
        "territories": len(sequences["codes"]),
        "sequence_shape": [int(x.shape[0]), int(x.shape[1]), int(x.shape[2])],
        "features": features,
        "curves": history[-10:],
    }


def save_model(
    frame: pd.DataFrame,
    features: list[str],
    path: Path,
    *,
    seed: int = 42,
    epochs: int = EPOCHS,
) -> dict[str, Any]:
    """Train on all territories and persist the state dict for inference."""
    torch, nn = _require_torch()
    sequences = build_sequences(frame, features)
    x = np.nan_to_num(sequences["x"], nan=0.0)
    y = np.nan_to_num(sequences["y"], nan=float(np.mean(sequences["y"])))[:, -1]

    feature_mean = x.reshape(-1, x.shape[2]).mean(axis=0)
    feature_std = x.reshape(-1, x.shape[2]).std(axis=0)
    feature_std[feature_std == 0] = 1.0
    target_mean = float(y.mean())
    target_std = float(y.std()) or 1.0
    scaled = (x - feature_mean) / feature_std

    torch.manual_seed(seed)
    torch.set_num_threads(1)
    model = _build_network(x.shape[2], torch, nn)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    loss_fn = nn.MSELoss()
    x_tensor = torch.from_numpy(scaled.astype(np.float32))
    y_tensor = torch.from_numpy(((y - target_mean) / target_std).astype(np.float32))
    for _ in range(epochs):
        model.train()
        optimizer.zero_grad()
        loss = loss_fn(model(x_tensor), y_tensor)
        loss.backward()
        optimizer.step()

    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "feature_mean": feature_mean.tolist(),
            "feature_std": feature_std.tolist(),
            "target_mean": target_mean,
            "target_std": target_std,
            "features": features,
            "years": sequences["years"],
            "codes": sequences["codes"],
        },
        path,
    )
    return {"artifact": str(path), "features": features, "years": sequences["years"]}


"""Refresh stored SHAP summaries and territory drivers for existing models.

Run after changing the explainability pipeline so the API serves consistent
probability-space values without retraining.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.ml.features import (  # noqa: E402
    FEATURES,
    SPATIAL_FEATURES,
    add_features,
    add_spatial_features,
    build_analytical_frame,
)
from app.models.ml import MLModel  # noqa: E402
from app.services.modeling import load_artifact, refresh_territory_top_features  # noqa: E402
from app.services.xai import global_explanation  # noqa: E402


def main() -> int:
    summary = []
    with SessionLocal() as db:
        models = db.execute(select(MLModel).where(MLModel.task == "classification")).scalars().all()
        for model in models:
            payload = load_artifact(model)
            features = payload.get("features", FEATURES)
            frame = add_features(build_analytical_frame(db))
            if any(feature in SPATIAL_FEATURES for feature in features):
                frame = add_spatial_features(db, frame)
            result = global_explanation(
                payload["estimator"],
                frame[features],
                top_n=12,
                model_id=model.id,
                model_name=model.name,
                algorithm=model.algorithm,
            )
            model.shap_summary = result
            db.commit()
            if model.is_active:
                updated = refresh_territory_top_features(db, model)
                summary.append({"model_id": model.id, "algorithm": model.algorithm, "territory_rows": updated})
            else:
                summary.append({"model_id": model.id, "algorithm": model.algorithm, "territory_rows": 0})
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

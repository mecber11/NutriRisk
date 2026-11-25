"""Reproducible training pipeline for the three core algorithms plus hybrids.

Usage (inside backend/):
    python -m scripts.train_pipeline --algorithms random_forest xgboost catboost
    python -m scripts.train_pipeline --include-spatial --include-cnn
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.bootstrap import bootstrap  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ml.features import build_analytical_frame  # noqa: E402
from app.models.data import Child  # noqa: E402
from app.models.ml import MLModel, ModelExperiment  # noqa: E402
from app.services.modeling import model_metrics_table, train_bundle  # noqa: E402

logger = logging.getLogger("nutririsk.train")


def main() -> int:
    parser = argparse.ArgumentParser(description="Entrena y registra los modelos de NutriRisk AI")
    parser.add_argument("--algorithms", nargs="+", default=["random_forest", "xgboost", "catboost"])
    parser.add_argument("--cv-strategy", default="group_kfold_region")
    parser.add_argument("--target", default="stunting")
    parser.add_argument("--task", default="classification")
    parser.add_argument("--seed", type=int, default=settings.random_seed)
    parser.add_argument("--include-spatial", action="store_true", default=True)
    parser.add_argument("--include-cnn", action="store_true")
    parser.add_argument("--skip-seed", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
    )

    if not args.skip_seed:
        bootstrap()

    with SessionLocal() as db:
        total = db.scalar(select(func.count(Child.id))) or 0
        if total == 0:
            logger.error("No hay niños cargados; ejecute primero scripts/seed.py")
            return 2
        frame = build_analytical_frame(db)
        logger.info("Conjunto analítico: %s filas, %s territorios", len(frame), frame["territory_code"].nunique())

        started = time.perf_counter()
        result = train_bundle(
            db,
            algorithms=args.algorithms,
            task=args.task,
            target=args.target,
            cv_strategy=args.cv_strategy,
            seed=args.seed,
            hyperparams=None,
            user_id=None,
            dataset_id=None,
            notes="Entrenamiento reproducible vía scripts/train_pipeline.py",
            include_spatial=args.include_spatial,
            include_cnn_lstm=args.include_cnn,
        )
        elapsed = round(time.perf_counter() - started, 1)

        experiments = db.execute(
            select(ModelExperiment).where(ModelExperiment.id.in_(result["experiments"]))
        ).scalars().all()
        summary = [
            {
                "experiment_id": experiment.id,
                "algorithm": experiment.algorithm,
                "status": experiment.status,
                "auc": (experiment.metrics or {}).get("auc"),
                "f1": (experiment.metrics or {}).get("f1"),
                "accuracy": (experiment.metrics or {}).get("accuracy"),
                "regions": len(experiment.per_region_metrics or {}),
                "duration_s": experiment.duration_seconds,
            }
            for experiment in experiments
        ]
        active = db.scalar(select(MLModel).where(MLModel.is_active.is_(True)))
        output = {
            "elapsed_seconds": elapsed,
            "experiments": summary,
            "errors": result["errors"],
            "active_model_id": active.id if active else None,
            "scoring": result["scoring"],
            "comparison": model_metrics_table(db),
        }
        print(json.dumps(output, indent=2, default=str))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

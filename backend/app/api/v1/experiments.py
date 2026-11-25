"""Model experiments: training queue, comparison and regional metrics."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.deps import DbSession, PageParams, paginated, require_permission
from app.core.rbac import Action, Module, RoleCode
from app.db.session import SessionLocal
from app.ml.models import ALGORITHM_DESCRIPTIONS, ALGORITHM_LABELS
from app.models.ml import MLModel, ModelExperiment
from app.models.user import User
from app.schemas.ml import (
    ExperimentOut,
    ModelComparisonRow,
    TrainRequest,
    TrainingJobAccepted,
)
from app.services.modeling import (
    activate_model,
    model_metrics_table,
    score_model,
    select_best_model,
    train_experiment,
)

router = APIRouter(prefix="/experiments", tags=["Modelado y experimentos"])
logger = logging.getLogger("nutririsk.experiments")

EXP_READ = Depends(require_permission(Module.EXPERIMENTS, Action.READ))
EXP_EXECUTE = Depends(require_permission(Module.EXPERIMENTS, Action.EXECUTE))


@router.get("/algorithms", summary="Algoritmos disponibles")
def algorithms(_: User = EXP_READ) -> dict:
    return {
        "algorithms": [
            {"code": code, "label": ALGORITHM_LABELS.get(code, code), "description": description}
            for code, description in ALGORITHM_DESCRIPTIONS.items()
        ],
        "cv_strategies": [
            {"code": "group_kfold_region", "label": "GroupKFold por región", "description": "5 pliegues agrupados por región."},
            {"code": "leave_one_region_out", "label": "Leave-one-region-out", "description": "Deja una región fuera por iteración."},
            {"code": "stratified_kfold", "label": "K-Fold estratificado", "description": "Partición aleatoria estratificada."},
        ],
        "tasks": ["classification", "regression"],
        "targets": ["stunting", "wasting", "underweight", "haz", "waz", "whz"],
    }


def _run_training_sequence(experiment_ids: list[int], user_id: int | None, include_spatial: bool) -> None:
    """Background worker: train every queued experiment, pick the best and score."""
    with SessionLocal() as db:
        completed: list[int] = []
        for experiment_id in experiment_ids:
            experiment = db.get(ModelExperiment, experiment_id)
            if experiment is None:
                continue
            try:
                train_experiment(
                    db,
                    algorithm=experiment.algorithm,
                    task=experiment.task,
                    target=experiment.target,
                    cv_strategy=experiment.cv_strategy,
                    seed=experiment.seed,
                    hyperparams=experiment.hyperparams,
                    user_id=user_id,
                    notes=experiment.notes,
                    include_spatial=include_spatial,
                    experiment_id=experiment_id,
                )
                completed.append(experiment_id)
            except Exception:  # noqa: BLE001
                logger.exception("Fallo entrenando experimento %s", experiment_id)
        best = select_best_model(db, completed)
        if best is not None:
            activate_model(db, best.id)
            try:
                score_model(db, best)
            except Exception:  # noqa: BLE001
                logger.exception("Fallo al puntuar tras el entrenamiento")


@router.post("/train", response_model=TrainingJobAccepted, status_code=status.HTTP_202_ACCEPTED, summary="Entrenar modelos")
def train(
    payload: TrainRequest,
    background: BackgroundTasks,
    db: DbSession,
    user: User = EXP_EXECUTE,
) -> TrainingJobAccepted:
    if user.role.code not in (RoleCode.ADMIN, RoleCode.DATA_SCIENTIST):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo científicos de datos o administradores")
    if not payload.algorithms:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Seleccione al menos un algoritmo")

    experiment_ids: list[int] = []
    for algorithm in payload.algorithms:
        experiment = ModelExperiment(
            name=f"{ALGORITHM_LABELS.get(algorithm, algorithm)} · {payload.target}",
            algorithm=algorithm,
            task="regression" if algorithm == "cnn_lstm" else payload.task,
            target=payload.target,
            dataset_id=payload.dataset_id,
            cv_strategy=payload.cv_strategy,
            seed=42,
            hyperparams=payload.hyperparams or {},
            metrics={},
            status="QUEUED",
            notes=payload.notes,
            created_by=user.id,
        )
        db.add(experiment)
        db.flush()
        experiment_ids.append(experiment.id)
    db.commit()

    background.add_task(
        _run_training_sequence,
        experiment_ids,
        user.id,
        payload.include_spatial,
    )
    return TrainingJobAccepted(
        message="Entrenamiento encolado. Consulte el estado en el listado de experimentos.",
        experiment_ids=experiment_ids,
        task=payload.task,
        algorithms=list(payload.algorithms),
    )


@router.get("", summary="Listar experimentos")
def list_experiments(
    db: DbSession,
    page: PageParams,
    algorithm: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    _: User = EXP_READ,
) -> dict:
    stmt = select(ModelExperiment)
    count_stmt = select(func.count(ModelExperiment.id))
    conditions = []
    if algorithm:
        conditions.append(ModelExperiment.algorithm == algorithm)
    if status_filter:
        conditions.append(ModelExperiment.status == status_filter)
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)
    total = db.scalar(count_stmt) or 0
    experiments = db.execute(
        stmt.order_by(ModelExperiment.id.desc()).offset(page.offset).limit(page.limit)
    ).scalars().all()
    return paginated(
        [ExperimentOut.model_validate(experiment).model_dump() for experiment in experiments],
        total,
        page.page,
        page.page_size,
    )


@router.get("/compare", response_model=list[ModelComparisonRow], summary="Comparar modelos")
def compare(db: DbSession, _: User = EXP_READ) -> list[ModelComparisonRow]:
    return [ModelComparisonRow(**row) for row in model_metrics_table(db)]


@router.get("/{experiment_id}", response_model=ExperimentOut, summary="Detalle del experimento")
def get_experiment(experiment_id: int, db: DbSession, _: User = EXP_READ) -> ExperimentOut:
    experiment = db.get(ModelExperiment, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experimento no encontrado")
    return ExperimentOut.model_validate(experiment)


@router.get("/{experiment_id}/regions", summary="Métricas por región y subgrupo")
def experiment_regions(experiment_id: int, db: DbSession, _: User = EXP_READ) -> dict:
    experiment = db.get(ModelExperiment, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experimento no encontrado")
    return {
        "experiment_id": experiment.id,
        "algorithm": experiment.algorithm,
        "cv_strategy": experiment.cv_strategy,
        "per_region": experiment.per_region_metrics or {},
        "per_group": experiment.per_group_metrics or {},
        "spatial_diagnostics": experiment.spatial_diagnostics or {},
    }


@router.delete("/{experiment_id}", summary="Eliminar experimento")
def delete_experiment(
    experiment_id: int,
    db: DbSession,
    _: User = Depends(require_permission(Module.EXPERIMENTS, Action.DELETE)),
) -> dict[str, str]:
    experiment = db.get(ModelExperiment, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experimento no encontrado")
    linked = db.execute(select(MLModel).where(MLModel.experiment_id == experiment.id)).scalars().all()
    if any(model.is_active for model in linked):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No puede eliminar el modelo activo")
    for model in linked:
        db.delete(model)
    db.delete(experiment)
    db.commit()
    return {"message": "Experimento eliminado"}


_ = datetime.now(timezone.utc)

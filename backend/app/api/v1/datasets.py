"""Dataset catalogue, uploads, quality control and variable dictionary."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.core.config import settings
from app.core.deps import DbSession, PageParams, paginated, require_permission
from app.core.rbac import Action, Module
from app.models.data import Child, Dataset, IngestionRun, Territory, VariableDefinition
from app.models.user import User
from app.schemas.data import DatasetCreate, DatasetDetail, DatasetOut, IngestionRunOut, UploadResult, VariableOut
from app.services.ingestion import (
    IngestionError,
    checksum,
    detect_format,
    ingest_file,
    read_table,
    slugify,
    SUPPORTED_EXTENSIONS,
)
from app.services.synthetic import VARIABLE_DICTIONARY

router = APIRouter(prefix="/datasets", tags=["Datasets e ingesta"])

DATASET_READ = Depends(require_permission(Module.DATASETS, Action.READ))
DATASET_CREATE = Depends(require_permission(Module.DATASETS, Action.CREATE))


def _serialize(dataset: Dataset) -> DatasetOut:
    return DatasetOut.model_validate(dataset)


@router.get("/sources", summary="Fuentes de datos soportadas")
def sources(_: User = DATASET_READ) -> dict[str, Any]:
    return {
        "sources": [
            {"code": "DHS", "label": "DHS Program", "description": "Encuestas demográficas y de salud."},
            {"code": "WORLD_BANK", "label": "World Bank Microdata", "description": "Microdatos socioeconómicos."},
            {"code": "UNICEF", "label": "UNICEF Data", "description": "Indicadores de nutrición y niñez."},
            {"code": "WORLDPOP", "label": "WorldPop", "description": "Capas de población geoespacial."},
            {"code": "SYNTHETIC", "label": "Sintético", "description": "Datos de demostración generados por NutriRisk AI."},
            {"code": "CUSTOM", "label": "Personalizado", "description": "Archivo propio con esquema canónico."},
        ],
        "formats": sorted(set(SUPPORTED_EXTENSIONS.values())),
        "max_upload_mb": settings.max_upload_mb,
        "canonical_columns": [item["name"] for item in VARIABLE_DICTIONARY],
    }


@router.get("/template", summary="Descargar plantilla CSV canónica")
def template(_: User = DATASET_READ) -> FileResponse:
    path = settings.storage_dir / "datasets" / "plantilla_carga_nutririsk.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        headers = ",".join(item["name"] for item in VARIABLE_DICTIONARY)
        example = ",".join(
            [
                "CH-2024-T01-0001", "HH-2024-T01-00001", "T01", "Norte", "2024", "24", "M",
                "11.2", "85.5", "13.4", "false", "3100", "8", "2", "-0.4", "PRIMARY", "27",
                "IMPROVED", "SHARED", "false", "WOOD", "3", "5", "0.55", "RURAL", "true", "true",
                "false", "false", "120", "700", "26", "0.42",
            ]
        )
        path.write_text(headers + "\n" + example + "\n", encoding="utf-8")
    return FileResponse(path, filename="plantilla_carga_nutririsk.csv", media_type="text/csv")


@router.get("", summary="Catálogo de datasets")
def list_datasets(
    db: DbSession,
    page: PageParams,
    source: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    _: User = DATASET_READ,
) -> dict:
    stmt = select(Dataset)
    count_stmt = select(func.count(Dataset.id))
    conditions = []
    if source:
        conditions.append(Dataset.source == source)
    if status_filter:
        conditions.append(Dataset.status == status_filter)
    if search:
        conditions.append(func.lower(Dataset.name).like(f"%{search.lower()}%"))
    if conditions:
        stmt = stmt.where(*conditions)
        count_stmt = count_stmt.where(*conditions)
    total = db.scalar(count_stmt) or 0
    datasets = db.execute(stmt.order_by(Dataset.id.desc()).offset(page.offset).limit(page.limit)).scalars().all()
    return paginated([_serialize(dataset).model_dump() for dataset in datasets], total, page.page, page.page_size)


@router.post("/upload", response_model=UploadResult, status_code=status.HTTP_201_CREATED, summary="Cargar dataset")
def upload_dataset(
    db: DbSession,
    file: UploadFile = File(...),
    name: str = Form(...),
    source: str = Form(default="CUSTOM"),
    kind: str = Form(default="CHILD"),
    analysis_unit: str = Form(default="CHILD"),
    description: str | None = Form(default=None),
    period_year: int | None = Form(default=None),
    country: str | None = Form(default=None),
    license: str | None = Form(default=None),
    user: User = DATASET_CREATE,
) -> UploadResult:
    filename = Path(file.filename or "dataset.csv").name
    try:
        fmt = detect_format(filename)
    except IngestionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    destination_dir = settings.storage_dir / "uploads"
    destination_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex[:10]}_{filename}"
    destination = destination_dir / stored_name
    size = 0
    with destination.open("wb") as buffer:
        while chunk := file.file.read(1 << 20):
            size += len(chunk)
            if size > settings.max_upload_mb * 1024 * 1024:
                buffer.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"El archivo excede {settings.max_upload_mb} MB",
                )
            buffer.write(chunk)

    slug_base = slugify(name)[:100] or "dataset"
    slug = slug_base
    suffix = 1
    while db.scalar(select(Dataset).where(Dataset.slug == slug)):
        suffix += 1
        slug = f"{slug_base}-{suffix}"

    dataset = Dataset(
        name=name,
        slug=slug,
        source=source,
        kind=kind,
        analysis_unit=analysis_unit,
        description=description,
        period_year=period_year,
        country=country,
        license=license,
        file_name=filename,
        file_path=str(destination),
        file_format=fmt,
        checksum_sha256=checksum(destination),
        is_synthetic=source == "SYNTHETIC",
        status="PENDING",
        created_by=user.id,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    try:
        outcome = ingest_file(db, dataset=dataset, path=destination, trigger="UPLOAD", user_id=user.id)
    except IngestionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    db.refresh(dataset)
    db.refresh(outcome.run)
    return UploadResult(
        dataset=_serialize(dataset),
        run=IngestionRunOut.model_validate(outcome.run),
        preview=outcome.preview,
        quality=outcome.quality or None,
    )


@router.post("", response_model=DatasetOut, status_code=status.HTTP_201_CREATED, summary="Registrar dataset vacío")
def create_dataset(payload: DatasetCreate, db: DbSession, user: User = DATASET_CREATE) -> DatasetOut:
    slug_base = slugify(payload.name)[:100]
    slug = slug_base
    suffix = 1
    while db.scalar(select(Dataset).where(Dataset.slug == slug)):
        suffix += 1
        slug = f"{slug_base}-{suffix}"
    dataset = Dataset(
        name=payload.name,
        slug=slug,
        source=payload.source,
        kind=payload.kind,
        analysis_unit=payload.analysis_unit,
        description=payload.description,
        period_year=payload.period_year,
        country=payload.country,
        license=payload.license,
        is_synthetic=payload.source == "SYNTHETIC",
        status="PENDING",
        created_by=user.id,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return _serialize(dataset)


@router.get("/{dataset_id}", response_model=DatasetDetail, summary="Detalle del dataset")
def get_dataset(dataset_id: int, db: DbSession, _: User = DATASET_READ) -> DatasetDetail:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado")
    variables = db.execute(
        select(VariableDefinition).where(VariableDefinition.dataset_id == dataset_id).order_by(VariableDefinition.id)
    ).scalars().all()
    payload = DatasetDetail.model_validate(dataset)
    payload.variables = [VariableOut.model_validate(variable) for variable in variables]
    return payload


@router.get("/{dataset_id}/variables", response_model=list[VariableOut], summary="Diccionario de variables")
def dataset_variables(dataset_id: int, db: DbSession, _: User = DATASET_READ) -> list[VariableOut]:
    variables = db.execute(
        select(VariableDefinition).where(VariableDefinition.dataset_id == dataset_id).order_by(VariableDefinition.id)
    ).scalars().all()
    return [VariableOut.model_validate(variable) for variable in variables]


@router.get("/{dataset_id}/quality", summary="Reporte de calidad")
def dataset_quality(dataset_id: int, db: DbSession, _: User = DATASET_READ) -> dict[str, Any]:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado")
    return {
        "dataset_id": dataset.id,
        "quality_report": dataset.quality_report or {},
        "rows": dataset.rows,
        "columns": dataset.columns,
        "status": dataset.status,
    }


@router.get("/{dataset_id}/preview", summary="Vista previa de registros")
def dataset_preview(dataset_id: int, db: DbSession, limit: int = Query(default=10, ge=1, le=100), _: User = DATASET_READ) -> dict:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or not dataset.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no disponible")
    path = Path(dataset.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado en disco")
    frame = read_table(path, dataset.file_format or detect_format(path.name))
    import pandas as pd

    return {
        "columns": list(frame.columns),
        "rows": frame.head(limit).replace({pd.NA: None}).to_dict(orient="records"),
        "total_rows": int(len(frame)),
    }


@router.post("/{dataset_id}/reprocess", response_model=IngestionRunOut, summary="Reprocesar dataset")
def reprocess_dataset(dataset_id: int, db: DbSession, user: User = Depends(require_permission(Module.INGESTION, Action.EXECUTE))) -> IngestionRunOut:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None or not dataset.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado")
    path = Path(dataset.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado")
    try:
        outcome = ingest_file(db, dataset=dataset, path=path, trigger="REPROCESS", user_id=user.id)
    except IngestionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return IngestionRunOut.model_validate(outcome.run)


@router.delete("/{dataset_id}", summary="Eliminar dataset")
def delete_dataset(dataset_id: int, db: DbSession, _: User = Depends(require_permission(Module.DATASETS, Action.DELETE))) -> dict[str, str]:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado")
    children = db.scalar(select(func.count(Child.id))) or 0
    if children and dataset.source == "SYNTHETIC":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El dataset sintético alimenta la demo; regenere los datos con el módulo de sistema.",
        )
    if dataset.file_path:
        Path(dataset.file_path).unlink(missing_ok=True)
    db.delete(dataset)
    db.commit()
    return {"message": "Dataset eliminado"}


@router.get("/{dataset_id}/runs", response_model=list[IngestionRunOut], summary="Historial de ingestas")
def dataset_runs(dataset_id: int, db: DbSession, _: User = DATASET_READ) -> list[IngestionRunOut]:
    runs = db.execute(
        select(IngestionRun).where(IngestionRun.dataset_id == dataset_id).order_by(IngestionRun.id.desc()).limit(50)
    ).scalars().all()
    return [IngestionRunOut.model_validate(run) for run in runs]


_ = (Territory, shutil)

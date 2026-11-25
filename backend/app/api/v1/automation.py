"""Six auditable orchestration operations for n8n; no arbitrary URL fetching."""
from datetime import datetime, timezone
import json

import httpx
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.deps import DbSession
from app.core.integrations import require_service_token
from app.db.session import SessionLocal
from app.models.data import Dataset
from app.models.ml import MLModel
from app.services.audit import write_audit as append_audit

router = APIRouter(prefix='/automation', tags=['Automatización n8n'], dependencies=[Depends(require_service_token)])

class EvidenceRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


@router.post('/evidence')
def evidence(payload: EvidenceRequest):
    from app.services.evidence import retrieve
    return retrieve(payload.question)


@router.post('/acquire')
def acquire(db: DbSession):
    # Contextual public indicator only; never fabricated child-level data.
    url = 'https://api.worldbank.org/v2/country/PER/indicator/SH.STA.STNT.ZS?format=json&per_page=100'
    try:
        response = httpx.get(url, timeout=30, follow_redirects=False)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or len(payload) != 2 or not isinstance(payload[1], list):
            raise ValueError('Respuesta del proveedor no válida')
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, f'No se pudo adquirir el indicador público: {type(exc).__name__}') from exc
    folder = settings.storage_dir / 'external'
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    path = folder / f'worldbank_stunting_PER_{stamp}.json'
    path.write_text(json.dumps({'source_url': url, 'retrieved_at': stamp, 'usage': 'Contexto nacional; no mezclar con microdatos sintéticos. Revisar metadatos y licencia del proveedor antes de publicar.', 'payload': payload}, ensure_ascii=False, indent=2), encoding='utf-8')
    result = {'source': 'World Bank', 'indicator': 'SH.STA.STNT.ZS', 'country': 'PER', 'rows': len(payload[1]), 'file': path.name, 'loaded_into_children': False}
    append_audit(db, module='ingestion', action='ACQUIRE_PUBLIC', result='SUCCESS', detail=result)
    return result


@router.post('/quality')
def quality(db: DbSession):
    from pathlib import Path
    from app.services.ingestion import read_table, normalize_columns, coerce_frame, build_quality_report
    results = []
    for dataset in db.scalars(select(Dataset)).all():
        if not dataset.file_path or not Path(dataset.file_path).is_file():
            results.append({'dataset_id': dataset.id, 'status': 'SKIPPED', 'reason': 'Archivo no disponible'})
            continue
        try:
            frame = normalize_columns(read_table(Path(dataset.file_path), dataset.file_format or 'csv'))
            clean, issues = coerce_frame(frame)
            report = build_quality_report(clean)
            dataset.quality_report = report
            results.append({'dataset_id': dataset.id, 'status': 'CHECKED', 'issues': len(issues), 'quality': report})
        except Exception as exc:
            results.append({'dataset_id': dataset.id, 'status': 'FAILED', 'error': type(exc).__name__})
    db.commit()
    append_audit(db, module='ingestion', action='QUALITY_SCAN', detail={'datasets': len(results)})
    return {'results': results, 'note': 'Normalización y coerción para evaluación; no se sobrescriben mediciones clínicas ni se imputan resultados.'}


def _score(model_id):
    from app.services.modeling import score_model
    with SessionLocal() as db:
        model = db.get(MLModel, model_id)
        try:
            score_model(db, model)
            append_audit(db, module='models', action='SCHEDULED_SCORE', resource_id=model_id)
        except Exception as exc:
            db.rollback()
            append_audit(db, module='models', action='SCHEDULED_SCORE', result='FAILED', detail={'error': type(exc).__name__})


@router.post('/predict', status_code=202)
def predict(db: DbSession, background: BackgroundTasks):
    model = db.scalar(select(MLModel).where(MLModel.is_active.is_(True), MLModel.task == 'classification'))
    if model is None:
        raise HTTPException(409, 'No hay modelo de clasificación activo')
    background.add_task(_score, model.id)
    return {'status': 'QUEUED', 'model_id': model.id}


@router.post('/monitor')
def monitor(db: DbSession):
    from app.services.modeling import model_metrics_table
    from app.models.audit import AuditLog
    from sqlalchemy import func
    result = {'timestamp': datetime.now(timezone.utc).isoformat(), 'models': model_metrics_table(db), 'audit_events': db.scalar(select(func.count(AuditLog.id))) or 0,
              'limitations': 'Métricas de entrenamiento/validación registradas. Sin etiquetas nuevas no se afirma evaluación prospectiva ni detección de deriva de desempeño.'}
    append_audit(db, module='system', action='SCHEDULED_MONITORING', detail={'model_count': len(result['models'])})
    return result

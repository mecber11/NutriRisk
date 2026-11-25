"""Research protocol, experiment execution, figures and integration inventory."""
from __future__ import annotations
import json
import csv
import re
import threading
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.deps import require_permission
from app.core.rbac import Module, Action
from app.models.user import User
from app.core.config import settings
from app.services.research import research_root, new_run_id, run_study

router = APIRouter(prefix='/research', tags=['Protocolo científico'])
READ = Depends(require_permission(Module.EXPERIMENTS, Action.READ))
EXECUTE = Depends(require_permission(Module.EXPERIMENTS, Action.EXECUTE))
LOCK = threading.Lock()
PROJECT = Path(__file__).resolve().parents[4]

def real_folder() -> Path:
    pointer = research_root() / 'latest_real.json'
    if not pointer.is_file():
        raise HTTPException(404, 'No hay ejecución real disponible')
    folder = run_folder(json.loads(pointer.read_text(encoding='utf-8'))['id'])
    if json.loads((folder / 'results.json').read_text(encoding='utf-8')).get('synthetic') is not False:
        raise HTTPException(409, 'La ejecución no acredita datos reales')
    return folder

@router.get('/real/latest')
def real_latest(_: User = READ):
    folder = real_folder()
    return {'results': json.loads((folder / 'results.json').read_text(encoding='utf-8')),
            'gallery': json.loads((folder / 'figures.json').read_text(encoding='utf-8')),
            'manifest': json.loads((PROJECT / 'data/real/manifest.json').read_text(encoding='utf-8-sig')),
            'verification': json.loads((folder / 'verification.json').read_text(encoding='utf-8'))}

@router.get('/real/trials')
def real_trials(_: User = READ):
    with (real_folder() / 'trials.csv').open(encoding='utf-8', newline='') as source:
        return {'items': list(csv.DictReader(source))}


@lru_cache(maxsize=2)
def _public_rows(modified: int):
    with (PROJECT / 'data/real/country_panel.csv').open(encoding='utf-8-sig', newline='') as source:
        rows = []
        for raw in csv.DictReader(source):
            row = {}
            for key, value in raw.items():
                if key == 'is_synthetic': row[key] = value.lower() == 'true'
                elif key == 'period_year': row[key] = int(value)
                elif key in ['country_code', 'country_name', 'region', 'region_code', 'source']: row[key] = value.strip()
                else: row[key] = float(value) if value else None
            rows.append(row)
        return rows


@router.get('/real/dataset')
def public_dataset(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                   year: int | None = Query(None, ge=2000, le=2024), country: str = Query('', max_length=3),
                   region: str = Query('', max_length=100), search: str = Query('', max_length=100), _: User = READ):
    path = PROJECT / 'data/real/country_panel.csv'
    rows = _public_rows(path.stat().st_mtime_ns)
    manifest = json.loads((PROJECT / 'data/real/manifest.json').read_text(encoding='utf-8-sig'))
    selected = [row for row in rows if (year is None or row['period_year'] == year)
                and (not country or row['country_code'] == country.upper())
                and (not region or row['region'] == region.strip())
                and (not search or search.casefold() in (row['country_name'] + ' ' + row['country_code']).casefold())]
    selected = sorted(selected, key=lambda x: (x['country_name'], x['period_year']))
    countries = sorted({(row['country_code'], row['country_name']) for row in rows}, key=lambda x: x[1])
    trend = []
    for period in sorted({row['period_year'] for row in selected}):
        group = [row for row in selected if row['period_year'] == period]
        values = [row['stunting_prevalence_pct'] for row in group if row['stunting_prevalence_pct'] is not None]
        trend.append({'year': period, 'prevalence': sum(values) / len(values) if values else None, 'countries': len(group)})
    variables = []
    for key, indicator in manifest['indicators'].items():
        metadata = manifest.get('indicator_metadata', {}).get(key, [{}])[0]
        variables.append({'variable': key, 'indicator': indicator, 'name': metadata.get('name', key),
                          'definition': metadata.get('sourceNote', ''), 'provider': metadata.get('sourceOrganization', ''),
                          'url': f'https://data.worldbank.org/indicator/{indicator}',
                          'api_url': f'https://api.worldbank.org/v2/country/all/indicator/{indicator}?format=json&date=2000:2024&per_page=20000'})
    return {'items': selected[(page - 1) * page_size:page * page_size], 'total': len(selected), 'page': page, 'page_size': page_size,
            'rows_total': len(rows), 'countries': [{'code': code, 'name': name} for code, name in countries],
            'years': sorted({row['period_year'] for row in rows}), 'regions': sorted({row['region'] for row in rows}),
            'trend': trend, 'variables': variables, 'synthetic': False, 'dataset_sha256': manifest['output']['sha256'],
            'retrieved_at': manifest['created_utc'], 'source_url': manifest['methodology_url'], 'license_url': manifest['license_url']}


def classification_folder() -> Path:
    root = settings.storage_dir / 'classification'
    pointer = root / 'latest.json'
    if not pointer.is_file(): raise HTTPException(404, 'La evaluación de clasificación todavía no está disponible')
    run_id = json.loads(pointer.read_text(encoding='utf-8'))['id']
    if not re.fullmatch(r'\d{8}T\d{6}-[a-f0-9]{8}', run_id): raise HTTPException(404, 'Ejecución no encontrada')
    folder = root / run_id
    if not (folder / 'results.json').is_file(): raise HTTPException(404, 'Evaluación incompleta')
    return folder


@router.get('/real/classification')
def classification_result(_: User = READ):
    return json.loads((classification_folder() / 'results.json').read_text(encoding='utf-8'))


@router.get('/real/classification/files/{filename:path}')
def classification_file(filename: str, _: User = READ):
    folder = classification_folder()
    result = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
    allowed = {key: folder / key for key in ['results.json', 'predictions.csv', 'trials.csv', 'epochs.csv', 'permutation_importance.csv', 'evidence.zip', 'verification.json']}
    for figure in result.get('figures', []):
        stem = figure.get('id', figure.get('name', ''))
        if re.fullmatch(r'[a-zA-Z0-9_-]+', stem):
            for extension in ['png', 'svg', 'pdf']: allowed[f'{stem}.{extension}'] = folder / 'figures' / f'{stem}.{extension}'
    path = allowed.get(filename)
    if path is None or not path.is_file() or not path.resolve().is_relative_to(folder.resolve()): raise HTTPException(404, 'Archivo no disponible')
    return FileResponse(path, filename=filename)

@router.get('/real/files/{filename:path}')
def real_file(filename: str, _: User = READ):
    folder = real_folder()
    allowed = {name: folder / name for name in ['results.json', 'metrics.csv', 'predictions.csv', 'regional_metrics.csv', 'pairwise_statistics.csv', 'epochs.csv', 'trials.csv', 'figures.json', 'evidence.zip', 'artifact_hashes.json', 'verification.json']}
    allowed.update({name: PROJECT / 'data/real' / name for name in ['country_panel.csv', 'manifest.json', 'README.md']})
    gallery = json.loads((folder / 'figures.json').read_text(encoding='utf-8'))
    for figure in gallery['figures']:
        for extension in figure['formats']:
            name = f"{figure['name']}.{extension}"
            if re.fullmatch(r'[a-zA-Z0-9_-]+\.(png|svg|pdf)', name):
                allowed[name] = folder / 'figures' / name
    path = allowed.get(filename)
    if path is None or not path.is_file() or not path.resolve().is_relative_to(PROJECT.resolve()):
        raise HTTPException(404, 'Archivo no disponible')
    return FileResponse(path, filename=filename)

class StudyRequest(BaseModel):
    trials: int = Field(default=50, ge=2, le=150)
    seed: int = Field(default=42, ge=0, le=2147483647)


def run_folder(run_id: str) -> Path:
    if not re.fullmatch(r'\d{8}T\d{6}-[a-f0-9]{8}', run_id):
        raise HTTPException(404, 'Experimento no encontrado')
    folder = research_root() / run_id
    if not folder.is_dir():
        raise HTTPException(404, 'Experimento no encontrado')
    return folder


@router.get('/audit')
def audit(_: User = READ):
    return {'items': [
        {'requirement': 'Datos públicos reales', 'state': 'verificado', 'evidence': '161 países; panel Banco Mundial/JME; manifiesto y hashes descargables. Estimaciones nacionales, no microdatos.'},
        {'requirement': 'Entrenamiento real de cinco modelos', 'state': 'completado', 'evidence': 'RF, XGBoost, CatBoost, XGBoost+GP y CNN-LSTM; siete regiones; 10 trials por modelo/pliegue, 350 candidatos, 35 ajustes finales.'},
        {'requirement': 'Pruebas estadísticas', 'state': 'completado', 'evidence': 'Friedman y Kendall W; diez Wilcoxon con Holm, efectos e IC; Shapiro y Moran exploratorios con p crudos; bootstrap regional.'},
        {'requirement': 'Reproducibilidad y figuras', 'state': 'disponible', 'evidence': 'Código, entorno, semillas, parámetros, trials, épocas, predicciones, cuatro figuras en tres formatos y ZIP.'},
        {'requirement': 'Validación clínica, causal o independiente en pacientes', 'state': 'pendiente de investigación', 'evidence': 'No acreditada. Estudio ecológico con siete regiones y dependencia espacial; no se traslada al riesgo individual.'},
        {'requirement': 'Módulos históricos sintéticos', 'state': 'separado', 'evidence': 'Conservados como demo sintética. No aportan evidencia al estudio real.'},
        {'requirement': 'Servicios externos', 'state': 'no acreditado', 'evidence': 'Esta ejecución no prueba operación de n8n, LangFlow, PostgreSQL, MinIO o MLflow.'},
    ]}


def _worker(run_id, trials, seed):
    try:
        run_study(run_id, trials, seed)
    finally:
        LOCK.release()


@router.post('/runs', status_code=202)
def start(payload: StudyRequest, background: BackgroundTasks, _: User = EXECUTE):
    if not LOCK.acquire(blocking=False):
        raise HTTPException(409, 'Ya hay un estudio en ejecución')
    run_id = new_run_id()
    folder = research_root() / run_id
    folder.mkdir()
    (folder / 'status.json').write_text(json.dumps({'id': run_id, 'status': 'QUEUED', 'trials_per_model_per_outer_fold': payload.trials}), encoding='utf-8')
    background.add_task(_worker, run_id, payload.trials, payload.seed)
    return {'id': run_id, 'status': 'QUEUED'}


@router.get('/runs')
def runs(_: User = READ):
    items = []
    for path in sorted(research_root().glob('*/status.json'), reverse=True):
        items.append(json.loads(path.read_text(encoding='utf-8')))
    return {'items': items}


@router.get('/runs/{run_id}')
def run(run_id: str, _: User = READ):
    folder = run_folder(run_id)
    data = json.loads((folder / 'status.json').read_text(encoding='utf-8'))
    for filename, key in [('results.json', 'results'), ('figures.json', 'gallery'), ('integrations.json', 'integrations')]:
        if (folder / filename).exists():
            data[key] = json.loads((folder / filename).read_text(encoding='utf-8'))
    return data


@router.get('/runs/{run_id}/files/{filename}')
def download(run_id: str, filename: str, _: User = READ):
    folder = run_folder(run_id)
    allowed = {'results.json', 'predictions.csv', 'region_blocks.csv', 'figures.json', 'figuras_alta_calidad.zip', 'integrations.json', 'classification_oof.csv', 'classification_metrics.json'}
    figures_path = folder / 'figures.json'
    if figures_path.exists():
        for figure in json.loads(figures_path.read_text(encoding='utf-8'))['figures']:
            allowed.update(f"{figure['name']}.{extension}" for extension in figure['formats'])
    if filename not in allowed or not (folder / filename).is_file():
        raise HTTPException(404, 'Archivo no disponible')
    media = {'png': 'image/png', 'svg': 'image/svg+xml', 'pdf': 'application/pdf', 'zip': 'application/zip', 'csv': 'text/csv', 'json': 'application/json'}
    return FileResponse(folder / filename, filename=filename, media_type=media.get(filename.rsplit('.',1)[-1]))


@router.get('/workflows')
def workflows(_: User = READ):
    return {'items': [{'name': path.name, 'title': json.loads(path.read_text(encoding='utf-8')).get('name', path.stem)} for path in sorted((PROJECT / 'n8n' / 'workflows').glob('WF-*.json'))]}


@router.get('/workflows/{filename}')
def workflow_file(filename: str, _: User = READ):
    if not re.fullmatch(r'WF-0[1-6]_[a-z_]+\.json', filename):
        raise HTTPException(404, 'Workflow no encontrado')
    path = PROJECT / 'n8n' / 'workflows' / filename
    if not path.is_file():
        raise HTTPException(404, 'Workflow no encontrado')
    return FileResponse(path, filename=filename, media_type='application/json')

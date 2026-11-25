"""Finalize a real run with provenance, verification and downloadable evidence."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
from app.services.real_research import ROOT, save
from app.core.config import settings


def complete(run_id):
    from scripts.verify_real import verify
    folder = settings.storage_dir / 'research' / run_id
    result = json.loads((folder / 'results.json').read_text(encoding='utf-8'))
    assert not result['synthetic'] and result['status'] == 'COMPLETED'
    result['protocol'].update(
        completed_trial_fits=len(result['folds']) * result['protocol']['trials_per_model_per_outer_fold'],
        completed_outer_fits=len(result['folds']),
        monitoring_note='Outer validation 2022 shares training-country identities; selection uses the separate inner-country validation. CatBoost use_best_model=False; all algorithms use fixed trial-selected iteration counts.',
        random_forest_history='No iterative epochs; trials and final train/validation metrics are recorded. Boosting/CNN histories are in epochs.csv.',
    )
    titles = ['MAE de transferencia geográfica en 2023', 'Prevalencia publicada frente a estimada', 'Heterogeneidad del MAE por región', 'Curvas de validación CNN-LSTM por época']
    existing = json.loads((folder / 'figures.json').read_text(encoding='utf-8')) if (folder / 'figures.json').exists() else {'figures': []}
    notes = {figure['name']: figure for figure in existing['figures']}
    figures = [{**notes.get(path.stem, {}), 'name': path.stem, 'title': title, 'formats': ['png', 'svg', 'pdf'], 'path': 'figures/' + path.stem} for path, title in zip(sorted((folder / 'figures').glob('*.png')), titles)]
    save(folder / 'figures.json', {'figures': figures})
    reproducibility = folder / 'reproducibility'
    reproducibility.mkdir(exist_ok=True)
    paths = ['data/real/country_panel.csv', 'data/real/manifest.json', 'data/real/README.md',
             'backend/app/services/real_research.py', 'backend/scripts/train_real.py',
             'backend/scripts/verify_real.py', 'backend/scripts/package_real.py', 'backend/scripts/acquire_real_data.ps1', 'backend/scripts/export_regression_figures.py']
    for relative in paths:
        destination = reproducibility / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    mutable = {'state.json', 'status.json', 'results.json', 'artifact_hashes.json', 'evidence.zip', 'verification.json'}
    hashes = {str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest() for path in folder.rglob('*') if path.is_file() and path.name not in mutable}
    save(folder / 'artifact_hashes.json', hashes)
    save(folder / 'results.json', result)
    verify(run_id)
    result['artifacts'] = [{'path': str(path.relative_to(folder)), 'bytes': path.stat().st_size} for path in folder.rglob('*') if path.is_file() and path.name not in ['evidence.zip', 'state.json']]
    save(folder / 'results.json', result)
    with zipfile.ZipFile(folder / 'evidence.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in folder.rglob('*'):
            if path.is_file() and path.name not in ['evidence.zip', 'state.json']:
                archive.write(path, str(path.relative_to(folder)))
    print('PACKAGED', run_id)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    complete(parser.parse_args().run_id)

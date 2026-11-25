"""Comparable, nested spatio-temporal experiments and publication figures.

This study is separate from operational child classification. All five models
estimate territory prevalence, on identical held-out regions in the final year.
No final-year labels enter preprocessing, tuning, model fitting or selection.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.preprocessing import StandardScaler

from app.core.config import settings
from app.db.session import SessionLocal
from app.ml.features import FEATURES, add_features, build_analytical_frame

LABELS = {'random_forest': 'Random Forest', 'xgboost': 'XGBoost', 'catboost': 'CatBoost', 'spatial_xgboost': 'XGBoost + GP espacial', 'cnn_lstm': 'CNN-LSTM'}


def research_root() -> Path:
    path = settings.storage_dir / 'research'
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def metrics(y, prediction) -> dict:
    return {'mae': float(mean_absolute_error(y, prediction)), 'rmse': float(np.sqrt(mean_squared_error(y, prediction))), 'r2': float(r2_score(y, prediction)) if len(y) > 2 else None}


def holm(pvalues: list[float]) -> list[float]:
    order = np.argsort(pvalues)
    adjusted = np.empty(len(order))
    previous = 0.0
    for rank, index in enumerate(order):
        previous = max(previous, min(1.0, float(pvalues[index]) * (len(order) - rank)))
        adjusted[index] = previous
    return adjusted.tolist()


def paired_statistics(blocks: pd.DataFrame) -> dict:
    """Blocks are disjoint held-out regions, never five aggregate model scores."""
    if len(blocks) < 3 or blocks.shape[1] < 3 or not np.isfinite(blocks.to_numpy()).all():
        raise ValueError('Se requieren al menos tres bloques completos y tres modelos comparables.')
    values = blocks.to_numpy()
    if np.all(np.ptp(values, axis=1) == 0):
        friedman = {'statistic': 0.0, 'pvalue': 1.0}
    else:
        test = stats.friedmanchisquare(*[values[:, i] for i in range(values.shape[1])])
        friedman = {'statistic': float(test.statistic), 'pvalue': float(test.pvalue)}
    pairs = []
    for a, b in itertools.combinations(blocks.columns, 2):
        delta = blocks[a].to_numpy() - blocks[b].to_numpy()
        p = 1.0 if np.allclose(delta, 0) else float(stats.wilcoxon(delta, method='exact').pvalue)
        pairs.append({'a': a, 'b': b, 'pvalue': p, 'median_mae_difference': float(np.median(delta))})
    for row, adjusted in zip(pairs, holm([p['pvalue'] for p in pairs])):
        row['pvalue_holm'] = adjusted
    return {'blocks': list(blocks.index), 'n_blocks': len(blocks), 'metric': 'MAE territorial', 'friedman': friedman, 'wilcoxon_holm': pairs,
            'interpretation': 'Exploratorio: pocas regiones, posible correlación espacial y entrenamiento solapado entre pliegues. No demuestra superioridad clínica ni independencia estadística de regiones.'}


def bootstrap_regions(y, prediction, groups, seed: int = 42, repeats: int = 1000) -> dict:
    rng = np.random.default_rng(seed)
    unique = np.unique(groups)
    estimates = []
    for _ in range(repeats):
        sampled = rng.choice(unique, len(unique), replace=True)
        indices = np.concatenate([np.flatnonzero(groups == group) for group in sampled])
        estimates.append(metrics(y[indices], prediction[indices])['mae'])
    lo, hi = np.quantile(estimates, [0.025, 0.975])
    return {'metric': 'mae', 'lower': float(lo), 'upper': float(hi), 'method': 'percentile cluster bootstrap por región', 'replicates': repeats, 'warning': 'Intervalo exploratorio; solo cinco grupos en la demostración.'}


def sample_params(trial, algorithm: str) -> dict:
    if algorithm == 'cnn_lstm':
        return {'learning_rate': trial.suggest_float('learning_rate', 0.001, 0.03, log=True), 'hidden': trial.suggest_categorical('hidden', [8, 16, 32]), 'channels': trial.suggest_categorical('channels', [4, 8, 16]), 'dropout': trial.suggest_float('dropout', 0.05, 0.4), 'weight_decay': trial.suggest_float('weight_decay', 1e-5, 0.03, log=True), 'epochs': trial.suggest_int('epochs', 30, 90, step=30)}
    if algorithm == 'random_forest':
        return {'n_estimators': trial.suggest_int('n_estimators', 40, 120, step=40), 'max_depth': trial.suggest_int('max_depth', 2, 8), 'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 4)}
    if algorithm == 'catboost':
        return {'iterations': trial.suggest_int('iterations', 40, 120, step=40), 'depth': trial.suggest_int('depth', 2, 6), 'learning_rate': trial.suggest_float('learning_rate', 0.02, 0.2, log=True), 'l2_leaf_reg': trial.suggest_float('l2_leaf_reg', 1, 10)}
    return {'n_estimators': trial.suggest_int('n_estimators', 40, 120, step=40), 'max_depth': trial.suggest_int('max_depth', 2, 6), 'learning_rate': trial.suggest_float('learning_rate', 0.02, 0.2, log=True), 'reg_lambda': trial.suggest_float('reg_lambda', 0.5, 10, log=True)}


def predict_fold(algorithm, x_train, y_train, x_test, coordinates_train, coordinates_test, params, seed=42):
    """All fitted transforms see training data only; no anthropometric features."""
    imputer = SimpleImputer(strategy='median', keep_empty_features=True)
    shape_train, shape_test = x_train.shape, x_test.shape
    train = imputer.fit_transform(x_train.reshape(len(x_train), -1))
    test = imputer.transform(x_test.reshape(len(x_test), -1))
    if algorithm == 'cnn_lstm':
        import torch
        from torch import nn
        torch.set_num_threads(1)
        torch.manual_seed(seed)
        scaler = StandardScaler().fit(train)
        train = scaler.transform(train).reshape(shape_train)
        test = scaler.transform(test).reshape(shape_test)
        class Network(nn.Module):
            def __init__(self):
                super().__init__()
                self.conv = nn.Conv1d(shape_train[2], params['channels'], 2, padding=1)
                self.lstm = nn.LSTM(params['channels'], params['hidden'], batch_first=True)
                self.dropout = nn.Dropout(params['dropout'])
                self.head = nn.Linear(params['hidden'], 1)
            def forward(self, value):
                value = torch.relu(self.conv(value.transpose(1, 2))).transpose(1, 2)
                value, _ = self.lstm(value)
                return self.head(self.dropout(value[:, -1])).squeeze(-1)
        model = Network()
        optimizer = torch.optim.AdamW(model.parameters(), lr=params['learning_rate'], weight_decay=params['weight_decay'])
        tx = torch.tensor(train, dtype=torch.float32)
        mean, scale = float(y_train.mean()), float(y_train.std()) or 1.0
        ty = torch.tensor((y_train - mean) / scale, dtype=torch.float32)
        history = []
        for _ in range(params['epochs']):
            model.train()
            optimizer.zero_grad()
            loss = nn.functional.mse_loss(model(tx), ty)
            loss.backward()
            optimizer.step()
            history.append(float(loss.detach()))
        model.eval()
        with torch.no_grad():
            result = model(torch.tensor(test, dtype=torch.float32)).numpy() * scale + mean
        return np.clip(result, 0, 1), history
    if algorithm == 'random_forest':
        model = RandomForestRegressor(**params, random_state=seed, n_jobs=1)
    elif algorithm == 'catboost':
        from catboost import CatBoostRegressor
        model = CatBoostRegressor(**params, random_seed=seed, verbose=False, allow_writing_files=False, thread_count=1)
    else:
        from xgboost import XGBRegressor
        model = XGBRegressor(**params, random_state=seed, n_jobs=1, tree_method='hist')
    model.fit(train, y_train)
    result = model.predict(test)
    if algorithm == 'spatial_xgboost':
        # Spatial residual model fitted exclusively to training territories.
        residual = y_train - model.predict(train)
        scaler = StandardScaler().fit(coordinates_train)
        gp = GaussianProcessRegressor(kernel=RBF(1.0) + WhiteKernel(0.01), alpha=1e-4, optimizer=None, normalize_y=True)
        gp.fit(scaler.transform(coordinates_train), residual)
        result = result + gp.predict(scaler.transform(coordinates_test))
    return np.clip(result, 0, 1), []


def prepare_data(frame: pd.DataFrame) -> dict:
    frame = add_features(frame)
    grouped = frame.groupby(['territory_code', 'region', 'period_year']).agg({**{key: 'mean' for key in FEATURES}, 'stunting': 'mean', 'latitude': 'first', 'longitude': 'first'}).reset_index()
    years = sorted(int(v) for v in grouped.period_year.unique())
    if len(years) < 3:
        raise ValueError('Se requieren tres años para separar ajuste y evaluación final con ventanas de dos años.')
    # Only complete territories. Never fill an absent territory/year with zeros.
    codes = sorted(code for code, rows in grouped.groupby('territory_code') if set(years[-3:]).issubset(set(rows.period_year)))
    indexed = grouped.set_index(['territory_code', 'period_year'])
    def array(periods):
        return np.array([[indexed.loc[(code, year), FEATURES].to_numpy(float) for year in periods] for code in codes])
    train_x, test_x = array(years[-3:-1]), array(years[-2:])
    train_y = np.array([indexed.loc[(code, years[-2]), 'stunting'] for code in codes], dtype=float)
    test_y = np.array([indexed.loc[(code, years[-1]), 'stunting'] for code in codes], dtype=float)
    groups = np.array([indexed.loc[(code, years[-2]), 'region'] for code in codes])
    coords = np.array([indexed.loc[(code, years[-2]), ['latitude', 'longitude']].to_numpy(float) for code in codes])
    if len(set(groups)) < 4 or not np.isfinite(coords).all():
        raise ValueError('Se requieren cuatro regiones y coordenadas completas para validación anidada.')
    return dict(train_x=train_x, test_x=test_x, train_y=train_y, test_y=test_y, groups=groups, coords=coords, codes=codes, years=years[-3:])


def run_study(run_id: str, trials: int = 50, seed: int = 42) -> None:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    folder = research_root() / run_id
    folder.mkdir(exist_ok=True)
    started = time.perf_counter()
    state = {'id': run_id, 'status': 'RUNNING', 'created_at': datetime.now(timezone.utc).isoformat(), 'trials_per_model_per_outer_fold': trials, 'seed': seed, 'completed_fits': 0}
    save_json(folder / 'status.json', state)
    try:
        with SessionLocal() as db:
            raw = build_analytical_frame(db)
        data = prepare_data(raw)
        x, xt, y, yt, groups, coords = (data[key] for key in ('train_x', 'test_x', 'train_y', 'test_y', 'groups', 'coords'))
        raw_hash = hashlib.sha256(raw.sort_values('child_id').to_csv(index=False).encode()).hexdigest()
        records, tuning, histories = [], [], {}
        outer = list(LeaveOneGroupOut().split(x, y, groups))
        for algorithm in LABELS:
            for fold, (train, test) in enumerate(outer):
                region = str(groups[test[0]])
                state.update(current_model=algorithm, current_region=region)
                save_json(folder / 'status.json', state)
                inner = list(LeaveOneGroupOut().split(x[train], y[train], groups[train]))
                def objective(trial):
                    params = sample_params(trial, algorithm)
                    errors = []
                    for step, (itr, iva) in enumerate(inner):
                        a, b = train[itr], train[iva]
                        prediction, _ = predict_fold(algorithm, x[a], y[a], x[b], coords[a], coords[b], params, seed)
                        errors.append(mean_absolute_error(y[b], prediction))
                        trial.report(float(np.mean(errors)), step)
                        if trial.should_prune():
                            raise optuna.TrialPruned()
                    return float(np.mean(errors))
                study = optuna.create_study(direction='minimize', sampler=optuna.samplers.TPESampler(seed=seed), pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=1))
                study.optimize(objective, n_trials=trials)
                prediction, history = predict_fold(algorithm, x[train], y[train], xt[test], coords[train], coords[test], study.best_params, seed)
                if history:
                    histories[region] = history
                for index, predicted in zip(test, prediction):
                    records.append({'algorithm': algorithm, 'region': region, 'territory': data['codes'][index], 'year': data['years'][-1], 'observed': float(yt[index]), 'predicted': float(predicted)})
                tuning.append({'algorithm': algorithm, 'held_out_region': region, 'best_params': study.best_params, 'inner_mae': study.best_value, 'trials': [{'number': t.number, 'state': t.state.name, 'value': t.value, 'params': t.params} for t in study.trials]})
                state['completed_fits'] += 1
                save_json(folder / 'status.json', state)
        predictions = pd.DataFrame(records)
        predictions.to_csv(folder / 'predictions.csv', index=False)
        rows, block_rows = [], []
        for algorithm, subset in predictions.groupby('algorithm', sort=False):
            observed = subset.observed.to_numpy()
            predicted = subset.predicted.to_numpy()
            rows.append({'algorithm': algorithm, 'label': LABELS[algorithm], **metrics(observed, predicted), 'ci': bootstrap_regions(observed, predicted, subset.region.to_numpy(), seed)})
            for region, block in subset.groupby('region'):
                block_rows.append({'algorithm': algorithm, 'region': region, **metrics(block.observed, block.predicted)})
        blocks = pd.DataFrame(block_rows).pivot(index='region', columns='algorithm', values='mae')
        blocks.to_csv(folder / 'region_blocks.csv')
        result = {'id': run_id, 'status': 'COMPLETED', 'synthetic': bool(raw.get('is_synthetic', pd.Series([True])).any()),
                  'protocol': 'Nested leave-one-region-out, same 2-year covariate windows; final-year labels sealed until outer evaluation.',
                  'target': 'Prevalencia territorial de retraso del crecimiento', 'task': 'regression', 'unit': 'territorio', 'years': data['years'], 'n_territories': len(data['codes']),
                  'training_label_year': data['years'][-2], 'final_label_year': data['years'][-1], 'trials': trials, 'budget': 'Mismo número de trials por modelo/pliegue; tiempo medido, no se afirma igualdad de cómputo.',
                  'sampler': 'TPESampler', 'pruner': 'MedianPruner', 'dataset_sha256': raw_hash, 'seed': seed, 'metrics': rows,
                  'statistics': paired_statistics(blocks), 'tuning': tuning, 'elapsed_seconds': round(time.perf_counter() - started, 2),
                  'limitations': ['Datos sintéticos: sin validación clínica ni externa.', '24 territorios y cinco regiones: estimaciones inestables.', 'Se utilizan determinantes del año final; es estimación contemporánea, no pronóstico sin covariables futuras.', 'Friedman y Wilcoxon son exploratorios; regiones espacialmente dependientes y ajustes solapados.', 'El híbrido espacial de este estudio es XGBoost + proceso gaussiano residual, distinto de los diagnósticos SAR/SEM operativos.', 'No se aplican McNemar ni DeLong a regresión; MASE, WIS, Dice, mAP y Grad-CAM no corresponden a esta tarea.', 'PRISMA, licencias de microdatos reales, validación externa y publicación requieren investigación y evidencia adicional.']}
        save_json(folder / 'results.json', result)
        make_figures(folder, result, predictions, blocks, histories)
        log_integrations(folder, result)
        state.update(status='COMPLETED', elapsed_seconds=result['elapsed_seconds'])
        save_json(folder / 'status.json', state)
        save_json(research_root() / 'latest.json', {'id': run_id})
    except Exception as exc:
        state.update(status='FAILED', error=str(exc))
        save_json(folder / 'status.json', state)
        raise


def make_figures(folder, result, predictions, blocks, histories):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False, 'svg.fonttype': 'none', 'savefig.facecolor': 'white'})
    manifest = []
    def save(fig, name, title):
        fig.text(0.5, 0.01, 'NutriRisk AI · Datos sintéticos · Evaluación exploratoria', ha='center', fontsize=9, color='#526173')
        for extension in ('png', 'svg', 'pdf'):
            fig.savefig(folder / f'{name}.{extension}', dpi=600, bbox_inches='tight', pad_inches=0.2)
        manifest.append({'name': name, 'title': title, 'formats': ['png', 'svg', 'pdf'], 'dpi': 600})
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.axis('off')
    layers = [('Adquisición', 'CSV / XLSX / Parquet · APIs públicas · diccionario y licencias'), ('n8n · WF-01 a WF-06', 'Descarga · calidad · inferencia · alertas · reportes · monitoreo'), ('LangChain + LangFlow', 'Herramientas de consulta · recuperación de evidencia · prototipado'), ('Motor de IA', 'RF · XGBoost · CatBoost · XGBoost + GP · CNN-LSTM\nOptuna · validación anidada · SHAP · estadística'), ('Backend y almacenamiento', 'FastAPI · PostgreSQL/PostGIS · MinIO · MLflow'), ('Resultados', 'React · mapas · alertas · reportes · figuras PNG 600 dpi / SVG / PDF')]
    for i, (title, detail) in enumerate(layers):
        y0 = 0.91 - i * 0.15
        ax.add_patch(FancyBboxPatch((0.05, y0 - .08), .9, .105, boxstyle='round,pad=0.015', facecolor='#eaf3fa', edgecolor='#166b91', transform=ax.transAxes))
        ax.text(.5, y0 + .003, title, transform=ax.transAxes, ha='center', weight='bold', color='#12334b')
        ax.text(.5, y0 - .030, detail, transform=ax.transAxes, ha='center', va='top', fontsize=9.5)
        if i < 5:
            ax.annotate('', xy=(.5, y0 - .125), xytext=(.5, y0 - .095), xycoords='axes fraction', arrowprops={'arrowstyle': '->', 'color': '#166b91'})
    ax.set_title('Arquitectura de investigación y aplicación', pad=20, weight='bold')
    ax.text(.5, -.02, 'n8n / LangFlow / PostgreSQL / MinIO: configuración disponible; consultar estado de despliegue.', transform=ax.transAxes, ha='center', fontsize=8, color='#526173')
    save(fig, 'arquitectura', 'Arquitectura tecnológica')
    fig, ax = plt.subplots(figsize=(10, 6))
    rows = result['metrics']
    positions = np.arange(len(rows))
    values = np.array([r['mae'] for r in rows])
    # Bootstrap intervals need not bracket the sample estimate; draw independently.
    ax.barh(positions, values, color='#167d9a', alpha=.75)
    for i, row in enumerate(rows):
        ax.plot([row['ci']['lower'], row['ci']['upper']], [i, i], color='#162f47', linewidth=2)
    ax.set_yticks(positions, [r['label'] for r in rows])
    ax.set_xlabel('MAE de prevalencia (menor es mejor) · IC bootstrap por región')
    ax.set_title('Cinco modelos sobre los mismos territorios y año final')
    fig.tight_layout(rect=(0,.04,1,1))
    save(fig, 'comparacion_modelos', 'Comparación e incertidumbre')
    fig, ax = plt.subplots(figsize=(11, 6))
    image = ax.imshow(blocks.to_numpy(), cmap='YlOrRd', aspect='auto')
    ax.set_xticks(range(len(blocks.columns)), [LABELS[a] for a in blocks.columns], rotation=20, ha='right')
    ax.set_yticks(range(len(blocks)), blocks.index)
    for i in range(len(blocks)):
        for j in range(len(blocks.columns)):
            ax.text(j, i, f'{blocks.iloc[i,j]:.3f}', ha='center', va='center', fontsize=10)
    fig.colorbar(image, ax=ax, label='MAE territorial')
    ax.set_title('Bloques regionales de evaluación · sin mezclar métricas agregadas')
    fig.tight_layout(rect=(0,.04,1,1))
    save(fig, 'mapa_calor_regiones', 'Errores por región y modelo')
    fig, axes = plt.subplots(2, 3, figsize=(13, 8))
    for ax, (algorithm, subset) in zip(axes.flat, predictions.groupby('algorithm', sort=False)):
        ax.scatter(subset.observed, subset.predicted, c='#167d9a', alpha=.8, edgecolors='white')
        ax.plot([0,.5],[0,.5], '--', color='#a44b3b')
        ax.set(xlabel='Prevalencia observada', ylabel='Prevalencia estimada', title=LABELS[algorithm], xlim=(0,.5), ylim=(0,.5))
    axes.flat[-1].axis('off')
    fig.tight_layout(rect=(0,.05,1,1))
    save(fig, 'observado_estimado', 'Observado frente a estimado')
    fig, ax = plt.subplots(figsize=(11, 6))
    for region, history in histories.items():
        ax.plot(range(1,len(history)+1), history, label=region)
    ax.legend(title='Región excluida')
    ax.set(xlabel='Época', ylabel='MSE estandarizado de entrenamiento', title='CNN-LSTM · curvas de entrenamiento (no curvas de validación)')
    fig.tight_layout(rect=(0,.04,1,1))
    save(fig, 'curvas_cnn_lstm', 'Curvas de entrenamiento CNN-LSTM')
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.axis('off')
    steps = [('2021–2022', 'Ajuste interno\nRegiones de entrenamiento'), ('Optuna', 'TPE + MedianPruner\nSin etiquetas finales'), ('2023', 'Región excluida\nEvaluación final'), ('Estadística', 'Bloques regionales\nBootstrap + Holm')]
    for i, (title, detail) in enumerate(steps):
        x0 = .025 + i*.25
        ax.add_patch(FancyBboxPatch((x0,.35),.20,.35,boxstyle='round,pad=.015',facecolor='#eaf3fa',edgecolor='#167d9a',transform=ax.transAxes))
        ax.text(x0+.10,.60,title,transform=ax.transAxes,ha='center',weight='bold')
        ax.text(x0+.10,.45,detail,transform=ax.transAxes,ha='center',fontsize=9)
        if i<3: ax.annotate('',xy=(x0+.24,.52),xytext=(x0+.21,.52),xycoords='axes fraction',arrowprops={'arrowstyle':'->'})
    ax.set_title('Protocolo común · estimación contemporánea con separación espacial y temporal')
    save(fig, 'protocolo_experimental', 'Protocolo experimental')
    # Separate classification figures: same child-level endpoint, no CNN regression
    # mixed into ROC curves. Fixed threshold; no threshold chosen on held-out labels.
    classification_figures(folder, save)
    save_json(folder / 'figures.json', {'figures': manifest})
    with zipfile.ZipFile(folder / 'figuras_alta_calidad.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in folder.iterdir():
            if path.suffix in ('.png', '.svg', '.pdf', '.csv') or path.name in ('results.json','figures.json','classification_metrics.json'):
                archive.write(path, path.name)


def architecture_figure():
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    fig, ax = plt.subplots(figsize=(12,8))
    ax.axis('off')
    layers = [
        ('Adquisición de datos', 'CSV / XLSX / Parquet · APIs públicas · diccionario y procedencia'),
        ('n8n · WF-01 a WF-06', 'Adquisición · calidad · predicciones · alertas · reportes · monitoreo'),
        ('LangChain + LangFlow', 'Herramientas y recuperación de evidencia · prototipo visual'),
        ('Motor de inteligencia artificial', 'RF · XGBoost · CatBoost · XGBoost + GP · CNN-LSTM\nOptuna · validación anidada · SHAP · estadística'),
        ('Backend y almacenamiento', 'FastAPI · PostgreSQL/PostGIS · MinIO · MLflow'),
        ('Frontend y resultados', 'React · mapas · alertas · reportes · figuras PNG / SVG / PDF'),
    ]
    for i,(title, detail) in enumerate(layers):
        y=.91-i*.15
        ax.add_patch(FancyBboxPatch((.05,y-.08),.90,.105,boxstyle='round,pad=.015',facecolor='#eaf3fa',edgecolor='#166b91',transform=ax.transAxes))
        ax.text(.5,y+.003,title,transform=ax.transAxes,ha='center',weight='bold',color='#12334b')
        ax.text(.5,y-.030,detail,transform=ax.transAxes,ha='center',va='top',fontsize=9.5)
        if i<5: ax.annotate('',xy=(.5,y-.125),xytext=(.5,y-.095),xycoords='axes fraction',arrowprops={'arrowstyle':'->','color':'#166b91'})
    ax.set_title('Arquitectura de investigación y aplicación',pad=20,weight='bold')
    ax.text(.5,-.02,'n8n / LangFlow / PostgreSQL / MinIO: configuración disponible; consultar estado de despliegue.',transform=ax.transAxes,ha='center',fontsize=8,color='#526173')
    return fig


def classification_figures(folder, save):
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve
    from sklearn.metrics import roc_curve, precision_recall_curve, confusion_matrix
    from app.ml.models import build_estimator, predict_scores, classification_metrics
    from app.ml.features import feature_matrix
    with SessionLocal() as db:
        frame = add_features(build_analytical_frame(db))
        from app.models.ml import MLModel
        from sqlalchemy import select
        active = db.scalar(select(MLModel).where(MLModel.is_active.is_(True)))
        shap_summary = dict(active.shap_summary or {}) if active else {}
        active_name = active.name if active else ''
    x = feature_matrix(frame, FEATURES)
    y = frame.stunting.to_numpy(dtype=int)
    groups = frame.region.to_numpy()
    splits = list(LeaveOneGroupOut().split(x, y, groups))
    outputs, rows = {}, []
    for algorithm in ['random_forest', 'xgboost', 'catboost']:
        predictions = np.full(len(y), np.nan)
        for train, test in splits:
            model = build_estimator(algorithm, 'classification')
            model.fit(x.iloc[train], y[train])
            predictions[test] = predict_scores(model, x.iloc[test])
        outputs[algorithm] = predictions
        rows.append({'algorithm': algorithm, **classification_metrics(y,predictions,.5)})
    pd.DataFrame({'child_id': frame.child_id, 'region': groups, 'observed': y, **outputs}).to_csv(folder / 'classification_oof.csv', index=False)
    save_json(folder / 'classification_metrics.json', {'task': 'child_classification', 'protocol': 'Leave-one-region-out, fixed defaults, threshold=0.5. Separate cross-sectional diagnostic, NOT the optimized five-model territory study.', 'synthetic': True, 'metrics': rows})
    fig, axes = plt.subplots(1,2,figsize=(12,5))
    for algorithm, prediction in outputs.items():
        fpr,tpr,_ = roc_curve(y,prediction)
        precision,recall,_ = precision_recall_curve(y,prediction)
        axes[0].plot(fpr,tpr,label=LABELS[algorithm])
        axes[1].plot(recall,precision,label=LABELS[algorithm])
    axes[0].plot([0,1],[0,1],'--',color='gray')
    axes[1].axhline(y.mean(),linestyle='--',color='gray',label='Prevalencia')
    axes[0].set(xlabel='Tasa de falsos positivos',ylabel='Sensibilidad',title='ROC · clasificación por niño')
    axes[1].set(xlabel='Recall',ylabel='Precisión',title='Precision–Recall · clasificación por niño')
    for ax in axes: ax.legend(fontsize=9)
    fig.tight_layout(rect=(0,.05,1,1))
    save(fig,'roc_precision_recall','ROC y Precision–Recall · tres clasificadores')
    fig, axes = plt.subplots(1,3,figsize=(13,4.5))
    for ax,(algorithm,prediction) in zip(axes,outputs.items()):
        matrix=confusion_matrix(y,prediction>=.5,labels=[0,1])
        ax.imshow(matrix,cmap='Blues')
        for i in range(2):
            for j in range(2): ax.text(j,i,str(matrix[i,j]),ha='center',va='center',color='white' if matrix[i,j]>matrix.max()/2 else '#12334b')
        ax.set(xticks=[0,1],yticks=[0,1],xlabel='Predicción',ylabel='Observación',title=LABELS[algorithm])
    fig.suptitle('Matrices de confusión · predicciones fuera de región · umbral fijo 0,5')
    fig.tight_layout(rect=(0,.06,1,.94))
    save(fig,'matrices_confusion','Matrices de confusión')
    fig, ax=plt.subplots(figsize=(8,6))
    for algorithm,prediction in outputs.items():
        observed,predicted=calibration_curve(y,prediction,n_bins=8,strategy='quantile')
        ax.plot(predicted,observed,marker='o',label=LABELS[algorithm])
    ax.plot([0,1],[0,1],'--',color='gray')
    ax.legend()
    ax.set(xlabel='Probabilidad media estimada',ylabel='Frecuencia observada',title='Calibración fuera de región · sin recalibración sobre prueba')
    fig.tight_layout(rect=(0,.04,1,1))
    save(fig,'calibracion','Calibración de clasificadores')
    features=shap_summary.get('features',[])[:12]
    if features:
        fig,ax=plt.subplots(figsize=(11,7))
        labels=[str(row.get('label',row.get('feature',''))) for row in features][::-1]
        values=[float(row.get('mean_abs_shap', row.get('importance',0))) for row in features][::-1]
        ax.barh(labels,values,color='#167d9a')
        ax.set(xlabel='Contribución absoluta media SHAP almacenada',title=f'SHAP operativo · {active_name}')
        fig.tight_layout(rect=(0,.04,1,1))
        save(fig,'shap_global','Explicabilidad SHAP del modelo operativo')


def log_integrations(folder, result):
    """Explicit, opt-in integrations; failures remain visible in the run record."""
    import os
    status = {'mlflow': 'not_configured', 'minio': 'not_configured'}
    tracking = os.getenv('MLFLOW_TRACKING_URI')
    if tracking:
        try:
            import mlflow
            mlflow.set_tracking_uri(tracking)
            mlflow.set_experiment('NutriRisk-common-protocol')
            with mlflow.start_run(run_name=result['id']):
                mlflow.log_params({'trials': result['trials'], 'seed': result['seed'], 'dataset_sha256': result['dataset_sha256'], 'task': result['task']})
                for row in result['metrics']:
                    mlflow.log_metric(f"{row['algorithm']}_mae", row['mae'])
                mlflow.log_artifacts(str(folder))
            status['mlflow'] = 'logged'
        except Exception as exc:
            status['mlflow'] = f'error: {type(exc).__name__}'
    if os.getenv('S3_ENDPOINT_URL'):
        try:
            import boto3
            client = boto3.client('s3', endpoint_url=os.environ['S3_ENDPOINT_URL'])
            bucket = os.getenv('S3_BUCKET', 'nutririsk')
            client.head_bucket(Bucket=bucket)
            client.upload_file(str(folder / 'figuras_alta_calidad.zip'), bucket, f"research/{result['id']}/figuras_alta_calidad.zip")
            status['minio'] = 'uploaded'
        except Exception as exc:
            status['minio'] = f'error: {type(exc).__name__}'
    save_json(folder / 'integrations.json', status)


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8]

"""Independently recompute final metrics and contrasts from exported predictions."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[1]
store = ROOT / 'backend/storage/research'
run_id = json.loads((store / 'latest_real.json').read_text())['id']
r = json.loads((store / run_id / 'results.json').read_text(encoding='utf-8'))
pred = pd.read_csv(store / run_id / 'predictions.csv')
checks = []
for model in r['models']:
    frame = pred[pred.algorithm == model['algorithm']]
    actual = [mean_absolute_error(frame.observed, frame.predicted), np.sqrt(mean_squared_error(frame.observed, frame.predicted)), r2_score(frame.observed, frame.predicted)]
    assert np.allclose(actual, [model['metrics']['test'][k] for k in ['mae', 'rmse', 'r2']])
    assert len(frame) == 161 and frame.country_code.nunique() == 161
    checks.append('recomputed_metrics_' + model['algorithm'])
algorithms = [m['algorithm'] for m in r['models'] if not m['algorithm'].startswith('baseline_')]
mae = pred.assign(error=lambda f: abs(f.observed - f.predicted)).groupby(['region', 'algorithm']).error.mean().unstack()[algorithms]
fr = stats.friedmanchisquare(*mae.to_numpy().T)
assert np.isclose(fr.statistic, r['statistics']['friedman']['statistic'])
assert np.isclose(fr.pvalue, r['statistics']['friedman']['pvalue'])
checks.append('independent_friedman_from_predictions')
for row in r['statistics']['wilcoxon_holm']:
    delta = mae[row['a']] - mae[row['b']]
    w = stats.wilcoxon(delta, method='exact')
    assert np.isclose(w.statistic, row['statistic']) and np.isclose(w.pvalue, row['pvalue'])
checks.append('ten_recomputed_wilcoxon_statistics')
pairs = r['statistics']['wilcoxon_holm']
assert np.allclose(multipletests([row['pvalue'] for row in pairs], method='holm')[1], [row['pvalue_holm'] for row in pairs])
checks.append('holm_verified_with_statsmodels')
assert not any('stunting' in feature for feature in r['features'])
assert r['protocol']['train_years'][1] < r['protocol']['validation_year'] < r['protocol']['test_year']
checks.append('target_excluded_and_chronology_checked')
out = {'status': 'PASSED', 'run_id': run_id, 'count': len(checks), 'checks': checks}
(ROOT / 'entregables/statistical_audit.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
print(json.dumps(out))

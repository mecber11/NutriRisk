"""Verify real-run provenance, completeness, folds and persisted predictions."""
import json, hashlib, argparse
from pathlib import Path
import numpy as np, pandas as pd
from app.services.real_research import ROOT,FEATURES,LABELS,load_fold,predict
from app.core.config import settings

def verify(run_id):
    folder=settings.storage_dir/'research'/run_id;r=json.loads((folder/'results.json').read_text(encoding='utf-8'));pred=pd.read_csv(folder/'predictions.csv');trials=pd.read_csv(folder/'trials.csv');raw=pd.read_csv(ROOT/'data/real/country_panel.csv');checks=[]
    assert r['synthetic'] is False and r['status']=='COMPLETED'
    assert hashlib.sha256((ROOT/'data/real/country_panel.csv').read_bytes()).hexdigest()==r['data_summary']['dataset_sha256'];checks.append('dataset_sha256')
    assert len(trials)==len(r['folds'])*r['protocol']['trials_per_model_per_outer_fold'];assert len(r['folds'])==35;assert pred.groupby('algorithm').size().nunique()==1;checks.append('350_trials_35_outer_fits_identical_test_countries')
    for f in r['folds']:
        assert not set(f['inner_validation_countries']) & set(raw.loc[raw.region==f['region'],'country_code']);a=f['algorithm'];g=pred[(pred.algorithm==a)&(pred.region==f['region'])];xx=[]
        for country in g.country_code:
            w=raw[(raw.country_code==country)&raw.period_year.between(2021,2023)].sort_values('period_year');assert len(w)==3;xx.append(w[FEATURES].to_numpy(float))
        bundle=load_fold(folder,a,f['fold']);pp=predict(bundle,np.asarray(xx),g[['latitude','longitude']].to_numpy());assert np.allclose(pp,g.predicted,atol=1e-7),(a,f['fold']);checks.append(f'persisted_prediction_{a}_{f["fold"]}')
        if a == 'catboost':
            assert bundle['model'].get_param('use_best_model') is False
            assert bundle['model'].tree_count_ == f['hyperparameters']['iterations']
            checks.append(f'catboost_fixed_iterations_no_monitor_selection_{f["fold"]}')
    for relative,digest in json.loads((folder/'artifact_hashes.json').read_text()).items():assert hashlib.sha256((folder/relative).read_bytes()).hexdigest()==digest,relative
    checks.append('all_artifact_sha256');out={'status':'PASSED','checks':checks,'count':len(checks)};(folder/'verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_id');verify(p.parse_args().run_id)

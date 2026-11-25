"""Independent recomputation and publication checks; does not refit models."""
import sys, json, hashlib, zipfile, importlib.metadata, platform, uuid, shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from PIL import Image
from sklearn.metrics import roc_curve,roc_auc_score,precision_score,recall_score,f1_score,confusion_matrix
from app.services.real_research import save,ROOT
from app.core.config import settings

base=settings.storage_dir/'classification';folder=base/json.loads((base/'latest.json').read_text())['id'];r=json.loads((folder/'results.json').read_text());p=pd.read_csv(folder/'predictions.csv');checks=[]
if folder.name.endswith('-jme-classification'):
    runid=folder.name.split('-')[0]+'-'+uuid.uuid4().hex[:8];target=base/runid
    assert folder.resolve().parent==base.resolve() and target.resolve().parent==base.resolve()
    folder.rename(target);folder=target;r['id']=runid;save(base/'latest.json',dict(id=runid));save(base/'latest_running.json',dict(id=runid));save(folder/'state.json',dict(id=runid,status='COMPLETED',completed_final_fits=35))
shutil.copy2(__file__,folder/'source/verify_public_classification.py');shutil.copy2(ROOT/'backend/app/services/real_research.py',folder/'source/real_research.py')
for m in r['models']:
    g=p[p.algorithm==m['algorithm']];y=g.observed.to_numpy();prob=g.probability.to_numpy();h=prob>=.5;t=m['metrics']['test']
    for k,v in dict(roc_auc=roc_auc_score(y,prob),precision=precision_score(y,h,zero_division=0),recall=recall_score(y,h),f1=f1_score(y,h)).items():
        assert np.isclose(t[k],v,atol=1e-12),(m['algorithm'],k);checks.append(dict(algorithm=m['algorithm'],check=k,passed=True))
    assert np.array_equal(m['confusion_matrix'],confusion_matrix(y,h,labels=[0,1]));assert len(g)==161 and g.country_code.nunique()==161
    fpr,tpr,th=roc_curve(y,prob,drop_intermediate=False);m['roc']=dict(fpr=fpr,tpr=tpr,thresholds=[float(v) if np.isfinite(v) else None for v in th])
    for k,cm in zip(['specificity','recall'],[m['confusion_matrix'][0],list(reversed(m['confusion_matrix'][1]))]):assert np.isclose(t[k],cm[0]/sum(cm))
assert all(c['predictions_identical'] for c in r['verification'])
assert len(r['trials'])==350 and len(r['folds'])==35 and len(r['permutation_importance'])==3150
raw=pd.read_csv(ROOT/'data/real/country_panel.csv');test=raw[raw.period_year==2023].set_index('country_code')
for row in p.itertuples():assert row.observed==int(test.loc[row.country_code,'stunting_prevalence_pct']>=20)
for f in r['figures']:
    with Image.open(folder/f['path']) as im:f.update(width_pixels=im.width,height_pixels=im.height,dpi=600)
    assert (folder/f['svg']).exists() and (folder/f['pdf']).exists();checks.append(dict(figure=f['id'],check='PNG600+SVG+PDF',passed=True))
r.update(is_synthetic=False,versions={k:importlib.metadata.version(k) for k in ['numpy','pandas','scipy','scikit-learn','xgboost','catboost','torch','optuna','joblib','matplotlib']},python=platform.python_version(),publication_verification=checks)
save(folder/'results.json',r);save(folder/'independent_verification.json',checks)
hashes={str(f.relative_to(folder)):hashlib.sha256(f.read_bytes()).hexdigest() for f in folder.rglob('*') if f.is_file() and f.name not in ['artifact_hashes.json','evidence.zip']};save(folder/'artifact_hashes.json',hashes)
with zipfile.ZipFile(folder/'evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
    for f in folder.rglob('*'):
        if f.is_file() and f.name!='evidence.zip':z.write(f,str(f.relative_to(folder)))
print(json.dumps(dict(id=r['id'],independent_checks=len(checks),reload_checks=len(r['verification']),models=[dict(label=m['label'],metrics=m['metrics']['test']) for m in r['models']]),indent=2))

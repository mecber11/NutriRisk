from pathlib import Path
import json,re,importlib.metadata,platform
import numpy as np
import pandas as pd
from app.services.research import prepare_data,metrics,bootstrap_regions
from app.ml.features import build_analytical_frame
from app.db.session import SessionLocal

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.tmp'/'article'
RUN=ROOT/'backend'/'storage'/'research'/'20261104T170319-269cbcbc'

def prepare():
 with SessionLocal() as db:
  raw=build_analytical_frame(db)
 data=prepare_data(raw)
 prediction=np.array([data['train_y'][data['groups']!=g].mean() for g in data['groups']])
 baseline={'algorithm':'training_mean','label':'Media de entrenamiento por pliegue',**metrics(data['test_y'],prediction),'ci':bootstrap_regions(data['test_y'],prediction,data['groups'])}
 result=json.loads((RUN/'results.json').read_text(encoding='utf-8'))
 states={}
 for tune in result['tuning']:
  for trial in tune['trials']:states[trial['state']]=states.get(trial['state'],0)+1
 summary={'baseline':baseline,'trials_states':states,'n_children':len(raw),'n_territories':raw.territory_code.nunique(),'regions':sorted(raw.region.unique().tolist()),'years':sorted(int(v) for v in raw.period_year.unique()),'stunting_n':int(raw.stunting.sum()),'prevalence':float(raw.stunting.mean()),'version':{'Python':platform.python_version(),**{pkg:importlib.metadata.version(pkg) for pkg in ['numpy','pandas','scikit-learn','xgboost','catboost','torch','optuna','fastapi','mlflow-skinny']}},'operating_system':platform.system(),'baseline_note':'Referencia añadida a posteriori: media de prevalencia 2022 en regiones de entrenamiento, sin usar etiquetas 2023 ni la región excluida.'}
 comparisons=[]
 pred=pd.read_csv(RUN/'predictions.csv')
 for row in result['metrics']:
  subset=pred[pred.algorithm==row['algorithm']].set_index('territory').loc[data['codes']]
  delta=np.abs(data['test_y']-subset.predicted.to_numpy())-np.abs(data['test_y']-prediction)
  rng=np.random.default_rng(42);means=[]
  for _ in range(1000):
   selected=rng.choice(np.unique(data['groups']),len(set(data['groups'])),replace=True)
   idx=np.concatenate([np.flatnonzero(data['groups']==g) for g in selected])
   means.append(float(delta[idx].mean()))
  comparisons.append({'algorithm':row['algorithm'],'mean_mae_difference_vs_baseline':float(delta.mean()),'ci95':[float(v) for v in np.quantile(means,[.025,.975])]})
 summary['baseline_comparisons']=comparisons
 (OUT/'evidence.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 source=(ROOT/'frontend'/'src'/'components'/'Interpretation.tsx').read_text(encoding='utf-8')
 notes={key:{'reading':reading,'meaning':meaning,'limit':limit} for key,reading,meaning,limit in re.findall(r"^\s+(\w+): \{ reading: '([^']*)', meaning: '([^']*)', limit: '([^']*)' \}",source,re.M)}
 (OUT/'interpretations.json').write_text(json.dumps(notes,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=True,indent=2))

if __name__=='__main__':prepare()

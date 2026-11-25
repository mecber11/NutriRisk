"""Reproducible ecological classification of published JME national prevalence."""
from __future__ import annotations
import hashlib, json, time, shutil, zipfile, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import joblib, optuna
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel
from sklearn.metrics import (accuracy_score,precision_score,recall_score,f1_score,roc_auc_score,average_precision_score,balanced_accuracy_score,matthews_corrcoef,brier_score_loss,log_loss,confusion_matrix,roc_curve,precision_recall_curve)
from app.services.real_research import FEATURES,LABELS,ROOT,params,make_net,save
from app.core.config import settings

def metrics(y,p):
    y=np.asarray(y);p=np.clip(np.asarray(p),1e-7,1-1e-7);h=p>=.5;cm=confusion_matrix(y,h,labels=[0,1]);tn,fp,fn,tp=cm.ravel();both=len(np.unique(y))==2
    return dict(n=len(y),positives=int(y.sum()),negatives=int(len(y)-y.sum()),accuracy=accuracy_score(y,h),precision=precision_score(y,h,zero_division=0),recall=recall_score(y,h,zero_division=0),specificity=float(tn/(tn+fp)) if tn+fp else None,f1=f1_score(y,h,zero_division=0),roc_auc=roc_auc_score(y,p) if both else None,average_precision=average_precision_score(y,p) if both else None,balanced_accuracy=balanced_accuracy_score(y,h) if both else None,mcc=matthews_corrcoef(y,h),brier=brier_score_loss(y,p),log_loss=log_loss(y,p,labels=[0,1]))

def fit(a,p,X,y,coords,countries,V,vy,seed):
    imp=SimpleImputer(strategy='median',keep_empty_features=True);sc=StandardScaler();xx=sc.fit_transform(imp.fit_transform(X.reshape(len(X),-1)));vv=sc.transform(imp.transform(V.reshape(len(V),-1)));history=[];gp=None
    if a=='cnn_lstm':
        import torch
        torch.manual_seed(seed);torch.set_num_threads(2);model=make_net(p['channels'],p['hidden'],X.shape[2]);opt=torch.optim.Adam(model.parameters(),lr=p['learning_rate'],weight_decay=p['weight_decay']);loss=torch.nn.BCELoss();tx=torch.tensor(xx.reshape(X.shape),dtype=torch.float32);ty=torch.tensor(y,dtype=torch.float32);tv=torch.tensor(vv.reshape(V.shape),dtype=torch.float32);tyv=torch.tensor(vy,dtype=torch.float32)
        for e in range(p['epochs']):
            model.train();opt.zero_grad();l=loss(model(tx),ty);l.backward();opt.step();model.eval()
            with torch.no_grad():history.append(dict(epoch=e+1,train_loss=float(loss(model(tx),ty)),validation_loss=float(loss(model(tv),tyv))))
    elif a=='random_forest':model=RandomForestClassifier(**p,random_state=seed,n_jobs=2).fit(xx,y)
    elif a=='catboost':
        from catboost import CatBoostClassifier
        model=CatBoostClassifier(**p,random_seed=seed,thread_count=2,verbose=False,allow_writing_files=False,use_best_model=False,loss_function='Logloss').fit(xx,y,eval_set=(vv,vy));ev=model.get_evals_result();history=[dict(epoch=i+1,train_loss=v,validation_loss=ev['validation']['Logloss'][i]) for i,v in enumerate(ev['learn']['Logloss'])]
    else:
        from xgboost import XGBClassifier
        model=XGBClassifier(**p,random_state=seed,n_jobs=2,objective='binary:logistic',eval_metric='logloss');model.fit(xx,y,eval_set=[(xx,y),(vv,vy)],verbose=False);ev=model.evals_result();history=[dict(epoch=i+1,train_loss=v,validation_loss=ev['validation_1']['logloss'][i]) for i,v in enumerate(ev['validation_0']['logloss'])]
        if a=='spatial_xgboost':
            frame=pd.DataFrame(dict(country=countries,lat=coords[:,0],lon=coords[:,1],residual=y-model.predict_proba(xx)[:,1])).groupby('country').mean();gp=GaussianProcessRegressor(kernel=.01*RBF([30,30])+WhiteKernel(.001),optimizer=None,alpha=1e-5).fit(frame[['lat','lon']].to_numpy(),frame.residual)
    return dict(model=model,imputer=imp,scaler=sc,gp=gp,algorithm=a,params=p),history

def predict(b,X,coords):
    xx=b['scaler'].transform(b['imputer'].transform(X.reshape(len(X),-1)))
    if b['algorithm']=='cnn_lstm':
        import torch
        b['model'].eval()
        with torch.no_grad():p=b['model'](torch.tensor(xx.reshape(X.shape),dtype=torch.float32)).numpy()
    else:p=b['model'].predict_proba(xx)[:,1]
    if b['gp'] is not None:p=p+b['gp'].predict(coords)
    return np.clip(p,1e-7,1-1e-7)

def load(folder,a,f):
    b=joblib.load(folder/'models'/f'{a}_{f}.joblib')
    if a=='cnn_lstm':
        import torch
        model=make_net(b['params']['channels'],b['params']['hidden'],len(FEATURES));model.load_state_dict(torch.load(folder/'models'/f'{a}_{f}.pt',map_location='cpu',weights_only=True));b['model']=model
    return b

def bootstrap(y,p,g,reps=1000):
    rng=np.random.default_rng(42);groups=np.unique(g);rows=[];invalid=0
    for _ in range(reps):
        ix=np.concatenate([np.flatnonzero(g==r) for r in rng.choice(groups,len(groups),replace=True)])
        if len(np.unique(y[ix]))<2:invalid+=1;continue
        rows.append(metrics(y[ix],p[ix]))
    keys=['accuracy','precision','recall','specificity','f1','roc_auc','average_precision','balanced_accuracy','mcc','brier','log_loss'];return dict(method='Exploratory percentile region-cluster bootstrap; only two-class replicates retained',requested_replicates=reps,valid_replicates=len(rows),invalid_single_class=invalid,n_clusters=len(groups),intervals={k:dict(lower=float(np.quantile([r[k] for r in rows],.025)),upper=float(np.quantile([r[k] for r in rows],.975))) for k in keys})

def run(trials=10):
    started=time.time();runid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8];folder=settings.storage_dir/'classification'/runid;folder.mkdir(parents=True);(folder/'models').mkdir();(folder/'source').mkdir();shutil.copy2(__file__,folder/'source/public_classification.py');shutil.copy2(ROOT/'data/real/manifest.json',folder/'source/manifest.json');shutil.copy2(ROOT/'data/real/country_panel.csv',folder/'source/country_panel.csv')
    raw=pd.read_csv(ROOT/'data/real/country_panel.csv');raw=raw[raw.period_year<=2023].sort_values(['country_code','period_year']);rows=[];arrays=[]
    for _,g in raw.groupby('country_code'):
        for j in range(2,len(g)):
            w=g.iloc[j-2:j+1]
            if list(w.period_year)==list(range(int(w.iloc[-1].period_year)-2,int(w.iloc[-1].period_year)+1)):rows.append(w.iloc[-1].to_dict());arrays.append(w[FEATURES].to_numpy(float))
    df=pd.DataFrame(rows).reset_index(drop=True);X=np.asarray(arrays);y=(df.stunting_prevalence_pct.to_numpy()>=20).astype(int);coords=df[['latitude','longitude']].to_numpy();regions=sorted(df.region.unique());folds=[];preds=[];trials_all=[];epochs=[];perms=[];checks=[];optuna.logging.set_verbosity(optuna.logging.WARNING)
    save(folder.parent/'latest_running.json',dict(id=runid));save(folder/'state.json',dict(id=runid,status='RUNNING'))
    for f,r in enumerate(regions):
        others=sorted(df.loc[df.region!=r,'country_code'].unique());inner=set(np.random.default_rng(42+f).choice(others,max(1,len(others)//5),replace=False));tr=(df.region!=r)&(df.period_year<=2021)&~df.country_code.isin(inner);va=(df.period_year==2022)&df.country_code.isin(inner);ot=(df.region!=r)&(df.period_year<=2021);ov=(df.region!=r)&(df.period_year==2022);te=(df.region==r)&(df.period_year==2023)
        for a in LABELS:
            def obj(t):
                p=params(t,a);b,h=fit(a,p,X[tr],y[tr],coords[tr],df.country_code[tr].to_numpy(),X[va],y[va],42);score=log_loss(y[va],predict(b,X[va],coords[va]),labels=[0,1]);trials_all.append(dict(fold=f,region=r,algorithm=a,trial=t.number,validation_log_loss=score,parameters=p));return score
            study=optuna.create_study(direction='minimize',sampler=optuna.samplers.TPESampler(seed=42+f));study.optimize(obj,n_trials=trials);b,h=fit(a,study.best_params,X[ot],y[ot],coords[ot],df.country_code[ot].to_numpy(),X[ov],y[ov],42);p=predict(b,X[te],coords[te]);epochs.extend([dict(fold=f,region=r,algorithm=a,stage='outer_fit',**v) for v in h]);folds.append(dict(fold=f,region=r,algorithm=a,hyperparameters=study.best_params,inner_validation_countries=sorted(inner),metrics=dict(train=metrics(y[ot],predict(b,X[ot],coords[ot])),validation=metrics(y[ov],predict(b,X[ov],coords[ov])),test=metrics(y[te],p)),confusion_matrix=confusion_matrix(y[te],p>=.5,labels=[0,1]).tolist()))
            for ix,pp in zip(df.index[te],p):preds.append(dict(algorithm=a,fold=f,region=r,country_code=df.loc[ix,'country_code'],country_name=df.loc[ix,'country_name'],year=2023,prevalence_pct=df.loc[ix,'stunting_prevalence_pct'],observed=int(y[ix]),probability=float(pp),predicted=int(pp>=.5)))
            base=brier_score_loss(y[te],p);rng=np.random.default_rng(4200+f)
            for k,feature in enumerate(FEATURES):
                for repeat in range(10):
                    xp=X[te].copy();order=rng.permutation(len(xp));xp[:,:,k]=xp[order,:,k];q=predict(b,xp,coords[te]);perms.append(dict(algorithm=a,fold=f,region=r,feature=feature,repeat=repeat,delta_brier=float(brier_score_loss(y[te],q)-base),n=int(te.sum())))
            if a=='cnn_lstm':
                import torch
                torch.save(b.pop('model').state_dict(),folder/'models'/f'{a}_{f}.pt')
            joblib.dump(b,folder/'models'/f'{a}_{f}.joblib');loaded=load(folder,a,f);again=predict(loaded,X[te],coords[te]);checks.append(dict(algorithm=a,fold=f,predictions_identical=bool(np.allclose(p,again,rtol=0,atol=1e-7)),max_difference=float(np.max(np.abs(p-again)))))
            save(folder/'state.json',dict(id=runid,status='RUNNING',completed_final_fits=len(folds),total_final_fits=35,region=r,algorithm=a,elapsed_seconds=time.time()-started));print(f'{len(folds)}/35 {r} {a} F1={metrics(y[te],p)["f1"]:.3f}',flush=True)
    pred=pd.DataFrame(preds);models=[]
    for a,g in pred.groupby('algorithm',sort=False):
        yy=g.observed.to_numpy();pp=g.probability.to_numpy();fr,tt,th=roc_curve(yy,pp,drop_intermediate=False);pr,re,pt=precision_recall_curve(yy,pp);fs=[v for v in folds if v['algorithm']==a];models.append(dict(algorithm=a,label=LABELS[a],metrics=dict(test=metrics(yy,pp),train={k:float(np.mean([v['metrics']['train'][k] for v in fs])) for k in ['accuracy','precision','recall','f1','roc_auc','brier','log_loss']},validation={k:float(np.mean([v['metrics']['validation'][k] for v in fs])) for k in ['accuracy','precision','recall','f1','roc_auc','brier','log_loss']}),test_ci=bootstrap(yy,pp,g.region.to_numpy()),roc=dict(fpr=fr,tpr=tt,thresholds=[float(v) if np.isfinite(v) else None for v in th]),pr=dict(precision=pr,recall=re,thresholds=pt),confusion_matrix=confusion_matrix(yy,pp>=.5,labels=[0,1]).tolist(),hyperparameters_by_fold=[dict(region=v['region'],parameters=v['hyperparameters']) for v in fs]))
    result=dict(id=runid,status='COMPLETED',synthetic=False,is_synthetic=False,study_type='Clasificación ecológica nacional JME >=20%; no diagnóstico individual',created_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.time()-started,seed=42,protocol=dict(target='stunting_prevalence_pct >= 20',target_unit='país-año',threshold_source='https://www.who.int/data/nutrition/nlis/info/malnutrition-in-children/',threshold_definition='OMS: alta 20 a <30%, muy alta >=30%',decision_threshold=.5,selection_metric='inner validation binary log loss',trials_per_model_per_outer_fold=trials,total_tuning_fits=len(trials_all),total_final_fits=len(folds),outer='leave-one-region-out; todas las historias de la región excluidas',inner='20% países restantes, historias excluidas; validación 2022',train_years=[2002,2021],validation_year=2022,test_year=2023,window_years=3,preprocessing='mediana y StandardScaler ajustados solo al entrenamiento de cada fold',cnn_loss='Binary cross entropy, full-batch Adam; epochs fijadas por Optuna; sin early stopping',catboost_use_best_model=False,final_validation='monitoring only; never selects final epochs',permutation='Post hoc held-out test diagnostic; shuffle country jointly across its 3 lags, 10 repeats/feature/fold; not used in tuning'),features=FEATURES,data_summary=dict(countries=int(raw.country_code.nunique()),sample_windows=len(df),test_countries=int(pred.country_code.nunique()),test_positives=int(pred[pred.algorithm=='random_forest'].observed.sum()),regions=regions,dataset_sha256=hashlib.sha256((ROOT/'data/real/country_panel.csv').read_bytes()).hexdigest(),manifest_sha256=hashlib.sha256((ROOT/'data/real/manifest.json').read_bytes()).hexdigest()),models=models,folds=folds,predictions=preds,trials=trials_all,epochs=epochs,permutation_importance=perms,verification=checks,limitations=['Resultados nacionales ecológicos; no diagnósticos infantiles individuales.','Etiqueta derivada de prevalencia JME modelada de encuestas; no microdatos clínicos.','Evaluación retrospectiva con covariables contemporáneas; no pronóstico prospectivo.','IC exploratorios por siete regiones desiguales; Norteamérica tiene un país.','Umbral de probabilidad 0.5 prefijado; no optimizado con prueba.','Recall/F1 de regiones con una sola clase son descriptivos; ROC-AUC regional no definido si falta una clase.','Importancia por permutación mide dependencia predictiva, no causalidad; variables correlacionadas comparten información.','Comparaciones con modelos de regresión corresponden a tareas distintas.','Una semilla; no representa incertidumbre de entrenamiento ni incertidumbre epidemiológica JME.'],figures=[])
    pd.DataFrame(preds).to_csv(folder/'predictions.csv',index=False);pd.DataFrame(epochs).to_csv(folder/'epochs.csv',index=False);pd.DataFrame(perms).to_csv(folder/'permutation_importance.csv',index=False);save(folder/'trials.json',trials_all);save(folder/'verification.json',checks);figures(folder,result);save(folder/'results.json',result)
    hashes={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()};save(folder/'artifact_hashes.json',hashes)
    with zipfile.ZipFile(folder/'evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in folder.rglob('*'):
            if p.is_file() and p.name!='evidence.zip':z.write(p,str(p.relative_to(folder)))
    save(folder/'state.json',dict(id=runid,status='COMPLETED',completed_final_fits=35));save(folder.parent/'latest.json',dict(id=runid));return result

def figures(folder,result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False});dest=folder/'figures';dest.mkdir(exist_ok=True);models=result['models'];pred=pd.DataFrame(result['predictions']);colors=['#2563eb','#059669','#d97706','#9333ea','#e11d48']
    def export(name,title,interpretation,explanation,limitations):
        plt.tight_layout()
        for ext in ['png','svg','pdf']:plt.savefig(dest/f'{name}.{ext}',dpi=600,bbox_inches='tight')
        plt.close();result['figures'].append(dict(id=name,title=title,path=f'figures/{name}.png',svg=f'figures/{name}.svg',pdf=f'figures/{name}.pdf',dpi=600,interpretation=interpretation,explanation=explanation,limitations=limitations))
    best=max(models,key=lambda m:m['metrics']['test']['roc_auc']);bm=best['metrics']['test']
    fig,ax=plt.subplots(figsize=(8,5))
    for m,c in zip(models,colors):ax.plot(m['roc']['fpr'],m['roc']['tpr'],color=c,label=f'{m["label"]}: AUC {m["metrics"]["test"]["roc_auc"]:.3f}')
    ax.plot([0,1],[0,1],'--',color='#94a3b8');ax.set(xlabel='Tasa de falsos positivos (1 − especificidad)',ylabel='Recall / sensibilidad',title='ROC · países de regiones excluidas, 2023');ax.legend(loc='lower right')
    export('01_roc','Curvas ROC',f'{best["label"]} presenta la mayor ROC-AUC observada ({bm["roc_auc"]:.3f}) en 161 países.', 'Cada punto varía el umbral de probabilidad; ROC-AUC mide discriminación entre países con prevalencia nacional alta y el resto. La diagonal representa orden aleatorio.','No establece superioridad significativa ni validez clínica individual; los países presentan dependencia regional.')
    fig,ax=plt.subplots(figsize=(8,5));base=result['data_summary']['test_positives']/result['data_summary']['test_countries']
    for m,c in zip(models,colors):ax.plot(m['pr']['recall'],m['pr']['precision'],color=c,label=f'{m["label"]}: AP {m["metrics"]["test"]["average_precision"]:.3f}')
    ax.axhline(base,ls='--',color='#94a3b8',label=f'Fracción positiva: {base:.3f}');ax.set(xlabel='Recall',ylabel='Precisión',title='Precisión–recall · países de prueba 2023');ax.legend(fontsize=8)
    export('02_precision_recall','Curvas precisión–recall',f'La fracción positiva es {base:.1%}; las leyendas muestran el AP medido de cada modelo.','Recall indica cuántos países de prevalencia alta se detectan; precisión indica qué fracción de las alertas corresponde a esa clase. AP resume precisión ponderada por incrementos de recall.','AP depende del balance de clases; no equivale al área trapezoidal PR ni a prevalencia infantil individual.')
    fig,axes=plt.subplots(2,3,figsize=(10,6))
    for ax,m in zip(axes.flat,models):
        cm=np.array(m['confusion_matrix']);ax.imshow(cm,cmap='Blues');ax.set(xticks=[0,1],yticks=[0,1],xticklabels=['<20%','≥20%'],yticklabels=['<20%','≥20%'],xlabel='Predicción',ylabel='Publicado',title=m['label'])
        for (i,j),v in np.ndenumerate(cm):ax.text(j,i,str(v),ha='center',va='center',color='white' if v>cm.max()/2 else '#0f172a',fontsize=13)
    axes.flat[-1].axis('off');export('03_confusion','Matrices de confusión',f'Cada panel contabiliza los mismos 161 países con umbral fijo 0.5. {best["label"]}: recall {bm["recall"]:.1%}, precisión {bm["precision"]:.1%}.','Filas: clase publicada; columnas: predicción. La celda inferior izquierda representa falsos negativos y la superior derecha falsos positivos.','Son conteos de países, no de niños; el umbral de 20% define la clase nacional y 0.5 define la decisión del modelo.')
    fig,ax=plt.subplots(figsize=(9,5));keys=['precision','recall','f1','roc_auc','specificity'];x=np.arange(len(keys));width=.15
    for i,(m,c) in enumerate(zip(models,colors)):ax.bar(x+(i-2)*width,[m['metrics']['test'][k] for k in keys],width,color=c,label=m['label'])
    ax.set_xticks(x,['Precisión','Recall','F1','ROC-AUC','Especificidad']);ax.set(ylim=(0,1.08),ylabel='Valor en prueba 2023',title='Comparación de métricas de clasificación');ax.legend(fontsize=8,ncol=2)
    export('04_metrics','Comparación de métricas',f'El modelo con mayor ROC-AUC es {best["label"]}; su F1 observado es {bm["f1"]:.3f}.','Las barras permiten comparar discriminación y decisiones a umbral fijo. F1 es media armónica de precisión y recall; especificidad evalúa países de la clase negativa.','Las diferencias descriptivas no implican diferencias estadísticamente significativas; consultar intervalos bootstrap exploratorios.')
    pi=pd.DataFrame(result['permutation_importance']);agg=pi.groupby(['algorithm','feature']).apply(lambda g:np.average(g.delta_brier,weights=g.n),include_groups=False).unstack().reindex([m['algorithm'] for m in models]);top=agg.mean().idxmax();fig,ax=plt.subplots(figsize=(10,5));im=ax.imshow(agg.to_numpy(),aspect='auto',cmap='RdBu_r');ax.set_yticks(range(5),[m['label'] for m in models]);ax.set_xticks(range(9),[v.replace('_',' ') for v in agg.columns],rotation=35,ha='right',fontsize=7);fig.colorbar(im,ax=ax,label='Δ Brier tras permutación (más alto = mayor dependencia)')
    export('05_permutation','Explicabilidad por permutación',f'La mayor pérdida de Brier promedio entre modelos se observa al permutar {top.replace("_"," ")}.','Se permuta cada variable entre países de prueba conservando juntos sus tres años, diez veces por región. Se resta Brier original al Brier permutado y se pondera por número de países.','Diagnóstico post hoc; no identifica causas. Variables correlacionadas y regiones de un país pueden reducir la importancia medida; no se usó para seleccionar modelos.')
    ep=pd.DataFrame(result['epochs']);ep=ep[ep.algorithm=='cnn_lstm'];fig,axes=plt.subplots(2,4,figsize=(11,6),sharey=True)
    for ax,(f,g) in zip(axes.flat,ep.groupby('fold')):ax.plot(g.epoch,g.train_loss,label='Entrenamiento',color='#2563eb');ax.plot(g.epoch,g.validation_loss,label='Validación 2022',color='#e11d48');ax.set(title=g.region.iloc[0],xlabel='Época',ylabel='Entropía cruzada binaria');ax.tick_params(labelsize=7);ax.title.set_fontsize(8)
    axes.flat[-1].axis('off');axes.flat[0].legend(fontsize=6);export('06_cnn_loss','Aprendizaje CNN-LSTM',f'Se muestran {ep.fold.nunique()} ajustes finales independientes; las épocas provienen de la selección interna de hiperparámetros.','La curva azul mide ajuste en entrenamiento y la roja pérdida en 2022 de países ajenos a la región de prueba. Una separación creciente señala posible sobreajuste o cambio de distribución.','La validación final solo se monitoriza, sin early stopping; el test 2023 permanece fuera de estas curvas.')
    fig,ax=plt.subplots(figsize=(8,5))
    for m,c in zip(models,colors):
        g=pred[pred.algorithm==m['algorithm']];obs,prob=calibration_curve(g.observed,g.probability,n_bins=6,strategy='quantile');ax.plot(prob,obs,'o-',color=c,label=f'{m["label"]} · Brier {m["metrics"]["test"]["brier"]:.3f}')
    ax.plot([0,1],[0,1],'--',color='#94a3b8');ax.set(xlabel='Probabilidad media predicha',ylabel='Fracción de países positivos',title='Calibración de probabilidades · prueba 2023',xlim=(0,1),ylim=(0,1));ax.legend(fontsize=8)
    export('07_calibration','Calibración',f'Brier de {best["label"]}: {bm["brier"]:.3f}; un valor menor representa menor error probabilístico.','Se agrupan probabilidades en hasta seis grupos de cuantiles. La diagonal indica concordancia entre probabilidad media y frecuencia observada de países con prevalencia ≥20%.','Pocos países y dependencia regional producen curvas inestables; no se aplicó recalibración posterior con el test.')

if __name__=='__main__':run()



"""Real public-data ecological regression; no synthetic or individual outcomes."""
from __future__ import annotations
import hashlib, itertools, json, time, zipfile, platform, importlib.metadata, uuid
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib, optuna
from app.core.config import settings

FEATURES=['gdp_per_capita_constant_usd','basic_drinking_water_pct','basic_sanitation_pct','electricity_access_pct','urban_population_pct','population_density','fertility_births_per_woman','female_secondary_enrollment_pct','pm25_exposure']
LABELS={'random_forest':'Random Forest','xgboost':'XGBoost','catboost':'CatBoost','spatial_xgboost':'XGBoost + GP espacial','cnn_lstm':'CNN-LSTM'}
ROOT=Path(__file__).resolve().parents[3]
def clean(v):
    if isinstance(v,dict): return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [clean(x) for x in v]
    if isinstance(v,np.ndarray): return clean(v.tolist())
    if isinstance(v,np.generic): return clean(v.item())
    if isinstance(v,float) and not np.isfinite(v): return None
    return v

def save(path,v):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(path)
def metric(y,p): return {'mae':float(mean_absolute_error(y,p)),'rmse':float(np.sqrt(mean_squared_error(y,p))),'r2':float(r2_score(y,p)) if len(y)>1 else None,'n':len(y)}
def params(t,a):
    if a=='cnn_lstm':return dict(hidden=t.suggest_categorical('hidden',[8,16,32]),channels=t.suggest_categorical('channels',[4,8]),learning_rate=t.suggest_float('learning_rate',.001,.02,log=True),weight_decay=t.suggest_float('weight_decay',1e-5,.01,log=True),epochs=t.suggest_categorical('epochs',[30,50]))
    if a=='random_forest':return dict(n_estimators=t.suggest_categorical('n_estimators',[60,100]),max_depth=t.suggest_int('max_depth',3,10),min_samples_leaf=t.suggest_int('min_samples_leaf',2,12),max_features=t.suggest_float('max_features',.5,1))
    if a=='catboost':return dict(iterations=t.suggest_categorical('iterations',[60,120]),depth=t.suggest_int('depth',3,6),learning_rate=t.suggest_float('learning_rate',.02,.2,log=True),l2_leaf_reg=t.suggest_float('l2_leaf_reg',1,10))
    return dict(n_estimators=t.suggest_categorical('n_estimators',[60,120]),max_depth=t.suggest_int('max_depth',2,5),learning_rate=t.suggest_float('learning_rate',.02,.2,log=True),reg_lambda=t.suggest_float('reg_lambda',.5,10,log=True),subsample=t.suggest_float('subsample',.7,1))

def make_net(channels,hidden,nfeatures):
    import torch
    class Net(torch.nn.Module):
        def __init__(self):
            super().__init__();self.conv=torch.nn.Conv1d(nfeatures,channels,2,padding=1);self.lstm=torch.nn.LSTM(channels,hidden,batch_first=True);self.head=torch.nn.Linear(hidden,1)
        def forward(self,x):
            x=torch.relu(self.conv(x.transpose(1,2))).transpose(1,2);x,_=self.lstm(x);return torch.sigmoid(self.head(x[:,-1])).squeeze(-1)
    return Net()

def fit(a,p,X,y,coords,countries,V,vy,seed):
    imp=SimpleImputer(strategy='median',keep_empty_features=True);sc=StandardScaler()
    shape=X.shape;xx=sc.fit_transform(imp.fit_transform(X.reshape(len(X),-1)));vv=sc.transform(imp.transform(V.reshape(len(V),-1)))
    history=[];gp=None
    if a=='cnn_lstm':
        import torch
        torch.manual_seed(seed);torch.set_num_threads(2)
        net=make_net(p['channels'],p['hidden'],shape[2]);optimizer=torch.optim.Adam(net.parameters(),lr=p['learning_rate'],weight_decay=p['weight_decay']);loss=torch.nn.MSELoss()
        tx=torch.tensor(xx.reshape(shape),dtype=torch.float32);ty=torch.tensor(y,dtype=torch.float32);tv=torch.tensor(vv.reshape(V.shape),dtype=torch.float32);tyv=torch.tensor(vy,dtype=torch.float32)
        for epoch in range(p['epochs']):
            net.train();optimizer.zero_grad();l=loss(net(tx),ty);l.backward();optimizer.step();net.eval()
            with torch.no_grad(): history.append({'epoch':epoch+1,'train_mse':float(loss(net(tx),ty)),'validation_mse':float(loss(net(tv),tyv))})
        model=net
    elif a=='random_forest':model=RandomForestRegressor(**p,random_state=seed,n_jobs=2).fit(xx,y)
    elif a=='catboost':
        from catboost import CatBoostRegressor
        model=CatBoostRegressor(**p,random_seed=seed,thread_count=2,verbose=False,allow_writing_files=False,use_best_model=False).fit(xx,y,eval_set=(vv,vy));ev=model.get_evals_result();history=[dict(epoch=i+1,train_mse=float(v*v),validation_mse=float(ev['validation']['RMSE'][i]**2)) for i,v in enumerate(ev['learn']['RMSE'])]
    else:
        from xgboost import XGBRegressor
        model=XGBRegressor(**p,random_state=seed,n_jobs=2,objective='reg:squarederror');model.fit(xx,y,eval_set=[(xx,y),(vv,vy)],verbose=False);ev=model.evals_result();history=[dict(epoch=i+1,train_mse=float(v*v),validation_mse=float(ev['validation_1']['rmse'][i]**2)) for i,v in enumerate(ev['validation_0']['rmse'])]
        if a=='spatial_xgboost':
            frame=pd.DataFrame({'country':countries,'lat':coords[:,0],'lon':coords[:,1],'residual':y-model.predict(xx)}).groupby('country').mean()
            gp=GaussianProcessRegressor(kernel=.01*RBF([30,30],length_scale_bounds=(1,180))+WhiteKernel(.001,noise_level_bounds=(1e-6,.1)),normalize_y=False,optimizer=None,alpha=1e-5).fit(frame[['lat','lon']].to_numpy(),frame.residual)
    return dict(model=model,imputer=imp,scaler=sc,gp=gp,shape=list(shape[1:]),algorithm=a,params=p),history

def predict(bundle,X,coords):
    xx=bundle['scaler'].transform(bundle['imputer'].transform(X.reshape(len(X),-1)))
    if bundle['algorithm']=='cnn_lstm':
        import torch
        bundle['model'].eval()
        with torch.no_grad():p=bundle['model'](torch.tensor(xx.reshape(X.shape),dtype=torch.float32)).numpy()
    else:p=bundle['model'].predict(xx)
    if bundle['gp'] is not None:p=p+bundle['gp'].predict(coords)
    return np.clip(p,0,1)

def ci(y,p,g,seed=42,reps=1000):
    rng=np.random.default_rng(seed);groups=np.unique(g);values=[]
    for _ in range(reps):
        ix=np.concatenate([np.flatnonzero(g==x) for x in rng.choice(groups,len(groups),replace=True)]);values.append([np.mean(np.abs(y[ix]-p[ix])),np.sqrt(np.mean((y[ix]-p[ix])**2)),r2_score(y[ix],p[ix])])
    q=np.quantile(values,[.025,.975],axis=0)
    return {'method':'percentile cluster bootstrap by region','replicates':reps,'n_clusters':len(groups),'mae':{'lower':q[0,0],'upper':q[1,0]},'rmse':{'lower':q[0,1],'upper':q[1,1]},'r2':{'lower':q[0,2],'upper':q[1,2]}}

def run_real(run_id=None,trials=10,seed=42):
    run_id=run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8];folder=settings.storage_dir/'research'/run_id;folder.mkdir(parents=True,exist_ok=True);(folder/'models').mkdir(exist_ok=True)
    state={'id':run_id,'status':'RUNNING','synthetic':False,'completed_fits':0,'trials_per_model_per_outer_fold':trials,'created_at':datetime.now(timezone.utc).isoformat()};save(folder/'state.json',state);save(folder/'status.json',state)
    raw=pd.read_csv(ROOT/'data/real/country_panel.csv');raw=raw[raw.period_year<=2023].sort_values(['country_code','period_year']);samples=[];arrays=[]
    for country,group in raw.groupby('country_code'):
        for j in range(2,len(group)):
            window=group.iloc[j-2:j+1]
            if list(window.period_year)!=list(range(int(window.iloc[-1].period_year)-2,int(window.iloc[-1].period_year)+1)):continue
            samples.append(window.iloc[-1].to_dict());arrays.append(window[FEATURES].to_numpy(dtype=float))
    df=pd.DataFrame(samples).reset_index(drop=True);X=np.asarray(arrays);y=df.stunting_prevalence_pct.to_numpy()/100;coords=df[['latitude','longitude']].to_numpy();regions=sorted(df.region.unique());all_trials=[];epochs=[];predictions=[];folds=[];train_metrics=[]
    optuna.logging.set_verbosity(optuna.logging.WARNING);started=time.time()
    for fold,region in enumerate(regions):
        others=sorted(df.loc[df.region!=region,'country_code'].unique());rng=np.random.default_rng(seed+fold);inner=set(rng.choice(others,max(1,len(others)//5),replace=False))
        tr=(df.region!=region)&(df.period_year<=2021)&(~df.country_code.isin(inner));va=(df.period_year==2022)&df.country_code.isin(inner);outer_tr=(df.region!=region)&(df.period_year<=2021);outer_va=(df.region!=region)&(df.period_year==2022);te=(df.region==region)&(df.period_year==2023)
        for a in LABELS:
            def objective(t):
                p=params(t,a);bundle,hist=fit(a,p,X[tr],y[tr],coords[tr],df.country_code[tr].to_numpy(),X[va],y[va],seed);score=metric(y[va],predict(bundle,X[va],coords[va]))['mae'];all_trials.append({'fold':fold,'held_out_region':region,'algorithm':a,'trial':t.number,'validation_mae':score,'parameters':json.dumps(p),'train_n':int(tr.sum()),'validation_n':int(va.sum())});epochs.extend([dict(fold=fold,algorithm=a,trial=t.number,stage='tuning',**h) for h in hist]);return score
            study=optuna.create_study(direction='minimize',sampler=optuna.samplers.TPESampler(seed=seed+fold));study.optimize(objective,n_trials=trials)
            bundle,hist=fit(a,study.best_params,X[outer_tr],y[outer_tr],coords[outer_tr],df.country_code[outer_tr].to_numpy(),X[outer_va],y[outer_va],seed);epochs.extend([dict(fold=fold,algorithm=a,trial=-1,stage='outer_fit',**h) for h in hist]);p=predict(bundle,X[te],coords[te]);tm=metric(y[outer_tr],predict(bundle,X[outer_tr],coords[outer_tr]));vm=metric(y[outer_va],predict(bundle,X[outer_va],coords[outer_va]));test=metric(y[te],p)
            folds.append(dict(fold=fold,region=region,algorithm=a,hyperparameters=study.best_params,metrics={'train':tm,'validation':vm,'test':test},inner_validation_countries=sorted(inner)))
            for idx,pp in zip(df.index[te],p):predictions.append(dict(algorithm=a,region=region,country_code=df.loc[idx,'country_code'],country_name=df.loc[idx,'country_name'],year=2023,observed=y[idx],predicted=float(pp),residual=float(y[idx]-pp),latitude=coords[idx,0],longitude=coords[idx,1]))
            if a=='cnn_lstm':
                import torch
                model=bundle.pop('model');torch.save({'state_dict':model.state_dict(),'params':study.best_params,'features':FEATURES,'window':3},folder/'models'/f'{a}_{fold}.pt');joblib.dump(bundle,folder/'models'/f'{a}_{fold}_preprocess.joblib')
            else:joblib.dump(bundle,folder/'models'/f'{a}_{fold}.joblib')
            state.update(completed_fits=state['completed_fits']+trials+1,current_region=region,current_model=a,elapsed_seconds=time.time()-started);save(folder/'state.json',state);save(folder/'status.json',state);pd.DataFrame(all_trials).to_csv(folder/'trials.csv',index=False);print(f'{region}: {a} MAE={test["mae"]:.4f}',flush=True)
        # Mean trained on identical allowed rows; persistence explicitly consumes historical labels.
        for a,base in [('baseline_mean',np.repeat(y[outer_tr].mean(),int(te.sum()))),('baseline_persistence',np.array([raw[(raw.country_code==c)&(raw.period_year==2022)].stunting_prevalence_pct.iloc[0]/100 for c in df.loc[te,'country_code']]))]:
            for idx,pp in zip(df.index[te],base):predictions.append(dict(algorithm=a,region=region,country_code=df.loc[idx,'country_code'],country_name=df.loc[idx,'country_name'],year=2023,observed=y[idx],predicted=float(pp),residual=float(y[idx]-pp),latitude=coords[idx,0],longitude=coords[idx,1]))
    pred=pd.DataFrame(predictions);pred.to_csv(folder/'predictions.csv',index=False);pd.DataFrame(epochs).to_csv(folder/'epochs.csv',index=False)
    return finalize(folder,state,raw,df,pred,folds,all_trials,epochs,started,seed)

def finalize(folder,state,raw,df,pred,folds,trials,epochs,started,seed):
    regional=[];models=[];normality=[];moran=[]
    for (a,r),g in pred.groupby(['algorithm','region']):regional.append(dict(algorithm=a,region=r,**metric(g.observed,g.predicted)))
    reg=pd.DataFrame(regional);reg.to_csv(folder/'regional_metrics.csv',index=False)
    for a,g in pred.groupby('algorithm'):
        y=g.observed.to_numpy();p=g.predicted.to_numpy();fs=[f for f in folds if f['algorithm']==a]
        models.append({'algorithm':a,'label':LABELS.get(a,a),'metrics':{'test':metric(y,p),'train':{k:float(np.mean([f['metrics']['train'][k] for f in fs])) for k in ['mae','rmse','r2']} if fs else None,'validation':{k:float(np.mean([f['metrics']['validation'][k] for f in fs])) for k in ['mae','rmse','r2']} if fs else None},'test_ci':ci(y,p,g.region.to_numpy(),seed),'hyperparameters_by_fold':[{'region':f['region'],'parameters':f['hyperparameters']} for f in fs],'historical_labels_as_input':a=='baseline_persistence'})
        residual=y-p;sw=stats.shapiro(residual);normality.append(dict(algorithm=a,test='Shapiro-Wilk residuals',statistic=float(sw.statistic),pvalue=float(sw.pvalue),skewness=float(stats.skew(residual)),excess_kurtosis=float(stats.kurtosis(residual)),warning='Descriptive; spatial dependence violates independent-sample interpretation.'))
        if a in LABELS:
            xy=g[['latitude','longitude']].to_numpy();lat=np.deg2rad(xy[:,0]);lon=np.deg2rad(xy[:,1]);dlat=lat[:,None]-lat;dlon=lon[:,None]-lon;distance=2*np.arcsin(np.sqrt(np.clip(np.sin(dlat/2)**2+np.cos(lat[:,None])*np.cos(lat)*np.sin(dlon/2)**2,0,1)));np.fill_diagonal(distance,np.inf);w=np.zeros_like(distance);nn=np.argsort(distance,axis=1)[:,:5];w[np.arange(len(w))[:,None],nn]=1;w=np.maximum(w,w.T);z=residual-residual.mean()
            def mi(v):return float(len(v)/w.sum()*(v@w@v)/(v@v))
            observed=mi(z);rng=np.random.default_rng(seed);sim=np.array([mi(rng.permutation(z)) for _ in range(999)]);expected=-1/(len(z)-1);pv=(1+np.sum(np.abs(sim-expected)>=abs(observed-expected)))/1000;moran.append(dict(algorithm=a,statistic=observed,pvalue=float(pv),permutations=999,expected=expected,weights='symmetric binary 5 nearest capitals; great-circle distances',coordinate_proxy=True))
    blocks=reg[reg.algorithm.isin(LABELS)].pivot(index='region',columns='algorithm',values='mae')[list(LABELS)];values=blocks.to_numpy();fr=stats.friedmanchisquare(*values.T);pairs=[];rng=np.random.default_rng(seed)
    for a,b in itertools.combinations(blocks.columns,2):
        delta=(blocks[a]-blocks[b]).to_numpy();w=stats.wilcoxon(delta,method='exact') if np.any(delta!=0) else None;boot=np.array([rng.choice(delta,len(delta),replace=True).mean() for _ in range(2000)]);nonzero=delta[delta!=0];ranks=stats.rankdata(np.abs(nonzero));effect=float(np.sum(ranks*np.sign(nonzero))/ranks.sum()) if len(nonzero) else 0
        pairs.append(dict(a=a,b=b,statistic=float(w.statistic) if w else 0,pvalue=float(w.pvalue) if w else 1,mean_mae_difference=float(delta.mean()),median_mae_difference=float(np.median(delta)),rank_biserial=effect,bootstrap_mean_difference_ci={'lower':float(np.quantile(boot,.025)),'upper':float(np.quantile(boot,.975)),'replicates':2000,'unit':'region'}))
    order=np.argsort([p['pvalue'] for p in pairs]);previous=0
    for rank,index in enumerate(order):previous=max(previous,min(1,pairs[index]['pvalue']*(len(pairs)-rank)));pairs[index]['pvalue_holm']=previous
    statistics={'friedman':{'statistic':float(fr.statistic),'pvalue':float(fr.pvalue),'n_blocks':len(blocks),'n_models':5,'blocks':list(blocks.index)},'kendall_w':float(fr.statistic/(len(blocks)*4)),'wilcoxon_holm':pairs,'normality':normality,'moran':moran,'inference_warning':'Exploratory inference: seven regions, unequal sample size, overlapping training folds and spatially dependent smoothed JME estimates. Exact Wilcoxon p-values have coarse resolution; no clinical or causal conclusion.'}
    pd.DataFrame([dict(algorithm=m['algorithm'],**m['metrics']['test']) for m in models]).to_csv(folder/'metrics.csv',index=False);pd.DataFrame(pairs).to_csv(folder/'pairwise_statistics.csv',index=False)
    # Coverage and missingness are reported without inventing clinical variables.
    missing={c:float(raw[c].isna().mean()) for c in FEATURES};manifest=json.loads((ROOT/'data/real/manifest.json').read_text(encoding='utf-8-sig'))
    limitations=['Ecological country-year regression, not individual child risk classification.','Outcome is modelled UNICEF/WHO/World Bank JME prevalence; possible shared covariates and retrospective revisions limit independence.','Contemporaneous covariates are used through 2023: retrospective nowcasting, not prospective forecasting.','No individual clinical, sex, wealth or rural fairness metrics are identifiable.','PM2.5 is absent in 2024; final test year is 2023.','Female secondary enrolment missingness is handled by fold-trained medians, not observed replacement measurements; sensitivity analysis has not been run.','Country capitals are geographic proxies. North America contains one country; regional inference is weak.','One fixed seed per study; hyperparameter and training stochasticity are not covered by bootstrap intervals.','Baseline persistence uses held-out country 2022 outcome labels and therefore has a stronger information set than transferable models.','All intervals are exploratory region-cluster bootstrap; no intervals for true epidemiological prevalence or JME estimation uncertainty.','Train and validation summary metrics average overlapping outer-fold fits; only test metrics are disjoint out-of-fold predictions.']
    space={'random_forest':{'n_estimators':[60,100],'max_depth':[3,10],'min_samples_leaf':[2,12],'max_features':[.5,1]},'xgboost':{'n_estimators':[60,120],'max_depth':[2,5],'learning_rate':{'range':[.02,.2],'log':True},'reg_lambda':{'range':[.5,10],'log':True},'subsample':[.7,1]},'catboost':{'iterations':[60,120],'depth':[3,6],'learning_rate':{'range':[.02,.2],'log':True},'l2_leaf_reg':[1,10]},'cnn_lstm':{'hidden':[8,16,32],'channels':[4,8],'learning_rate':{'range':[.001,.02],'log':True},'weight_decay':{'range':[1e-5,.01],'log':True},'epochs':[30,50]}}
    space['spatial_xgboost']={'xgboost':space['xgboost'],'gp_fixed':{'length_scale_degrees':[30,30],'signal_variance':.01,'white_noise':.001,'alpha':1e-5,'optimizer':None,'training_unit':'country-mean training residual'}}
    result={'id':state['id'],'status':'COMPLETED','synthetic':False,'study_type':'public national ecological prevalence regression','created_at':state['created_at'],'completed_at':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.time()-started,'seed':seed,'protocol':{'outer':'leave-one-World-Bank-region-out, all years of test region excluded from fitting/tuning','inner':'20% of remaining countries sampled once per outer fold; their 2022 labels validate candidates; their complete histories excluded from inner train','train_years':[2002,2021],'validation_year':2022,'test_year':2023,'window_years':3,'target':'stunting_prevalence_pct / 100','selection_metric':'inner validation MAE','trials_per_model_per_outer_fold':state['trials_per_model_per_outer_fold'],'sampler':'Optuna TPE, seed + outer fold','preprocessing':'training-only median imputation and StandardScaler on flattened 3-year windows, no country/region IDs or outcome features','final_fit':'all non-held-out-region countries, years <=2021; 2022 outer validation is monitoring only, never early stopping','prediction_clipping':[0,1],'cnn_training':'full-batch Adam/MSE, no early stopping, convolution kernel 2 padding1 + LSTM + sigmoid linear head','metrics_scale':'fraction; multiply MAE/RMSE by 100 for percentage points'},'data_summary':{'rows_raw_through_2023':len(raw),'countries':int(raw.country_code.nunique()),'sample_windows':len(df),'test_countries':int(pred.country_code.nunique()),'regions':list(blocks.index),'missing_fraction':missing,'unit':'country-year','dataset_sha256':hashlib.sha256((ROOT/'data/real/country_panel.csv').read_bytes()).hexdigest(),'manifest_sha256':hashlib.sha256((ROOT/'data/real/manifest.json').read_bytes()).hexdigest()},'features':FEATURES,'models':models,'folds':folds,'statistics':statistics,'regional_metrics':regional,'predictions':pred.to_dict('records'),'hyperparameter_space':space,'limitations':limitations,'versions':{p:importlib.metadata.version(p) for p in ['numpy','pandas','scipy','scikit-learn','xgboost','catboost','torch','optuna','joblib']},'python':platform.python_version(),'artifacts':[]}
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'savefig.dpi':220})
    figures=folder/'figures';figures.mkdir(exist_ok=True)
    def export(name):
        plt.tight_layout()
        for suffix in ['png','svg','pdf']:plt.savefig(figures/f'{name}.{suffix}',bbox_inches='tight')
        plt.close()
    fig,ax=plt.subplots(figsize=(10,5));ms=sorted(models,key=lambda m:m['metrics']['test']['mae']);ax.barh([m['label'] for m in ms],[100*m['metrics']['test']['mae'] for m in ms]);ax.set_xlabel('Out-of-region 2023 MAE (percentage points)');ax.invert_yaxis();export('01_model_mae')
    fig,axes=plt.subplots(2,3,figsize=(13,8))
    for ax,a in zip(axes.flat,LABELS):
        g=pred[pred.algorithm==a];ax.scatter(g.observed*100,g.predicted*100,s=15,alpha=.7);ax.plot([0,60],[0,60],'k--');ax.set(title=LABELS[a],xlabel='Published prevalence (%)',ylabel='Predicted (%)')
    axes.flat[-1].axis('off');export('02_observed_predicted')
    fig,ax=plt.subplots(figsize=(12,5));image=ax.imshow(blocks.to_numpy()*100,aspect='auto');ax.set_xticks(range(5),[LABELS[a] for a in blocks.columns],rotation=20,ha='right');ax.set_yticks(range(len(blocks)),blocks.index);fig.colorbar(image,ax=ax,label='MAE (percentage points)');export('03_region_errors')
    ep=pd.DataFrame(epochs);ep=ep[(ep.algorithm=='cnn_lstm')&(ep.stage=='outer_fit')];fig,ax=plt.subplots(figsize=(9,5))
    for fold,g in ep.groupby('fold'):ax.plot(g.epoch,g.validation_mse,label=f'Region fold {fold}')
    ax.set(xlabel='Epoch',ylabel='Validation MSE (fraction squared)',title='CNN-LSTM validation histories');ax.legend(fontsize=8);export('04_cnn_learning')
    hashes={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file() and p.name not in ['state.json','results.json']};save(folder/'artifact_hashes.json',hashes)
    result['artifacts']=[{'path':str(p.relative_to(folder)),'bytes':p.stat().st_size} for p in folder.rglob('*') if p.is_file() and p.name!='state.json'];save(folder/'results.json',result)
    with zipfile.ZipFile(folder/'evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in folder.rglob('*'):
            if p.is_file() and p.name not in ['evidence.zip','state.json']:z.write(p,str(p.relative_to(folder)))
    state.update(status='COMPLETED',elapsed_seconds=time.time()-started);save(folder/'state.json',state);save(folder/'status.json',state);save(folder.parent/'latest_real.json',{'id':state['id']});return result




def load_fold(folder,algorithm,fold):
    """Reload a persisted outer-fold predictor without refitting transforms."""
    folder=Path(folder)
    if algorithm!='cnn_lstm':return joblib.load(folder/'models'/f'{algorithm}_{fold}.joblib')
    import torch
    bundle=joblib.load(folder/'models'/f'{algorithm}_{fold}_preprocess.joblib');checkpoint=torch.load(folder/'models'/f'{algorithm}_{fold}.pt',map_location='cpu',weights_only=False);p=checkpoint['params'];model=make_net(p['channels'],p['hidden'],len(checkpoint['features']));model.load_state_dict(checkpoint['state_dict']);model.eval();bundle['model']=model;return bundle

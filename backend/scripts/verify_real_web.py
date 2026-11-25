"""Read-only endpoint checks against immutable real-run artifacts; no seed or training."""
import os, sys, json
from pathlib import Path
os.environ['AUTO_SEED']='false'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.v1 import research
app=FastAPI(); app.include_router(research.router,prefix='/api/v1')
with TestClient(app) as client:
    assert client.get('/api/v1/research/real/latest').status_code==401
    app.dependency_overrides[research.READ.dependency]=lambda: object()
    detail=client.get('/api/v1/research/real/latest')
    assert detail.status_code==200, detail.text
    data=detail.json(); r=data['results']
    assert r['synthetic'] is False and len(r['folds'])==35
    assert len(r['statistics']['wilcoxon_holm'])==10
    assert len(client.get('/api/v1/research/real/trials').json()['items'])==350
    for name in ['results.json','country_panel.csv','evidence.zip','01_model_mae.svg']:
        response=client.get('/api/v1/research/real/files/'+name)
        assert response.status_code==200, (name,response.text[:80])
    for name in ['secret.txt','models/random_forest_0.joblib','%2e%2e%2fresults.json','%2e%2e%5cresults.json','C:%5cWindows%5cwin.ini']:
        assert client.get('/api/v1/research/real/files/'+name).status_code==404, name
    print(json.dumps({'status':'PASS','run':r['id'],'fits':35,'trials':350,'pairwise':10,'auth_required':True,'download_allowlist_and_traversal':True}))

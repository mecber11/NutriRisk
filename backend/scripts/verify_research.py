"""Live checks without printing tokens or sending external notifications."""
import io
import json
import zipfile
import httpx
from app.core.config import settings

def main():
    checks=[]
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=120) as client:
        response=client.post('/api/v1/auth/login',json={'email':'admin@nutririsk.ai','password':'Admin#2026!'})
        response.raise_for_status()
        headers={'Authorization':'Bearer '+response.json()['access_token']}
        def get(path):
            response=client.get('/api/v1'+path,headers=headers)
            response.raise_for_status()
            checks.append({'path':path,'status':response.status_code})
            return response
        get('/research/audit')
        workflows=get('/research/workflows').json()['items']
        assert len(workflows)==6
        for item in workflows: get('/research/workflows/'+item['name'])
        runs=get('/research/runs').json()['items']
        completed=next(row for row in runs if row['status']=='COMPLETED' and row['trials_per_model_per_outer_fold']==50)
        run_id=completed['id']
        detail=get('/research/runs/'+run_id).json()
        assert len(detail['results']['metrics'])==5
        assert detail['results']['statistics']['n_blocks']==5
        for figure in detail['gallery']['figures']:
            for extension in figure['formats']:
                response=get(f"/research/runs/{run_id}/files/{figure['name']}.{extension}")
                assert len(response.content)>500
        response=get(f'/research/runs/{run_id}/files/figuras_alta_calidad.zip')
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.testzip() is None
            assert 'predictions.csv' in archive.namelist()
            assert 'roc_precision_recall.png' in archive.namelist()
        service={'X-N8N-Token':settings.n8n_webhook_token}
        for operation in ['quality','monitor']:
            response=client.post('/api/v1/automation/'+operation,headers=service)
            response.raise_for_status()
            if operation=='quality':
                assert all(row['status']!='FAILED' for row in response.json()['results']),response.text
            checks.append({'operation':operation,'status':response.status_code})
        evidence=client.post('/api/v1/automation/evidence',headers=service,json={'question':'OMS emaciación y retraso del crecimiento'})
        evidence.raise_for_status()
        assert evidence.json()['data']['sources']
        answer=client.post('/api/v1/agent/chat',headers=headers,json={'message':'Qué dice la OMS sobre emaciación y retraso del crecimiento'})
        answer.raise_for_status()
        assert 'who.int' in answer.json()['answer']
        checks.append({'operation':'LangChain evidence_search','status':200})
        assert client.post('/api/v1/automation/monitor').status_code==401
        assert client.get('/api/v1/research/audit').status_code==401
        print(json.dumps({'passed':len(checks),'run_id':run_id,'figures':len(detail['gallery']['figures']),'integrations':detail.get('integrations'), 'checks':checks},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()

"""Verify publication metadata using the DOI registration agency, not generated citations."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json,re,time
import httpx

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.tmp'/'article'
OUT.mkdir(parents=True,exist_ok=True)
SOURCES={
 'tripod':'10.1136/bmj-2023-078378', 'probast':'10.1136/bmj-2024-082505',
 'validation1':'10.1136/bmj-2023-074819', 'validation2':'10.1136/bmj-2023-074820', 'samplesize':'10.1136/bmj-2023-074821',
 'decide':'10.1038/s41591-022-01772-9', 'future':'10.1136/bmj-2024-081554',
 'leakage_questions':'10.1038/s41592-024-02362-y', 'leakage_crisis':'10.1016/j.patter.2023.100804',
 'synthetic_replication':'10.1038/s41598-024-57207-7', 'synthetic_biomedicine':'10.1038/s44222-024-00245-7',
 'leakage_connectome':'10.1038/s41467-024-46150-w',
 'india':'Unveiling predictive factors for household-level stunting in India A machine learning approach using NFHS-5 and satellite-driven data',
 'bangladesh':'10.1371/journal.pone.0315393', 'eastafrica':'10.1038/s41598-026-46944-6',
 'attention':'10.1016/j.ibmed.2025.100255', 'hybrid':'10.1177/18724981251399860', 'egypt':'10.1186/s12887-025-06138-x',
 'imbalance':'10.1038/s41598-026-64018-5', 'determinants':'10.1038/s41598-025-99288-y',
 'ethiopia_hybrid':'10.1038/s41598-026-46417-w', 'fairness':'10.1038/s41551-023-01056-8',
 'concepts':'10.1007/s11229-022-03485-5', 'stakeholders':'10.1038/s42256-023-00698-2',
 'llm_limits':'10.1038/s41746-023-00879-8', 'interpretable':'10.1214/21-SS133',
 'rf':'10.1023/A:1010933404324','xgb':'10.1145/2939672.2939785',
 'optuna':'10.1145/3292500.3330701', 'shap':'A unified approach to interpreting model predictions Lundberg Lee 2017',
}

def fetch(item):
 key,query=item
 with httpx.Client(timeout=45,follow_redirects=True,headers={'User-Agent':'NutriRisk-research-manuscript/1.0 (metadata verification)'}) as client:
  if query.startswith('10.'):
   response=client.get('https://api.crossref.org/works/'+query)
   for attempt in range(4):
    if response.status_code!=429: break
    time.sleep(5*(attempt+1));response=client.get('https://api.crossref.org/works/'+query)
   response.raise_for_status();m=response.json()['message']
  else:
   response=client.get('https://api.crossref.org/works',params={'query.bibliographic':query,'rows':1})
   response.raise_for_status();m=response.json()['message']['items'][0]
  return key,{'doi':m.get('DOI'),'title':m.get('title',[''])[0],'authors':m.get('author',[]),'year':m.get('published',{}).get('date-parts',[[0]])[0][0], 'journal':m.get('container-title',[''])[0] if m.get('container-title') else '', 'volume':m.get('volume',''),'issue':m.get('issue',''),'page':m.get('page',m.get('article-number','')),'type':m.get('type'), 'abstract':re.sub('<[^>]+>',' ',m.get('abstract','')), 'url':m.get('URL'),'checked':'2026-11-04'}

if __name__=='__main__':
 cache=OUT/'references_verified.json'
 data=json.loads(cache.read_text(encoding='utf-8')) if cache.exists() else {}
 with ThreadPoolExecutor(max_workers=2) as pool:
  for key,record in pool.map(fetch,[(k,v) for k,v in SOURCES.items() if k not in data]):
   data[key]=record
   cache.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
   print(key,record['year'],record['title'],record['doi'],flush=True)
 (OUT/'references_verified.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

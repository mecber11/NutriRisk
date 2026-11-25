"""Repair presentation encoding and refresh figures without changing fitted results."""
from pathlib import Path
import sys, json, hashlib, zipfile, shutil
ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'backend/storage/classification/20261106T203950-42926913'
def repair(value):
    if isinstance(value, dict): return {k:repair(v) for k,v in value.items()}
    if isinstance(value, list): return [repair(v) for v in value]
    if not isinstance(value,str): return value
    for _ in range(3):
        old=value
        for character in '\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00c1\u00c9\u00cd\u00d3\u00da\u00d1\u00b7\u2013\u2014\u2212\u2265\u0394':
            try: bad=character.encode('utf-8').decode('cp1252')
            except UnicodeDecodeError: bad=character.encode('utf-8').decode('latin1')
            value=value.replace(bad,character)
        if value==old: break
    return value
source=ROOT/'backend/app/services/public_classification.py'
source.write_text(repair(source.read_text(encoding='utf-8')),encoding='utf-8')
sys.path.insert(0,str(ROOT/'backend'))
from app.services.public_classification import figures
r=repair(json.loads((RUN/'results.json').read_text(encoding='utf-8')))
before=[(m['metrics'],m['roc'],m['pr'],m['confusion_matrix']) for m in r['models']]
r['figures']=[]
figures(RUN,r)
assert before==[(m['metrics'],m['roc'],m['pr'],m['confusion_matrix']) for m in r['models']]
(RUN/'results.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(source,RUN/'source/public_classification.py')
hashes={str(p.relative_to(RUN)):hashlib.sha256(p.read_bytes()).hexdigest() for p in RUN.rglob('*') if p.is_file() and p.name not in ['artifact_hashes.json','evidence.zip']}
(RUN/'artifact_hashes.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
with zipfile.ZipFile(RUN/'evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in RUN.rglob('*'):
        if p.is_file() and p.name!='evidence.zip': z.write(p,str(p.relative_to(RUN)))
print(json.dumps({'figures':len(r['figures']),'dpi':600,'metrics_unchanged':True}))

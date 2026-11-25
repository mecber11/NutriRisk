from pathlib import Path
import io, json, zipfile, xml.etree.ElementTree as ET
import httpx, fitz
from docx import Document
from openpyxl import load_workbook
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
checks={}
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=120) as client:
    auth=client.post('/api/v1/auth/login',json={'email':'admin@nutririsk.ai','password':'Admin#2026!'})
    auth.raise_for_status()
    headers={'Authorization':'Bearer '+auth.json()['access_token']}
    for fmt in ['pdf','docx','xlsx']:
        response=client.post('/api/v1/reports/generate',headers=headers,json={'kind':'priority_ranking','fmt':fmt,'params':{'year':2023}})
        response.raise_for_status()
        data=client.get(response.json()['download_url'],headers=headers)
        data.raise_for_status()
        if fmt=='pdf':
            doc=fitz.open(stream=data.content,filetype='pdf')
            content=' '.join(page.get_text() for page in doc)
            assert 'Interpretación' in content
        elif fmt=='docx':
            doc=Document(io.BytesIO(data.content))
            assert sum('Interpretación' in p.text for p in doc.paragraphs)>=len(doc.tables)
        else:
            book=load_workbook(io.BytesIO(data.content))
            for sheet in book:
                assert any('Interpretación' in str(cell.value) for row in sheet for cell in row),sheet.title
        checks[fmt]='OK'
with zipfile.ZipFile(ROOT/'entregables/Figuras_NutriRisk_con_interpretacion.zip') as archive:
    assert archive.testzip() is None
    assert len(archive.namelist())==30
for path in (ROOT/'entregables/figuras_interpretadas').glob('*.png'):
    with Image.open(path) as picture:
        assert min(picture.info['dpi'])>599
for path in (ROOT/'entregables/figuras_interpretadas').glob('*.svg'):
    ET.parse(path)
pdf=fitz.open(ROOT/'.tmp/article/final-v3.pdf')
assert len(pdf)==25
assert sum(page.get_text().count('Interpretación y alcance.') for page in pdf)==15
figure=fitz.open(next((ROOT/'entregables/figuras_interpretadas').glob('*.pdf')))
figure[0].get_pixmap(dpi=100).save(ROOT/'.tmp/article/figure-delivery-preview.png')
checks.update({'article_pages':25,'interpreted_tables_and_figures':15,'figure_files':30,'png_dpi':600})
(ROOT/'.tmp/article/delivery_checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
print(json.dumps(checks))

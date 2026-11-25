"""Explicit reading notes for every tabular and plotted view."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'frontend'/'src'
tables={
 'Audit':['audit','audit'], 'Explainability':['shap'], 'Fairness':['fairness'],
 'Datasets':['datasets','datasets'], 'Dashboard':['territories','models'],
 'Indicators':['records'], 'Models':['models','models','regional'], 'Reports':['reports'],
 'Settings':['settings'], 'Territories':['territories'], 'TerritoryDetail':['shap'], 'Users':['users'],
}
charts={
 'Audit':['audit'], 'Explainability':['shap','dependence','shap','shap'],
 'Fairness':['fairness'], 'Dashboard':['trend','risk','prevalence'],
 'Indicators':['prevalence','prevalence','prevalence','histogram'], 'Models':['regional'],
}
for page in set(tables)|set(charts)|{'Research','RiskMap'}:
 path=ROOT/'pages'/f'{page}.tsx'
 text=path.read_text(encoding='utf-8')
 if page in tables:
  assert text.count('<DataTable')==len(tables[page]),(page,'tables')
  chunks=text.split('<DataTable')
  text=chunks[0]+''.join('<DataTable interpretationId="'+key+'"'+chunk for key,chunk in zip(tables[page],chunks[1:]))
 if page in charts:
  assert text.count('<ResponsiveContainer')==len(charts[page]),(page,'charts')
  chunks=text.split('<ResponsiveContainer')
  text=chunks[0]+''.join('<ExplainedChart explanationId="'+key+'"'+chunk for key,chunk in zip(charts[page],chunks[1:]))
  text=text.replace('</ResponsiveContainer>','</ExplainedChart>')
  text="import { ExplainedChart, Interpretation } from '../components/Interpretation';\n"+text
 else:
  text="import { Interpretation } from '../components/Interpretation';\n"+text
 if page in ['Datasets','Users']:
  text=text.replace('</table>','</table>\n<Interpretation id="'+('datasets' if page=='Datasets' else 'users')+'" />')
 if page=='Research':
  for key in ['comparison','statistics','requirements']:
   text=text.replace('</table></div>','</table><Interpretation id="'+key+'" /></div>',1)
  text=text.replace('<Preview path=', '<Preview path=')
  text=text.replace('title={figure.title} />','title={figure.title} />\n      <Interpretation id={figure.name} />')
 if page in ['RiskMap','TerritoryDetail']:
  text=text.replace('</MapContainer>\n            </div>','</MapContainer>\n            </div>\n            <Interpretation id="territories" />') if page=='RiskMap' else text.replace('</MapContainer>\n                  </div>','</MapContainer>\n                  </div>\n                  <Interpretation id="territories" />')
 path.write_text(text,encoding='utf-8')

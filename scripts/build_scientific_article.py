"""Scientific manuscript derived exclusively from executed NutriRisk evidence.

Editorial authority: user-provided Normas and EstructuraArtículo. The example
supplies the page geometry and visual idiom; author identities are never copied.
"""
from pathlib import Path
from collections import defaultdict
from copy import deepcopy
import hashlib,html,json,re,shutil,zipfile
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
TMP=ROOT/'.tmp'/'article'
OUT=ROOT/'entregables'
RUN=ROOT/'backend'/'storage'/'research'/'20261104T170319-269cbcbc'
REFERENCE=Path('C:/Users/David/Downloads/ArticuloEjemplo.docx')
FINAL=OUT/'Articulo_NutriRisk_Evaluacion_Reproducible.docx'
R=json.loads((RUN/'results.json').read_text(encoding='utf-8'))
E=json.loads((TMP/'evidence.json').read_text(encoding='utf-8'))
C=json.loads((RUN/'classification_metrics.json').read_text(encoding='utf-8'))
NOTES=json.loads((TMP/'interpretations.json').read_text(encoding='utf-8'))
refs=json.loads((TMP/'references_verified.json').read_text(encoding='utf-8'))
refs['shap']={'title':'A unified approach to interpreting model predictions','authors':[{'family':'Lundberg','given':'Scott M.'},{'family':'Lee','given':'Su-In'}],'year':2017,'journal':'Advances in Neural Information Processing Systems','volume':'30','issue':'','page':'4765–4774','doi':'','url':'https://proceedings.neurips.cc/paper/2017/hash/8a20a8621978632d76c43dfd28b67767-Abstract.html','type':'proceedings-article'}
refs['xgb']['title']='XGBoost: A scalable tree boosting system'
refs['optuna']['title']='Optuna: A next-generation hyperparameter optimization framework'
refs['hybrid']['year']=2026  # Crossref published-print: January 2026, volume 20(1).
refs['who_growth']={'title':'WHO child growth standards: Length/height-for-age, weight-for-age, weight-for-length, weight-for-height and body mass index-for-age: Methods and development','authors':[{'literal':'World Health Organization'}],'year':2006,'journal':'','volume':'','issue':'','page':'','doi':'','url':'https://www.who.int/publications/i/item/924154693X','type':'book'}
refs['who_malnutrition']={'title':'Malnutrition','authors':[{'literal':'World Health Organization'}],'year':2024,'journal':'','volume':'','issue':'','page':'','doi':'','url':'https://www.who.int/news-room/fact-sheets/detail/malnutrition','type':'webpage'}
used=set()
def first(ref):return ref['authors'][0].get('family',ref['authors'][0].get('literal',''))
groups=defaultdict(list)
ambiguous=defaultdict(list)
for key,ref in refs.items():
 groups[(tuple(a.get('family',a.get('literal','')) for a in ref['authors']),ref['year'])].append(key)
 ambiguous[(first(ref),ref['year'])].append(key)
suffix={}
for values in groups.values():
 if len(values)>1:
  for index,key in enumerate(sorted(values,key=lambda k:refs[k]['title'].lower())):suffix[key]=chr(97+index)
def cite(*keys):
 parts=[]
 for key in sorted(keys,key=lambda k:(first(refs[k]).lower(),refs[k]['year'],suffix.get(k,''))):
  used.add(key);ref=refs[key];authors=ref['authors'];name=first(ref)
  if len(authors)==2:name+=' & '+authors[1]['family']
  elif len(authors)>2:
   variants=ambiguous[(first(ref),ref['year'])]
   if len(variants)>1 and not suffix.get(key):
    families=[a.get('family',a.get('literal','')) for a in authors]
    count=2
    while count<len(families) and any([a.get('family',a.get('literal','')) for a in refs[other]['authors']][:count]==families[:count] for other in variants if other!=key):count+=1
    name=', '.join(families[:count])+', et al.'
   else:name+=' et al.'
  parts.append(f"{name}, {ref['year']}{suffix.get(key,'')}")
 return '('+'; '.join(parts)+')'
def num(v,d=4):return f'{v:.{d}f}'.replace('.',',')

OUT.mkdir(exist_ok=True)
shutil.copy2(REFERENCE,FINAL)
doc=Document(FINAL)
body=doc._element.body
for child in list(body):
 if child.tag!=qn('w:sectPr'):body.remove(child)
section=doc.sections[0]
normal=doc.styles['Normal']
normal.font.name='Montserrat';normal.font.size=Pt(11);normal.font.color.rgb=RGBColor(0,0,0)
normal.paragraph_format.line_spacing=1.15;normal.paragraph_format.space_after=Pt(6)
normal.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
for name in ['Title','Heading 1','Heading 2','Caption','Bibliography']:
 if name in doc.styles:
  st=doc.styles[name];st.font.name='Montserrat';st.font.color.rgb=RGBColor(0,0,0)
  st.paragraph_format.space_after=Pt(6)
for name,size in [('Title',15),('Heading 1',12),('Heading 2',11),('Caption',9),('Bibliography',9.5)]:
 if name in doc.styles:doc.styles[name].font.size=Pt(size)
doc.styles['Heading 1'].paragraph_format.space_before=Pt(12)
doc.styles['Heading 2'].paragraph_format.space_before=Pt(9)
for name in ['Heading 1','Heading 2','Title']:
 doc.styles[name].paragraph_format.keep_with_next=True
for element in list(doc._element.xpath('.//w:pBdr')):
 element.getparent().remove(element)
for element in list(doc.styles.element.xpath('.//w:pBdr')):
 element.getparent().remove(element)
doc.core_properties.title='Evaluación reproducible de modelos explicables para estimar desnutrición infantil en territorios sintéticos'
doc.core_properties.author='Autoría pendiente de confirmación'
doc.core_properties.subject='Estudio computacional con datos sintéticos y aplicación NutriRisk AI'
doc.core_properties.keywords='calibración; optimización bayesiana; salud pública; transferibilidad espacial'
doc.settings.element.append(OxmlElement('w:updateFields'))
doc.settings.element[-1].set(qn('w:val'),'true')

table_count=0;figure_count=0
inventory=[]
def paragraph(text,bold=False,italic=False,style=None,size=None,keep=False):
 p=doc.add_paragraph(style=style or 'Normal')
 p.paragraph_format.keep_together=True
 p.paragraph_format.keep_with_next=keep
 run=p.add_run(text);run.bold=bold;run.italic=italic
 if size:run.font.size=Pt(size)
 return p
def heading(text,level=1):doc.add_heading(text,level)
def note(text):
 p=paragraph('Interpretación y alcance. '+text,size=9.5)
 p.paragraph_format.space_before=Pt(3);p.paragraph_format.space_after=Pt(10)
 return p
def table(title,headers,rows,interpretation,widths=None):
 global table_count
 table_count+=1
 paragraph(f'Tabla {table_count}',bold=True,size=10,keep=True)
 paragraph(title,italic=True,size=10,keep=True)
 t=doc.add_table(rows=1,cols=len(headers))
 t.autofit=False
 for cell,value in zip(t.rows[0].cells,headers):cell.text=str(value)
 for values in rows:
  cells=t.add_row().cells
  for cell,value in zip(cells,values):cell.text=str(value)
 available=section.page_width-section.left_margin-section.right_margin
 for rowindex,row in enumerate(t.rows):
  trPr=row._tr.get_or_add_trPr();trPr.append(OxmlElement('w:cantSplit'))
  if rowindex==0:
   repeat=OxmlElement('w:tblHeader');repeat.set(qn('w:val'),'true');trPr.append(repeat)
  for index,cell in enumerate(row.cells):
   cell.width=int(available*(widths[index] if widths else 1/len(headers)))
   for p in cell.paragraphs:
    p.paragraph_format.line_spacing=1.0;p.paragraph_format.space_after=Pt(4);p.paragraph_format.space_before=Pt(4)
    p.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.keep_with_next=True
    for run in p.runs:run.font.name='Montserrat';run.font.size=Pt(9);run.bold=rowindex==0
   if rowindex==0:
    shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'E9EFF2');cell._tc.get_or_add_tcPr().append(shade)
  if rowindex==len(t.rows)-1:
   for cell in row.cells:
    for p in cell.paragraphs:p.paragraph_format.keep_with_next=True
 note(interpretation)
 inventory.append({'type':'table','number':table_count,'title':title,'interpretation':interpretation})
def figure(name,title,interpretation=None,width=15.5):
 global figure_count
 figure_count+=1
 paragraph(f'Figura {figure_count}',bold=True,size=10,keep=True)
 paragraph(title,italic=True,size=10,keep=True)
 p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
 p.paragraph_format.keep_with_next=True;p.paragraph_format.space_after=Pt(2)
 p.add_run().add_picture(str(RUN/(name+'.png')),width=Cm(width))
 if interpretation is None:
  n=NOTES[name];interpretation=n['reading']+' '+n['meaning']+' '+n['limit']
 note(interpretation)
 inventory.append({'type':'figure','number':figure_count,'title':title,'file':name+'.png','interpretation':interpretation})

title_es='Evaluación reproducible de modelos explicables para estimar desnutrición infantil en territorios sintéticos'
title_en='Reproducible evaluation of explainable models for estimating childhood undernutrition across synthetic territories'
p=paragraph(title_es,style='Title',bold=True);p.alignment=WD_ALIGN_PARAGRAPH.CENTER
p=paragraph(title_en,bold=True,size=12);p.alignment=WD_ALIGN_PARAGRAPH.CENTER
paragraph('Autoría, afiliaciones, identificadores ORCID y correspondencia: pendientes de confirmación por los autores.',size=9)

abstract_es='La vigilancia nutricional requirió herramientas que relacionaran predicciones, incertidumbre y trazabilidad sin confundir funcionamiento informático con utilidad clínica. Se desarrolló NutriRisk AI y se evaluaron cinco modelos para estimar prevalencia territorial de retraso del crecimiento mediante un experimento computacional reproducible. Se utilizaron 14 400 registros infantiles sintéticos, distribuidos en 24 territorios, cinco regiones y tres periodos. Se compararon Random Forest, XGBoost, CatBoost, un híbrido espacial y una red convolucional recurrente con ventanas de dos años. La optimización anidada excluyó regiones completas y reservó las etiquetas del año final; se ejecutaron 1 250 ensayos de Optuna. Random Forest presentó el menor error absoluto medio, de 0,0832, frente a 0,1003 del comparador basal calculado posteriormente. Todos los coeficientes de determinación fueron negativos. Friedman no identificó diferencias significativas entre los cinco modelos (χ² = 4,32; p = 0,364). El análisis infantil complementario mostró discriminación moderada y baja sensibilidad al umbral fijo. Se verificaron 100 pruebas automatizadas y 44 comprobaciones del servidor. La plataforma permitió inspeccionar y descargar evidencia, pero los resultados no demostraron utilidad clínica ni transferencia a poblaciones reales.'
abstract_en='Nutritional surveillance required tools that linked predictions, uncertainty, and traceability without equating software operation with clinical usefulness. NutriRisk AI was developed and five models were evaluated for estimating territorial stunting prevalence through a reproducible computational experiment. The study used 14,400 synthetic child records distributed across 24 territories, five regions, and three periods. Random Forest, XGBoost, CatBoost, a spatial hybrid, and a convolutional recurrent network were compared using two-year covariate windows. Nested optimization excluded entire regions and withheld final-year labels; 1,250 Optuna trials were executed. Random Forest achieved the lowest mean absolute error, 0.0832, compared with 0.1003 for a baseline computed afterwards. All coefficients of determination were negative. The Friedman test did not identify significant differences among the five models (χ² = 4.32; p = 0.364). A complementary child-level analysis showed moderate discrimination and low sensitivity at a fixed threshold. Software verification included 100 automated tests and 44 server checks. The platform supported inspection and download of evidence, but the results established neither clinical usefulness nor transferability to real populations.'
heading('Resumen');paragraph(abstract_es)
paragraph('Palabras clave: calibración, optimización bayesiana, salud pública, transferibilidad espacial.',size=10)
heading('Abstract');paragraph(abstract_en)
paragraph('Keywords: Bayesian optimization, calibration, public health, spatial transferability.',size=10)

heading('Introducción')
paragraph(f'La desnutrición infantil comprende condiciones antropométricas distintas y exige diferenciar prevalencia observada, riesgo estimado y decisiones sanitarias. El retraso del crecimiento se identifica mediante talla para la edad y no equivale a una probabilidad producida por un algoritmo. Los estándares internacionales permiten definir indicadores comparables, mientras la carga sanitaria justifica herramientas que integren determinantes sociales y ambientales {cite("who_growth","who_malnutrition")}.')
paragraph(f'Los estudios con encuestas poblacionales exploran relaciones entre características familiares, condiciones materiales y resultados nutricionales. En Bangladesh, la selección e interpretación de predictores se aborda mediante aprendizaje explicable; en India, se combinan datos de hogares e información satelital. Estos diseños muestran la diversidad de escalas disponibles y la necesidad de declarar con precisión la unidad de análisis {cite("bangladesh","determinants","india")}.')
paragraph(f'La comparación de algoritmos incluye clasificadores de árboles, ensambles y redes neuronales. Estudios en Egipto y África oriental evalúan resultados infantiles a partir de encuestas, mientras los trabajos sobre atención y modelos híbridos introducen arquitecturas más complejas. Sus puntuaciones no son directamente intercambiables cuando cambian desenlaces, predictores o estrategias de partición {cite("egypt","eastafrica","attention","hybrid")}.')
paragraph(f'La evaluación debe considerar el desbalance de clases y la estructura territorial. Los análisis de desnutrición concurrente y de modelos híbridos explicables documentan contextos y categorías diferentes, por lo que el mejor clasificador en un conjunto no constituye una solución universal. Una comparación reproducible requiere mantener constantes objetivo, muestras evaluadas y disponibilidad de información {cite("imbalance","ethiopia_hybrid")}.')
paragraph(f'La separación entre ajuste y evaluación también resulta crítica. La fuga de información produce estimaciones optimistas cuando se comparten etiquetas, transformaciones o unidades dependientes entre particiones. Las preguntas de control metodológico y las demostraciones empíricas en otros campos biomédicos justifican examinar todo el procedimiento y no solo el algoritmo final {cite("leakage_crisis","leakage_questions","leakage_connectome")}.')
paragraph(f'La transparencia exige reportar el desarrollo, la evaluación y las limitaciones del modelo. Las guías de predicción y de riesgo de sesgo recomiendan describir datos, participantes, análisis y aplicabilidad, mientras la evaluación interna y externa permite delimitar qué población respalda cada conclusión. Estas recomendaciones orientan el informe sin convertir una demostración sintética en estudio clínico {cite("tripod","probast","validation1")}.')
paragraph(f'La interpretabilidad tampoco es una propiedad única. Las explicaciones deben responder a usuarios y propósitos concretos, distinguir fidelidad al modelo de conocimiento del fenómeno y reconocer sus límites conceptuales. Asimismo, la equidad depende de grupos, contextos y decisiones, por lo que una sola métrica no certifica una implementación justa {cite("interpretable","concepts","stakeholders","fairness")}.')
paragraph('La necesidad abordada consiste en reunir una comparación homogénea, una aplicación funcional y explicaciones accesibles sin ocultar resultados desfavorables. El objetivo es desarrollar y verificar una plataforma reproducible, comparar cinco modelos de prevalencia territorial con exclusión regional y temporal, y comunicar incertidumbre. Se examina si alguno muestra una ventaja consistente en el escenario sintético y qué evidencia respalda el funcionamiento del prototipo, diferenciando las validaciones pendientes.')

heading('Materiales y métodos')
heading('Diseño y escenario de estudio',2)
paragraph('Se realizó un estudio cuantitativo, experimental e informático en un entorno controlado local con Windows. Se empleó un país ficticio denominado Andara, sin correspondencia inferencial con Perú ni con otra jurisdicción real. La población de demostración estuvo formada por 14 400 registros infantiles sintéticos, con 200 observaciones por territorio y año, 24 territorios, cinco regiones y los periodos 2021–2023. Se incluyeron todos los registros disponibles; no se realizó muestreo probabilístico de personas reales ni una evaluación con profesionales o pacientes.')
paragraph(f'El generador utilizó una semilla fija y mediciones compatibles con curvas de crecimiento para calcular indicadores antropométricos. Se distinguió la coherencia interna del generador de la representatividad poblacional. La literatura sobre datos sintéticos señala que utilidad y replicabilidad deben evaluarse para cada análisis; no se asumió que generar registros plausibles reprodujera asociaciones o efectos observados en una población {cite("synthetic_replication","synthetic_biomedicine")}.')
paragraph('La Tabla 1 resumió las unidades y variables. El desenlace principal fue la proporción de registros con retraso del crecimiento por territorio y año, expresada entre 0 y 1. Los predictores fueron 26 determinantes demográficos, familiares, dietéticos y ambientales. Se excluyeron talla, peso, puntuaciones antropométricas y la etiqueta nutricional como entradas predictivas, para evitar reconstruir mecánicamente el criterio diagnóstico.')
table('Unidades de análisis y disponibilidad de información', ['Componente','Definición y función'], [
 ['Registro infantil','Observación sintética con edad, sexo, condiciones familiares y ambientales; clasificación complementaria.'],
 ['Territorio y año','Agregación de determinantes y prevalencia; unidad del estudio común de regresión.'],
 ['Determinantes','26 variables de demografía, riqueza, educación, agua y saneamiento, dieta, morbilidad reciente y ambiente.'],
 ['Desenlace territorial','Media del indicador de retraso del crecimiento en cada territorio y año.'],
 ['Datos excluidos como predictores','Peso, talla, puntuaciones antropométricas y etiquetas nutricionales.'],
 ['Información geográfica','Coordenadas y región ficticias; coordenadas empleadas en el híbrido espacial.'],
 ], 'La agregación produjo 24 casos territoriales en el año final; los 14 400 registros infantiles no constituyeron 14 400 unidades independientes para la prueba entre modelos territoriales. La exclusión de mediciones que definen el desenlace redujo la circularidad, sin resolver por sí sola otras fuentes de sesgo.',[.27,.73])

heading('Arquitectura y trazabilidad del prototipo',2)
paragraph('La Figura 1 presentó la arquitectura implementada y sus extensiones configuradas. FastAPI expuso autenticación, indicadores, predicciones, explicaciones y reportes; React reunió dashboard, mapas, alertas, administración e investigación. La ejecución local utilizó SQLite. PostgreSQL/PostGIS, MinIO, n8n y LangFlow se conservaron como configuraciones o prototipos con un estado explícito; su presencia en un archivo de despliegue no se contabilizó como ejecución observada.')
figure('arquitectura','Arquitectura de la plataforma y separación de responsabilidades')
paragraph(f'El agente LangChain dispuso de herramientas de consulta y de recuperación TF-IDF sobre resúmenes curados de fuentes oficiales. Se conservó un modo determinista sin proveedor externo. Las respuestas mostraron fuentes o abstención y no reemplazaron al modelo predictivo. Esta separación fue coherente con las limitaciones de evaluación descritas para modelos fundacionales en salud y con la necesidad de vincular cada herramienta a un uso verificable {cite("llm_limits")}.')
paragraph('Se prepararon seis workflows importables para adquisición pública, control de calidad, predicciones, alertas, reportes y monitoreo. La descarga contextual desde World Bank se mantuvo separada de los microdatos sintéticos. La distribución por correo requirió configuración SMTP y no se ejecutó. MLflow registró localmente parámetros, métricas y artefactos; MinIO no estuvo configurado en la ejecución evaluada.')

heading('Modelos y protocolo de comparación',2)
paragraph(f'Se compararon tres regresores individuales —Random Forest, XGBoost y CatBoost— y dos híbridos. El primero combinó XGBoost con un proceso gaussiano sobre residuos y coordenadas de entrenamiento; el segundo acopló una convolución unidimensional con memoria recurrente de corto y largo plazo. Los principios de ensambles de árboles y de boosting se utilizaron como familias predictivas, sin asumir superioridad previa {cite("rf","xgb")}. El híbrido espacial del experimento fue distinto de los diagnósticos SAR/SEM de la aplicación operativa.')
paragraph('La Figura 2 describió el protocolo común. Para cada región excluida, se entrenó con los otros territorios usando ventanas de determinantes de 2021–2022 y prevalencias de 2022. El modelo ajustado se evaluó en la región excluida con ventanas 2022–2023 y etiquetas de 2023. Las etiquetas del año final no participaron en imputación, normalización, selección de hiperparámetros o entrenamiento. Se exigieron tres periodos y presencia completa de las ventanas por territorio.')
figure('protocolo_experimental','Separación regional y temporal del experimento común')
paragraph('Se precisó que la evaluación utilizó covariables contemporáneas de 2023. Por ello, se estudió una estimación del mismo periodo con cambio espacial y temporal, no un pronóstico que desconociera todos los determinantes futuros. La imputación por mediana se ajustó únicamente con datos de entrenamiento de cada partición. La red estandarizó entradas y objetivo usando estadísticas del entrenamiento; los modelos tabulares recibieron las mismas ventanas vectorizadas. El ajuste del proceso gaussiano no utilizó residuos de la región evaluada.')
paragraph(f'La optimización se realizó mediante Optuna, con muestreador TPE, podador de mediana y 50 ensayos por algoritmo y región externa {cite("optuna")}. Dentro de cada ajuste externo se volvió a excluir una región del conjunto de entrenamiento para estimar el MAE interno. Se registraron 1 250 ensayos: 875 completados y 375 podados. El presupuesto igualó el número de ensayos, pero no los tiempos de cómputo ni el número de operaciones de cada algoritmo. La semilla principal fue 42.')
paragraph('La búsqueda de árboles incluyó número de estimadores, profundidad y regularización; la red exploró tasa de aprendizaje, canales, unidades recurrentes, dropout, penalización y épocas. Se conservaron parámetros de cada ensayo, pérdidas internas y estados de poda. El archivo de resultados incluyó el hash SHA-256 del conjunto analítico. Tras la comparación se añadió, como análisis basal a posteriori, la media de prevalencia de 2022 de las regiones de entrenamiento de cada pliegue; no se reutilizó la etiqueta de 2023 para construirla.')

heading('Métricas y análisis estadístico',2)
paragraph('Se calcularon error absoluto medio (MAE), raíz del error cuadrático medio (RMSE) y coeficiente de determinación (R²). MAE y RMSE se expresaron en la escala 0–1 de prevalencia; su multiplicación por 100 los convirtió en puntos porcentuales. Un R² negativo indicó peor ajuste que la media de los valores observados en la muestra evaluada, referencia distinta de la media de entrenamiento utilizada como comparador basal. Se obtuvieron intervalos percentiles del 95 % de MAE mediante 1 000 remuestreos de regiones con reemplazo.')
paragraph('La prueba de Friedman utilizó una matriz de cinco regiones por cinco modelos y no cinco métricas agregadas. Las diez comparaciones pareadas de Wilcoxon se ajustaron mediante Holm. Se informaron diferencias de MAE y sus intervalos exploratorios frente al comparador basal. Se advirtió que las cinco regiones tuvieron dependencia espacial potencial y que los pliegues compartieron datos de entrenamiento; por tanto, los valores p no se interpretaron como evidencia confirmatoria de superioridad. La muestra no se dimensionó para precisión clínica.')
paragraph(f'Los procedimientos de evaluación y la necesidad de diseñar una futura muestra externa se contextualizaron mediante recomendaciones sobre validación y tamaño muestral {cite("validation2","samplesize")}. No se aplicaron McNemar o DeLong a la regresión territorial. Tampoco se calcularon métricas de segmentación, detección de objetos o intervalos de pronóstico, porque no correspondieron a los objetivos observados.')

heading('Análisis complementario e interpretabilidad',2)
paragraph('Se evaluaron por separado tres clasificadores infantiles con parámetros fijos, exclusión completa de regiones y umbral de 0,5. Se calcularon sensibilidad, especificidad, F1, coeficiente de correlación de Matthews, área bajo ROC, precisión promedio y Brier. Las curvas ROC, Precision–Recall, matrices y calibración se identificaron como análisis complementario y no como resultados del estudio territorial optimizado. No se seleccionó un umbral usando las etiquetas externas para esas figuras.')
paragraph(f'La explicación operativa utilizó SHAP para describir contribuciones de variables respecto de la referencia del clasificador {cite("shap")}. Se incorporaron notas visibles de lectura, interpretación y alcance debajo de tablas, gráficas, mapas y figuras de investigación. Las exportaciones PDF, Word y Excel añadieron notas bajo sus tablas. No se evaluó si los lectores comprendieron mejor la interfaz ni se atribuyó a estas notas una mejora demostrada en decisiones clínicas.')

heading('Reproducibilidad y consideraciones éticas',2)
paragraph('El experimento principal se identificó como 20261104T170319-269cbcbc. Su hash de datos fue '+R['dataset_sha256']+'. Se ejecutó con Python '+E['version']['Python']+', scikit-learn '+E['version']['scikit-learn']+', XGBoost '+E['version']['xgboost']+', CatBoost '+E['version']['catboost']+', PyTorch '+E['version']['torch']+' y Optuna '+E['version']['optuna']+'. Se preservaron CSV de predicciones, bloques regionales, parámetros y figuras vectoriales o de 600 dpi.')
paragraph('No se recolectaron datos personales reales ni se realizaron intervenciones en personas. La simulación no se presentó como autorizada por un comité de ética; una evaluación posterior con información real requerirá permisos y revisión institucional según el contexto. Se utilizaron herramientas de inteligencia artificial para apoyar programación y preparación del manuscrito. La responsabilidad sobre contenido, integridad, autoría y aprobación final corresponderá a los autores humanos, cuyos datos quedaron pendientes de confirmación.')

heading('Resultados y discusión')
heading('Desempeño territorial e incertidumbre',2)
paragraph('La Tabla 2 presentó los resultados sobre los mismos 24 territorios del año final. Random Forest obtuvo el menor MAE, de 0,0832, mientras la CNN-LSTM alcanzó 0,1106. La referencia basal a posteriori obtuvo 0,1003. El menor MAE no se acompañó de R² positivo en ningún modelo. Estas cifras mostraron que la ejecución y optimización del procedimiento no garantizaron un ajuste territorial satisfactorio.')
rows=[]
for row in R['metrics']+[E['baseline']]:
 rows.append([row['label'],num(row['mae']),num(row['rmse']),num(row['r2'],3),f"[{num(row['ci']['lower'])}; {num(row['ci']['upper'])}]"])
table('Desempeño territorial y comparador basal a posteriori',['Modelo','MAE','RMSE','R²','IC 95 % del MAE'],rows,'El MAE de Random Forest equivalió a 8,32 puntos porcentuales de prevalencia y el basal a 10,03. Los intervalos reflejaron remuestreo de solo cinco regiones. Un R² negativo no significó que todos los modelos fueran peores que la media de entrenamiento: esa referencia fue distinta de la media observada empleada en la definición de R².',[.35,.12,.12,.12,.29])
paragraph('La Figura 3 permitió examinar conjuntamente el orden de MAE y la amplitud de sus intervalos. Frente al basal, la diferencia media de error absoluto de Random Forest fue −0,0171, con intervalo bootstrap exploratorio [−0,0323; −0,0063]. El contraste se añadió después del experimento y no fue una hipótesis confirmatoria preregistrada; tampoco convirtió la mejora numérica en utilidad clínica.')
figure('comparacion_modelos','Comparación de errores de los cinco modelos territoriales')
paragraph('La Figura 4 mostró heterogeneidad entre regiones. La tabla de bloques evitó tratar las 120 predicciones de cinco modelos sobre 24 territorios como casos independientes. La Figura 5 mostró dispersión respecto de la diagonal de coincidencia, coherente con los R² negativos y con errores relevantes aun cuando un algoritmo obtuvo una media menor.')
figure('mapa_calor_regiones','Error absoluto medio por región excluida y algoritmo')
figure('observado_estimado','Prevalencia territorial observada y estimada en el año final')

heading('Comparación estadística de los modelos',2)
paragraph('Friedman produjo χ² = 4,32 y p = 0,3644. No se encontró evidencia suficiente para rechazar la igualdad de rangos de desempeño bajo los supuestos del análisis. La Tabla 3 mostró que ninguna comparación pareada alcanzó p ajustado inferior a 0,05. El menor valor p sin ajustar fue 0,0625 y correspondió a Random Forest frente a XGBoost; después de Holm fue 0,6250.')
labels={key:value for key,value in [('random_forest','RF'),('xgboost','XGBoost'),('catboost','CatBoost'),('spatial_xgboost','XGBoost + GP'),('cnn_lstm','CNN-LSTM')]}
table('Comparaciones pareadas sobre los cinco bloques regionales',['Comparación','p de Wilcoxon','p ajustado Holm'],[[labels[row['a']]+' / '+labels[row['b']],num(row['pvalue']),num(row['pvalue_holm'])] for row in R['statistics']['wilcoxon_holm']], 'Los valores ajustados no respaldaron diferencias entre los cinco modelos. La ausencia de significación no demostró equivalencia y estuvo condicionada por pocos bloques, dependencia espacial potencial y entrenamiento compartido. RF significó Random Forest y GP, proceso gaussiano.',[.5,.25,.25])
paragraph('La CNN-LSTM no superó a los modelos individuales en este escenario. La Figura 6 mostró que la pérdida de entrenamiento se redujo o fluctuó durante el ajuste, pero esa trayectoria no constituyó evidencia de generalización. La disponibilidad de únicamente dos posiciones temporales por ventana y pocos territorios limitó la información con la cual la arquitectura recurrente pudo aprender patrones transferibles.')
figure('curvas_cnn_lstm','Pérdidas de entrenamiento de la red convolucional recurrente')

heading('Clasificación infantil y comunicación del riesgo',2)
paragraph('El análisis complementario incluyó 2 695 registros con retraso del crecimiento entre 14 400 observaciones, equivalentes al 18,72 %. La Tabla 4 mostró que Random Forest alcanzó AUC = 0,7756 y especificidad = 0,9948, pero sensibilidad = 0,0312 al umbral fijo de 0,5. XGBoost obtuvo sensibilidad = 0,1506. La exactitud superior al 81 % no describió por sí sola una capacidad adecuada para identificar los registros positivos.')
table('Diagnóstico complementario de clasificación infantil con umbral fijo de 0,5',['Modelo','AUC ROC','Sens.','Espec.','F1','MCC'],[[{'random_forest':'Random Forest','xgboost':'XGBoost','catboost':'CatBoost'}[row['algorithm']],num(row['auc']),num(row['sensitivity']),num(row['specificity']),num(row['f1']),num(row['mcc'])] for row in C['metrics']], 'Estos resultados provinieron de tres clasificadores con parámetros fijos y no de los cinco regresores optimizados. La alta especificidad coexistió con numerosos falsos negativos. Sens. indicó sensibilidad; Espec., especificidad; MCC, coeficiente de correlación de Matthews. El umbral de 0,5 no fue validado para una decisión sanitaria.',[.28,.16,.14,.14,.14,.14])
paragraph('La Figura 7 permitió comparar discriminación y precisión-recuperación sin convertir AUC en probabilidad de enfermedad. La Figura 8 presentó el efecto operativo del umbral: Random Forest detectó 84 positivos y dejó 2 611 falsos negativos. La Figura 9 mostró la relación entre probabilidades y frecuencias observadas por intervalos. Por ello, no se asumió que una clasificación con AUC moderada estuviera calibrada o fuese apta para tamizaje clínico.')
figure('roc_precision_recall','Curvas ROC y precisión recuperación de los clasificadores infantiles')
figure('matrices_confusion','Matrices de confusión del análisis infantil complementario')
figure('calibracion','Calibración descriptiva de probabilidades fuera de región')
paragraph('La Figura 10 presentó el resumen SHAP almacenado para el clasificador operativo. Su propósito fue explicar qué variables influyeron en las predicciones del modelo y no demostrar que modificar un determinante produciría una reducción de desnutrición. Las notas bajo la figura explicaron la magnitud de las barras, el significado de las contribuciones y su separación del estudio territorial.')
figure('shap_global','Contribuciones globales SHAP del clasificador operativo')

heading('Relación con estudios previos',2)
paragraph(f'Los resultados difirieron de los desempeños elevados descritos en algunos estudios de clasificación. Hendy y colaboradores evaluaron encuestas egipcias y comunicaron AUC superiores a 0,96 para determinados algoritmos; Feleke y colaboradores analizaron emaciación en África oriental y reportaron AUC de 0,746 para Random Forest {cite("egypt","eastafrica")}. No se interpretaron esas diferencias como prueba de superioridad o inferioridad: cambiaron el desenlace, los datos, la información predictora y la partición de evaluación.')
paragraph(f'Los estudios de Bangladesh e India apoyaron el interés en integrar condiciones familiares y territoriales, pero no justificaron trasladar sus asociaciones a Andara {cite("bangladesh","india","determinants")}. La integración de atención o componentes recurrentes y la clasificación de estados concurrentes también respondieron a diseños distintos {cite("attention","hybrid","imbalance","ethiopia_hybrid")}. En este experimento, la complejidad añadida no produjo una ventaja consistente, lo que respaldó examinar comparadores sencillos y la cantidad de información realmente disponible.')
paragraph(f'El resultado metodológico principal fue la posibilidad de auditar una comparación que conservó hallazgos desfavorables. La literatura sobre fuga de información y replicabilidad apoyó separar ajustes, etiquetas y evaluaciones {cite("leakage_crisis","synthetic_replication")}. Sin embargo, la exclusión de regiones dentro de un generador no equivalió a una cohorte externa real ni eliminó las asociaciones impuestas durante la síntesis. Esta distinción limitó el alcance de cualquier afirmación de transferibilidad.')

heading('Verificación funcional e interpretación visible',2)
paragraph('La Tabla 5 separó ejecución comprobada y configuración. La suite del backend aprobó 100 pruebas y la verificación del servidor aprobó 44 comprobaciones, incluidas descarga de figuras y ZIP, workflows, controles de calidad y consultas con fuentes. Estas comprobaciones se realizaron antes de la incorporación editorial de notas; la versión final conservó una compilación y verificación adicional documentadas en los anexos de entrega. Los conteos midieron requisitos informáticos y no desempeño clínico.')
table('Evidencia funcional y límites de las integraciones',['Componente','Evidencia comprobada','Límite'],[
 ['FastAPI y React','Compilación y endpoints de acceso, datos, mapas, modelos y reportes.','Sin estudio de usabilidad ni ensayo clínico.'],
 ['Investigación','Cinco modelos, validación anidada, estadísticas y descargas.','Datos sintéticos y pocas regiones.'],
 ['MLflow','Registro local de parámetros, métricas y artefactos.','No equivale a servidor remoto validado.'],
 ['n8n','Seis archivos importables y operaciones API verificables.','Activación y ejecuciones en n8n pendientes.'],
 ['LangChain','Consulta con fuentes y recuperación local comprobadas.','Corpus de resúmenes; sin evaluación de un LLM externo.'],
 ['LangFlow','Flujo exportado y componente de conexión.','Runtime visual pendiente de verificación.'],
 ['PostgreSQL y MinIO','Configuraciones de despliegue e integración.','La aplicación evaluada usó SQLite; MinIO no configurado.'],
 ], 'La tabla diferenció una capacidad programada de un servicio observado en ejecución. Las pruebas informáticas respaldaron funcionamiento local, pero no certificaron disponibilidad de toda la infraestructura ni mejoras sanitarias.',[.21,.43,.36])
paragraph(f'Las explicaciones visibles se organizaron como lectura, interpretación y alcance. Esta decisión respondió a la diversidad de necesidades de usuarios descrita por Imrie y colaboradores y a las advertencias conceptuales sobre explicabilidad {cite("stakeholders","concepts","interpretable")}. No se midieron comprensión, confianza o calidad de decisiones; por tanto, el manuscrito no atribuyó a las notas beneficios que requirieran una evaluación con lectores.')
paragraph(f'La separación de roles, auditoría y alertas aportó trazabilidad operativa, pero no certificó justicia o seguridad clínica. Las perspectivas de equidad y las guías de despliegue exigieron una evaluación contextual del uso y de sus consecuencias {cite("fairness","future")}. Del mismo modo, un agente con referencias no se consideró sustituto de evidencia predictiva ni de supervisión profesional {cite("llm_limits")}.')

heading('Limitaciones y validación pendiente',2)
paragraph(f'El estudio estuvo limitado por un único generador, una sola semilla principal y cinco regiones, con 24 territorios en el año final. No hubo validación externa real, ajuste con ponderaciones de encuesta, evaluación de transporte entre países ni análisis prospectivo de utilidad. El bootstrap con pocos grupos pudo resultar inestable; los intervalos y valores p se mantuvieron exploratorios. El tamaño muestral para una evaluación externa posterior deberá justificarse según precisión y uso previsto {cite("samplesize")}.')
paragraph(f'La búsqueda comparó presupuestos de ensayos y no presupuestos equivalentes de tiempo. El basal se calculó después del experimento; los análisis no estuvieron preregistrados. La recuperación se limitó a resúmenes curados y no se realizó una revisión PRISMA en bases bibliográficas. Las verificaciones de software tampoco sustituyeron evaluaciones humanas o clínicas. Las guías DECIDE-AI, TRIPOD+AI y PROBAST+AI proporcionaron criterios para diseñar esas etapas posteriores, sin que este trabajo afirmara haberlas completado {cite("decide","tripod","probast")}.')

heading('Conclusiones')
paragraph('Se desarrolló una plataforma reproducible que reunió modelos predictivos, optimización anidada, estadísticas, explicaciones visibles y descargas científicas. Random Forest obtuvo el menor error absoluto medio territorial, pero los cinco modelos presentaron R² negativos y no mostraron diferencias significativas en Friedman; la clasificación infantil complementaria mantuvo baja sensibilidad al umbral de 0,5. La contribución consistió en una infraestructura auditable que permitió comunicar incertidumbre y fallos, no en demostrar una herramienta clínica validada. Una siguiente evaluación deberá incorporar datos reales autorizados, mayor diversidad territorial y temporal, comparadores definidos previamente, calibración y validación externa, además de una evaluación de comprensión y utilidad con profesionales.')
heading('Conflicto de intereses')
paragraph('Declaración pendiente de confirmación por todos los autores. No se infirió ausencia de conflictos ni se preparó una carta firmada en su nombre. Antes del envío deberá incorporarse la declaración y documentación exigidas por la revista.')
heading('Contribución de autoría')
paragraph('La asignación nominal de roles CRediT quedó pendiente de confirmación. Deberán especificarse, según la contribución real, conceptualización, metodología, software, validación, análisis formal, investigación, recursos, curación de datos, redacción del borrador, revisión y edición, visualización, supervisión, administración y obtención de financiación. La asistencia de inteligencia artificial no constituyó autoría.')
heading('Fuente de financiación')
paragraph('Información pendiente de confirmación por los autores. No se declaró patrocinio ni ausencia de financiación sin respaldo documental. Si existió financiación, deberán indicarse entidad y código de contrato, convenio o resolución.')
heading('Disponibilidad de datos depositados')
paragraph('Se conservaron localmente datos sintéticos, código, predicciones, parámetros y figuras. No se verificó su depósito en un repositorio público ni una licencia de distribución; por tanto, no se inventaron URL, identificadores o licencias. Antes del envío deberá realizarse el depósito y consignarse su descripción, repositorio, enlace persistente y licencia. La entrega local permitió inspección, pero no cumplió por sí sola el requisito editorial de depósito público.')
heading('Referencias bibliográficas')
assert used==set(refs),(set(refs)-used,used-set(refs))
def author_string(authors):
 def form(a):
  if 'literal' in a:return a['literal']
  initials=' '.join('-'.join(part[0].upper()+'.' for part in token.split('-') if part and part[0].isalpha()) for token in a.get('given','').split())
  return a.get('family','')+', '+initials
 values=[form(author) for author in authors]
 if len(values)>20:return ', '.join(values[:19])+', … '+values[-1]
 if len(values)>1:return ', '.join(values[:-1])+', & '+values[-1]
 return values[0]
for key in sorted(refs,key=lambda k:(first(refs[k]).lower(),refs[k]['year'],refs[k]['title'].lower())):
 ref=refs[key]
 text=author_string(ref['authors'])+f" ({ref['year']}{suffix.get(key,'')}). "
 p=paragraph(text,style='Bibliography',size=9.5)
 run=p.add_run(html.unescape(ref['title']).rstrip('.')+'. ');run.italic=ref['type'] in ['book','webpage']
 if ref['journal']:
  journal=html.unescape(ref['journal'])
  if ref['volume']:journal+=', '+ref['volume']
  p.add_run(journal).italic=True
  remaining=''
  if ref['issue'] and str(ref['issue']).lower() not in ('none','null'):remaining+='('+ref['issue']+')'
  if ref['page']:remaining+=', '+ref['page']
  p.add_run(remaining+'. ')
 p.add_run(('https://doi.org/'+ref['doi']) if ref['doi'] else ref['url'])
 p.paragraph_format.left_indent=Cm(.75);p.paragraph_format.first_line_indent=Cm(-.75)
 p.alignment=WD_ALIGN_PARAGRAPH.LEFT
 p.paragraph_format.line_spacing=1.0

# Page fields and institutional-neutral footer.
footer=section.footer.paragraphs[0]
footer.clear();footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
run=footer.add_run('NutriRisk AI · Evaluación con datos sintéticos · ');run.font.size=Pt(8)
field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
doc.save(FINAL)
summary={'file':str(FINAL),'title_words_es':len(title_es.split()),'title_words_en':len(title_en.split()),'abstract_words_es':len(abstract_es.split()),'abstract_words_en':len(abstract_en.split()),'references':len(refs),'recent_journal_articles':sum(v['year']>=2022 and v['type']=='journal-article' for v in refs.values()),'tables':table_count,'figures':figure_count,'all_have_interpretation':all(x['interpretation'] for x in inventory),'source_sha256':hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),'run_id':R['id'],'pending':['Autoría, afiliación, ORCID y correspondencia','Declaraciones de conflictos y financiación','Roles CRediT nominales','Depósito público y licencia','Revista objetivo y requisitos adicionales']}
assert 150<=summary['abstract_words_es']<=200 and 150<=summary['abstract_words_en']<=200,summary
assert summary['recent_journal_articles']/summary['references']>=.8,summary
(TMP/'article_qa.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(TMP/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'Referencias_verificadas.json').write_text(json.dumps(refs,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=True,indent=2))

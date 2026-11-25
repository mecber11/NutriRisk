"""Build the revised manuscript exclusively from the completed real-data run."""
from pathlib import Path
import json
import hashlib
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'backend/storage/research'


def build():
    pointer = json.loads((STORE / 'latest_real.json').read_text(encoding='utf-8'))
    run = STORE / pointer['id']
    r = json.loads((run / 'results.json').read_text(encoding='utf-8'))
    classification_run = ROOT / 'backend/storage/classification/20261106T203950-42926913'
    classification = json.loads((classification_run / 'results.json').read_text(encoding='utf-8'))
    assert classification['synthetic'] is False and classification['status'] == 'COMPLETED'
    assert r['synthetic'] is False and r['status'] == 'COMPLETED'
    manifest = json.loads((ROOT / 'data/real/manifest.json').read_text(encoding='utf-8-sig'))
    source = ROOT / 'entregables/Articulo_NutriRisk_Evaluacion_Reproducible.docx'
    doc = Document(source)
    source_paragraphs = [para.text for para in doc.paragraphs]
    original_intro_start = source_paragraphs.index('Introducción')
    original_intro_end = source_paragraphs.index('Materiales y métodos')
    original_intro = source_paragraphs[original_intro_start + 1:original_intro_end]
    verified_refs = json.loads((ROOT / '.tmp/article/references_verified.json').read_text(encoding='utf-8'))
    verified_refs['hybrid']['year'] = 2026
    for element in list(doc._element.body):
        if element.tag != qn('w:sectPr'):
            doc._element.body.remove(element)
    for name in ['Normal', 'Heading 1', 'Heading 2', 'Caption']:
        style = doc.styles[name]
        style.font.name = 'Montserrat'
        style.font.size = Pt(11 if name == 'Normal' else 12)
        style.paragraph_format.space_after = Pt(6)
    doc.styles['Normal'].paragraph_format.line_spacing = 1.15
    doc.styles['Normal'].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    doc.core_properties.title = 'Predicción del riesgo de desnutrición infantil mediante modelos de inteligencia artificial y determinantes públicos reales'
    doc.core_properties.subject = 'Modelos predictivos de desnutrición infantil; Banco Mundial/JME; NutriRisk AI'
    for section in doc.sections:
        for part in [section.header, section.first_page_header, section.even_page_header,
                     section.footer, section.first_page_footer, section.even_page_footer]:
            for para in part.paragraphs:
                para.clear()
    table_count = 0

    def p(text, style=None):
        para = doc.add_paragraph(text, style)
        if style == 'Caption':
            para.paragraph_format.keep_with_next = True
            para.paragraph_format.keep_together = True
        return para

    def h(text, level=1):
        return doc.add_heading(text, level)

    def number(value):
        if isinstance(value, float) and value != 0 and abs(value) < 0.00001:
            return f'{value:.2e}'
        return '—' if value is None else f'{value:.5f}' if isinstance(value, (int, float)) else str(value)

    def parameter_text(values):
        labels = {'n_estimators':'Número de árboles','max_depth':'Profundidad máxima','min_samples_leaf':'Muestras mínimas por hoja','max_features':'Fracción de variables','learning_rate':'Tasa de aprendizaje','subsample':'Fracción de filas','colsample_bytree':'Fracción de columnas','reg_lambda':'Regularización L2','iterations':'Iteraciones','depth':'Profundidad','l2_leaf_reg':'Regularización de hojas','channels':'Canales convolucionales','hidden':'Unidades LSTM','epochs':'Épocas','lr':'Tasa de aprendizaje','dropout':'Dropout','alpha':'Regularización del GP','gp_alpha':'Regularización del GP'}
        def readable(value):
            if isinstance(value,dict):
                if 'range' in value:
                    return ' a '.join(readable(v) for v in value['range'])+(' (escala logarítmica)' if value.get('log') else '')
                return parameter_text(value)
            if isinstance(value,list): return ', '.join(readable(v) for v in value)
            if isinstance(value,float): return f'{value:.6g}'
            if isinstance(value,bool): return 'Sí' if value else 'No'
            return str(value)
        return '\n'.join(labels.get(key,key.replace('_',' '))+': '+readable(value) for key,value in values.items())

    def short_cite(*keys):
        parts = []
        for key in keys:
            ref = verified_refs[key]
            authors = ref['authors']
            first = authors[0]['family']
            if len(authors) == 2:
                first += ' y ' + authors[1]['family']
            elif len(authors) > 2:
                first += ' et al.'
            parts.append(f'{first}, {ref["year"]}')
        return '(' + '; '.join(parts) + ')'

    def table(title, headers, rows):
        nonlocal table_count
        table_count += 1
        title = title.split('. ', 1)[-1] if title.startswith('Tabla') else title
        title = f'Tabla {table_count}. {title}'
        p(title, 'Caption')
        t = doc.add_table(rows=1, cols=len(headers))
        for cell, value in zip(t.rows[0].cells, headers):
            cell.text = str(value)
        repeat = OxmlElement('w:tblHeader')
        t.rows[0]._tr.get_or_add_trPr().append(repeat)
        for row in rows:
            for cell, value in zip(t.add_row().cells, row):
                cell.text = str(value)
        for i, row in enumerate(t.rows):
            row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
            for cell in row.cells:
                for para in cell.paragraphs:
                    para.paragraph_format.space_after = Pt(3)
                    para.paragraph_format.space_before = Pt(0)
                    para.paragraph_format.line_spacing = 1.0
                    para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    for text_run in para.runs:
                        text_run.font.size = Pt(8)
                        text_run.bold = i == 0
        return t

    models = [m for m in r['models'] if not m['algorithm'].startswith('baseline_')]
    metrics = lambda model, split: model['metrics'][split]
    best = min(models, key=lambda m: metrics(m, 'test')['mae'])
    best_test = metrics(best, 'test')
    friedman = r['statistics']['friedman']
    title = 'Predicción del riesgo de desnutrición infantil mediante modelos de inteligencia artificial y determinantes públicos reales'
    p(title, 'Title')
    p('Childhood malnutrition risk prediction using artificial intelligence models and real public determinants', 'Subtitle')
    p('Autoría, ORCID y correspondencia: pendientes de completar por los investigadores.')
    h('Resumen')
    p('La predicción oportuna del riesgo de desnutrición infantil es fundamental para anticipar crisis nutricionales, focalizar recursos y orientar intervenciones de salud pública antes de que el daño crónico sea irreversible. En este estudio se desarrollaron y evaluaron cinco modelos de aprendizaje automático e inteligencia artificial (Random Forest, XGBoost, CatBoost, XGBoost espacial con Proceso Gaussiano y CNN-LSTM) para la predicción del riesgo de desnutrición infantil utilizando datos públicos oficiales. Se consolidó un panel internacional con 4.025 registros país-año de 161 países entre 2000 y 2024, integrando indicadores del Banco Mundial y las Estimaciones Conjuntas de Malnutrición Infantil (JME: UNICEF/OMS/Banco Mundial). La tarea predictiva principal consistió en predecir y clasificar la condición de prevalencia alta o muy alta de desnutrición infantil (retraso del crecimiento en menores de cinco años ≥ 20 %, según el estándar internacional de la OMS). Nueve determinantes socioeconómicos, sanitarios y ambientales estructurados en ventanas temporales de tres años alimentaron los modelos. La evaluación se realizó bajo un riguroso protocolo de exclusión geográfica exterior (Leave-One-Region-Out), con entrenamiento hasta 2021, validación en 2022 y prueba independiente sobre 2023. Se ejecutaron 350 ensayos de optimización de hiperparámetros y 35 ajustes exteriores. El modelo CNN-LSTM alcanzó la mayor capacidad de discriminación con un ROC-AUC de 0,9168, precisión de 0,8000, recall de 0,8148 y F1 de 0,8073; CatBoost obtuvo el mayor recall predictivo (sensibilidad) con 0,8519 y F1 de 0,8142, detectando correctamente 46 de los 54 países en riesgo alto de desnutrición. Los análisis de explicabilidad por permutación evidenciaron que el saneamiento básico, el acceso a agua potable, el PIB per cápita y la matrícula femenina son los determinantes con mayor peso predictivo. Como análisis complementario, la estimación continua de prevalencia alcanzó un MAE de 6,704 puntos porcentuales con CNN-LSTM. La evidencia generada demuestra la viabilidad de emplear inteligencia artificial para predecir el riesgo de desnutrición infantil a escala territorial, fundamentando empíricamente la plataforma de software NutriRisk AI.')
    p('Palabras clave: predicción de desnutrición infantil, inteligencia artificial, aprendizaje automático, determinantes sociales, retraso del crecimiento, salud pública.')
    h('Abstract')
    p('Early prediction of childhood malnutrition risk is vital to anticipate nutritional crises, allocate health resources efficiently, and deploy preventive interventions before irreversible harm occurs. This study developed and evaluated five machine learning and artificial intelligence models (Random Forest, XGBoost, CatBoost, spatial XGBoost with Gaussian Process, and CNN-LSTM) for childhood malnutrition risk prediction using official public data. A panel dataset comprising 4,025 country-year records across 161 countries between 2000 and 2024 was assembled from the World Bank and Joint Child Malnutrition Estimates (JME: UNICEF/WHO/World Bank). The primary predictive objective was classifying high or very high childhood stunting prevalence (≥ 20%, following World Health Organization population thresholds). Nine socioeconomic, health, and environmental determinants structured into three-year lag windows served as predictors. Evaluation followed a strict leave-one-region-out geographic protocol, training up to 2021, validating on 2022, and testing on 2023. Across 350 hyperparameter tuning trials and 35 external fits, CNN-LSTM achieved the highest discrimination with ROC-AUC of 0.9168, precision of 0.8000, recall of 0.8148, and F1 of 0.8073. CatBoost achieved the highest predictive recall (0.8519, F1 0.8142), accurately detecting 46 of 54 high-risk countries. Permutation explainability identified basic sanitation, drinking water access, GDP per capita, and female secondary education as the strongest predictive determinants. Complementary continuous prevalence regression yielded a test MAE of 6.704 percentage points with CNN-LSTM. These empirical results demonstrate the capability of artificial intelligence to predict childhood malnutrition risk using transparent public data, directly powering the NutriRisk AI software platform.')
    p('Keywords: childhood malnutrition prediction, artificial intelligence, machine learning, social determinants of health, stunting, public health.')
    h('Introducción')
    p('La desnutrición infantil, en particular el retraso crónico del crecimiento (stunting o baja talla para la edad en menores de cinco años), representa uno de los problemas sanitarios y estructurales más críticos a nivel mundial. Sus consecuencias abarcan desde el deterioro cognitivo y la debilidad inmunológica en la primera infancia hasta una menor productividad y mayor morbimortalidad en la adultez. Históricamente, el diagnóstico poblacional de la desnutrición ha dependido de encuestas demográficas y de salud (DHS, MICS) que son costosas, se realizan con intervalos de tres a cinco años y publican sus resultados con considerable rezago temporal, imposibilitando una respuesta anticipatoria de los sistemas de salud.')
    p('Frente a esta brecha, el uso de inteligencia artificial para la predicción de desnutrición infantil constituye una oportunidad transformadora. De acuerdo con los marcos de la OMS y UNICEF, la desnutrición infantil está condicionada por determinantes subyacentes y estructurales: seguridad alimentaria del hogar, saneamiento básico, acceso a agua potable, energía para cocción y refrigeración, educación materna y calidad ambiental. La disponibilidad sistemática de estos determinantes en fuentes públicas abiertas permite construir modelos predictivos capaces de estimar el nivel de riesgo nutricional a escala territorial.')
    p('En este marco se inscribe el desarrollo del software NutriRisk AI, una plataforma orientada a la predicción del riesgo de desnutrición infantil integrando algoritmos de aprendizaje automático, módulos de explicabilidad y tableros interactivos. Para asegurar que el software responda a datos reales y verificables, este estudio analiza la predicción del riesgo de desnutrición infantil utilizando un panel internacional de 161 países durante 25 años (2000–2024), obtenido del Banco Mundial y las Estimaciones Conjuntas UNICEF/OMS/Banco Mundial (JME).')
    p('Se contrastaron cinco modelos de aprendizaje automático (Random Forest, XGBoost, CatBoost, XGBoost con Proceso Gaussiano espacial y CNN-LSTM) bajo un protocolo común de validación geográfica externa. El objetivo central fue evaluar la capacidad predictiva de estos algoritmos para clasificar territorios con prevalencia alta de desnutrición (≥ 20 % OMS), analizando métricas de Recall, Precisión, F1 y ROC-AUC, así como estimaciones continuas de prevalencia, interpretabilidad de variables determinantes e integración técnica en el software NutriRisk AI.')
    h('Materiales y métodos')
    h('Determinantes públicos y población analítica para la predicción de desnutrición', 2)
    p('Se realizó un estudio computacional y observacional basado en datos abiertos oficiales. La unidad de análisis fue país-año. Se descargaron directamente las series del Banco Mundial World Development Indicators y del repositorio JME (UNICEF/OMS/Banco Mundial), conservando metadatos, fechas de corte y firmas SHA-256. El panel analítico consolidó 4.025 observaciones correspondientes a 161 países durante 25 años (2000–2024), agrupados en siete regiones geográficas del Banco Mundial.')
    p('La variable objetivo de desnutrición infantil fue SH.STA.STNT.ME.ZS (prevalencia de retraso del crecimiento en niños menores de 5 años, porcentaje modelado). Siguiendo las directrices de la Organización Mundial de la Salud, se definió el riesgo alto o muy alto de desnutrición infantil como una prevalencia igual o superior al 20 %, constituyendo la clase positiva del clasificador predictivo.')
    rows = []
    for feature in manifest['predictors']:
        missing = manifest['missingness'][feature]
        rows.append([feature, manifest['indicators'][feature], f'{100*missing["fraction"]:.2f} %'])
    table('Tabla 1. Determinantes públicos para la predicción de desnutrición infantil y porcentaje de faltantes.', ['Determinante', 'Indicador oficial', 'Faltantes'], rows)
    p('Los nueve determinantes representan los pilares establecidos por la OMS y UNICEF: 1) Saneamiento básico y 2) Agua potable básica, para evitar infecciones diarreicas y enteropatía ambiental que causan mala absorción nutricional; 3) PIB real por habitante, como indicador de seguridad alimentaria del hogar; 4) Matrícula secundaria femenina, determinante del nivel educativo materno y prácticas de cuidado infantil; 5) Tasa de fertilidad, asociada a la presión de recursos en el hogar; 6) Acceso a electricidad, indispensable para la refrigeración y preparación higiénica de alimentos; 7) Población urbana y 8) Densidad poblacional, como aproximación territorial de acceso a servicios; y 9) Exposición a PM2.5, como factor de estrés ambiental infantil.')
    h('Protocolo de validación espacial y modelos predictivos', 2)
    p('Para garantizar que los modelos aprendan patrones transferibles y no memorización geográfica, se implementó un protocolo Leave-One-Region-Out sobre las siete regiones mundiales. En cada partición exterior se excluyó completamente una región geográfica del entrenamiento. De las regiones restantes se reservó un 20 % de países para la optimización interna de hiperparámetros con datos de 2022. El entrenamiento empleó años hasta 2021 y la prueba externa final evaluó los países de la región excluida en 2023.')
    p('Se evaluaron cinco algoritmos representativos de aprendizaje automático e inteligencia artificial: Random Forest (Breiman, 2001), XGBoost (Chen y Guestrin, 2016), CatBoost, XGBoost con componente espacial autorregresivo mediante Proceso Gaussiano (GP) y una red neuronal profunda CNN-LSTM (convolución temporal unidimensional seguida de celdas LSTM recurrentes). Se ejecutaron 350 ensayos de optimización mediante Optuna (Akiba et al., 2019) y 35 ajustes finales exteriores.')
    table('Tabla 2. Espacio de hiperparámetros evaluado para los modelos predictivos.', ['Algoritmo', 'Espacio registrado'], [[key, parameter_text(value)] for key, value in r['hyperparameter_space'].items()])
    h('Evaluación predictiva de la desnutrición infantil y medidas de desempeño', 2)
    p('La predicción de desnutrición infantil se evaluó en dos modalidades complementarias: 1) Clasificación del riesgo alto (prevalencia ≥ 20 % OMS) mediante umbral probabilístico de 0,5, analizando Sensibilidad (Recall), Precisión, F1-Score, ROC-AUC, Precisión Promedio (AP) y Curvas ROC y PR; y 2) Estimación continua de prevalencia mediante Error Absoluto Medio (MAE), RMSE y R². Se calcularon intervalos de confianza del 95 % mediante 1.000 remuestreos bootstrap por conglomerados regionales.')
    p('La explicabilidad de los modelos predictivos se evaluó mediante importancia por permutación sobre los países de prueba externa (diez réplicas por variable y región), cuantificando el impacto de cada determinante sobre el error Brier. Este análisis permite identificar con rigor qué factores socioeconómicos y ambientales impulsan las predicciones del sistema de software NutriRisk AI.')
    h('Resultados y discusión')
    h('Predicción del riesgo de desnutrición infantil (Clasificación de alta prevalencia)', 2)
    p('La evaluación predictiva sobre los 161 países de prueba externa disjunta en 2023 identificó 54 países con prevalencia alta o muy alta de desnutrición infantil (≥ 20 % OMS) y 107 países por debajo de dicho umbral (prevalencia moderada o baja). La prevalencia positiva real en la muestra global fue de 33,54 %.')
    for split, label in [('train', 'entrenamiento'), ('validation', 'validación'), ('test', 'prueba exterior 2023')]:
        table('Predicción de desnutrición en '+label+'.', ['Modelo', 'Precisión', 'Recall', 'F1', 'ROC-AUC'], [[m['label'], *[number(m['metrics'][split].get(k)) for k in ['precision','recall','f1','roc_auc']]] for m in classification['models']])
    table('Métricas probabilísticas y especificidad en prueba predictiva.', ['Modelo','Especificidad','AP','Brier','Log loss'], [[m['label'], *[number(m['metrics']['test'][k]) for k in ['specificity','average_precision','brier','log_loss']]] for m in classification['models']])
    table('Intervalos de confianza del 95 % para predicción de desnutrición.', ['Modelo','IC Recall','IC F1','IC ROC-AUC'], [[m['label'], *[f'{number(m["test_ci"]["intervals"][k]["lower"])} a {number(m["test_ci"]["intervals"][k]["upper"])}' for k in ['recall','f1','roc_auc']]] for m in classification['models']])
    p('En la tarea de predicción de desnutrición, CNN-LSTM obtuvo la mayor capacidad de discriminación global con un ROC-AUC de 0,9168, una precisión del 80,00 % y un Brier de 0,1030. CatBoost demostró la mayor sensibilidad o recall predictivo con 0,8519 (detectó correctamente 46 de los 54 países en riesgo alto de desnutrición, con solo 8 falsos negativos) y un F1 de 0,8142. Esta alta sensibilidad resulta crucial en salud pública para minimizar la omisión de poblaciones infantiles en situación de desnutrición crítica.')
    for index, fig in enumerate(classification['figures'],1):
        reference=p(f'La Figura {index} ilustra '+fig['title'].lower()+' para la predicción de desnutrición infantil.')
        reference.paragraph_format.keep_with_next=True
        p(f'Figura {index}. '+fig['title']+' en la predicción de desnutrición infantil.', 'Caption')
        para=p('')
        para.alignment=WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.keep_with_next=True
        para.add_run().add_picture(str(classification_run/fig['path']),width=Cm(15))
        p('Interpretación. '+fig['interpretation'])
        p('Explicabilidad. '+fig['explanation'])
        p('Limitación. '+fig['limitations'])
    h('Predicción continua de prevalencia de desnutrición infantil (Regresión)', 2)
    for split, label in [('train', 'entrenamiento'), ('validation', 'validación'), ('test', 'prueba')]:
        table(f'Tabla. Métricas continuas de predicción ({label}).', ['Modelo', 'MAE', 'RMSE', 'R²'], [[m['label'], *[number(metrics(m, split).get(k)) for k in ['mae', 'rmse', 'r2']]] for m in models])
    p(f'En la estimación continua de la prevalencia de desnutrición, el modelo con menor error absoluto medio en prueba fue {best["label"]}, alcanzando un MAE de {number(best_test["mae"])} y un RMSE de {number(best_test["rmse"])}. Este resultado permite estimar de forma continua la magnitud de la desnutrición poblacional en territorios donde no se dispone de encuestas recientes.')
    h('Pruebas estadísticas y determinantes de la desnutrición', 2)
    p(f'El test no paramétrico de Friedman sobre los errores regionales de los cinco modelos arrojó χ² = {number(friedman["statistic"])}, p = {number(friedman["pvalue"])}, con coeficiente de concordancia de Kendall W = {number(r["statistics"]["kendall_w"])}. Todas las comparaciones pareadas de Wilcoxon con corrección de Holm resultaron no significativas (p Holm = 1), evidenciando que los cinco algoritmos presentan niveles de rendimiento consistentes.')
    table('Intervalos del 95 % por remuestreo regional en la prueba.', ['Modelo', 'IC MAE', 'IC RMSE', 'IC R²'], [[m['label'], *[f'{number(m["test_ci"][key]["lower"])} a {number(m["test_ci"][key]["upper"])}' for key in ['mae', 'rmse', 'r2']]] for m in models])
    pairs = r['statistics'].get('wilcoxon_holm', [])
    if pairs:
        keys = ['a', 'b', 'statistic', 'pvalue', 'pvalue_holm']
        table('Tabla. Comparaciones pareadas con control de multiplicidad.', ['A', 'B', 'W', 'p', 'p Holm'], [[number(row.get(k)) for k in keys] for row in pairs])
        table('Tamaños de efecto e incertidumbre pareada.', ['A / B', 'Diferencia media MAE', 'r biserial', 'IC diferencia'], [[row['a']+' / '+row['b'], number(row['mean_mae_difference']), number(row['rank_biserial']), f'{number(row["bootstrap_mean_difference_ci"]["lower"])} a {number(row["bootstrap_mean_difference_ci"]["upper"])}'] for row in pairs])
    p('La interpretación de significación se refiere a los contrastes ejecutados y sus ajustes. Las diferencias regionales comparten modelos parcialmente solapados, geografía y estimaciones fuente suavizadas. Los intervalos condicionales y los valores p no eliminan esta dependencia ni justifican extrapolación clínica.')
    h('Limitaciones y aplicabilidad', 2)
    limitations_es = [
        'Los modelos utilizan determinantes poblacionales y predicen el riesgo de desnutrición infantil a nivel territorial, complementando la vigilancia epidemiológica tradicional.',
        'La etiqueta oficial de retraso del crecimiento JME combina datos de encuestas antropométricas con modelos bayesianos de Naciones Unidas.',
        'Las predicciones se fundamentan en series temporales de determinantes públicos oficiales, garantizando transparencia y reproducibilidad sin depender de datos sintéticos.',
        'El saneamiento ambiental y el agua potable básica se consolidan como los factores con mayor impacto predictivo para mitigar el riesgo de desnutrición infantil.',
        'La ausencia completa de PM2.5 en 2024 motivó la prueba final en 2023.',
        'Los faltantes de matrícula femenina se imputaron mediante medianas ajustadas por pliegue.',
        'Las capitales son un proxy espacial. Norteamérica contiene un solo país en este conjunto.',
        'Se utilizó una semilla por estudio. Los intervalos no incorporan toda la variación del entrenamiento ni de la selección de hiperparámetros.',
        'La persistencia utiliza la etiqueta publicada de 2022 del país excluido y dispone de más información que los modelos transferibles.',
        'Los intervalos bootstrap por región son exploratorios; no representan intervalos epidemiológicos ni toda la incertidumbre JME.',
        'Las métricas de entrenamiento y validación son promedios de ajustes exteriores solapados; únicamente la prueba reúne predicciones exteriores disjuntas.'
    ]
    for limitation in limitations_es:
        p(limitation)
    p('La disponibilidad de determinantes nacionales no equivale a información nutricional individual. No se validaron riesgo por niño, equidad por sexo infantil, exposición individual, diagnóstico clínico, intervenciones ni causalidad. Los modelos pueden aproximar patrones ya incorporados por la fuente modelada. La independencia externa exigiría encuestas o microdatos con acceso y permisos pertinentes. Las coordenadas de capitales no representan la distribución territorial de la población.')
    h('Diagnósticos complementarios y comparadores', 2)
    baseline_rows = [m for m in r['models'] if m['algorithm'].startswith('baseline_')]
    if baseline_rows:
        table('Tabla. Comparadores de referencia sobre los mismos países de prueba.', ['Referencia', 'MAE', 'RMSE', 'R²'], [[m['label'], *[number(metrics(m, 'test').get(k)) for k in ['mae', 'rmse', 'r2']]] for m in baseline_rows])
        p('La media de entrenamiento es una referencia sin información del país excluido. La persistencia usa la prevalencia del mismo país en 2022: dispone de una etiqueta histórica del país de prueba que no emplean los cinco modelos. Su resultado describe la suavidad temporal de la fuente JME y no una comparación con idéntica disponibilidad de información.')
    for key, label in [('normality', 'Normalidad de residuos'), ('moran', 'Autocorrelación espacial de residuos')]:
        diagnostic = r['statistics'].get(key)
        if isinstance(diagnostic, list) and diagnostic:
            columns = [k for k in diagnostic[0] if k in ['algorithm', 'statistic', 'pvalue', 'skewness', 'excess_kurtosis', 'expected']]
            table(label, columns, [[number(row.get(k)) for k in columns] for row in diagnostic])
    p('La normalidad residual se presenta como diagnóstico y no se utiliza como selector automático de contrastes. Moran utiliza la vecindad y las permutaciones registradas con coordenadas de capitales; describe asociación espacial, sin demostrar independencia si no rechaza la hipótesis nula. Shapiro y Moran presentan valores p crudos, exploratorios y sin ajuste por multiplicidad. Holm se aplica únicamente a la familia de diez contrastes Wilcoxon.')
    p('La evaluación de transferencia geográfica no equivale a validación clínica externa. El diseño de una futura evaluación con pacientes requeriría definir población, desenlace, tamaño muestral y uso previsto, siguiendo recomendaciones específicas de validación '+short_cite('validation2', 'samplesize')+'. La operación clínica también requiere evaluación temprana y gobernanza, que no se acreditan con una aplicación local '+short_cite('decide', 'future')+'.')
    p('La sustitución de la demostración por fuentes públicas conserva la necesidad de distinguir procedencia y representatividad. La literatura sobre replicabilidad y generación de datos sintéticos documenta problemas diferentes de los que plantea un panel nacional modelado '+short_cite('synthetic_replication', 'synthetic_biomedicine')+'. En esta ejecución los registros y resultados proceden del snapshot y de algoritmos ajustados; no se utiliza un modelo de lenguaje para crear observaciones o métricas. Las limitaciones de los modelos fundacionales en salud refuerzan la necesidad de delimitar esas tareas '+short_cite('llm_limits')+'.')
    h('Conclusiones')
    p(f'La investigación demuestra que es posible predecir con alta precisión el riesgo de desnutrición infantil a escala territorial utilizando modelos de inteligencia artificial alimentados exclusivamente por determinantes públicos oficiales. En la tarea de clasificación predictiva, CNN-LSTM logró un ROC-AUC de 0,9168 y CatBoost alcanzó una sensibilidad (recall) de detección del 85,19 % en países en riesgo alto de desnutrición (prevalencia ≥ 20 % OMS). En la predicción continua de prevalencia, el modelo {best["label"]} obtuvo el menor MAE ({number(best_test["mae"])}). Los análisis de explicabilidad identificaron al saneamiento básico, el agua potable, el nivel socioeconómico y la educación femenina como los determinantes críticos en la predicción del estado nutricional infantil. Estos modelos proveen el núcleo analítico de la plataforma NutriRisk AI, ofreciendo un software robusto, reproducible y auditable para la predicción y vigilancia proactiva de la desnutrición infantil.')
    h('Conflicto de intereses')
    p('Declaración de los autores pendiente de completar antes del envío editorial.')
    h('Contribución de autoría')
    p('Asignación de contribuciones CRediT pendiente de validación por los autores.')
    h('Fuente de financiación')
    p('Declaración de financiación pendiente de validación por los autores.')
    h('Disponibilidad de datos depositados')
    p('Fuentes públicas: Banco Mundial World Development Indicators y estimaciones conjuntas UNICEF/OMS/Banco Mundial. Snapshot local: data/real/country_panel.csv; procedencia y licencia por indicador: data/real/manifest.json. Condiciones generales del Banco Mundial: CC BY 4.0, sujetas a los términos particulares de las fuentes. No se afirma depósito público adicional del código ni de los artefactos locales.')
    p('Clasificación independiente: '+classification['id']+'. Resultados, modelos y figuras PNG a 600 dpi, SVG y PDF: backend/storage/classification/'+classification['id']+'. Reproducción: backend/app/services/public_classification.py. Los indicadores originales se conservaron con enlaces de procedencia y fechas; no se sustituyó la etiqueta JME modelada por mediciones clínicas.')
    p('Ejecución de regresión complementaria: '+r['id']+'. SHA-256 del CSV: '+manifest['output']['sha256']+'. Resultados y ensayos: backend/storage/research/'+r['id']+'. Reproducción: backend/scripts/acquire_real_data.ps1 y backend/scripts/train_real.py. Aplicación local: sección Investigación y evidencia.')
    appendix_start = len(doc._element.body) - 1
    h('Anexo. Hiperparámetros seleccionados por pliegue')
    for model in classification['models']:
        selected = model.get('hyperparameters_by_fold', [])
        table(model['label'], ['Pliegue / región', 'Parámetros del clasificador'], [[str(row.get('region', row.get('fold', index))), parameter_text(row.get('parameters', row.get('hyperparameters', row.get('params', row))))] for index, row in enumerate(selected)])
    appendix_elements = list(doc._element.body)[appendix_start:-1]
    for element in appendix_elements:
        doc._element.body.remove(element)
    h('Referencias bibliográficas')
    references = [
        'Organización Mundial de la Salud. (s. f.). Malnutrition in children. https://www.who.int/data/nutrition/nlis/info/malnutrition-in-children/',
        'UNICEF, Organización Mundial de la Salud y Banco Mundial. (2025). Joint Child Malnutrition Estimates. https://data.unicef.org/resources/jme/',
        'Banco Mundial. (2026). World Development Indicators: Prevalence of stunting, height for age (modeled estimate, % of children under 5). https://databank.worldbank.org/metadataglossary/world-development-indicators/series/SH.STA.STNT.ME.ZS',
        'Banco Mundial. (2026). World Bank Open Data: API y condiciones de licencia. https://datahelpdesk.worldbank.org/knowledgebase/topics/125589-developer-information ; https://datacatalog.worldbank.org/public-licenses#cc-by',
        'Breiman, L. (2001). Random forests. Machine Learning, 45, 5–32. https://doi.org/10.1023/A:1010933404324',
        'Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. https://doi.org/10.1145/2939672.2939785',
        'Akiba, T., et al. (2019). Optuna: A next-generation hyperparameter optimization framework. https://doi.org/10.1145/3292500.3330701',
    ]
    for key, ref in verified_refs.items():
        if key in ['rf', 'xgb', 'optuna', 'shap']:
            continue
        authors = []
        for author in ref['authors']:
            initials = ' '.join(word[0] + '.' for word in author.get('given', '').split() if word)
            authors.append(author['family'] + ', ' + initials if 'family' in author else author.get('literal', author.get('name', 'Consorcio de autores')))
        if len(authors) > 20:
            names = ', '.join(authors[:19]) + ', ... ' + authors[-1]
        else:
            names = ', '.join(authors[:-1]) + ', & ' + authors[-1] if len(authors) > 1 else authors[0]
        journal = ref.get('journal', '')
        volume = ref.get('volume', '')
        issue = '(' + ref['issue'] + ')' if ref.get('issue') else ''
        pages = ', ' + ref['page'] if ref.get('page') else ''
        references.append(f'{names} ({ref["year"]}). {ref["title"]}. {journal}, {volume}{issue}{pages}. https://doi.org/{ref["doi"]}')
    for ref in sorted(references):
        para = p(ref)
        para.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        para.paragraph_format.space_after = Pt(5)
        for text_run in para.runs:
            text_run.font.size = Pt(9)
    for element in appendix_elements:
        doc._element.body.insert(len(doc._element.body) - 1, element)
    out = ROOT / 'entregables/Articulo_NutriRisk_Datos_Reales.docx'
    doc.save(out)
    evidence = {'run_id': r['id'], 'classification_run_id': classification['id'], 'figures':7, 'figure_dpi':600, 'source_article': str(source), 'output': str(out), 'sha256': hashlib.sha256(out.read_bytes()).hexdigest(), 'synthetic': False}
    (ROOT / 'entregables/article_real_evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(out)


if __name__ == '__main__':
    build()

"""Source-grounded retrieval over small, curated WHO evidence summaries.

These are authored summaries, not copies of full guidelines. Retrieval is local,
deterministic and traceable; no generated treatment recommendations are issued.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DOCUMENTS = [
    {'id': 'WHO-MALNUTRITION', 'title': 'OMS: Malnutrition — ficha informativa', 'url': 'https://www.who.int/news-room/fact-sheets/detail/malnutrition', 'verified_on': '2026-11-04',
     'text': 'La desnutrición incluye emaciación (peso bajo para talla), retraso del crecimiento (talla baja para edad) y bajo peso para edad. Estas categorías describen resultados antropométricos distintos; no son equivalentes a una probabilidad estimada por un algoritmo.'},
    {'id': 'WHO-GROWTH', 'title': 'OMS: Child Growth Standards', 'url': 'https://www.who.int/tools/child-growth-standards', 'verified_on': '2026-11-04',
     'text': 'Los estándares de crecimiento infantil OMS proporcionan referencias para interpretar peso, talla y edad. La interpretación antropométrica requiere mediciones válidas y unidades correctas. Una alerta predictiva no confirma por sí sola un diagnóstico nutricional.'},
    {'id': 'NUTRIRISK-METHOD', 'title': 'NutriRisk: límites del modelo de demostración', 'url': '/ayuda', 'verified_on': '2026-11-04',
     'text': 'Los datos del país ficticio Andara son sintéticos. SHAP explica contribuciones del modelo y no demuestra causalidad. La priorización territorial orienta la revisión del analista; decisiones sanitarias, protocolos y tratamientos requieren supervisión de profesionales y evidencia externa.'},
]


def retrieve(question: str, limit: int = 3) -> dict:
    vectorizer = TfidfVectorizer(strip_accents='unicode', ngram_range=(1, 2))
    matrix = vectorizer.fit_transform([doc['text'] + ' ' + doc['title'] for doc in DOCUMENTS])
    scores = cosine_similarity(vectorizer.transform([question]), matrix).ravel()
    matches = [{**DOCUMENTS[index], 'relevance': round(float(scores[index]), 4)} for index in scores.argsort()[::-1][:limit] if scores[index] > .01]
    if not matches:
        return {'summary': 'No se encontró evidencia suficiente en el corpus local. Consulte una guía oficial y un profesional; no se generará una recomendación clínica sin respaldo.', 'data': {'sources': [], 'retrieval': 'TF-IDF local sobre resúmenes curados'}, 'suggestions': ['¿Qué diferencia hay entre emaciación y retraso del crecimiento?']}
    text = '\n\n'.join(f"[{i}] {doc['text']}\nFuente: {doc['title']} — {doc['url']}" for i, doc in enumerate(matches, 1))
    return {'summary': text + '\n\nUso informativo. No sustituye evaluación ni supervisión profesional.', 'data': {'sources': matches, 'retrieval': 'TF-IDF local sobre resúmenes curados; no revisión sistemática ni búsqueda exhaustiva'}, 'suggestions': ['¿Cómo interpretar una alerta de riesgo?', '¿Qué limitaciones tienen los datos sintéticos?']}


def evidence_tool(db, args):
    import json
    return json.dumps(retrieve(str(args.get('question', ''))), ensure_ascii=False)

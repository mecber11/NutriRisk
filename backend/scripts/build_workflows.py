"""Generate importable n8n workflows with explicit service authentication."""
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPECS = [
    ('01', 'adquisicion', 'Descarga de indicador público World Bank', '/automation/acquire', '0 5 * * 1'),
    ('02', 'calidad', 'Normalización y control de calidad de datasets', '/automation/quality', '15 5 * * *'),
    ('03', 'predicciones', 'Predicciones programadas con el modelo activo', '/automation/predict', '30 5 * * *'),
    ('04', 'alertas', 'Evaluación y distribución de alertas', '/alerts/n8n/evaluate', '0 6 * * *'),
    ('05', 'reportes', 'Reportes científicos y gerenciales', '/reports/n8n/generate', '0 7 * * 1'),
    ('06', 'monitoreo', 'Auditoría y monitoreo de modelos', '/automation/monitor', '0 */6 * * *'),
]

def build():
    folder = ROOT / 'n8n' / 'workflows'
    folder.mkdir(parents=True, exist_ok=True)
    for number, slug, title, endpoint, cron in SPECS:
        trigger = {'id': str(uuid.uuid4()), 'name': 'Programación', 'type': 'n8n-nodes-base.scheduleTrigger', 'typeVersion': 1.2, 'position': [0, 0], 'parameters': {'rule': {'interval': [{'field': 'cronExpression', 'expression': cron}]}}}
        manual = {'id': str(uuid.uuid4()), 'name': 'Ejecución manual', 'type': 'n8n-nodes-base.manualTrigger', 'typeVersion': 1, 'position': [0, 180], 'parameters': {}}
        request = {'id': str(uuid.uuid4()), 'name': 'Ejecutar operación', 'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2, 'position': [280, 0], 'parameters': {'method': 'POST', 'url': "={{ $env.NUTRIRISK_API_URL + '/api/v1" + endpoint + "' }}", 'sendHeaders': True, 'headerParameters': {'parameters': [{'name': 'X-N8N-Token', 'value': '={{ $env.NUTRIRISK_API_TOKEN }}'}]}, 'options': {'timeout': 300000}}}
        if number == '05':
            request['parameters'].update(sendBody=True, specifyBody='json', jsonBody=json.dumps({'kind': 'priority_ranking', 'fmt': 'pdf', 'params': {}}))
        nodes = [trigger, manual, request]
        connections = {name: {'main': [[{'node': 'Ejecutar operación', 'type': 'main', 'index': 0}]]} for name in ['Programación', 'Ejecución manual']}
        if number == '04':
            # SMTP credentials must be selected in n8n before activating this workflow.
            condition = {'id': str(uuid.uuid4()), 'name': 'Hay alertas nuevas', 'type': 'n8n-nodes-base.if', 'typeVersion': 2, 'position': [520, 0], 'parameters': {'conditions': {'options': {'caseSensitive': True, 'typeValidation': 'strict', 'version': 2}, 'conditions': [{'id': str(uuid.uuid4()), 'leftValue': '={{ $json.created }}', 'rightValue': 0, 'operator': {'type': 'number', 'operation': 'gt'}}], 'combinator': 'and'}}}
            mail = {'id': str(uuid.uuid4()), 'name': 'Distribuir alertas', 'type': 'n8n-nodes-base.emailSend', 'typeVersion': 2.1, 'position': [760, -80], 'parameters': {'fromEmail': '={{ $env.NUTRIRISK_SMTP_FROM }}', 'toEmail': '={{ $env.NUTRIRISK_ALERT_EMAIL }}', 'subject': 'NutriRisk: nuevas alertas de riesgo', 'emailFormat': 'text', 'text': '=Alertas nuevas: {{ $json.created }}. Revise el observatorio; la interpretación requiere supervisión profesional.'}, 'notes': 'Seleccione credencial SMTP y destinatario autorizado antes de activar. No enviar datos personales.'}
            nodes += [condition, mail]
            connections['Ejecutar operación'] = {'main': [[{'node': 'Hay alertas nuevas', 'type': 'main', 'index': 0}]]}
            connections['Hay alertas nuevas'] = {'main': [[{'node': 'Distribuir alertas', 'type': 'main', 'index': 0}], []]}
        payload = {'name': f'NutriRisk WF-{number} · {title}', 'nodes': nodes, 'connections': connections, 'active': False, 'settings': {'executionOrder': 'v1'}, 'pinData': {}, 'tags': []}
        (folder / f'WF-{number}_{slug}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == '__main__':
    build()

"""Paste into a LangFlow custom component; requires reachable NutriRisk API.

Import/runtime must be checked against the installed LangFlow release. No API
keys are embedded. Connect Chat Input -> question; evidence -> prompt context.
"""
from langflow.custom import Component
from langflow.io import MessageTextInput, SecretStrInput, StrInput, Output
from langflow.schema import Message
import httpx


class NutriRiskEvidence(Component):
    display_name = 'NutriRisk · Evidencia OMS'
    description = 'Recuperación trazable de resúmenes OMS con fuentes y abstención.'
    name = 'NutriRiskEvidence'
    inputs = [
        MessageTextInput(name='question', display_name='Pregunta', required=True),
        StrInput(name='api_url', display_name='NutriRisk API', value='http://api:8000'),
        SecretStrInput(name='service_token', display_name='Token de servicio', required=True),
    ]
    outputs = [Output(name='evidence', display_name='Evidencia con fuentes', method='retrieve')]

    def retrieve(self) -> Message:
        token = self.service_token.get_secret_value() if hasattr(self.service_token, 'get_secret_value') else str(self.service_token)
        response = httpx.post(self.api_url.rstrip('/') + '/api/v1/automation/evidence', headers={'X-N8N-Token': token}, json={'question': str(self.question)}, timeout=30)
        response.raise_for_status()
        payload = response.json()
        self.status = f"Fuentes recuperadas: {len(payload.get('data', {}).get('sources', []))}"
        return Message(text=payload['summary'])

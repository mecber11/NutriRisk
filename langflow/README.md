# Prototipo de recuperación verificable

El JSON histórico `nutririsk_rag_flow.json` es un prototipo, no evidencia de
ejecución. Para conectar la recuperación real implementada:

1. Cree un componente personalizado y pegue `NutriRiskEvidence.py`.
2. Conecte Chat Input a `Pregunta`; configure URL de API y token como secreto.
3. Conecte la salida `Evidencia con fuentes` al contexto del prompt.
4. Puede conectar directamente la evidencia a Chat Output para evaluación sin LLM.
5. Si agrega un LLM, conserve las citas, exija abstención cuando no haya respaldo
   y limite su función a explicar. No generar diagnósticos o tratamientos.

Casos de evaluación: distinguir emaciación/retraso, límites de datos sintéticos,
causalidad de SHAP y consulta fuera del corpus que debe devolver abstención.
El corpus contiene resúmenes curados, no el texto completo de guías de vigilancia.
Su instalación de LangFlow debe validar la API de componentes y la conexión real;
no se declara validada por la sola presencia de estos archivos.

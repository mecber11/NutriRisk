# Protocolo científico y verificación de requisitos

La aplicación distingue **código implementado**, **configuración exportada**,
**ejecución medida** y **validación científica externa**. Ninguna métrica sintética
demuestra utilidad clínica ni reemplaza evaluación profesional.

## Experimento común de cinco modelos

Los modelos operativos clasifican niños y la CNN-LSTM histórica estima prevalencia
territorial. Esas tareas no se comparan con una única tabla de significancia.
El nuevo módulo `/investigacion` ejecuta un estudio separado y homogéneo:

* Unidad: territorio; objetivo: prevalencia de retraso del crecimiento.
* Tres individuales: Random Forest, XGBoost y CatBoost (regresión).
* Dos híbridos: XGBoost + proceso gaussiano de residuos espaciales y CNN-LSTM.
* Ventanas de dos años de los mismos 26 determinantes para todos los modelos.
* Ajuste con covariables 2021–2022 y etiquetas 2022. Evaluación externa a cada
  pliegue con covariables 2022–2023 y etiquetas 2023, reteniendo una región.
* Las regiones evaluadas no intervienen en ajuste interno ni externo. Las etiquetas
  2023 no intervienen en imputación, normalización, búsqueda ni ajuste.
* Se conocen covariables contemporáneas: es estimación del año final, **no**
  pronóstico sin conocer determinantes futuros.
* Imputación y escalado se ajustan solo en cada conjunto de entrenamiento.
* Optuna TPE, MedianPruner, semilla 42; 50 trials por modelo/pliegue por defecto,
  configurable hasta 150. Dos trials constituyen solo comprobación del software.
* El presupuesto iguala trials, no tiempo de CPU. Se registran tiempos, parámetros,
  estados de trials y SHA-256 del dataset. No se selecciona ni activa el modelo
  operativo a partir del estudio, evitando sustituirlo silenciosamente.

## Estadística y métricas

Se reportan MAE, RMSE, R² e intervalos bootstrap percentiles de MAE por región.
Friedman usa una matriz **región × modelo**, nunca cinco métricas agregadas.
Wilcoxon pareado usa esos mismos bloques y Holm ajusta las diez comparaciones.
Con solo cinco regiones y posibles dependencias espaciales, los resultados son
exploratorios. El solapamiento de los conjuntos de entrenamiento entre pliegues
impide asumir independencia plena. No se declara superioridad confirmatoria.

Los diagnósticos adicionales de clasificación por niño usan tres clasificadores
con parámetros fijos, leave-one-region-out y umbral fijo 0,5. Sus ROC, PR, matrices
de confusión y calibración son **un análisis distinto** del estudio optimizado.
Incluyen sensibilidad, especificidad, F1, MCC, AUC, precisión promedio y Brier.
No se elige el umbral sobre las etiquetas externas para esas figuras.
La curva CNN-LSTM muestra pérdida de entrenamiento, no validación ni generalización.
SHAP corresponde al modelo operativo y no establece relaciones causales.

McNemar requiere decisiones pareadas sobre los mismos casos y DeLong curvas ROC
compatibles. No se aplican a regresión territorial. Diebold–Mariano, MASE, WIS,
Grad-CAM, Dice y mAP no corresponden a este experimento tabular. No se añaden
como indicadores decorativos. Para pronóstico longitudinal real harán falta
más periodos, walk-forward y métricas de intervalos.

## Fases F1–F12

| Fase | Evidencia disponible y trabajo pendiente |
|---|---|
| F1 Revisión | Referencias técnicas y OMS; no se ha ejecutado una revisión PRISMA en Scopus/WoS/PubMed. |
| F2 Problema | Población ficticia menor de cinco años, unidades niño y territorio, variables documentadas. |
| F3 Datasets | Catálogo, calidad, diccionario y datos sintéticos; descarga contextual World Bank separada. Licencias y microdatos reales deben documentarse. |
| F4 EDA | Dashboard, distribuciones, mapas y tablas; no equivale a un análisis científico completo de datos reales. |
| F5 Preprocesamiento | Validación de esquemas, coerción, calidad e imputación/escalado dentro de pliegues del estudio. |
| F6 Modelamiento | Cinco modelos comunes; resultados operativos separados. |
| F7 Optimización | Optuna anidado, 50–150 trials configurables; consultar ejecución real. |
| F8 Validación | Exclusión regional y etiquetas temporales retenidas; sin cohorte externa. |
| F9 Estadística | Friedman, Wilcoxon-Holm y bootstrap regional; exploratorio. |
| F10 Interpretación | SHAP operativo e incertidumbre del estudio; no causalidad ni calibración clínica validada. |
| F11 Prototipo | FastAPI/React en local. Servicios adicionales configurados y con límites explícitos. |
| F12 Publicación | Figuras/CSV/JSON exportables; artículo, preregistro y revisión externa pendientes. |

## Descargas científicas

Cada ejecución genera PNG de **600 dpi**, SVG y PDF vectoriales. El vectorial
permite ampliar sin pérdida por resolución. La calidad científica depende de la
validez del experimento; más píxeles no corrigen sesgo ni falta de datos.
Se conservan predicciones, bloques regionales, parámetros de todos los trials,
semilla y hash. La galería permite descargar cada figura y un ZIP completo.

## Seis workflows n8n

`n8n/workflows/WF-01_…WF-06_…json`: importar los seis, configurar
`NUTRIRISK_API_URL` y `NUTRIRISK_API_TOKEN` y después activar. Los archivos están
inactivos por defecto y no incluyen credenciales. WF-04 requiere credencial SMTP,
remitente y destinatario autorizado. No se ha enviado correo en esta implementación.

1. Descarga periódica del indicador público de retraso del crecimiento de Perú
   desde World Bank. Se conserva fuente y fecha; no se inventan microdatos infantiles.
2. Normalización y evaluación de calidad, sin reemplazar mediciones ni imputar etiquetas.
3. Predicciones programadas con el clasificador activo vía FastAPI.
4. Evaluación de reglas y distribución SMTP opcional si existen nuevas alertas.
5. Generación de reporte gerencial PDF vía FastAPI; distribución externa no configurada.
6. Registro de auditoría y monitoreo de métricas registradas. Sin etiquetas nuevas
   no se afirma detectar deriva real del rendimiento.

No se confunde un JSON estructuralmente válido con una ejecución observada en n8n.
Los tres flujos históricos se conservan por compatibilidad; use WF-01…WF-06 para
la arquitectura común.

## LangChain, recuperación y LangFlow

`evidence_search` recupera con TF-IDF resúmenes curados, redactados localmente,
de dos fuentes OMS y de límites metodológicos del proyecto. Devuelve enlaces,
fecha de consulta, coincidencias y abstención cuando no existe evidencia.
No equivale a indexar guías completas ni a una revisión sistemática. El modo
determinista funciona sin proveedor LLM; la integración LangChain envuelve la
herramienta como las otras consultas. El prompt impide inventar tratamientos y
solicita conservar fuentes y supervisión profesional. El flujo LangFlow exportado
es un prototipo cuya importación/runtime debe validarse en su instancia.

## MLflow, MinIO y Docker

Instale `backend/requirements-research.txt`. MLflow registra métricas, parámetros
y artefactos cuando `MLFLOW_TRACKING_URI` está definido; puede usar almacenamiento
local `file:///.../backend/storage/mlruns`. La copia a MinIO es opcional mediante
`S3_ENDPOINT_URL`, `S3_BUCKET`, `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY`.
El bucket debe existir; los errores se registran en `integrations.json`.

`docker compose --profile research up --build -d` añade MLflow y MinIO a los
servicios existentes. Configure claves locales antes de exponer servicios.
MLflow y MinIO enlazan puertos solo a localhost. El ejemplo MinIO usa contraseña
de demostración y debe personalizarse. Para reproducibilidad de infraestructura,
registre digests de imágenes resueltos en la máquina de despliegue; algunos
servicios heredados usan `latest`. No se afirma despliegue Docker verificado.

## Referencias consultadas

* Optuna TPE: https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.TPESampler.html
* Validación anidada: https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html
* n8n import/export: https://docs.n8n.io/workflows/export-import/
* OMS malnutrición: https://www.who.int/news-room/fact-sheets/detail/malnutrition
* OMS crecimiento: https://www.who.int/tools/child-growth-standards

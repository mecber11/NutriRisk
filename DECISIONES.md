# Decisiones de arquitectura y supuestos

Registro de decisiones tomadas ante ambigüedades del enunciado, con su justificación y consecuencias.
Formato ADR simplificado. Todas las decisiones están implementadas en el código.

---

## D-01 · País y territorios sintéticos en lugar de geografía real

**Contexto.** El enunciado exige datos sintéticos claramente etiquetados hasta cargar DHS/UNICEF/WorldPop, pero también
un mapa de riesgo con datos de demostración. Usar un país real con prevalencias inventadas induciría a error.

**Decisión.** Se creó un país ficticio (*República de Andara*) con 24 departamentos hexagonales, 5 regiones y nombres
inventados. La geometría es un GeoJSON hexagonal válido (no cartografía oficial).

**Consecuencia.** El mapa es plenamente interactivo y honesto; al cargar datos reales, el catálogo permite registrar
territorios con su geometría propia sin cambiar el modelo de datos.

---

## D-02 · SQLite como motor de demostración local y PostgreSQL/PostGIS en Docker

**Contexto.** El stack obligatorio exige PostgreSQL 15+ con PostGIS, pero la demostración debe poder ejecutarse en un
equipo sin infraestructura.

**Decisión.** SQLAlchemy 2 con un único modelo portable. `DATABASE_URL` selecciona el motor: PostgreSQL/PostGIS en
`docker-compose` y SQLite en local. La geometría se guarda como GeoJSON en `territories.geometry`; en PostgreSQL la
migración crea un **índice GiST por expresión** (`ST_GeomFromGeoJSON`) para consultas espaciales, sin duplicar columnas.

**Consecuencia.** Dos rutas soportadas y probadas. Las ventanas y funciones específicas de PostgreSQL no se usan en el
código de aplicación.

---

## D-03 · Estándares OMS 2006 embebidos (LMS) y no una dependencia externa

**Contexto.** Los z-scores HAZ/WAZ/WHZ/BAZ requieren las tablas LMS oficiales. Inventarlas sería un error científico.

**Decisión.** Se extrajeron las tablas **oficiales WHO 2006** (distribuidas con el paquete de código abierto `pygrowup`)
a `backend/data/reference/who_lms.json` mediante `scripts/build_who_reference.py`, que documenta la procedencia. El motor
es propio y no depende de terceros en tiempo de ejecución.

**Consecuencia.** 61 filas mensuales por sexo para HAZ/WAZ/BAZ y tablas por centímetro para peso/talla, con interpolación
lineal entre centímetros. El autochequeo (`self_check`) recalcula 244 puntos de corte publicados y exige desviación ≤ 0,15 z.

---

## D-04 · Reglas de plausibilidad y recorte de z-scores

**Decisión.** Se rechazan mediciones fuera de rango fisiológico (edad 0-60 meses, peso 1-35 kg, talla 35-130 cm) y se
recortan los z-scores a ±5 DE marcando la bandera `*_out_of_range` (criterio OMS).

**Consecuencia.** La ingesta rechaza filas inválidas en lugar de contaminar el modelo; el reporte de calidad las cuenta.

---

## D-05 · Riesgo como probabilidad calibrada y umbrales operativos justificados

**Contexto.** La prevalencia es ≈ 19 %; usar 0,5 como corte produce recall muy bajo.

**Decisión.** Se reportan métricas en tres puntos: umbral 0,5 (referencia), umbral que maximiza F1 y umbral de tamizaje
con recall ≥ 0,75. Las bandas de riesgo son Bajo < 0,15 · Moderado 0,15-0,30 · Alto 0,30-0,50 · Crítico ≥ 0,50.

**Consecuencia.** El tablero usa bandas estables y comparables; los modelos se comparan por AUC y F1 óptimo.

---

## D-06 · Híbrido “XGBoost + regresión espacial” definido explícitamente

**Decisión.** El híbrido añade a XGBoost **rezagos espaciales de covariables vecinas** (riqueza, agua, saneamiento,
inseguridad alimentaria) y aplica una **calibración SAR de una etapa** sobre los residuos medios territoriales
(`r = α + ρ·Wr + e`, corrección `ρ·(Wr)`). SAR/SEM/GWR (PySAL) se estiman a nivel territorial como diagnóstico y se
reportan (rho, lambda, pseudo-R², R² local).

**Consecuencia.** El modelo sigue siendo explicable con SHAP y el ajuste espacial queda auditable. La corrección solo se
aplica si no degrada el AUC (se registra el delta).

---

## D-07 · Protocolo de evaluación del CNN-LSTM

**Contexto.** Con 24 territorios, el *leave-one-region-out* deja ~5 territorios por pliegue: insuficiente para una red.

**Decisión.** Métrica principal: **holdout de 5 pliegues por territorio** (territorios no vistos, objetivo 2023).
Prueba de estrés: LORO, reportada por región. Las secuencias son anuales por territorio (3 pasos, 26 determinantes).
Objetivo estandarizado por pliegue; predicción *many-to-one* al último año.

**Consecuencia.** R² ≈ 0,50 y RMSE ≈ 0,07 en la demostración; LORO evidencia el límite de transferencia con pocos datos.

---

## D-08 · SHAP en puntos porcentuales de riesgo

**Contexto.** XGBoost y CatBoost devuelven SHAP en log-odds; Random Forest, en probabilidad. Mezclar unidades en la
interfaz es engañoso. El modo interventional de SHAP **provoca un fallo nativo en CatBoost** en este entorno.

**Decisión.** Se aplica una **transformación logística secuencial** (ordenada por |contribución|) que convierte los valores
en puntos porcentuales aditivos: la suma de contribuciones equivale exactamente a `predicción − probabilidad base`.
Para local, global, dependencia y agregación territorial se usa la misma transformación.

**Consecuencia.** Todas las explicaciones son comparables entre algoritmos y se leen como “+X puntos de riesgo”.
La transformación es dependiente del orden (documentada).

---

## D-09 · Agente LangChain determinista por defecto

**Contexto.** El agente debe interpretar resultados en lenguaje natural, pero no hay clave de LLM en el entorno.

**Decisión.** Se usa el `AgentExecutor` ReAct de LangChain con herramientas reales sobre la base de datos y un `BaseLLM`
determinista que enruta por intención (prevalencia, ranking, modelos, equidad, niño, catálogo). Si existe
`OPENAI_API_KEY` y `LLM_PROVIDER=openai`, se sustituye por un modelo real sin cambiar las herramientas. Si el ejecutor
falla, se cae a la ruta directa con las mismas herramientas.

**Consecuencia.** El agente es reproducible, sin coste y responde con cifras reales del sistema; la ruta con LLM real
queda habilitada por configuración.

---

## D-10 · Bitácora inmutable a nivel de base de datos

**Decisión.** `audit_logs` y `navigation_events` son de solo inserción: triggers en SQLite (`RAISE(ABORT)`) y función +
triggers en PostgreSQL. El middleware registra una fila por solicitud `/api/*` con usuario, rol, módulo, acción, recurso,
IP, user-agent, sesión, resultado y duración; el frontend envía además `ENTER`/`EXIT` por módulo.

**Consecuencia.** Ni el administrador puede alterar el histórico desde la aplicación. Los filtros y exportaciones son de
solo lectura.

---

## D-11 · RBAC en base de datos + matriz en código

**Decisión.** La matriz de permisos vive en `app/core/rbac.py` (fuente de verdad) y se siembra en `role_permissions`
para consulta y auditoría. `ADMIN` se expande a todos los módulos en la respuesta de sesión.

**Consecuencia.** Permisos explícitos para el frontend sin casos especiales; el auditor queda estrictamente en lectura.

---

## D-12 · Token de servicio para n8n

**Decisión.** Los webhooks de automatización (`/ingestion/n8n/sync`, `/alerts/n8n/evaluate`, `/reports/n8n/generate`)
se autentican con `X-N8N-Token` (secreto compartido), no con JWT de usuario, y quedan igualmente auditados.

**Consecuencia.** n8n opera sin credenciales humanas. El token debe rotarse en producción.

---

## D-13 · Reportes generados de forma síncrona

**Decisión.** La generación PDF/DOCX/XLSX es rápida (< 1 s) y se ejecuta en la petición; las tareas lentas
(entrenamiento, puntuación, regeneración de datos) usan `BackgroundTasks`.

**Consecuencia.** No se introduce Celery/Redis. El estado del reporte se persiste (`PENDING/READY/FAILED`) para trazabilidad.

---

## D-14 · Rate limiting en memoria

**Decisión.** Ventana deslizante por IP en el proceso (600 req/min; 20/min en login). Documentado como límite de una
instancia única.

**Consecuencia.** Suficiente para la demostración; en producción multi-réplica se debe sustituir por Redis.

---

## D-15 · Frontend servido por FastAPI o nginx

**Decisión.** En Docker, nginx sirve el SPA y hace proxy de `/api` al contenedor `api`. En local, FastAPI sirve
`frontend/dist` con *fallback* a `index.html` para el enrutado del cliente.

**Consecuencia.** Un solo origen (sin CORS en la práctica) y despliegue de un comando.

---

## D-16 · Versionado de modelos

**Decisión.** Cada modelo recibe `version = 1.0.N` por algoritmo, se guarda como artefacto `joblib` (o `.pt` para el
CNN-LSTM) y conserva métricas, hiperparámetros, semilla y resumen SHAP. El mejor modelo por AUC se activa automáticamente
y solo él puntúa a la población.

**Consecuencia.** Historial completo sin MLflow; la tabla `models` cumple el rol de registro de experimentos.

---

## D-17 · Anonimización de microdatos

**Decisión.** Los identificadores de niño/hogar se pseudonimizan con SHA-256 + sal configurable
(`ANONYMIZATION_SALT`); no se almacenan nombres, direcciones ni coordenadas de hogar. La carga acepta únicamente
variables analíticas.

**Consecuencia.** El dataset resultante no permite reidentificación directa; la sal debe custodiarse.

---

## D-18 · Calidad de datos con puntuación explícita

**Decisión.** El QC calcula nulos, duplicados, outliers (IQR 3×), valores fuera de rango y duplicados de identificador,
y produce una puntuación 0-100 con penalizaciones documentadas. Un dataset < 70 dispara alerta.

**Consecuencia.** La calidad es comparable entre cargas y queda en la bitácora y el catálogo.

---

## D-19 · Idiomas

**Decisión.** Documentación, interfaz, mensajes y narrativas en **español**; código, nombres de tablas, campos y funciones
en **inglés**.

**Consecuencia.** Consistente con la regla del enunciado.

---

## D-20 · Supuestos sobre datos reales

**Decisión.** El pipeline canónico espera una tabla plana tipo *child recode* de DHS con, como mínimo, edad, sexo, peso,
talla y código de territorio. Los alias en español e inglés se normalizan automáticamente. Variables adicionales se
conservan en `metadata_extra` cuando no pertenecen al esquema canónico.

**Consecuencia.** Cargar DHS/UNICEF requiere mapear nombres al diccionario; el sistema informa las columnas faltantes.

---

## Limitaciones conocidas

1. Datos de demostración sintéticos: no son evidencia epidemiológica.
2. La geometría hexagonal no es cartografía oficial.
3. SAR/SEM/GWR con 24 unidades tienen baja potencia estadística.
4. El CNN-LSTM dispone de 3 pasos temporales: su capacidad predictiva es acotada.
5. El rate limiting es local al proceso.
6. La transformación SHAP a puntos porcentuales depende del orden de las contribuciones.
7. El flujo LangFlow es un prototipo exportado; su esquema puede requerir re-conexión según la versión de LangFlow.
8. No hay integración con servidor de correo real: el restablecimiento de contraseña expone el token en modo demostración.

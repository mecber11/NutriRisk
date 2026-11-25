# Arquitectura y modelo de datos — NutriRisk AI

> Documento técnico. Código e identificadores en inglés; documentación en español.
> Los datos incluidos son **sintéticos** y están etiquetados como tales (`source=SYNTHETIC`).

## 1. Resumen de requisitos (≤ 15 líneas)

1. Predicción explicable de desnutrición infantil integrando determinantes socioeconómicos, nutricionales y ambientales.
2. Unidad de análisis configurable: niño, hogar o área geográfica.
3. Ingesta de datasets tipo DHS / World Bank / UNICEF / WorldPop con validación, diccionario y control de calidad.
4. Indicadores antropométricos OMS: HAZ, WAZ, WHZ, BAZ y clasificación stunting/wasting/underweight.
5. Modelos Random Forest, XGBoost y CatBoost (clasificación y regresión), más híbridos XGBoost+SAR/SEM y CNN-LSTM espaciotemporal.
6. Validación por regiones (GroupKFold / leave-one-region-out) para demostrar transferibilidad espacial.
7. Métricas AUC-ROC, F1, precision/recall, RMSE, MAE y Moran's I de residuos.
8. Explicabilidad SHAP global/local y análisis de equidad por sexo, quintil de riqueza, urbano/rural y región.
9. Cartografía de riesgo, ranking de territorios prioritarios e integración de capas WorldPop/ambientales.
10. Dashboard con KPIs, filtros, tendencias, comparativos y mapa interactivo.
11. Reportes PDF, Word y Excel, con programación automática vía n8n.
12. Autenticación JWT + refresh, roles Administrador/Científico/Analista/Gestor/Auditor y RBAC.
13. Bitácora inmutable con entrada/salida de módulo, filtros, búsqueda y exportación.
14. Agente conversacional LangChain, gestión de modelos/experimentos, catálogo de datasets, alertas, configuración y ayuda.
15. Seguridad, rendimiento, calidad (pytest ≥70 %, ruff, eslint), reproducibilidad y Docker Compose.

## 2. Vista de componentes

```mermaid
flowchart LR
  U[Usuario] -->|HTTPS| WEB[React 18 + Vite + TS<br/>TanStack Query · Recharts · Leaflet]
  WEB -->|REST /api/v1<br/>JWT Bearer| API[FastAPI · Pydantic v2]
  API --> RBAC[RBAC + Rate limit +<br/>Audit middleware]
  API --> DB[(PostgreSQL 15 + PostGIS)]
  API --> FS[(Storage<br/>datasets · artefactos · reportes)]
  API --> ML[Servicio ML<br/>RF · XGBoost · CatBoost ·<br/>CNN-LSTM · SAR/SEM]
  ML --> XAI[SHAP · Fairlearn ·<br/>Moran's I]
  ML --> FS
  API --> AG[Agente LangChain<br/>tools sobre métricas y datos]
  N8N[n8n<br/>ingesta programada · alertas] -->|HTTP API key / JWT| API
  LF[LangFlow<br/>prototipo RAG] -.-> AG
  API --> REP[Reportes<br/>ReportLab · python-docx · openpyxl]
```

## 3. Modelo de datos (ER)

```mermaid
erDiagram
  ROLES ||--o{ USERS : has
  ROLES ||--o{ ROLE_PERMISSIONS : grants
  USERS ||--o{ REFRESH_TOKENS : owns
  USERS ||--o{ AUDIT_LOGS : generates
  USERS ||--o{ NAVIGATION_EVENTS : navigates
  USERS ||--o{ DATASETS : creates
  DATASETS ||--o{ VARIABLE_DEFINITIONS : describes
  DATASETS ||--o{ INGESTION_RUNS : ingests
  DATASETS ||--o{ MODEL_EXPERIMENTS : feeds
  TERRITORIES ||--o{ HOUSEHOLDS : contains
  TERRITORIES ||--o{ CHILDREN : locates
  TERRITORIES ||--o{ TERRITORY_RISK : ranks
  TERRITORIES ||--o{ ALERTS : triggers
  HOUSEHOLDS ||--o{ CHILDREN : hosts
  CHILDREN ||--|| ANTHROPOMETRIC_INDICATORS : measured
  CHILDREN ||--o{ PREDICTIONS : scored
  MODEL_EXPERIMENTS ||--o{ MODELS : produces
  MODELS ||--o{ PREDICTIONS : serves
  MODELS ||--o{ TERRITORY_RISK : maps
  MODELS ||--o{ FAIRNESS_REPORTS : audits
  PREDICTIONS ||--o| PREDICTION_EXPLANATIONS : explains
  USERS ||--o{ REPORTS : requests
  USERS ||--o{ CHAT_SESSIONS : talks
  CHAT_SESSIONS ||--o{ CHAT_MESSAGES : contains

  ROLES {
    int id PK
    string code UK
    string name
  }
  USERS {
    int id PK
    string email UK
    string hashed_password
    int role_id FK
    bool is_active
    datetime last_login_at
  }
  AUDIT_LOGS {
    int id PK
    int user_id FK
    string module
    string action
    string resource_type
    string result
    string ip_address
    datetime started_at
    datetime finished_at
    int duration_ms
  }
  DATASETS {
    int id PK
    string name
    string source
    string analysis_unit
    int rows
    json quality_report
    json dictionary
  }
  TERRITORIES {
    int id PK
    string code UK
    string name
    string region
    json geometry
    float population
  }
  HOUSEHOLDS {
    int id PK
    string code UK
    int territory_id FK
    int wealth_quintile
    string maternal_education
    string water_source
    string sanitation
  }
  CHILDREN {
    int id PK
    string code UK
    int household_id FK
    int territory_id FK
    int age_months
    string sex
    float weight_kg
    float height_cm
    int period_year
  }
  ANTHROPOMETRIC_INDICATORS {
    int id PK
    int child_id FK
    float haz
    float waz
    float whz
    float baz
    bool stunting
    bool wasting
    bool underweight
  }
  MODEL_EXPERIMENTS {
    int id PK
    string algorithm
    string task
    json metrics
    json per_region_metrics
    string cv_strategy
    int seed
  }
  MODELS {
    int id PK
    int experiment_id FK
    string version
    string artifact_path
    bool is_active
  }
  PREDICTIONS {
    int id PK
    int model_id FK
    int child_id FK
    float score
    string risk_band
    int period_year
  }
  TERRITORY_RISK {
    int id PK
    int model_id FK
    int territory_id FK
    int period_year
    float mean_risk
    int priority_rank
    json top_features
  }
```

## 4. Estructura del monorepo

```
nutririsk-ai/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # routers REST (auth, users, audit, datasets, ingestion,
│   │   │                    # indicators, experiments, models, xai, fairness, geo,
│   │   │                    # dashboard, reports, agent, alerts, settings, help)
│   │   ├── core/            # config, security, rbac, rate_limit, logging, errors
│   │   ├── db/              # base, session, bootstrap
│   │   ├── middleware/      # audit, security headers, rate limiting
│   │   ├── ml/              # features, training, spatial, cnn_lstm, registry
│   │   ├── models/          # entidades SQLAlchemy 2.x
│   │   ├── schemas/         # contratos Pydantic v2
│   │   ├── services/        # anthropometry, ingestion, modeling, xai, fairness,
│   │   │                    # spatial, reporting (pdf/docx/xlsx), agent, alerts
│   │   └── main.py
│   ├── alembic/             # migraciones (incluye triggers de inmutabilidad)
│   ├── scripts/             # seed, generate_synthetic, train_pipeline
│   ├── tests/               # pytest ≥ 70 %
│   └── requirements*.txt
├── frontend/                # React 18 + Vite + TS (TanStack Query, Recharts, Leaflet)
├── data/synthetic/          # CSV de demostración etiquetados SYNTHETIC
├── n8n/workflows/           # flujos exportados (.json)
├── langflow/                # flujo RAG exportado (.json)
├── notebooks/               # EDA reproducible
├── docs/                    # arquitectura, diccionario, manual
├── infra/                   # init SQL, nginx
├── docker-compose.yml
├── .env.example
├── README.md
├── DECISIONES.md
├── MANUAL_USUARIO.md
└── DICCIONARIO_DATOS.md
```

## 5. Flujo de datos

1. **Ingesta**: CSV/XLSX/Parquet → validación de esquema y tipos → control de calidad (nulos, outliers, duplicados) → normalización al modelo canónico (`children`, `households`, `territories`) → registro en catálogo con checksum SHA-256.
2. **Indicadores**: LMS OMS 2006 → z-scores y clasificaciones → `anthropometric_indicators`.
3. **Modelado**: tabla analítica → split por región → RF / XGBoost / CatBoost (+SAR/SEM, CNN-LSTM) → métricas globales y por región/subgrupo → artefacto versionado + registro en `model_experiments` / `models`.
4. **Explicabilidad**: SHAP (TreeExplainer) → importancia global, valores locales y agregación por territorio → `territory_risk.top_features`.
5. **Cartografía**: agregación por territorio y periodo → `territory_risk` con ranking y población en riesgo (WorldPop sintético) → GeoJSON servido a Leaflet.
6. **Consumo**: dashboard, reportes PDF/DOCX/XLSX, alertas n8n, agente LangChain.

## 6. Topología de despliegue

```mermaid
flowchart TB
  subgraph Docker["docker compose (red nutririsk)"]
    WEB["web · nginx :8080<br/>SPA + proxy /api"]
    API["api · uvicorn :8000<br/>migraciones + seed + entrenamiento"]
    DB[("db · postgis 16-3.4<br/>volumen pgdata")]
    N8N["n8n :5678"]
    LF["langflow :7860"]
  end
  BROWSER[Usuario] --> WEB
  WEB -->|/api| API
  API --> DB
  N8N -->|X-N8N-Token| API
  LF -.->|prototipo RAG| API
  API --> VOL["volúmenes<br/>artifacts · storage"]
```

* **Arranque**: `entrypoint.sh` aplica `alembic upgrade head`, siembra datos (idempotente), entrena si no hay modelos
  (`SEED_TRAIN=true`), refresca explicaciones almacenadas e inicia uvicorn.
* **Salud**: `/health` y `HEALTHCHECK` del contenedor; el servicio `db` usa `pg_isready`.
* **Integración**: los flujos n8n llaman a endpoints autenticados con `X-N8N-Token`
  (`/ingestion/n8n/sync`, `/alerts/n8n/evaluate`, `/reports/n8n/generate`), que también quedan auditados.

## 7. Módulos de API y responsabilidades

| Router | Prefijo | Responsabilidad |
|---|---|---|
| auth | `/auth` | Login, refresh rotativo, logout, perfil, cambio y recuperación de contraseña |
| users | `/users` | CRUD de usuarios, roles y matriz de permisos (ADMIN) |
| audit | `/audit` | Bitácora inmutable, navegación, resumen y exportación triple formato |
| datasets | `/datasets` | Catálogo, carga, diccionario, calidad, vista previa y plantilla |
| ingestion | `/ingestion` | Historial, reproceso manual y sincronización programada (n8n) |
| indicators | `/indicators` | Z-scores OMS, prevalencias, distribución, referencia y recálculo |
| experiments | `/experiments` | Entrenamiento en segundo plano, comparación y métricas por región |
| models | `/models` | Registro, activación, puntuación y artefactos |
| xai | `/xai` | SHAP global, local, territorial y dependencia |
| fairness | `/fairness` | Métricas de equidad y recálculo con Fairlearn |
| geo | `/geo` | GeoJSON de riesgo, ranking, detalle territorial y capas |
| dashboard | `/dashboard` | KPIs, tendencias, comparativos y opciones de filtro |
| reports | `/reports` | Generación y descarga PDF/DOCX/XLSX (+ endpoint n8n) |
| alerts | `/alerts` | Reglas, reconocimiento, resolución y resumen |
| agent | `/agent` | Chat, sesiones y capacidades del agente LangChain |
| settings | `/settings` | Configuración agrupada y lectura pública |
| help | `/help` | Guías y FAQ |
| system | `/system` | Salud, información, monitoreo y regeneración de datos |

## 8. Decisiones clave

Las ambigüedades resueltas (motor de base de datos, SHAP en puntos porcentuales, protocolo del CNN-LSTM, token de n8n,
entre otras) están documentadas en [`DECISIONES.md`](../DECISIONES.md). El modelo se describe en
[`MODEL_CARD.md`](MODEL_CARD.md).

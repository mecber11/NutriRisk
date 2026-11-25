# Diccionario de datos — NutriRisk AI

Documento de referencia del modelo de datos, las variables canónicas de ingesta, los indicadores antropométricos y los
catálogos del sistema. Los datos de demostración son **sintéticos**.

---

## 1. Convenciones

| Convención | Detalle |
|---|---|
| Identificadores | Enteros autoincrementales (`id`); códigos públicos en texto (`code`, `slug`) |
| Fechas | `timestamptz` (UTC); SQLite las almacena sin zona y la aplicación las normaliza |
| Booleanos | `true/false` |
| JSON | `jsonb` en PostgreSQL, `JSON` en SQLite |
| Unidad de análisis | Niño por defecto (`children`), configurable a hogar o territorio en el catálogo |
| Datos sintéticos | `is_synthetic = true` en territorios, hogares, niños, datasets y modelos |

---

## 2. Entidades principales

### 2.1 `roles`
| Campo | Tipo | Descripción |
|---|---|---|
| id | int PK | Identificador |
| code | varchar(40) UK | `ADMIN`, `DATA_SCIENTIST`, `PUBLIC_HEALTH_ANALYST`, `MANAGER`, `AUDITOR` |
| name | varchar(120) | Nombre en español |
| description | varchar(400) | Descripción del rol |

### 2.2 `role_permissions`
| Campo | Tipo | Descripción |
|---|---|---|
| role_id | FK roles | Rol |
| module | varchar(40) | Módulo (`dashboard`, `datasets`, `audit`, …) |
| action | varchar(20) | `read`, `create`, `update`, `delete`, `execute`, `export`, `use` |
| allowed | bool | Concedido (restricción única `role_id+module+action`) |

### 2.3 `users`
| Campo | Tipo | Descripción |
|---|---|---|
| id | int PK | Identificador |
| email | varchar(255) UK | Correo institucional |
| full_name | varchar(160) | Nombre completo |
| hashed_password | varchar(255) | Argon2id (bcrypt heredado aceptado) |
| role_id | FK roles | Rol asignado |
| is_active | bool | Habilitado |
| organization / position / phone | varchar | Metadatos de perfil |
| last_login_at | timestamptz | Último acceso correcto |
| failed_login_count | int | Intentos fallidos consecutivos |
| locked_until | timestamptz | Bloqueo temporal por intentos fallidos |
| must_change_password | bool | Fuerza cambio en el próximo acceso |
| preferences | json | Preferencias de interfaz |

### 2.4 `refresh_tokens` y `password_reset_tokens`
Almacenan únicamente el **hash SHA-256** del token, su expiración, revocación/uso y metadatos de cliente
(`user_agent`, `ip_address`). Nunca se guarda el token en claro.

### 2.5 `audit_logs` — **inmutable (solo inserción)**
| Campo | Tipo | Descripción |
|---|---|---|
| id | int PK | Identificador |
| user_id | FK users (SET NULL) | Usuario que ejecutó la acción |
| user_email / role_code | varchar | Instantánea del usuario y rol |
| module | varchar(40) | Módulo funcional resuelto por ruta |
| action | varchar(30) | `read`, `create`, `update`, `delete`, `execute`, `export`, `login`, `logout`, `use` |
| resource_type / resource_id | varchar | Recurso afectado |
| method / path / status_code | varchar/int | Detalle HTTP |
| result | varchar(20) | `SUCCESS`, `FAILURE`, `DENIED`, `ERROR` |
| detail | text(JSON) | Parámetros saneados (credenciales enmascaradas) |
| ip_address / user_agent / session_id | varchar | Contexto de la solicitud |
| started_at / finished_at / duration_ms | timestamptz/int | Entrada, salida y duración |

### 2.6 `navigation_events` — **inmutable (solo inserción)**
`user_id`, `session_id`, `module`, `event_type` (`ENTER`/`EXIT`), `path`, `ip_address`, `user_agent`, `occurred_at`.

### 2.7 `datasets`
| Campo | Tipo | Descripción |
|---|---|---|
| name / slug | varchar | Nombre y clave URL única |
| source | varchar(40) | `DHS`, `WORLD_BANK`, `UNICEF`, `WORLDPOP`, `SYNTHETIC`, `CUSTOM` |
| kind / analysis_unit | varchar | `CHILD`, `HOUSEHOLD`, `TERRITORY`, `MIXED` |
| period_year / country / license | | Contexto del dataset |
| file_name / file_path / file_format | | Archivo almacenado |
| checksum_sha256 | varchar(64) | Integridad |
| rows / columns | int | Dimensiones |
| schema_definition | json | Esquema detectado |
| quality_report | json | Reporte de calidad (puntuación 0-100, issues, estadísticas) |
| status | varchar | `PENDING`, `READY`, `PARTIAL`, `FAILED` |
| is_synthetic | bool | Marca de datos sintéticos |

### 2.8 `variable_definitions`
Diccionario por dataset: `name`, `label`, `dtype`, `unit`, `description`, `allowed_values`, `min_value`, `max_value`,
`is_required`, `is_identifier`, `missing_count`, `stats` (min/max/media/mediana/desviación/outliers).

### 2.9 `ingestion_runs`
Ejecuciones de ingesta: `dataset_id`, `status`, `trigger` (`UPLOAD`/`SCHEDULE`/`API`/`SEED`/`REPROCESS`), `rows_in`,
`rows_loaded`, `rows_rejected`, `errors`, `warnings`, `quality_report`, `duration_ms`, `triggered_by`, marcas de tiempo.

### 2.10 `territories`
| Campo | Tipo | Descripción |
|---|---|---|
| code / name / level / parent_code | varchar | Identificación administrativa |
| region | varchar(80) | Región (5 en la demo) |
| urban_rural | varchar | `URBAN`, `RURAL`, `MIXED` |
| population / population_u5 | int | Población total y menor de 5 años |
| area_km2 / altitude_m / climate_zone | | Contexto geográfico |
| rainfall_mm / temperature_c / ndvi | float | Variables ambientales |
| food_insecurity_index | float | Índice 0-1 de inseguridad alimentaria territorial |
| water_coverage / sanitation_coverage | float | Cobertura 0-1 |
| latitude / longitude | float | Centroide |
| geometry | json | GeoJSON `Polygon` |
| neighbor_codes | json | Adyacencia para matrices W |

### 2.11 `households`
| Campo | Tipo | Descripción |
|---|---|---|
| code | varchar UK | Identificador del hogar |
| territory_id | FK | Territorio |
| period_year | int | Año |
| wealth_quintile | int 1-5 | 1 = más pobre, 5 = más rico |
| wealth_index | float | Índice continuo de riqueza |
| maternal_education | varchar | `NONE`, `PRIMARY`, `SECONDARY`, `TERTIARY` |
| maternal_age | int | Edad de la madre |
| water_source | varchar | `PIPED`, `IMPROVED`, `UNIMPROVED`, `SURFACE` |
| sanitation | varchar | `IMPROVED`, `SHARED`, `UNIMPROVED`, `OPEN` |
| electricity | bool | Acceso a electricidad |
| cooking_fuel | varchar | `GAS`, `ELECTRICITY`, `KEROSENE`, `WOOD`, `CHARCOAL` |
| assets_count / household_size | int | Activos durables y tamaño del hogar |
| food_insecurity_score | float 0-1 | Escala del hogar |
| urban_rural | varchar | `URBAN`/`RURAL` |

### 2.12 `children`
| Campo | Tipo | Descripción |
|---|---|---|
| code | varchar UK | Identificador seudonimizado del niño |
| household_id / territory_id | FK | Hogar y territorio |
| period_year | int | Año del levantamiento |
| age_months | int 0-59 | Edad en meses |
| sex | char | `M`/`F` |
| weight_kg | float | Peso (kg) |
| height_cm | float | Longitud (<24 m) o talla (≥24 m) en cm |
| muac_cm | float | Perímetro braquial (cm) |
| edema | bool | Edema bilateral |
| birth_weight_g | float | Peso al nacer (g) |
| breastfeeding_months | int | Duración de lactancia |
| minimum_diet_diversity | bool | Dieta mínima diversa |
| vaccination_complete | bool | Esquema completo para la edad |
| diarrhea_14d / fever_14d | bool | Morbilidad reciente |

### 2.13 `anthropometric_indicators`
| Campo | Tipo | Descripción |
|---|---|---|
| child_id | FK UK | Relación 1:1 con el niño |
| haz / waz / whz / baz | float | Z-scores OMS 2006 |
| stunting / severe_stunting | bool | HAZ < -2 / < -3 |
| wasting / severe_wasting | bool | WHZ < -2 / < -3 (o edema) |
| underweight / severe_underweight | bool | WAZ < -2 / < -3 |
| overweight | bool | WHZ > +2 |
| edematous | bool | Edema bilateral |
| reference_version | varchar | `WHO-2006` |
| computed_at | timestamptz | Momento del cálculo |

### 2.14 `model_experiments` y `models`
**Experimentos**: `name`, `algorithm`, `task`, `target`, `dataset_id`, `cv_strategy`, `seed`, `hyperparams`, `metrics`,
`per_region_metrics`, `per_group_metrics`, `spatial_diagnostics` (Moran, SAR/SEM/GWR, corrección), `feature_importance`,
`status`, `duration_seconds`, marcas temporales.

**Modelos**: `name`, `version`, `algorithm`, `task`, `target`, `artifact_path`, `feature_names`, `metrics`,
`feature_importance`, `shap_summary`, `hyperparams`, `is_active`, `is_synthetic`, `trained_at`.

### 2.15 `predictions` y `prediction_explanations`
**Predicciones**: `model_id`, `child_id`, `territory_id`, `score` (probabilidad 0-1), `predicted_label` (umbral óptimo),
`risk_band` (`LOW`/`MODERATE`/`HIGH`/`CRITICAL`), `period_year`.

**Explicaciones locales** (bajo demanda): `prediction_id`, `base_value`, `contributions` (top-5 con etiqueta, valor y
contribución en puntos porcentuales), `narrative`.

### 2.16 `territory_risk`
`model_id`, `territory_id`, `period_year`, `mean_risk`, `risk_band`, `stunting_prevalence`, `children_screened`,
`population_at_risk` (población <5 × riesgo medio), `priority_rank` (1 = mayor riesgo), `top_features` (SHAP agregado).

### 2.17 `fairness_reports`
`model_id`, `sensitive_attribute`, `metric`, `results` (métricas por grupo + salida de Fairlearn), `disparity`,
`is_acceptable`, `created_by`.

### 2.18 `alerts`
`rule_code`, `severity` (`INFO`/`WARNING`/`CRITICAL`), `title`, `message`, `module`, `territory_id`, `value`, `threshold`,
`status` (`OPEN`/`ACKNOWLEDGED`/`RESOLVED`), `context`, `created_at`, `acknowledged_by/at`.

### 2.19 `reports`
`kind`, `title`, `fmt` (`pdf`/`docx`/`xlsx`), `params`, `file_path`, `file_name`, `size_bytes`, `status`, `error`,
`created_by`, `created_at`.

### 2.20 `chat_sessions` / `chat_messages`
Sesiones del agente: `user_id`, `title`; mensajes con `role` (`user`/`assistant`/`tool`), `content` y `meta`
(intención, herramientas usadas, datos estructurados).

### 2.21 `system_settings`
`key` PK, `value` (json), `category`, `description`, `updated_by`, `updated_at`.

---

## 3. Variables canónicas de ingesta (tabla plana de niño)

Columnas aceptadas por el cargador. Los alias en español e inglés se normalizan automáticamente
(`Código Niño` → `child_code`, `Peso kg` → `weight_kg`, etc.).

| Variable | Tipo | Unidad | Rango | Obligatoria | Descripción |
|---|---|---|---|---|---|
| child_code | string | — | — | ✅ | Identificador del niño (seudonimizado) |
| household_code | string | — | — | ✅ | Identificador del hogar |
| territory_code | string | — | — | ✅ | Código del territorio |
| region | string | — | — | ✅ | Región administrativa |
| period_year | int | año | 1990-2100 | ✅ | Año del levantamiento |
| age_months | int | meses | 0-59 | ✅ | Edad al momento de la medición |
| sex | category | — | M/F | ✅ | Sexo |
| weight_kg | float | kg | 1-35 | ✅ | Peso |
| height_cm | float | cm | 35-130 | ✅ | Longitud (<24 m) o talla (≥24 m) |
| muac_cm | float | cm | 9-20 | — | Perímetro braquial |
| edema | bool | — | — | — | Edema bilateral |
| birth_weight_g | float | g | 500-6000 | — | Peso al nacer |
| breastfeeding_months | int | meses | 0-36 | — | Lactancia materna |
| wealth_quintile | int | — | 1-5 | ✅ | Quintil de riqueza |
| wealth_index | float | — | — | — | Índice continuo de riqueza |
| maternal_education | category | — | NONE/PRIMARY/SECONDARY/TERTIARY | ✅ | Educación materna |
| maternal_age | int | años | 12-55 | — | Edad de la madre |
| water_source | category | — | PIPED/IMPROVED/UNIMPROVED/SURFACE | ✅ | Fuente de agua |
| sanitation | category | — | IMPROVED/SHARED/UNIMPROVED/OPEN | ✅ | Saneamiento |
| electricity | bool | — | — | — | Electricidad |
| cooking_fuel | category | — | GAS/ELECTRICITY/KEROSENE/WOOD/CHARCOAL | — | Combustible |
| assets_count | int | — | 0-30 | — | Activos durables |
| household_size | int | personas | 1-30 | — | Tamaño del hogar |
| food_insecurity_score | float | — | 0-1 | — | Inseguridad alimentaria del hogar |
| urban_rural | category | — | URBAN/RURAL | — | Área |
| minimum_diet_diversity | bool | — | — | — | Dieta mínima diversa |
| vaccination_complete | bool | — | — | — | Vacunación completa |
| diarrhea_14d | bool | — | — | — | Diarrea en 14 días |
| fever_14d | bool | — | — | — | Fiebre en 14 días |
| altitude_m | float | m | — | — | Altitud del territorio |
| rainfall_mm | float | mm/año | — | — | Precipitación |
| temperature_c | float | °C | — | — | Temperatura media |
| ndvi | float | — | 0-1 | — | Índice de vegetación |

**Plantilla descargable**: `GET /api/v1/datasets/template`.

---

## 4. Indicadores antropométricos (OMS 2006)

Fórmula LMS: `z = ((X/M)^L − 1) / (L·S)` para `L ≠ 0`, y `z = ln(X/M)/S` para `L = 0`, con `X` la medición y `L, M, S`
los parámetros de la tabla de referencia para edad/sexo (o talla/sexo).

| Indicador | Medición | Referencia | Clasificación |
|---|---|---|---|
| HAZ | talla/longitud para la edad | `hfa` mensual 0-60 m | Retraso del crecimiento: < −2 DE; severo: < −3 DE |
| WAZ | peso para la edad | `wfa` mensual 0-60 m | Bajo peso: < −2 DE; severo: < −3 DE |
| WHZ | peso para la talla | `wfl` (<24 m) / `wfh` (≥24 m) | Emaciación: < −2 DE; severa: < −3 DE |
| BAZ | IMC para la edad | `bfa` mensual 0-60 m | Sobrepeso: WHZ > +2 DE |

**Reglas aplicadas**
* Longitud (<24 meses) vs talla (≥24 meses): tablas `lhfa_0_2` y `lhfa_2_5`.
* Interpolación lineal entre centímetros enteros en peso/talla.
* Z-scores recortados a ±5 DE con bandera `*_out_of_range`.
* Edema bilateral ⇒ emaciación severa.
* Autochequeo: 244 puntos de corte OMS recalculados, desviación máxima ≤ 0,15 z (`GET /indicators/reference`).

---

## 5. Catálogos

| Catálogo | Valores |
|---|---|
| Bandas de riesgo | `LOW` < 0,15 · `MODERATE` 0,15-0,30 · `HIGH` 0,30-0,50 · `CRITICAL` ≥ 0,50 |
| Regiones | Norte, Centro, Sur, Oriente, Occidente (sintéticas) |
| Grupos de edad | 0-5 m · 6-11 m · 12-23 m · 24-35 m · 36-59 m |
| Roles | ADMIN · DATA_SCIENTIST · PUBLIC_HEALTH_ANALYST · MANAGER · AUDITOR |
| Acciones auditadas | read · create · update · delete · execute · export · use · login · logout |
| Resultado de auditoría | SUCCESS · FAILURE · DENIED · ERROR |
| Formatos de reporte | pdf · docx · xlsx |
| Severidad de alerta | INFO · WARNING · CRITICAL |
| Fuentes de datos | DHS · WORLD_BANK · UNICEF · WORLDPOP · SYNTHETIC · CUSTOM |

---

## 6. Reglas de control de calidad

| Regla | Criterio | Efecto |
|---|---|---|
| Columnas obligatorias | edad, sexo, peso, talla (+ territorio/hogar) | Rechaza el archivo (HTTP 422) |
| Filas sin antropometría válida | edad/peso/talla nulos o no numéricos | Se rechazan y se reportan |
| Rangos fisiológicos | edad 0-60, peso 1-35 kg, talla 35-130 cm, MUAC 9-20 cm | Se rechazan al calcular z-scores |
| Duplicados de identificador | `child_code` repetido | Advertencia/error en el reporte |
| Duplicados de fila | fila idéntica | Advertencia |
| Outliers | fuera de `Q1 − 3·IQR` / `Q3 + 3·IQR` | Se contabilizan |
| Nulos por columna | > 20 % | Advertencia |
| Puntuación de calidad | 100 − penalizaciones (nulos, outliers, duplicados, errores) | < 70 genera alerta |
| Códigos ya existentes | `child_code` presente en la base | Se omiten (idempotencia) |

---

## 7. Relaciones (resumen)

```
roles 1—N users 1—N refresh_tokens
users 1—N audit_logs / navigation_events / datasets / reports / chat_sessions
datasets 1—N variable_definitions / ingestion_runs / model_experiments
territories 1—N households 1—N children 1—1 anthropometric_indicators
territories 1—N territory_risk / alerts
model_experiments 1—N models 1—N predictions / territory_risk / fairness_reports
children 1—N predictions 1—1 prediction_explanations
```

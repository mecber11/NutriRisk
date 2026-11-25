# Model card — NutriRisk AI

## 1. Información general

| Campo | Valor |
|---|---|
| Nombre | NutriRisk AI — modelo de riesgo de desnutrición infantil |
| Versión de referencia | `1.0.x` (registrada en la tabla `models`) |
| Tipo | Clasificación binaria (riesgo de retraso del crecimiento) y modelos de regresión (z-scores) |
| Algoritmos | Random Forest, XGBoost, CatBoost, XGBoost + regresión espacial, CNN-LSTM |
| Unidad de predicción | Niño (clasificación) · territorio-año (CNN-LSTM) |
| Datos de entrenamiento | Encuesta sintética *República de Andara* 2021-2023, n = 14.400 (demostración) |
| Autoría | Proyecto de tesis SP-08, implementado en este repositorio |
| Licencia | Uso académico |

## 2. Uso previsto

* **Priorización territorial** de intervenciones nutricionales y de salud pública.
* **Tamizaje de apoyo** para identificar niños con mayor probabilidad de retraso del crecimiento antes de la medición.
* **Comunicación de factores de riesgo** a equipos territoriales mediante explicaciones SHAP.
* **Docencia e investigación** sobre XAI aplicado a salud pública.

### Fuera de alcance

* Diagnóstico clínico individual o decisión terapéutica.
* Sustituir la antropometría presencial o el juicio profesional.
* Inferencia causal sobre intervenciones.
* Uso con poblaciones distintas a las de entrenamiento sin recalibración.

## 3. Datos

| Aspecto | Detalle |
|---|---|
| Fuente | Generador sintético calibrado (`backend/app/services/synthetic.py`) |
| Cobertura | 24 territorios, 5 regiones, 3 años (2021-2023) |
| Prevalencias | Retraso 18,7 % · Emaciación 6,9 % · Bajo peso 9,9 % |
| Etiquetas | Retraso del crecimiento = HAZ < −2 DE (OMS 2006) |
| Predictores | 26 determinantes socioeconómicos, WASH, dietéticos y ambientales |
| Exclusiones | Mediciones antropométricas (peso, talla, MUAC) para evitar fuga de información |
| Consentimiento / privacidad | Datos sintéticos, sin información personal identificable |

## 4. Evaluación

| Dimensión | Protocolo | Resultado (referencia) |
|---|---|---|
| Desempeño global | GroupKFold por región (5 pliegues), predicciones out-of-fold | AUC ≈ 0,78 · F1 óptimo ≈ 0,48 |
| Transferibilidad espacial | Leave-one-region-out | AUC 0,76-0,79 por región |
| Equidad | Métricas por sexo, quintil, área y región; disparidad de tasa de selección | Brechas ≤ 0,20 en la mayoría de atributos |
| Calibración | Brier ≈ 0,13 · log-loss ≈ 0,41 | Probabilidades utilizables como riesgo |
| Espacialidad de residuos | Moran's I de residuos medios territoriales | No significativo (p > 0,05) |
| Serie temporal | CNN-LSTM, holdout por territorio, objetivo 2023 | R² ≈ 0,50 · RMSE ≈ 0,07 |
| Regresión de z-scores | RMSE/MAE sobre HAZ | Reportado por experimento |

Los umbrales operativos se eligen maximizando F1 y, para tamizaje, con recall ≥ 0,75.

## 5. Explicabilidad

* **Global**: importancia media |SHAP| por determinante.
* **Local**: contribuciones del niño en puntos porcentuales de riesgo + narrativa y recomendación.
* **Territorial**: agregación de |SHAP| por territorio para el mapa y la ficha.
* **Dependencia**: relación entre el valor de una variable y su contribución.

Los determinantes dominantes en la demostración son el quintil de riqueza, la educación materna, la precipitación, los
activos del hogar, la diarrea reciente y el acceso a agua mejorada.

## 6. Limitaciones

1. Datos sintéticos: los resultados no son evidencia epidemiológica.
2. La etiqueta depende de una única medición antropométrica (sin repetición ni control de calidad de campo).
3. No se modelan factores genéticos, infecciones subclínicas ni inseguridad alimentaria estacional.
4. SAR/SEM/GWR con 24 territorios tienen baja potencia estadística.
5. El CNN-LSTM dispone de tres pasos temporales.
6. La calibración puede degradarse al aplicar el modelo a poblaciones con distinta prevalencia basal.

## 7. Consideraciones éticas

* Las predicciones pueden estigmatizar territorios: deben presentarse como **priorización de recursos**, no como juicio
  sobre comunidades.
* Los modelos de equidad deben revisarse antes de cada despliegue; un AUC alto no garantiza trato justo.
* Los microdatos reales requieren anonimización y base legal; el sistema no almacena nombres ni direcciones.
* Se recomienda validación local y supervisión humana antes de cualquier decisión programática.

## 8. Mantenimiento

* Reentrenar ante nuevos levantamientos (botón *Reentrenar* o `scripts/train_pipeline.py`).
* Versionar cada modelo (`1.0.N`) y conservar su artefacto y métricas.
* Revisar alertas de desempeño (AUC < 0,70) y de calidad de datos (< 70/100).
* Documentar cambios de esquema con migraciones Alembic.

# Datos públicos reales: panel nacional Banco Mundial/JME

Adquisición reproducible desde la raíz del repositorio:

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/acquire_real_data.ps1
# Agregar -Refresh para renovar el snapshot desde la API.
```

`country_panel.csv`: 4.025 observaciones país-año, 161 países, 2000–2024. Se conservan únicamente países con región y coordenadas oficiales y años con etiqueta disponible; se excluyen agregados regionales. Identificador único: `country_code, period_year`. El CSV no contiene niños, hogares ni observaciones clínicas individuales.

`stunting_prevalence_pct` es la prevalencia nacional **modelada** de retraso del crecimiento en menores de cinco años, indicador `SH.STA.STNT.ME.ZS` de UNICEF/OMS/Banco Mundial. Las estimaciones oficiales se derivan de encuestas y modelos; no son etiquetas individuales observadas. Escala 0–100; dividir por 100 si el modelo necesita fracciones. Al provenir de un snapshot revisado retrospectivamente, la evaluación temporal no demuestra predicción prospectiva con datos disponibles en tiempo real.

Las nueve covariables son PIB real por habitante, servicios básicos de agua y saneamiento, acceso a electricidad, urbanización, densidad poblacional, fertilidad, matrícula secundaria femenina y exposición PM2.5. Sus códigos, metadatos, unidades originales y fuentes están en `manifest.json` y las respuestas crudas. Los valores ausentes se conservan vacíos. Ninguna variable antropométrica ni otra prevalencia nutricional se usa como predictor. Puede existir relación entre covariables y los modelos originales que producen las estimaciones JME: el experimento evalúa reproducción/predicción de estimaciones nacionales publicadas, no validación clínica independiente.

`latitude, longitude` son coordenadas de la capital publicadas por el Banco Mundial: **proxy geográfico**, no centroides poblacionales, coordenadas de niños ni ubicaciones de encuestas. `region` es la clasificación actual del Banco Mundial y no reproduce necesariamente las agrupaciones históricas. Son metadatos para partición/diagnóstico espacial; no determinantes individuales.

Contrato recomendado de evaluación:

- Regresión ecológica nacional; mantener el mismo target, países y filas de prueba para todos los algoritmos.
- No dividir filas aleatoriamente. Separar países o regiones completas para transferencia geográfica y mantener la separación temporal explícita.
- Ajustar imputadores, escaladores e hiperparámetros solo dentro de entrenamiento; elegir parámetros con validación interna y conservar prueba exterior intacta.
- PM2.5 está completamente ausente en 2024. Para usar las nueve covariables, el último año común con cobertura es **2023**; alternativamente excluir PM2.5 y justificar evaluación 2024.
- Matrícula secundaria femenina tiene aproximadamente 32,75 % de faltantes. Reportar análisis de sensibilidad o excluirla justificadamente; no inventar datos.
- Bootstrap y pruebas pareadas deben respetar grupos (país/región). Norteamérica aporta solo un país. Los años repetidos, estimaciones suavizadas y dependencia espacial limitan la inferencia.
- No reportar AUC/F1 infantil, equidad individual, efecto causal, longitudinalidad infantil ni rendimiento clínico con este conjunto.

`manifest.json` conserva URLs, fecha UTC de recuperación, SHA-256 y tamaño de cada respuesta original, huella del CSV, cobertura anual y faltantes. `raw/` contiene el snapshot de la API y los metadatos de indicadores. No se interpola, remuestrea ni sintetiza ningún registro.

Fuentes primarias y atribución:

- Banco Mundial, World Development Indicators: https://api.worldbank.org/v2/
- UNICEF/OMS/Banco Mundial, Joint Child Malnutrition Estimates: https://data.unicef.org/resources/jme/
- Metodología de stunting: https://databank.worldbank.org/metadataglossary/world-development-indicators/series/SH.STA.STNT.ME.ZS
- Condiciones de licencia del catálogo (generalmente CC BY 4.0; revisar términos específicos de fuente): https://datacatalog.worldbank.org/public-licenses#cc-by

El archivo `manifest.json` documenta los proveedores particulares de cada indicador. Las fechas de actualización pueden diferir entre series.

# Manual de usuario — NutriRisk AI

Guía breve para operar la plataforma según el rol asignado. Los datos de la demostración son **sintéticos**.

---

## 1. Acceso

1. Abra http://localhost:8080 (Docker) o http://127.0.0.1:8000 (local).
2. Ingrese correo y contraseña institucional.
3. Puede hacer clic en cualquiera de los **chips de credenciales demo** del panel de acceso para autocompletar.

| Rol | Correo | Contraseña |
|---|---|---|
| Administrador | `admin@nutririsk.ai` | `Admin#2026!` |
| Científico de datos | `cientifico@nutririsk.ai` | `Ciencia#2026!` |
| Analista de salud pública | `analista@nutririsk.ai` | `Analista#2026!` |
| Gestor / Decisor | `gestor@nutririsk.ai` | `Gestor#2026!` |
| Auditor | `auditor@nutririsk.ai` | `Auditor#2026!` |

**¿Olvidó su contraseña?** Use el enlace del formulario. En modo demostración el sistema muestra el token de
restablecimiento en pantalla (no hay servidor de correo configurado). En producción el token se envía por correo.

La sesión dura 60 minutos y se renueva automáticamente mientras use la aplicación. El botón **Salir** revoca el refresh token.

---

## 2. Navegación general

* La barra lateral solo muestra los módulos permitidos para su rol.
* Los filtros de **año, región, sexo y grupo de edad** del tablero afectan a todos los indicadores de la vista.
* Cada entrada y salida de módulo queda registrada en la bitácora (módulo, fecha/hora, IP y sesión).
* El pie de la barra lateral indica la versión y el identificador de sesión.

---

## 3. Tablero

1. Elija los filtros y observe las tarjetas KPI: niños evaluados, retraso del crecimiento, emaciación, bajo peso,
   riesgo medio, niños en riesgo alto/crítico, territorios críticos, población menor de 5 años en riesgo, AUC del modelo
   y retraso severo.
2. Los indicadores muestran la **variación** respecto al año anterior cuando aplica.
3. Revise la **tendencia** (línea), el **comparativo por región** (barras), la **distribución de riesgo** (anillo) y la
   **tabla de territorios prioritarios**.
4. La tarjeta de **desempeño de modelos** resume AUC y F1 del modelo activo; las **alertas** abiertas aparecen al final.

> El aviso “Demostración” del encabezado recuerda que los datos son sintéticos.

---

## 4. Mapa de riesgo

1. Seleccione el año en la parte superior.
2. Cada territorio se colorea según el riesgo medio predicho: azul (bajo), ámbar (moderado), naranja (alto) y rojo (crítico).
3. Pase el cursor para ver nombre, región, riesgo, prevalencia de retraso, ranking y población en riesgo.
4. Haga clic en un territorio para abrir su **ficha territorial**.
5. El panel derecho muestra el **ranking de priorización** completo.

---

## 5. Territorios y ficha territorial

* **Listado**: tabla con ranking, territorio, región, riesgo medio, prevalencia observada, población en riesgo y niños
  evaluados. Ordenado por prioridad (1 = mayor riesgo).
* **Ficha**: KPIs del territorio, mapa del polígono, historia de riesgo por año, **determinantes SHAP** (qué factores
  explican su riesgo) y un texto interpretativo.
* **Generar ficha PDF**: botón “Descargar ficha PDF”. El archivo se genera y descarga; queda registrado en *Reportes*.

---

## 6. Indicadores OMS

1. Consulte las prevalencias nacionales y por región, sexo, grupo de edad y quintil de riqueza.
2. El **histograma de HAZ** muestra la distribución con la línea de referencia −2 DE.
3. La tarjeta de **referencia OMS** indica la versión, cobertura de tablas y el resultado del autochequeo (244 puntos de corte).
4. La **tabla de niños** permite buscar por código, filtrar por año/región/sexo y ver z-scores y clasificaciones.
5. Los roles con permiso pueden **recalcular z-scores** si se corrigieron mediciones.

---

## 7. Modelos y experimentos

* **Comparación**: tabla con AUC, F1 al umbral óptimo, precisión, recall, exactitud, Brier, umbral y RMSE por modelo.
  El mejor modelo aparece marcado y es el **activo**.
* **Entrenar** (científico de datos / administrador): seleccione algoritmos (Random Forest, XGBoost, CatBoost,
  XGBoost + espacial, CNN-LSTM) y la estrategia de validación; el entrenamiento se ejecuta en segundo plano y la tabla se
  actualiza automáticamente.
* **Métricas por región** y **diagnósticos espaciales** (Moran's I de residuos, rho del SAR, lambda del SEM, R² local del GWR).
* **Activar modelo**: cambia el modelo que puntúa a la población y alimenta el mapa.
* **Repuntuar**: recalcula predicciones, ranking territorial y alertas con el modelo activo.

---

## 8. Explicabilidad (XAI)

Tres pestañas:

1. **Global** — barras con los determinantes de mayor impacto medio (puntos porcentuales de riesgo) y selector de modelo.
2. **Niño** — escriba el código (por ejemplo `CH-2023-T16-0001`) o el id; verá la probabilidad, la banda, las
   contribuciones que aumentan (rojo) y reducen (verde) el riesgo, y una narrativa con recomendación de intervención.
3. **Territorio** — determinantes agregados del territorio y texto interpretativo.

El panel inferior permite **gráficos de dependencia**: relación entre el valor de una variable y su contribución al riesgo.

---

## 9. Equidad

1. Seleccione el modelo y el atributo (sexo, quintil de riqueza, área urbano/rural, región o grupo de edad).
2. Pulse **Recalcular** para actualizar con las predicciones vigentes.
3. Interprete:
   * **Tasa de selección**: proporción de niños marcados en riesgo alto por el modelo.
   * **TPR/recall**: sensibilidad del modelo en el grupo.
   * **FPR**: falsos positivos relativos.
   * **Disparidad máxima**: diferencia entre grupos; ≤ 0,20 se considera aceptable (regla de los cuatro quintos).
4. Exporte el informe en PDF o Word desde *Reportes*.

---

## 10. Datasets e ingesta

1. **Descargue la plantilla** (`Plantilla CSV`) y complete las columnas obligatorias.
2. **Cargar dataset**: archivo CSV/XLSX/Parquet + nombre, fuente, unidad de análisis y año.
3. El sistema valida el esquema, calcula el **reporte de calidad** (nulos, duplicados, outliers, rangos, puntuación 0-100) y
   carga los registros, calculando z-scores OMS en la misma operación.
4. Consulte variables (diccionario), calidad y vista previa desde la tabla.
5. Los archivos con errores de esquema se rechazan con un mensaje que indica las columnas faltantes.

> Los códigos de niño ya existentes se omiten para que la recarga sea idempotente.

---

## 11. Reportes

1. Elija el **tipo**: ficha territorial, ranking de priorización, desempeño de modelos, equidad, bitácora o prevalencias.
2. Elija el **formato**: PDF, Word (.docx) o Excel (.xlsx).
3. Complete los parámetros (año, territorio, modelo).
4. Pulse **Generar** y descargue desde el historial. El tamaño y el estado se muestran en la tabla.
5. La programación automática se configura en **n8n** (flujo `03_reportes_programados.json`).

---

## 12. Bitácora (auditoría)

* **Resumen**: total de eventos, tasa de éxito, eventos por módulo y usuarios más activos.
* **Eventos**: tabla paginada con usuario, rol, módulo, acción, resultado, ruta, IP y duración; filtros por módulo,
  acción, resultado, texto y fechas.
* **Navegación**: marcas de entrada/salida por módulo enviadas por la interfaz.
* **Exportar**: PDF, Word o Excel (respeta permisos; el rol Auditor puede exportar).
* La bitácora es **inmutable**: no existe operación de edición o borrado.

---

## 13. Agente analista

1. Escriba una pregunta en lenguaje natural o use una sugerencia.
2. El agente identifica la intención, consulta la base de datos con sus herramientas y responde con cifras reales.
3. Las etiquetas muestran qué herramienta se usó (prevalencia, ranking, modelos, equidad, niño, catálogo).
4. El historial de conversaciones queda disponible a la izquierda.
5. Ejemplos: “¿Cuál es la prevalencia de retraso del crecimiento en 2023?”, “¿Qué territorios priorizar?”,
   “Explica el riesgo del niño CH-2023-T16-0001”.

---

## 14. Administración

**Usuarios** (solo administrador): crear, editar rol, activar/desactivar, restablecer contraseña y consultar la matriz de permisos.

**Configuración** (solo administrador): identidad institucional, preferencias del tablero, umbrales de alerta, política de
seguridad, integraciones y reportes. Los valores se editan en formato JSON y se validan al guardar.

También puede **regenerar los datos sintéticos y reentrenar** desde el panel de sistema (tarda unos minutos).

---

## 15. Ayuda y soporte

* El módulo **Ayuda** contiene guías por tema y preguntas frecuentes.
* La documentación técnica de la API está en `/docs` (Swagger) y `/openapi.json`.
* Para problemas de instalación consulte la sección *Solución de problemas* del README.

---

## 16. Buenas prácticas

* No comparta credenciales; cada acción queda asociada a su usuario en la bitácora.
* Verifique la calidad del dataset antes de entrenar.
* Revise siempre la **equidad** al cambiar de modelo.
* Trate las predicciones como apoyo a la priorización, nunca como diagnóstico clínico.
* Recuerde que la demostración usa datos sintéticos: no cite sus cifras como evidencia real.

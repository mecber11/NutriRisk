"""Visible, task-specific interpretations shared by exported report formats."""
def table_note(title: str, headers: list[str]) -> str:
    text=(title+' '+' '.join(headers)).lower()
    if any(word in text for word in ('tpr','fpr','selección','equidad')):
        return 'Interpretación: compare tasas de selección, sensibilidad y falsos positivos entre grupos del mismo modelo. Una disparidad pequeña no certifica equidad; los tamaños de grupo, la prevalencia y el umbral modifican el resultado. Datos de demostración sintéticos.'
    if any(word in text for word in ('shap','determinante','contribución')):
        return 'Interpretación: las contribuciones describen cómo el modelo usa los determinantes respecto de su referencia. Una magnitud mayor indica mayor influencia en la predicción, no causalidad ni efecto de una intervención. No constituye recomendación clínica.'
    if any(word in text for word in ('auc','rmse','f1','modelo')):
        return 'Interpretación: AUC mide discriminación y F1 depende del umbral; MAE y RMSE miden error en las unidades del objetivo. Compare únicamente tareas y particiones equivalentes. Las métricas sintéticas no prueban desempeño en pacientes reales.'
    if any(word in text for word in ('evento','bitácora','auditoría')):
        return 'Interpretación: cada fila representa actividad registrada por el sistema. Los errores y la duración orientan la revisión operativa; la ausencia de errores en estos registros no demuestra ausencia de incidentes externos ni eficacia clínica.'
    if any(word in text for word in ('riesgo','ranking','prioridad')):
        return 'Interpretación: el orden prioriza territorios por riesgo medio estimado, mientras la prevalencia refleja resultados observados. El ranking depende del año y del modelo y no confirma diagnósticos ni efectos de intervenciones. Los territorios son sintéticos.'
    return 'Interpretación: las cifras describen la distribución observada en el periodo y los grupos indicados. Compare porcentajes junto con sus denominadores y filtros; los cambios descriptivos no establecen causalidad ni representan prevalencias reales en esta demostración sintética.'

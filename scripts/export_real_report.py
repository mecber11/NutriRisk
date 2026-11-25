"""Export complete human-readable real-run evidence without recalculation."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
store = ROOT / 'backend/storage/research'
run_id = json.loads((store / 'latest_real.json').read_text())['id']
r = json.loads((store / run_id / 'results.json').read_text(encoding='utf-8'))
lines = ['# NutriRisk AI: entrenamiento con datos públicos reales', '',
         f'Ejecución: `{run_id}`. Estado: {r["status"]}. Semilla: {r["seed"]}.', '',
         '161 países; siete regiones; ventanas reales de tres años; nueve determinantes.',
         'La etiqueta es prevalencia nacional JME modelada desde encuestas. No son microdatos infantiles.', '',
         '## Protocolo ejecutado', '', '```json', json.dumps(r['protocol'], ensure_ascii=False, indent=2), '```', '',
         '## Métricas', '', 'MAE y RMSE se expresan en puntos porcentuales. R² no tiene unidades.', '',
         '| Modelo | Etapa | MAE (pp) | RMSE (pp) | R² |', '|---|---|---:|---:|---:|']
for model in r['models']:
    for split, m in model['metrics'].items():
        if m:
            lines.append(f'| {model["label"]} | {split} | {m["mae"]*100:.6f} | {m["rmse"]*100:.6f} | {m["r2"]:.6f} |')
lines += ['', 'Las métricas train/validation son promedios de pliegues solapados; test reúne predicciones exteriores disjuntas.', '',
          'La persistencia usa la etiqueta de 2022 del mismo país excluido. Tiene información adicional y supera ampliamente a los cinco modelos; no se incluye en el contraste de sus cinco rangos.', '',
          '## Intervalos de confianza', '']
for model in r['models']:
    lines += [f'### {model["label"]}', '', '```json', json.dumps(model['test_ci'], indent=2), '```', '']
lines += ['## Todas las pruebas estadísticas', '',
          'Friedman: H0 = igualdad de rangos de error entre los cinco modelos por región. Wilcoxon: diferencias regionales simétricas centradas en cero. Holm controla la familia de diez comparaciones.',
          'Shapiro-Wilk: diagnóstico de normalidad residual. Moran: asociación espacial residual respecto de vecindad de capitales; p por 999 permutaciones. Estos dos diagnósticos presentan p crudas exploratorias.',
          'Los IC, efectos y contrastes no incorporan toda la incertidumbre JME ni la variación por semillas. Siete bloques, dependencia y ajustes solapados limitan la inferencia.', '',
          '```json', json.dumps(r['statistics'], ensure_ascii=False, indent=2), '```', '',
          '## Espacio de hiperparámetros', '', '```json', json.dumps(r['hyperparameter_space'], ensure_ascii=False, indent=2), '```', '',
          '## Hiperparámetros finales y métricas de cada ajuste', '', '```json', json.dumps(r['folds'], ensure_ascii=False, indent=2), '```', '',
          '## Dependencias', '', '```json', json.dumps(r['versions'], indent=2), '```', '',
          '## Limitaciones registradas', '']
lines += ['- '+text for text in r['limitations']]
lines += ['', '## Reproducir', '', 'Desde la raíz del proyecto:', '',
          '```powershell', 'powershell -ExecutionPolicy Bypass -File backend/scripts/acquire_real_data.ps1',
          'cd backend', '../.venv/Scripts/python.exe -m scripts.train_real --trials 10 --seed 42',
          f'../.venv/Scripts/python.exe -m scripts.verify_real {run_id}', '```', '',
          'El snapshot no se actualiza salvo que se solicite `-Refresh`. La nueva ejecución tendrá otro identificador. Las versiones y el hardware pueden modificar resultados numéricos.', '',
          '## Artefactos de esta ejecución', '',
          f'Carpeta: `backend/storage/research/{run_id}/`.', '',
          '- `results.json`: evidencia completa y predicciones.',
          '- `trials.csv`: los 350 ensayos completos.',
          '- `epochs.csv`: pérdidas train/validation por iteración o época. Random Forest no tiene épocas.',
          '- `models/`: 35 predictores exteriores y transformadores; CNN conserva pesos.',
          '- `predictions.csv`, `regional_metrics.csv`, `pairwise_statistics.csv`, `metrics.csv`.',
          '- `figures/`: cuatro gráficos en PNG, SVG y PDF.',
          '- `verification.json`: verificaciones de integridad y recarga de los 35 modelos, incluidas iteraciones fijas de CatBoost.',
          '- `artifact_hashes.json`: huellas de artefactos inmutables.',
          '- `evidence.zip`: paquete de evidencia, snapshot, código y modelos.', '',
          '## Aplicación y artículo', '',
          'Iniciar la web sin sembrar datos sintéticos:', '',
          '```powershell', 'powershell -ExecutionPolicy Bypass -File scripts/run_real_web.ps1', '```', '',
          'Abrir http://127.0.0.1:8000/investigacion. La investigación nacional real no valida los módulos clínicos históricos de demostración.',
          'Artículo revisado: `entregables/Articulo_NutriRisk_Datos_Reales.docx` y PDF. La copia anterior se conserva.', '',
          'Fuentes: https://data.unicef.org/resources/jme/ y https://api.worldbank.org/v2/. Procedencia y condiciones por indicador en `data/real/manifest.json`.']
(ROOT / 'entregables/Informe_Entrenamiento_Datos_Reales.md').write_text('\n'.join(lines), encoding='utf-8')
print('Informe_Entrenamiento_Datos_Reales.md')

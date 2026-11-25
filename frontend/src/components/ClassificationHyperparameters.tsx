import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api/client';
import { Card, ErrorBox, Loading } from './ui';
import { VisualExplanation } from './VisualExplanation';

type Data = Record<string, any>;

const labels: Record<string, string> = {
  n_estimators: 'Árboles',
  max_depth: 'Profundidad máx.',
  min_samples_leaf: 'Mín. muestras hoja',
  max_features: 'Frac. variables',
  iterations: 'Iteraciones',
  depth: 'Profundidad',
  learning_rate: 'Tasa aprendizaje',
  l2_leaf_reg: 'Regularización L2',
  reg_lambda: 'Regularización lambda',
  subsample: 'Submuestreo',
  hidden: 'Unidades LSTM',
  channels: 'Canales conv.',
  weight_decay: 'Decaimiento pesos',
  epochs: 'Épocas',
};

const regionNames: Record<string, string> = {
  'East Asia & Pacific': 'Asia oriental y Pacífico',
  'Europe & Central Asia': 'Europa y Asia central',
  'Latin America & Caribbean': 'América Latina y Caribe',
  'Middle East, North Africa, Afghanistan & Pakistan': 'Oriente Medio y N. de África',
  'North America': 'Norteamérica',
  'South Asia': 'Asia meridional',
  'Sub-Saharan Africa': 'África subsahariana',
};

const number = (x: unknown) => {
  if (typeof x === 'number') {
    return Number.isInteger(x) ? String(x) : x.toLocaleString('es-PE', { maximumFractionDigits: 4 });
  }
  return String(x ?? '—');
};

function ModelFoldTable({ modelInfo, folds }: { modelInfo: Data; folds: Data[] }) {
  const modelFolds = folds.filter((x: Data) => x.algorithm === modelInfo.algorithm);
  if (!modelFolds.length) return null;
  const paramKeys = Object.keys(modelFolds[0].hyperparameters);

  return (
    <div className="nr-model-config-block" key={modelInfo.algorithm}>
      <h4>
        <span>Modelo: <strong>{modelInfo.label}</strong></span>
        <span>7 regiones de prueba exterior</span>
      </h4>
      <div className="nr-dataset-table">
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ minWidth: '160px', textAlign: 'left' }}>Región evaluada</th>
              {paramKeys.map((key) => (
                <th key={key} style={{ textAlign: 'right' }}>
                  {labels[key] || key}
                </th>
              ))}
              <th style={{ textAlign: 'right', minWidth: '100px' }}>Recall prueba</th>
              <th style={{ textAlign: 'right', minWidth: '100px' }}>ROC-AUC prueba</th>
              <th style={{ textAlign: 'right', minWidth: '90px' }}>Log-loss</th>
            </tr>
          </thead>
          <tbody>
            {modelFolds.map((f: Data, idx: number) => {
              const test = f.metrics?.test || {};
              return (
                <tr key={idx}>
                  <td style={{ textAlign: 'left' }}>
                    <strong>{regionNames[f.region] || f.region}</strong>
                  </td>
                  {paramKeys.map((key) => (
                    <td key={key} style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                      {number(f.hyperparameters[key])}
                    </td>
                  ))}
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: '#0d9488', fontWeight: 650 }}>
                    {typeof test.recall === 'number' ? test.recall.toFixed(3) : 'No estimable'}
                  </td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: '#245b7c', fontWeight: 650 }}>
                    {typeof test.roc_auc === 'number' ? test.roc_auc.toFixed(3) : 'No estimable'}
                  </td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: '#64748b' }}>
                    {typeof test.log_loss === 'number' ? test.log_loss.toFixed(3) : '—'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ClassificationHyperparameters() {
  const query = useQuery({
    queryKey: ['research-classification'],
    queryFn: () => api.get<Data>('/research/real/classification'),
    retry: false,
  });
  const [model, setModel] = useState('random_forest');
  const [region, setRegion] = useState('');
  const [tableModel, setTableModel] = useState('all');

  if (query.isLoading) return <Loading label="Leyendo hiperparámetros de clasificación…" />;
  if (query.error || !query.data) return <ErrorBox message="La evidencia de clasificación todavía no está disponible." />;

  const r = query.data;
  const regions = Array.from(new Set(r.folds.map((x: Data) => x.region))) as string[];
  const chosen = region || regions[0];
  const fold = r.folds.find((x: Data) => x.algorithm === model && x.region === chosen);
  let best = Infinity;
  const trials = r.trials
    .filter((x: Data) => x.algorithm === model && x.region === chosen)
    .map((x: Data) => {
      best = Math.min(best, x.validation_log_loss);
      return { Ensayo: x.trial + 1, 'Log-loss': x.validation_log_loss, 'Mejor acumulado': best };
    });

  const activeModels = tableModel === 'all' ? r.models : r.models.filter((m: Data) => m.algorithm === tableModel);

  return (
    <>
      <div className="nr-section-heading">
        <div>
          <h2>Hiperparámetros de clasificación</h2>
          <p>350 ensayos reales. La selección utiliza log-loss interna, sin etiquetas de prueba.</p>
        </div>
      </div>
      <Card title="Configuración seleccionada y búsqueda real" subtitle="Cada selección corresponde a un ajuste que excluyó una región completa.">
        <div className="research-filters">
          <label>
            Clasificador
            <select
              aria-label="Modelo de hiperparámetros de clasificación"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            >
              {r.models.map((x: Data) => (
                <option key={x.algorithm} value={x.algorithm}>
                  {x.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Región excluida
            <select
              aria-label="Región de hiperparámetros de clasificación"
              value={chosen}
              onChange={(e) => setRegion(e.target.value)}
            >
              {regions.map((x) => (
                <option key={x} value={x}>
                  {regionNames[x] || x}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="nr-tuning-grid">
          <div className="nr-dataset-table">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Hiperparámetro</th>
                  <th>Valor seleccionado</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(fold.hyperparameters).map(([key, v]) => (
                  <tr key={key}>
                    <td>{labels[key] || key}</td>
                    <td>{number(v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ height: 300 }}>
            <ResponsiveContainer>
              <LineChart data={trials} margin={{ left: 5, right: 20, bottom: 15 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="Ensayo" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line isAnimationActive={false} dataKey="Log-loss" stroke="#9ab1bf" />
                <Line isAnimationActive={false} dataKey="Mejor acumulado" type="stepAfter" stroke="#0d9488" strokeWidth={3} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        <VisualExplanation
          interpretation={`La mejor pérdida interna de las diez configuraciones fue ${Math.min(...trials.map((x: Data) => x['Log-loss'])).toFixed(4)}. La línea verde muestra cuándo se encontró una configuración con menor pérdida.`}
          explanation="El optimizador TPE ajusta los parámetros con países internos apartados y resultados de 2022. Después se entrena el modelo final en los años permitidos y se evalúa en la región excluida de 2023."
          limitations="No se eligió el umbral con datos de prueba. Estos parámetros pertenecen a clasificación nacional; son diferentes de los del experimento de regresión."
        />
        <div className="nr-fold-metrics">
          {['train', 'validation', 'test'].map((stage) => (
            <div key={stage}>
              <span>{({ train: 'Entrenamiento', validation: 'Validación', test: 'Prueba externa' } as Data)[stage]}</span>
              <strong>
                {typeof fold.metrics[stage].recall === 'number' ? fold.metrics[stage].recall.toFixed(3) : 'No estimable'}{' '}
                <small>recall</small>
              </strong>
              <small>
                ROC-AUC{' '}
                {typeof fold.metrics[stage].roc_auc === 'number'
                  ? fold.metrics[stage].roc_auc.toFixed(3)
                  : 'No estimable: una sola clase'}
              </small>
            </div>
          ))}
        </div>
      </Card>
      <details className="nr-details nr-block-details">
        <summary>Ver las 35 configuraciones seleccionadas en tablas por modelo</summary>
        <p className="nr-caption" style={{ margin: '0.4rem 0 0.8rem' }}>
          Selecciona un modelo para ver sus hiperparámetros organizados en columnas independientes por región, junto con su desempeño en la prueba externa.
        </p>
        <div className="nr-sub-tabs">
          <button
            type="button"
            className="nr-sub-tab"
            aria-pressed={tableModel === 'all'}
            onClick={() => setTableModel('all')}
          >
            Todos los modelos (35)
          </button>
          {r.models.map((m: Data) => (
            <button
              key={m.algorithm}
              type="button"
              className="nr-sub-tab"
              aria-pressed={tableModel === m.algorithm}
              onClick={() => setTableModel(m.algorithm)}
            >
              {m.label} (7)
            </button>
          ))}
        </div>
        <div>
          {activeModels.map((m: Data) => (
            <ModelFoldTable key={m.algorithm} modelInfo={m} folds={r.folds} />
          ))}
        </div>
      </details>
    </>
  );
}

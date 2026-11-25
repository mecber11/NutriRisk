import { ExplainedChart, Interpretation } from '../components/Interpretation';
import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Bar as RBar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import {
  Badge,
  Card,
  CHART_COLORS,
  DataTable,
  Empty,
  ErrorBox,
  Field,
  Loading,
  MetricRow,
  PageHeader,
  dateTime,
  decimal,
  num,
  pct,
  pctValue,
} from '../components/ui';
import type { Column } from '../components/ui';
import type {
  ExperimentAlgorithms,
  ExperimentOut,
  ModelComparison,
  ModelMetrics,
  ModelOut,
  Page,
  RegionMetricsResponse,
} from '../types';

interface TrainingAccepted {
  message: string;
  experiment_ids: number[];
  task: string;
  algorithms: string[];
}

interface RegionRow extends ModelMetrics {
  region: string;
}

const ALGORITHM_FALLBACK = [
  { code: 'random_forest', label: 'Random Forest', description: 'Ensemble de árboles con bagging.' },
  { code: 'xgboost', label: 'XGBoost', description: 'Gradiente boosting regularizado.' },
  { code: 'catboost', label: 'CatBoost', description: 'Gradiente boosting con variables categóricas.' },
  { code: 'spatial_xgboost', label: 'XGBoost espacial', description: 'XGBoost con corrección espacial SAR.' },
  { code: 'cnn_lstm', label: 'CNN-LSTM espaciotemporal', description: 'Red neuronal para series por territorio.' },
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo completar la operación.';
}

function statusTone(status: string): 'ok' | 'info' | 'warning' | 'danger' | 'neutral' {
  switch (status.toUpperCase()) {
    case 'COMPLETED':
      return 'ok';
    case 'RUNNING':
      return 'info';
    case 'QUEUED':
      return 'warning';
    case 'FAILED':
    case 'ERROR':
      return 'danger';
    default:
      return 'neutral';
  }
}

export default function Models() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [experimentId, setExperimentId] = useState<number | null>(null);
  const [algorithms, setAlgorithms] = useState<string[]>(['xgboost']);
  const [cvStrategy, setCvStrategy] = useState('group_kfold_region');
  const [task, setTask] = useState('classification');
  const [target, setTarget] = useState('stunting');
  const [trainMessage, setTrainMessage] = useState<string | null>(null);
  const [trainError, setTrainError] = useState<string | null>(null);
  const [modelMessage, setModelMessage] = useState<string | null>(null);

  const canTrain = can('experiments', 'execute');
  const canActivate = can('models', 'update');

  const experimentsQuery = useQuery({
    queryKey: ['experiments', 'list'],
    queryFn: () => api.get<Page<ExperimentOut>>('/experiments', { page: 1, page_size: 50 }),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((item) => ['QUEUED', 'RUNNING'].includes(item.status.toUpperCase()))
        ? 5000
        : false;
    },
  });

  const experiments = experimentsQuery.data?.items ?? [];
  const hasRunning = experiments.some((item) => ['QUEUED', 'RUNNING'].includes(item.status.toUpperCase()));

  const modelsQuery = useQuery({
    queryKey: ['models', 'list'],
    queryFn: () => api.get<Page<ModelOut>>('/models', { page: 1, page_size: 50 }),
    refetchInterval: hasRunning ? 5000 : false,
  });

  const activeQuery = useQuery({
    queryKey: ['models', 'active'],
    queryFn: () => api.get<ModelOut>('/models/active'),
    retry: false,
  });

  const comparisonQuery = useQuery({
    queryKey: ['models', 'comparison'],
    queryFn: () => api.get<ModelComparison[]>('/models/comparison'),
  });

  const algorithmsQuery = useQuery({
    queryKey: ['experiments', 'algorithms'],
    queryFn: () => api.get<ExperimentAlgorithms>('/experiments/algorithms'),
  });

  const models = modelsQuery.data?.items ?? [];
  const active = activeQuery.data;
  const chosenExperimentId = experimentId ?? active?.experiment_id ?? experiments[0]?.id ?? null;
  const chosenExperiment = experiments.find((item) => item.id === chosenExperimentId);
  const spatialExperiment = experiments.find((item) => item.spatial_diagnostics?.moran?.available);
  const diagnosticsExperimentId =
    chosenExperiment?.spatial_diagnostics?.moran?.available
      ? chosenExperimentId
      : (spatialExperiment?.id ?? null);
  const diagnosticsIsChosen = diagnosticsExperimentId !== null && diagnosticsExperimentId === chosenExperimentId;

  const regionQuery = useQuery({
    queryKey: ['experiments', 'regions', chosenExperimentId],
    queryFn: () => api.get<RegionMetricsResponse>(`/experiments/${chosenExperimentId}/regions`),
    enabled: chosenExperimentId !== null,
  });

  const diagnosticsQuery = useQuery({
    queryKey: ['experiments', 'regions', 'diagnostics', diagnosticsExperimentId],
    queryFn: () => api.get<RegionMetricsResponse>(`/experiments/${diagnosticsExperimentId}/regions`),
    enabled: diagnosticsExperimentId !== null && !diagnosticsIsChosen,
  });

  const diagnostics = diagnosticsIsChosen
    ? regionQuery.data?.spatial_diagnostics
    : diagnosticsQuery.data?.spatial_diagnostics;
  const diagnosticsExperiment = experiments.find((item) => item.id === diagnosticsExperimentId);
  const regionRows = useMemo<RegionRow[]>(
    () =>
      Object.entries(regionQuery.data?.per_region ?? {}).map(([region, metrics]) => ({
        region,
        ...metrics,
      })),
    [regionQuery.data],
  );
  const regionChart = regionRows.map((row) => ({
    region: row.region,
    auc: (row.auc ?? 0) * 100,
  }));

  const trainMutation = useMutation({
    mutationFn: () =>
      api.post<TrainingAccepted>('/experiments/train', {
        algorithms,
        task,
        target,
        cv_strategy: cvStrategy,
        include_spatial: algorithms.includes('spatial_xgboost'),
        include_cnn_lstm: algorithms.includes('cnn_lstm'),
      }),
    onSuccess: (result) => {
      setTrainError(null);
      setTrainMessage(
        `${result.message} Experimentos #${result.experiment_ids.join(', #')}. La página se actualizará cada 5 segundos.`,
      );
      void queryClient.invalidateQueries({ queryKey: ['experiments'] });
      void queryClient.invalidateQueries({ queryKey: ['models'] });
    },
    onError: (error) => {
      setTrainMessage(null);
      setTrainError(errorMessage(error));
    },
  });

  const activateMutation = useMutation({
    mutationFn: (modelId: number) => api.post<ModelOut>(`/models/${modelId}/activate`),
    onSuccess: (model) => {
      setModelMessage(`Modelo ${model.name} v${model.version} activado.`);
      void queryClient.invalidateQueries({ queryKey: ['models'] });
      void queryClient.invalidateQueries({ queryKey: ['experiments'] });
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: (error) => setModelMessage(errorMessage(error)),
  });

  const modelColumns: Column<ModelComparison>[] = [
    {
      key: 'name',
      header: 'Modelo',
      render: (row) => (
        <div>
          <div style={{ fontWeight: 600 }}>
            {row.name} {row.is_best && <Badge tone="ok">Mejor</Badge>}
          </div>
          <div style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>
            v{row.version} · {row.algorithm}
          </div>
        </div>
      ),
    },
    { key: 'auc', header: 'AUC', align: 'right', render: (row) => pct(row.auc) },
    { key: 'f1_optimal', header: 'F1 óptimo', align: 'right', render: (row) => decimal(row.f1_optimal, 3) },
    { key: 'precision', header: 'Precisión', align: 'right', render: (row) => decimal(row.precision, 3) },
    { key: 'recall', header: 'Recall', align: 'right', render: (row) => decimal(row.recall, 3) },
    { key: 'threshold', header: 'Umbral', align: 'right', render: (row) => decimal(row.threshold, 3) },
    { key: 'rmse', header: 'RMSE', align: 'right', render: (row) => decimal(row.rmse, 3) },
    { key: 'mae', header: 'MAE', align: 'right', render: (row) => decimal(row.mae, 3) },
  ];

  const regionColumns: Column<RegionRow>[] = [
    { key: 'region', header: 'Región' },
    { key: 'n', header: 'Registros', align: 'right', render: (row) => num(row.n) },
    { key: 'prevalence', header: 'Prevalencia', align: 'right', render: (row) => pct(row.prevalence) },
    { key: 'auc', header: 'AUC', align: 'right', render: (row) => pct(row.auc) },
    { key: 'f1', header: 'F1', align: 'right', render: (row) => decimal(row.f1, 3) },
    { key: 'recall', header: 'Recall', align: 'right', render: (row) => pct(row.recall) },
    { key: 'precision', header: 'Precisión', align: 'right', render: (row) => pct(row.precision) },
  ];

  const experimentColumns: Column<ExperimentOut>[] = [
    { key: 'id', header: 'ID', render: (row) => `#${row.id}` },
    { key: 'algorithm', header: 'Algoritmo' },
    {
      key: 'status',
      header: 'Estado',
      render: (row) => <Badge tone={statusTone(row.status)}>{row.status}</Badge>,
    },
    { key: 'auc', header: 'AUC', align: 'right', render: (row) => pct(row.metrics?.auc) },
    {
      key: 'duration',
      header: 'Duración',
      align: 'right',
      render: (row) =>
        row.duration_seconds !== null && row.duration_seconds !== undefined
          ? `${decimal(row.duration_seconds, 1)} s`
          : '—',
    },
    { key: 'created_at', header: 'Creado', render: (row) => dateTime(row.created_at) },
  ];

  const algorithmOptions = algorithmsQuery.data?.algorithms ?? ALGORITHM_FALLBACK;
  const cvOptions = algorithmsQuery.data?.cv_strategies ?? [
    { code: 'group_kfold_region', label: 'GroupKFold por región', description: '5 pliegues agrupados por región.' },
  ];
  const taskOptions = algorithmsQuery.data?.tasks ?? ['classification', 'regression'];
  const targetOptions = algorithmsQuery.data?.targets ?? ['stunting', 'wasting', 'underweight'];

  function toggleAlgorithm(code: string) {
    setAlgorithms((current) =>
      current.includes(code) ? current.filter((item) => item !== code) : [...current, code],
    );
  }

  return (
    <>
      <PageHeader
        title="Modelos y experimentos"
        subtitle="Gobierno del ciclo de vida de los modelos: entrenamiento, validación espacial, activación y comparación."
        actions={
          active ? (
            <Badge tone="ok">
              Activo: {active.name} v{active.version}
            </Badge>
          ) : undefined
        }
      />

      {hasRunning && (
        <div className="notice" data-tone="info">
          <span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
          <span>Hay experimentos en cola o en ejecución. La información se actualiza cada 5 segundos.</span>
        </div>
      )}
      {modelMessage && (
        <div className="notice" data-tone="info">
          {modelMessage}
        </div>
      )}

      {modelsQuery.isError && <ErrorBox message={errorMessage(modelsQuery.error)} />}
      {modelsQuery.isLoading && <Loading label="Cargando modelos entrenados…" />}
      {!modelsQuery.isLoading && models.length === 0 && (
        <Empty title="Sin modelos entrenados" hint="Ejecute un experimento para generar el primer modelo." />
      )}

      <div className="grid grid-3">
        {models.map((model) => {
          const metrics = model.metrics ?? {};
          const topFeatures = Object.entries(model.feature_importance ?? {})
            .sort((a, b) => b[1] - a[1])
            .slice(0, 3);
          return (
            <Card
              key={model.id}
              title={`${model.name} v${model.version}`}
              subtitle={`${model.algorithm} · ${model.target ?? 'stunting'}`}
              actions={model.is_active ? <Badge tone="ok">Activo</Badge> : <Badge>En reserva</Badge>}
            >
              <MetricRow label="AUC" value={pct(metrics.auc)} />
              <MetricRow label="F1" value={decimal(metrics.f1, 3)} />
              <MetricRow label="F1 óptimo" value={decimal(metrics.f1_optimal, 3)} />
              <MetricRow label="Recall" value={pct(metrics.recall_optimal ?? metrics.recall)} />
              <MetricRow label="Umbral óptimo" value={decimal(metrics.threshold_optimal ?? metrics.screening_threshold, 3)} />
              <MetricRow label="Entrenado" value={dateTime(model.trained_at)} />
              {topFeatures.length > 0 && (
                <div style={{ marginTop: '0.55rem' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--muted)', marginBottom: '0.25rem' }}>
                    Variables dominantes
                  </div>
                  <div className="chip-row">
                    {topFeatures.map(([feature, importance]) => (
                      <Badge key={feature} tone="info">
                        {feature} · {pct(importance, 1)}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {!model.is_active && canActivate && (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  style={{ marginTop: '0.75rem' }}
                  disabled={activateMutation.isPending}
                  onClick={() => activateMutation.mutate(model.id)}
                >
                  {activateMutation.isPending ? 'Activando…' : 'Activar modelo'}
                </button>
              )}
            </Card>
          );
        })}
      </div>

      <Card
        title="Comparación de modelos"
        subtitle="Métricas de validación y umbrales operativos; el mejor modelo se marca automáticamente."
        actions={<Badge tone="brand">{comparisonQuery.data?.length ?? 0} modelos</Badge>}
      >
        {comparisonQuery.isError && <ErrorBox message={errorMessage(comparisonQuery.error)} />}
        {comparisonQuery.isLoading && <Loading label="Cargando comparación…" />}
        {comparisonQuery.data && (
          <DataTable interpretationId="models"
            columns={modelColumns}
            rows={comparisonQuery.data}
            getKey={(row) => row.model_id}
            empty="Sin modelos para comparar"
          />
        )}
      </Card>

      {canTrain && (
        <Card
          title="Entrenar nuevos modelos"
          subtitle="Seleccione algoritmos y estrategia de validación. El entrenamiento se ejecuta en segundo plano."
        >
          {trainError && <ErrorBox message={trainError} />}
          {trainMessage && (
            <div className="notice" data-tone="ok">
              {trainMessage}
            </div>
          )}
          <div className="grid grid-2">
            <div>
              <div style={{ fontSize: '0.73rem', color: 'var(--muted)', fontWeight: 600, marginBottom: '0.4rem' }}>
                Algoritmos
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                {algorithmOptions.map((algorithm) => (
                  <label
                    key={algorithm.code}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.85rem' }}
                    title={algorithm.description}
                  >
                    <input
                      type="checkbox"
                      checked={algorithms.includes(algorithm.code)}
                      onChange={() => toggleAlgorithm(algorithm.code)}
                    />
                    {algorithm.label}
                  </label>
                ))}
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              <Field label="Estrategia de validación">
                <select value={cvStrategy} onChange={(event) => setCvStrategy(event.target.value)}>
                  {cvOptions.map((option) => (
                    <option key={option.code} value={option.code}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="grid grid-2">
                <Field label="Tarea">
                  <select value={task} onChange={(event) => setTask(event.target.value)}>
                    {taskOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Objetivo">
                  <select value={target} onChange={(event) => setTarget(event.target.value)}>
                    {targetOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
              <div className="chip-row">
                <Badge tone={algorithms.includes('spatial_xgboost') ? 'brand' : 'neutral'}>
                  Ajuste espacial {algorithms.includes('spatial_xgboost') ? 'incluido' : 'no incluido'}
                </Badge>
                <Badge tone={algorithms.includes('cnn_lstm') ? 'brand' : 'neutral'}>
                  CNN-LSTM {algorithms.includes('cnn_lstm') ? 'incluido' : 'no incluido'}
                </Badge>
              </div>
              <button
                type="button"
                className="btn btn-primary"
                disabled={algorithms.length === 0 || trainMutation.isPending}
                onClick={() => trainMutation.mutate()}
              >
                {trainMutation.isPending ? 'Encolando entrenamiento…' : 'Iniciar entrenamiento'}
              </button>
              <small style={{ color: 'var(--muted)' }}>
                El ajuste espacial y la red CNN-LSTM se activan automáticamente al seleccionar sus
                algoritmos. El conjunto de datos es el sintético activo.
              </small>
            </div>
          </div>
        </Card>
      )}

      <Card
        title="Experimentos recientes"
        subtitle="Estado del ciclo de entrenamiento y validación."
        actions={<Badge tone="brand">{experiments.length}</Badge>}
      >
        {experimentsQuery.isError && <ErrorBox message={errorMessage(experimentsQuery.error)} />}
        {experimentsQuery.isLoading && <Loading label="Cargando experimentos…" />}
        {experimentsQuery.data && (
          <DataTable interpretationId="models"
            columns={experimentColumns}
            rows={experiments.slice(0, 10)}
            getKey={(row) => row.id}
            empty="Sin experimentos registrados"
          />
        )}
      </Card>

      <Card
        title="Validación por región y diagnóstico espacial"
        subtitle="Desempeño del experimento seleccionado y autocorrelación espacial de los residuos."
        actions={
          <Field label="Experimento">
            <select
              value={chosenExperimentId ?? ''}
              onChange={(event) => setExperimentId(Number(event.target.value))}
            >
              {experiments.map((experiment) => (
                <option key={experiment.id} value={experiment.id}>
                  #{experiment.id} · {experiment.algorithm} · {experiment.status}
                </option>
              ))}
            </select>
          </Field>
        }
      >
        <div className="grid grid-sidebar">
          <div>
            {regionQuery.isError && <ErrorBox message={errorMessage(regionQuery.error)} />}
            {regionQuery.isLoading && <Loading label="Cargando métricas por región…" />}
            {regionQuery.data && regionRows.length === 0 && (
              <Empty title="Sin métricas regionales" hint="El experimento aún no ha finalizado." />
            )}
            {regionRows.length > 0 && (
              <>
                <ExplainedChart explanationId="regional" width="100%" height={230}>
                  <BarChart data={regionChart} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="region" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} unit="%" />
                    <Tooltip formatter={(value) => pctValue(Number(value), 2)} />
                    <RBar dataKey="auc" name="AUC" fill={CHART_COLORS[0]} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ExplainedChart>
                <DataTable interpretationId="regional"
                  columns={regionColumns}
                  rows={regionRows}
                  getKey={(row) => row.region}
                  empty="Sin métricas regionales"
                />
                <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--muted)' }}>
                  Experimento #{chosenExperimentId} · {chosenExperiment?.algorithm ?? '—'} · validación{' '}
                  {regionQuery.data?.cv_strategy ?? '—'} · {num(regionQuery.data?.per_region ? Object.keys(regionQuery.data.per_region).length : 0)} regiones
                </div>
              </>
            )}
          </div>

          <div>
            {diagnosticsQuery.isError && !diagnostics && <ErrorBox message={errorMessage(diagnosticsQuery.error)} />}
            {!diagnostics && diagnosticsQuery.isLoading && <Loading label="Cargando diagnóstico espacial…" />}
            {diagnostics?.moran?.available ? (
              <>
                {diagnosticsExperimentId !== chosenExperimentId && (
                  <div className="notice" data-tone="warning">
                    El experimento seleccionado no reporta Moran&apos;s I. Se muestran los diagnósticos del
                    experimento #{diagnosticsExperimentId} ({diagnosticsExperiment?.algorithm ?? 'espacial'}).
                  </div>
                )}
                <MetricRow label="Moran's I" value={decimal(diagnostics.moran.i, 4)} />
                <MetricRow label="I esperado" value={decimal(diagnostics.moran.expected_i, 4)} />
                <MetricRow label="z-score" value={decimal(diagnostics.moran.z_score, 3)} />
                <MetricRow label="p-valor" value={decimal(diagnostics.moran.p_value, 3)} />
                <MetricRow label="Unidades espaciales" value={num(diagnostics.moran.units)} />
                {diagnostics.moran.interpretation && (
                  <p style={{ fontSize: '0.78rem', color: 'var(--muted)', marginTop: '0.4rem' }}>
                    {diagnostics.moran.interpretation}.
                  </p>
                )}
                <div style={{ marginTop: '0.65rem' }}>
                  <MetricRow label="Rho SAR" value={decimal(diagnostics.models?.sar?.rho, 4)} />
                  <MetricRow label="Pseudo R² SAR" value={decimal(diagnostics.models?.sar?.pseudo_r2, 4)} />
                  <MetricRow label="Lambda SEM" value={decimal(diagnostics.models?.sem?.lambda, 4)} />
                  <MetricRow label="Pseudo R² SEM" value={decimal(diagnostics.models?.sem?.pseudo_r2, 4)} />
                  <MetricRow label="R² OLS" value={decimal(diagnostics.models?.ols?.r2, 4)} />
                  <MetricRow label="R² local medio GWR" value={decimal(diagnostics.models?.gwr?.mean_local_r2, 4)} />
                  <MetricRow
                    label="Ancho de banda GWR"
                    value={
                      diagnostics.models?.gwr?.bandwidth_km !== undefined
                        ? `${decimal(diagnostics.models.gwr.bandwidth_km, 1)} km`
                        : '—'
                    }
                  />
                  {diagnostics.correction?.available && (
                    <MetricRow label="ΔAUC por corrección espacial" value={decimal(diagnostics.correction.delta_auc, 4)} />
                  )}
                </div>
                {diagnostics.summary && diagnostics.summary.length > 0 && (
                  <div style={{ marginTop: '0.6rem', fontSize: '0.78rem', color: 'var(--muted)' }}>
                    {diagnostics.summary.map((line) => (
                      <p key={line} style={{ margin: '0 0 0.25rem' }}>
                        {line}
                      </p>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <Empty
                title="Sin diagnóstico espacial"
                hint="Seleccione un experimento con ajuste espacial (por ejemplo, spatial_xgboost) para ver Moran's I, rho SAR y lambda SEM."
              />
            )}
          </div>
        </div>
      </Card>
    </>
  );
}

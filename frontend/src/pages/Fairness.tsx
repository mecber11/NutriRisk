import { ExplainedChart, Interpretation } from '../components/Interpretation';
import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Bar as RBar,
  BarChart,
  CartesianGrid,
  Legend,
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
  FairnessAttributes,
  FairnessGroup,
  FairnessResult,
  FairnessSummary,
  XaiModel,
} from '../types';

interface XaiModelsResponse {
  models: XaiModel[];
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo calcular la equidad.';
}

export default function Fairness() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [modelId, setModelId] = useState<number | null>(null);
  const [attribute, setAttribute] = useState('');
  const [threshold, setThreshold] = useState('0.2');
  const [runMessage, setRunMessage] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const canRun = can('fairness', 'execute');

  const modelsQuery = useQuery({
    queryKey: ['xai', 'models'],
    queryFn: () => api.get<XaiModelsResponse>('/xai/models'),
  });

  const attributesQuery = useQuery({
    queryKey: ['fairness', 'attributes'],
    queryFn: () => api.get<FairnessAttributes>('/fairness/attributes'),
  });

  const models = modelsQuery.data?.models ?? [];
  const attributes = attributesQuery.data?.attributes ?? [];

  useEffect(() => {
    if (modelId === null && models.length > 0) {
      const active = models.find((model) => model.is_active);
      setModelId(active ? active.id : models[0].id);
    }
  }, [models, modelId]);

  useEffect(() => {
    if (attributesQuery.data && threshold === '0.2') {
      setThreshold(String(attributesQuery.data.threshold));
    }
  }, [attributesQuery.data, threshold]);

  const summaryQuery = useQuery({
    queryKey: ['fairness', 'summary', modelId],
    queryFn: () => api.get<FairnessSummary>(`/fairness/${modelId}`),
    enabled: modelId !== null,
  });

  const selectedAttribute = attribute || attributes[0]?.code || '';
  const summary = summaryQuery.data;
  const selectedResult =
    summary?.attributes.find((item) => item.sensitive_attribute === selectedAttribute) ??
    summary?.attributes[0];

  const chartData = useMemo(
    () =>
      (selectedResult?.groups ?? []).map((group) => ({
        group: group.group,
        selection_rate: group.selection_rate * 100,
        tpr: (group.tpr ?? 0) * 100,
      })),
    [selectedResult],
  );

  const runMutation = useMutation({
    mutationFn: () =>
      api.post<FairnessResult[]>('/fairness/run', {
        model_id: modelId,
        attributes: [selectedAttribute],
        threshold: Number(threshold),
      }),
    onSuccess: (results) => {
      setRunError(null);
      const result = results[0];
      setRunMessage(
        result
          ? `Equidad recalculada para ${selectedAttribute}: ${
              result.is_acceptable ? 'aceptable' : 'requiere revisión'
            } (disparidad máxima ${pct(result.max_disparity)}).`
          : 'Cálculo de equidad ejecutado.',
      );
      void queryClient.invalidateQueries({ queryKey: ['fairness', 'summary'] });
    },
    onError: (error) => {
      setRunMessage(null);
      setRunError(errorMessage(error));
    },
  });

  const groupColumns: Column<FairnessGroup>[] = [
    { key: 'group', header: 'Grupo' },
    { key: 'n', header: 'Registros', align: 'right', render: (row) => num(row.n) },
    {
      key: 'selection_rate',
      header: 'Tasa de selección',
      align: 'right',
      render: (row) => pct(row.selection_rate),
    },
    { key: 'tpr', header: 'TPR', align: 'right', render: (row) => pct(row.tpr) },
    { key: 'fpr', header: 'FPR', align: 'right', render: (row) => pct(row.fpr) },
    { key: 'precision', header: 'Precisión', align: 'right', render: (row) => pct(row.precision) },
    { key: 'recall', header: 'Recall', align: 'right', render: (row) => pct(row.recall) },
    { key: 'accuracy', header: 'Exactitud', align: 'right', render: (row) => pct(row.accuracy) },
    { key: 'auc', header: 'AUC', align: 'right', render: (row) => pct(row.auc) },
    { key: 'mean_score', header: 'Score medio', align: 'right', render: (row) => pct(row.mean_score) },
    {
      key: 'stunting_rate',
      header: 'Prevalencia',
      align: 'right',
      render: (row) => pct(row.stunting_rate),
    },
  ];

  return (
    <>
      <PageHeader
        title="Equidad y sesgo del modelo"
        subtitle="Evaluación de paridad demográfica y odds igualadas por atributos sensibles."
        actions={
          summary ? (
            <Badge tone={summary.overall_acceptable ? 'ok' : 'warning'}>
              {summary.overall_acceptable ? 'Modelo aceptable' : 'Requiere revisión'}
            </Badge>
          ) : undefined
        }
      />

      <Card
        title="Configuración del análisis"
        subtitle="Seleccione el modelo y el atributo sensible; ajuste el umbral de disparidad permitido."
      >
        <div className="filters">
          <Field label="Modelo">
            <select
              value={modelId ?? ''}
              disabled={!models.length}
              onChange={(event) => setModelId(Number(event.target.value))}
            >
              {!models.length && <option value="">Sin modelos</option>}
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name} v{model.version} {model.is_active ? '· activo' : ''}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Atributo sensible">
            <select
              value={selectedAttribute}
              disabled={!attributes.length}
              onChange={(event) => setAttribute(event.target.value)}
            >
              {attributes.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Umbral de disparidad">
            <input
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={threshold}
              style={{ width: 110 }}
              onChange={(event) => setThreshold(event.target.value)}
            />
          </Field>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={!canRun || runMutation.isPending || !selectedAttribute}
            onClick={() => runMutation.mutate()}
            title={canRun ? undefined : 'Su rol no permite ejecutar cálculos de equidad'}
          >
            {runMutation.isPending ? 'Recalculando…' : 'Recalcular equidad'}
          </button>
        </div>
        <div className="chip-row" style={{ marginTop: '0.7rem' }}>
          {summary?.attributes.map((result) => (
            <button
              key={result.sensitive_attribute}
              type="button"
              className="chip"
              onClick={() => setAttribute(result.sensitive_attribute)}
              style={
                result.sensitive_attribute === selectedResult?.sensitive_attribute
                  ? { borderColor: 'var(--brand)', color: 'var(--brand)' }
                  : undefined
              }
            >
              {attributes.find((item) => item.code === result.sensitive_attribute)?.label ??
                result.sensitive_attribute}
              <Badge tone={result.is_acceptable ? 'ok' : 'warning'}>
                {result.is_acceptable ? 'Aceptable' : 'Revisar'}
              </Badge>
            </button>
          ))}
        </div>
      </Card>

      {runError && <ErrorBox message={runError} />}
      {runMessage && (
        <div className="notice" data-tone="ok">
          {runMessage}
        </div>
      )}
      {attributesQuery.isError && <ErrorBox message={errorMessage(attributesQuery.error)} />}
      {summaryQuery.isError && <ErrorBox message={errorMessage(summaryQuery.error)} />}
      {summaryQuery.isLoading && <Loading label="Calculando métricas de equidad…" />}

      {selectedResult && (
        <>
          <div className="kpi-grid">
            <div className="kpi" data-severity={selectedResult.is_acceptable ? 'ok' : 'critical'}>
              <div className="kpi-label">Estado del atributo</div>
              <div className="kpi-value" style={{ fontSize: '1.25rem' }}>
                <Badge tone={selectedResult.is_acceptable ? 'ok' : 'warning'}>
                  {selectedResult.is_acceptable ? 'Aceptable' : 'Requiere revisión'}
                </Badge>
              </div>
              <div className="kpi-foot">
                <span>{selectedAttribute}</span>
              </div>
            </div>
            <div className="kpi" data-severity={selectedResult.is_acceptable ? 'neutral' : 'warning'}>
              <div className="kpi-label">Disparidad máxima</div>
              <div className="kpi-value">{pct(selectedResult.max_disparity)}</div>
              <div className="kpi-foot">
                <span>Umbral permitido: {pct(selectedResult.threshold)}</span>
              </div>
            </div>
            <div className="kpi" data-severity="neutral">
              <div className="kpi-label">Razón entre grupos</div>
              <div className="kpi-value">{decimal(selectedResult.ratio, 3)}</div>
              <div className="kpi-foot">
                <span>1,000 indica paridad perfecta</span>
              </div>
            </div>
            <div className="kpi" data-severity="neutral">
              <div className="kpi-label">Generado</div>
              <div className="kpi-value" style={{ fontSize: '1.05rem' }}>
                {dateTime(selectedResult.generated_at)}
              </div>
              <div className="kpi-foot">
                <span>{selectedResult.metric}</span>
              </div>
            </div>
          </div>

          <div className="grid grid-sidebar">
            <Card
              title="Tasa de selección y TPR por grupo"
              subtitle="La tasa de selección mide cuántos niños son marcados en riesgo; el TPR, cuántos casos reales se detectan."
            >
              {chartData.length === 0 ? (
                <Empty title="Sin grupos para el atributo" />
              ) : (
                <ExplainedChart explanationId="fairness" width="100%" height={300}>
                  <BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="group" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} unit="%" />
                    <Tooltip formatter={(value) => pctValue(Number(value), 2)} />
                    <Legend />
                    <RBar
                      dataKey="selection_rate"
                      name="Tasa de selección"
                      fill={CHART_COLORS[0]}
                      radius={[4, 4, 0, 0]}
                    />
                    <RBar dataKey="tpr" name="TPR" fill={CHART_COLORS[1]} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ExplainedChart>
              )}
            </Card>

            <Card title="Resumen del atributo" subtitle={selectedAttribute}>
              <MetricRow label="Atributo" value={selectedAttribute} />
              <MetricRow label="Métrica" value={selectedResult.metric} />
              <MetricRow label="Grupos" value={num(selectedResult.groups.length)} />
              <MetricRow label="Disparidad máxima" value={pct(selectedResult.max_disparity)} />
              <MetricRow label="Umbral" value={pct(selectedResult.threshold)} />
              <MetricRow label="Razón" value={decimal(selectedResult.ratio, 3)} />
              <MetricRow
                label="Resultado"
                value={
                  <Badge tone={selectedResult.is_acceptable ? 'ok' : 'warning'}>
                    {selectedResult.is_acceptable ? 'Aceptable' : 'Revisar'}
                  </Badge>
                }
              />
              <p style={{ marginTop: '0.7rem', fontSize: '0.78rem', color: 'var(--muted)' }}>
                La disparidad máxima se compara contra el umbral configurado. Si la supera, el atributo
                requiere revisión antes de desplegar el modelo.
              </p>
            </Card>
          </div>

          <Card
            title="Métricas por grupo"
            subtitle={`Desempeño desagregado por ${selectedAttribute}.`}
            actions={<Badge tone="brand">{num(selectedResult.groups.length)} grupos</Badge>}
          >
            <DataTable interpretationId="fairness"
              columns={groupColumns}
              rows={selectedResult.groups}
              getKey={(row) => row.group}
              empty="Sin grupos evaluados"
            />
          </Card>

          {summary?.notes && summary.notes.length > 0 && (
            <Card title="Notas del análisis">
              <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.83rem', color: 'var(--muted)' }}>
                {summary.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}

      {!summaryQuery.isLoading && !summaryQuery.isError && !selectedResult && (
        <Empty
          title="Sin resultados de equidad"
          hint="El modelo seleccionado no tiene atributos calculados. Ejecute el análisis con el botón Recalcular."
        />
      )}
    </>
  );
}

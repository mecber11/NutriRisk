import { ExplainedChart, Interpretation } from '../components/Interpretation';
import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../api/client';
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
  RiskBadge,
  Tabs,
  decimal,
  num,
  pct,
  pctValue,
} from '../components/ui';
import type { Column } from '../components/ui';
import type {
  ChildListPage,
  DependenceResponse,
  GlobalExplanation,
  LocalExplanation,
  ShapFeature,
  TerritoryExplanation,
  XaiModel,
} from '../types';

interface XaiModelsResponse {
  models: XaiModel[];
}

interface TerritoryOption {
  id: number;
  code: string;
  name: string;
  region: string;
}

interface TerritoryListResponse {
  items: TerritoryOption[];
  total: number;
}

type Tab = 'global' | 'child' | 'territory';

const TAB_OPTIONS: { value: Tab; label: string }[] = [
  { value: 'global', label: 'Global' },
  { value: 'child', label: 'Niño' },
  { value: 'territory', label: 'Territorio' },
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo calcular la explicación.';
}

function directionTone(direction: string): 'danger' | 'ok' | 'neutral' {
  const value = direction.toLowerCase();
  if (value.includes('pos') || value.includes('inc')) return 'danger';
  if (value.includes('neg') || value.includes('dec')) return 'ok';
  return 'neutral';
}

function directionLabel(direction: string): string {
  const tone = directionTone(direction);
  if (tone === 'danger') return 'Aumenta';
  if (tone === 'ok') return 'Reduce';
  return direction;
}

export default function Explainability() {
  const [tab, setTab] = useState<Tab>('global');
  const [modelId, setModelId] = useState<number | null>(null);
  const [childInput, setChildInput] = useState('');
  const [childSubmitted, setChildSubmitted] = useState('');
  const [territoryId, setTerritoryId] = useState<number | null>(null);
  const [dependenceFeature, setDependenceFeature] = useState<string | null>(null);

  const modelsQuery = useQuery({
    queryKey: ['xai', 'models'],
    queryFn: () => api.get<XaiModelsResponse>('/xai/models'),
  });

  const territoriesQuery = useQuery({
    queryKey: ['geo', 'territories'],
    queryFn: () => api.get<TerritoryListResponse>('/geo/territories'),
  });

  const models = modelsQuery.data?.models ?? [];
  const territories = territoriesQuery.data?.items ?? [];

  useEffect(() => {
    if (modelId === null && models.length > 0) {
      const active = models.find((model) => model.is_active);
      setModelId(active ? active.id : models[0].id);
    }
  }, [models, modelId]);

  useEffect(() => {
    if (territoryId === null && territories.length > 0) {
      const first = territories.find((territory) => territory.code === 'T01') ?? territories[0];
      setTerritoryId(first.id);
    }
  }, [territories, territoryId]);

  const globalQuery = useQuery({
    queryKey: ['xai', 'global', modelId],
    queryFn: () => api.get<GlobalExplanation>('/xai/global', { model_id: modelId, top_n: 12 }),
    enabled: modelId !== null,
  });

  const globalData = globalQuery.data;
  const features = globalData?.features ?? [];
  const activeFeature =
    dependenceFeature && features.some((feature) => feature.feature === dependenceFeature)
      ? dependenceFeature
      : (features[0]?.feature ?? null);

  const dependenceQuery = useQuery({
    queryKey: ['xai', 'dependence', modelId, activeFeature],
    queryFn: () =>
      api.get<DependenceResponse>('/xai/dependence', {
        feature: activeFeature,
        model_id: modelId,
      }),
    enabled: modelId !== null && activeFeature !== null,
  });
  const dependence = dependenceQuery.data;

  const samplesQuery = useQuery({
    queryKey: ['indicators', 'children', 'xai-samples'],
    queryFn: () => api.get<ChildListPage>('/indicators/children', { page: 1, page_size: 4 }),
    enabled: tab === 'child',
  });

  const childSearchQuery = useQuery({
    queryKey: ['indicators', 'children', 'xai-search', childSubmitted],
    queryFn: () =>
      api.get<ChildListPage>('/indicators/children', {
        search: childSubmitted,
        page: 1,
        page_size: 5,
      }),
    enabled: childSubmitted.length > 0,
  });

  const childMatch = useMemo(() => {
    const items = childSearchQuery.data?.items ?? [];
    if (!childSubmitted) return null;
    return (
      items.find((item) => item.child.code.toUpperCase() === childSubmitted.toUpperCase()) ??
      items[0] ??
      null
    );
  }, [childSearchQuery.data, childSubmitted]);

  const childId = childMatch?.child.id;

  const childQuery = useQuery({
    queryKey: ['xai', 'child', childId, modelId],
    queryFn: () => {
      if (!childId) throw new Error('Niño no disponible.');
      return api.get<LocalExplanation>(`/xai/child/${childId}`, { model_id: modelId });
    },
    enabled: Boolean(childId) && modelId !== null,
  });

  const territoryQuery = useQuery({
    queryKey: ['xai', 'territory', territoryId],
    queryFn: () => {
      if (!territoryId) throw new Error('Territorio no disponible.');
      return api.get<TerritoryExplanation>(`/xai/territory/${territoryId}`);
    },
    enabled: territoryId !== null,
  });

  function searchChild(value?: string) {
    const code = (value ?? childInput).trim();
    if (!code) return;
    setChildInput(code);
    setChildSubmitted(code);
  }

  const featureColumns: Column<ShapFeature>[] = [
    { key: 'label', header: 'Variable' },
    {
      key: 'mean_abs_shap',
      header: 'Impacto medio |SHAP|',
      align: 'right',
      render: (row) => decimal(row.mean_abs_shap, 4),
    },
    { key: 'share', header: 'Participación', align: 'right', render: (row) => pct(row.share, 1) },
    {
      key: 'direction',
      header: 'Sentido',
      render: (row) => <Badge tone={directionTone(row.direction)}>{directionLabel(row.direction)}</Badge>,
    },
  ];

  const sortedContributions = useMemo(
    () =>
      [...(childQuery.data?.contributions ?? [])].sort(
        (a, b) => Math.abs(b.contribution) - Math.abs(a.contribution),
      ),
    [childQuery.data],
  );

  return (
    <>
      <PageHeader
        title="Explicabilidad del modelo"
        subtitle="Contribuciones SHAP globales, por niño y por territorio para auditar las predicciones."
        actions={
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
        }
      />

      {modelsQuery.isError && <ErrorBox message={errorMessage(modelsQuery.error)} />}
      {modelsQuery.isLoading && <Loading label="Cargando modelos explicables…" />}

      <Tabs value={tab} options={TAB_OPTIONS} onChange={setTab} />

      {tab === 'global' && (
        <>
          {globalQuery.isError && <ErrorBox message={errorMessage(globalQuery.error)} />}
          {globalQuery.isLoading && <Loading label="Calculando valores SHAP globales…" />}
          {!globalQuery.isLoading && !globalQuery.isError && features.length === 0 && (
            <Empty
              title="Sin explicación global"
              hint="El modelo seleccionado no reporta valores SHAP o no hay datos disponibles."
            />
          )}
          {globalData && features.length > 0 && (
            <>
              <Card
                title="Importancia global de variables"
                subtitle={`Impacto medio absoluto de cada variable en el riesgo predicho · ${num(
                  globalData.n_samples,
                )} muestras`}
                actions={<Badge tone="brand">{globalData.algorithm}</Badge>}
              >
                <ExplainedChart explanationId="shap" width="100%" height={380}>
                  <BarChart
                    data={features}
                    layout="vertical"
                    margin={{ top: 5, right: 34, bottom: 5, left: 12 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(value) => Number(value).toFixed(2)} />
                    <YAxis
                      type="category"
                      dataKey="label"
                      width={190}
                      tick={{ fontSize: 11 }}
                    />
                    <Tooltip formatter={(value) => decimal(Number(value), 4)} />
                    <Bar
                      dataKey="mean_abs_shap"
                      name="Impacto medio |SHAP|"
                      fill={CHART_COLORS[0]}
                      radius={[0, 4, 4, 0]}
                    />
                  </BarChart>
                </ExplainedChart>
                <div className="legend">
                  <span>Valor base del modelo: {pct(globalData.base_value)}</span>
                  <span>Atribución media absoluta sobre probabilidad de riesgo.</span>
                </div>
              </Card>

              <div className="grid grid-2" style={{ marginTop: '1rem' }}>
                <Card title="Detalle de variables" subtitle="Participación y sentido del efecto.">
                  <DataTable interpretationId="shap"
                    columns={featureColumns}
                    rows={features}
                    getKey={(row) => row.feature}
                    empty="Sin variables"
                  />
                </Card>

                <Card
                  title="Dependencia SHAP"
                  subtitle="Relación entre el valor de una variable y su contribución al riesgo."
                >
                  <Field label="Variable">
                    <select
                      value={activeFeature ?? ''}
                      onChange={(event) => setDependenceFeature(event.target.value)}
                    >
                      {features.map((feature) => (
                        <option key={feature.feature} value={feature.feature}>
                          {feature.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                  {dependenceQuery.isError && <ErrorBox message={errorMessage(dependenceQuery.error)} />}
                  {dependenceQuery.isLoading && <Loading label="Calculando dependencia…" />}
                  {dependence && dependence.points.length === 0 && (
                    <Empty title="Sin puntos de dependencia" />
                  )}
                  {dependence && dependence.points.length > 0 && (
                    <>
                      <ExplainedChart explanationId="dependence" width="100%" height={290}>
                        <ScatterChart margin={{ top: 10, right: 20, bottom: 5, left: -12 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis
                            type="number"
                            dataKey="value"
                            name={dependence.label}
                            tick={{ fontSize: 11 }}
                          />
                          <YAxis
                            type="number"
                            dataKey="shap"
                            name="SHAP"
                            tick={{ fontSize: 11 }}
                            tickFormatter={(value) => Number(value).toFixed(2)}
                          />
                          <Tooltip
                            formatter={(value) => decimal(Number(value), 4)}
                            labelFormatter={(label) => `${dependence.label}: ${label}`}
                          />
                          <ReferenceLine y={0} stroke="#94a3b8" />
                          <Scatter data={dependence.points} name="SHAP">
                            {dependence.points.map((point, index) => (
                              <Cell
                                key={index}
                                fill={point.shap >= 0 ? '#dc2626' : '#059669'}
                              />
                            ))}
                          </Scatter>
                        </ScatterChart>
                      </ExplainedChart>
                      <div className="legend">
                        <span>
                          <span className="legend-swatch" style={{ background: '#dc2626' }} />
                          Aumenta el riesgo
                        </span>
                        <span>
                          <span className="legend-swatch" style={{ background: '#059669' }} />
                          Reduce el riesgo
                        </span>
                        <span>{num(dependence.points.length)} observaciones</span>
                      </div>
                    </>
                  )}
                </Card>
              </div>
            </>
          )}
        </>
      )}

      {tab === 'child' && (
        <>
          <Card
            title="Explicación local por niño"
            subtitle="Busque el código del niño para descomponer su predicción individual."
          >
            <form
              className="filters"
              onSubmit={(event) => {
                event.preventDefault();
                searchChild();
              }}
            >
              <Field label="Código o identificador del niño">
                <input
                  type="search"
                  value={childInput}
                  placeholder="Ej.: CH-2021-T01-0001"
                  style={{ minWidth: 260 }}
                  onChange={(event) => setChildInput(event.target.value)}
                />
              </Field>
              <button type="submit" className="btn btn-primary btn-sm">
                Explicar predicción
              </button>
              {samplesQuery.data && samplesQuery.data.items.length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', flexWrap: 'wrap' }}>
                  <small style={{ color: 'var(--muted)' }}>Ejemplos:</small>
                  {samplesQuery.data.items.map((item) => (
                    <button
                      key={item.child.id}
                      type="button"
                      className="chip"
                      onClick={() => searchChild(item.child.code)}
                    >
                      {item.child.code}
                    </button>
                  ))}
                </div>
              )}
            </form>

            {childSearchQuery.isError && <ErrorBox message={errorMessage(childSearchQuery.error)} />}
            {childSearchQuery.isLoading && <Loading label="Buscando niño…" />}
            {childSubmitted && !childSearchQuery.isLoading && !childSearchQuery.isError && !childMatch && (
              <Empty
                title="No se encontró el niño"
                hint="Verifique el código e intente nuevamente con el formato CH-AÑO-TERRITORIO-####."
              />
            )}
          </Card>

          {childMatch && (
            <Card
              title={`Niño ${childMatch.child.code}`}
              subtitle={`${childMatch.territory.name} · ${childMatch.territory.region} · ${childMatch.child.period_year}`}
              actions={<RiskBadge band={childQuery.data?.risk_band ?? 'UNKNOWN'} />}
            >
              <div className="grid grid-sidebar">
                <div>
                  {childQuery.isError && <ErrorBox message={errorMessage(childQuery.error)} />}
                  {childQuery.isLoading && <Loading label="Calculando contribuciones…" />}
                  {childQuery.data && (
                    <>
                      <div className="kpi-grid" style={{ marginBottom: '1rem' }}>
                        <div className="kpi" data-severity="warning">
                          <div className="kpi-label">Riesgo predicho</div>
                          <div className="kpi-value">{pct(childQuery.data.prediction)}</div>
                          <div className="kpi-foot">
                            <span>Probabilidad de desnutrición</span>
                          </div>
                        </div>
                        <div className="kpi" data-severity="neutral">
                          <div className="kpi-label">Valor base</div>
                          <div className="kpi-value">{pct(childQuery.data.base_value)}</div>
                          <div className="kpi-foot">
                            <span>Referencia media del modelo</span>
                          </div>
                        </div>
                        <div className="kpi" data-severity="neutral">
                          <div className="kpi-label">Edad y sexo</div>
                          <div className="kpi-value" style={{ fontSize: '1.2rem' }}>
                            {num(childMatch.child.age_months)} m ·{' '}
                            {childMatch.child.sex === 'F' ? 'F' : childMatch.child.sex === 'M' ? 'M' : childMatch.child.sex}
                          </div>
                          <div className="kpi-foot">
                            <span>Peso {decimal(childMatch.child.weight_kg, 2)} kg</span>
                          </div>
                        </div>
                      </div>

                      {sortedContributions.length > 0 && (
                        <ExplainedChart explanationId="shap" width="100%" height={360}>
                          <BarChart
                            data={sortedContributions}
                            layout="vertical"
                            margin={{ top: 5, right: 30, bottom: 5, left: 12 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                            <XAxis
                              type="number"
                              tick={{ fontSize: 11 }}
                              tickFormatter={(value) => Number(value).toFixed(3)}
                            />
                            <YAxis type="category" dataKey="label" width={185} tick={{ fontSize: 11 }} />
                            <Tooltip formatter={(value) => decimal(Number(value), 4)} />
                            <ReferenceLine x={0} stroke="#94a3b8" />
                            <Bar dataKey="contribution" name="Contribución SHAP">
                              {sortedContributions.map((item) => (
                                <Cell
                                  key={item.feature}
                                  fill={item.contribution >= 0 ? '#dc2626' : '#059669'}
                                />
                              ))}
                            </Bar>
                          </BarChart>
                        </ExplainedChart>
                      )}
                    </>
                  )}
                </div>

                <div>
                  {childQuery.data && (
                    <>
                      <MetricRow label="Código" value={childQuery.data.child_code} />
                      <MetricRow label="Modelo" value={`#${childQuery.data.model_id}`} />
                      <MetricRow label="Banda de riesgo" value={<RiskBadge band={childQuery.data.risk_band} />} />
                      <div style={{ marginTop: '0.7rem' }}>
                        <div style={{ fontSize: '0.73rem', color: 'var(--muted)', marginBottom: '0.3rem' }}>
                          Factores que aumentan el riesgo
                        </div>
                        <div className="chip-row">
                          {(childQuery.data.positive ?? []).map((item) => (
                            <Badge key={item.feature} tone="danger">
                              {item.label} +{decimal(item.contribution, 3)}
                            </Badge>
                          ))}
                          {(childQuery.data.positive ?? []).length === 0 && <Badge>Ninguno</Badge>}
                        </div>
                      </div>
                      <div style={{ marginTop: '0.7rem' }}>
                        <div style={{ fontSize: '0.73rem', color: 'var(--muted)', marginBottom: '0.3rem' }}>
                          Factores protectores
                        </div>
                        <div className="chip-row">
                          {(childQuery.data.negative ?? []).map((item) => (
                            <Badge key={item.feature} tone="ok">
                              {item.label} {decimal(item.contribution, 3)}
                            </Badge>
                          ))}
                          {(childQuery.data.negative ?? []).length === 0 && <Badge>Ninguno</Badge>}
                        </div>
                      </div>
                      <p style={{ marginTop: '0.9rem', fontSize: '0.82rem', color: 'var(--muted)' }}>
                        {childQuery.data.narrative}
                      </p>
                      <small>
                        Interpretación generada con valores SHAP del modelo; no constituye diagnóstico
                        clínico.
                      </small>
                    </>
                  )}
                </div>
              </div>
            </Card>
          )}
        </>
      )}

      {tab === 'territory' && (
        <>
          <Card
            title="Explicación territorial"
            subtitle="Determinantes agregados del riesgo en el territorio seleccionado."
            actions={
              <Field label="Territorio">
                <select
                  value={territoryId ?? ''}
                  disabled={!territories.length}
                  onChange={(event) => setTerritoryId(Number(event.target.value))}
                >
                  {!territories.length && <option value="">Sin territorios</option>}
                  {territories.map((territory) => (
                    <option key={territory.id} value={territory.id}>
                      {territory.name} · {territory.region}
                    </option>
                  ))}
                </select>
              </Field>
            }
          >
            {territoryQuery.isError && <ErrorBox message={errorMessage(territoryQuery.error)} />}
            {territoryQuery.isLoading && <Loading label="Calculando determinantes territoriales…" />}
            {territoryQuery.data && (
              <div className="grid grid-sidebar">
                <div>
                  <ExplainedChart explanationId="shap" width="100%" height={350}>
                    <BarChart
                      data={territoryQuery.data.features}
                      layout="vertical"
                      margin={{ top: 5, right: 30, bottom: 5, left: 12 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                      <XAxis
                        type="number"
                        tick={{ fontSize: 11 }}
                        tickFormatter={(value) => Number(value).toFixed(3)}
                      />
                      <YAxis type="category" dataKey="label" width={180} tick={{ fontSize: 11 }} />
                      <Tooltip formatter={(value) => decimal(Number(value), 4)} />
                      <Bar dataKey="mean_abs_shap" name="Impacto medio |SHAP|" fill={CHART_COLORS[0]} radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ExplainedChart>
                </div>
                <div>
                  <MetricRow label="Territorio" value={territoryQuery.data.territory_name} />
                  <MetricRow label="Región" value={territoryQuery.data.region} />
                  <MetricRow label="Código" value={territoryQuery.data.territory_code} />
                  <MetricRow label="Riesgo medio" value={pct(territoryQuery.data.mean_risk)} />
                  <MetricRow
                    label="Retraso del crecimiento"
                    value={pct(territoryQuery.data.stunting_prevalence)}
                  />
                  <MetricRow label="Niños evaluados" value={num(territoryQuery.data.children_screened)} />
                  <p style={{ marginTop: '0.8rem', fontSize: '0.82rem', color: 'var(--muted)' }}>
                    {territoryQuery.data.narrative}
                  </p>
                </div>
              </div>
            )}
          </Card>
        </>
      )}
    </>
  );
}


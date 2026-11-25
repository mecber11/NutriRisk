import { ExplainedChart, Interpretation } from '../components/Interpretation';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../api/client';
import type { Column } from '../components/ui';
import {
  Badge,
  Card,
  CHART_COLORS,
  DataTable,
  Empty,
  ErrorBox,
  Field,
  KpiCard,
  Loading,
  PageHeader,
  RISK_COLORS,
  RISK_LABELS,
  RiskBadge,
  dateTime,
  num,
  pct,
  pctValue,
  severityTone,
} from '../components/ui';
import type {
  ComparisonRow,
  DashboardOptions,
  ModelPerformance,
  Overview,
  TerritoryRisk,
} from '../types';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo cargar el tablero.';
}

export default function Dashboard() {
  const [year, setYear] = useState<number | null>(null);
  const [region, setRegion] = useState('');
  const [sex, setSex] = useState('');
  const [ageGroup, setAgeGroup] = useState('');

  const optionsQuery = useQuery({
    queryKey: ['dashboard', 'options'],
    queryFn: () => api.get<DashboardOptions>('/dashboard/options'),
  });

  const overviewQuery = useQuery({
    queryKey: ['dashboard', 'overview', year, region, sex, ageGroup],
    queryFn: () =>
      api.get<Overview>('/dashboard/overview', {
        year: year ?? undefined,
        region: region || undefined,
        sex: sex || undefined,
        age_group: ageGroup || undefined,
      }),
  });

  const options = optionsQuery.data;
  const latestYear = options?.years?.length ? options.years[options.years.length - 1] : undefined;
  const selectedYear = year ?? latestYear ?? '';
  const overview = overviewQuery.data;

  const trendData = overview?.trend ?? [];
  const regionData = overview?.regions ?? [];
  const distribution = overview?.risk_distribution ?? [];

  const territoryColumns: Column<TerritoryRisk>[] = [
    { key: 'priority_rank', header: 'Prioridad', width: '90px', render: (row) => <span className="rank">#{row.priority_rank}</span> },
    {
      key: 'name',
      header: 'Territorio',
      render: (row) => (
        <div>
          <Link to={`/territorios/${row.code}`}>{row.name}</Link>
          <div style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>
            {row.code} · {row.region}
          </div>
        </div>
      ),
    },
    {
      key: 'mean_risk',
      header: 'Riesgo',
      align: 'right',
      render: (row) => (
        <span>
          <RiskBadge band={row.risk_band} /> <span className="risk-pill">{pct(row.mean_risk)}</span>
        </span>
      ),
    },
    {
      key: 'stunting_prevalence',
      header: 'Retraso',
      align: 'right',
      render: (row) => pct(row.stunting_prevalence),
    },
    {
      key: 'population_at_risk',
      header: 'Población en riesgo',
      align: 'right',
      render: (row) => num(row.population_at_risk),
    },
    {
      key: 'children_screened',
      header: 'Niños evaluados',
      align: 'right',
      render: (row) => num(row.children_screened),
    },
  ];

  const modelColumns: Column<ModelPerformance>[] = [
    {
      key: 'name',
      header: 'Modelo',
      render: (row) => (
        <div>
          <div style={{ fontWeight: 600 }}>{row.name}</div>
          <div style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>{row.algorithm}</div>
        </div>
      ),
    },
    { key: 'auc', header: 'AUC', align: 'right', render: (row) => pct(row.auc) },
    { key: 'f1', header: 'F1', align: 'right', render: (row) => decimalMetric(row.f1) },
    { key: 'precision', header: 'Precisión', align: 'right', render: (row) => decimalMetric(row.precision) },
    { key: 'recall', header: 'Recall', align: 'right', render: (row) => decimalMetric(row.recall) },
    {
      key: 'is_active',
      header: 'Estado',
      render: (row) => (row.is_active ? <Badge tone="ok">Activo</Badge> : <Badge>En reserva</Badge>),
    },
  ];

  return (
    <>
      <PageHeader
        title="Tablero de riesgo nutricional"
        subtitle="Panorama de prevalencias, riesgo predicho y territorios prioritarios para la primera infancia."
        actions={
          <div className="filters">
            <Field label="Año">
              <select
                value={String(selectedYear)}
                disabled={!options}
                onChange={(event) => setYear(Number(event.target.value))}
              >
                {(options?.years ?? []).map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Región">
              <select value={region} disabled={!options} onChange={(event) => setRegion(event.target.value)}>
                <option value="">Todas las regiones</option>
                {(options?.regions ?? []).map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Sexo">
              <select value={sex} disabled={!options} onChange={(event) => setSex(event.target.value)}>
                <option value="">Ambos sexos</option>
                {(options?.sexes ?? []).map((item) => (
                  <option key={item} value={item}>
                    {item === 'F' ? 'Femenino' : item === 'M' ? 'Masculino' : item}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Grupo de edad">
              <select
                value={ageGroup}
                disabled={!options}
                onChange={(event) => setAgeGroup(event.target.value)}
              >
                <option value="">Todos los grupos</option>
                {(options?.age_groups ?? []).map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </Field>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => {
                setYear(null);
                setRegion('');
                setSex('');
                setAgeGroup('');
              }}
            >
              Limpiar
            </button>
          </div>
        }
      />

      {overview?.meta.synthetic && (
        <div className="notice" data-tone="warning">
          <span>
            <strong>Datos sintéticos.</strong> La información de esta demostración no representa
            prevalencias reales. {num(overview.meta.children_total)} niños simulados · modelo activo{' '}
            {overview.meta.active_model_algorithm ?? 'sin modelo'} · generado el{' '}
            {dateTime(overview.meta.generated_at)}.
          </span>
        </div>
      )}

      {overviewQuery.isError && <ErrorBox message={errorMessage(overviewQuery.error)} />}

      {overviewQuery.isLoading && <Loading label="Calculando indicadores del tablero…" />}

      {overview && (
        <>
          {overview.kpis.length === 0 ? (
            <Empty title="Sin indicadores para el filtro seleccionado" hint="Pruebe con otro año o región." />
          ) : (
            <div className="kpi-grid">
              {overview.kpis.map((kpi) => (
                <KpiCard key={kpi.key} kpi={kpi} />
              ))}
            </div>
          )}

          <div className="grid grid-sidebar">
            <Card
              title="Evolución de prevalencias"
              subtitle="Porcentaje de niños evaluados por periodo; línea punteada: riesgo medio predicho."
            >
              {trendData.length === 0 ? (
                <Empty title="Sin serie de tiempo" />
              ) : (
                <ExplainedChart explanationId="trend" width="100%" height={300}>
                  <LineChart data={trendData} margin={{ top: 8, right: 18, bottom: 0, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} unit="%" />
                    <Tooltip formatter={(value) => pctValue(Number(value), 2)} />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="stunting"
                      name="Retraso del crecimiento"
                      stroke="#dc2626"
                      strokeWidth={2.2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="wasting"
                      name="Emaciación"
                      stroke="#f59e0b"
                      strokeWidth={2.2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="underweight"
                      name="Bajo peso"
                      stroke="#0f766e"
                      strokeWidth={2.2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="mean_risk"
                      name="Riesgo medio"
                      stroke="#7c3aed"
                      strokeWidth={2}
                      strokeDasharray="5 4"
                      dot={false}
                    />
                  </LineChart>
                </ExplainedChart>
              )}
            </Card>

            <Card
              title="Distribución del riesgo"
              subtitle="Bandas de riesgo predicho del modelo activo."
              actions={<Badge tone="brand">{overview.meta.active_model_algorithm ?? 'Sin modelo'}</Badge>}
            >
              {distribution.length === 0 ? (
                <Empty title="Sin distribución de riesgo" />
              ) : (
                <>
                  <ExplainedChart explanationId="risk" width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={distribution}
                        dataKey="share"
                        nameKey="label"
                        innerRadius={55}
                        outerRadius={92}
                        paddingAngle={2}
                      >
                        {distribution.map((item) => (
                          <Cell key={item.band} fill={RISK_COLORS[item.band] ?? '#94a3b8'} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(value, name) => [pctValue(Number(value), 2), String(name)]}
                      />
                    </PieChart>
                  </ExplainedChart>
                  <div className="legend">
                    {distribution.map((item) => (
                      <span key={item.band}>
                        <span
                          className="legend-swatch"
                          style={{ background: RISK_COLORS[item.band] ?? '#94a3b8' }}
                        />
                        {RISK_LABELS[item.band] ?? item.label}: {pctValue(item.share, 1)} ·{' '}
                        {num(item.count)} niños
                      </span>
                    ))}
                  </div>
                </>
              )}
            </Card>
          </div>

          <div className="grid grid-2" style={{ marginTop: '1rem' }}>
            <Card title="Prevalencias por región" subtitle="Retraso, emaciación y bajo peso.">
              {regionData.length === 0 ? (
                <Empty title="Sin regiones para el filtro" />
              ) : (
                <ExplainedChart explanationId="prevalence" width="100%" height={300}>
                  <BarChart data={regionData} margin={{ top: 8, right: 12, bottom: 0, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} />
                    <YAxis tick={{ fontSize: 12 }} unit="%" />
                    <Tooltip formatter={(value) => pctValue(Number(value), 2)} />
                    <Legend />
                    <Bar dataKey="stunting" name="Retraso" fill={CHART_COLORS[2]} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="wasting" name="Emaciación" fill={CHART_COLORS[1]} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="underweight" name="Bajo peso" fill={CHART_COLORS[0]} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ExplainedChart>
              )}
            </Card>

            <Card
              title="Desempeño de modelos"
              subtitle="Métricas de validación del conjunto de modelos entrenados."
            >
              <DataTable interpretationId="territories"
                columns={modelColumns}
                rows={overview.model_performance}
                getKey={(row) => row.model_id}
                empty="Sin modelos entrenados"
              />
            </Card>
          </div>

          <div className="grid grid-sidebar" style={{ marginTop: '1rem' }}>
            <Card
              title="Territorios prioritarios"
              subtitle="Ordenados por riesgo medio predicho; haga clic en el nombre para abrir la ficha."
              actions={<Link className="btn btn-sm" to="/territorios">Ver ranking completo</Link>}
            >
              <DataTable interpretationId="models"
                columns={territoryColumns}
                rows={overview.top_territories}
                getKey={(row) => row.territory_id}
                empty="Sin territorios priorizados"
              />
            </Card>

            <Card
              title="Alertas operativas"
              subtitle={`${overview.alerts.length} novedades del monitoreo`}
            >
              {overview.alerts.length === 0 ? (
                <Empty title="Sin alertas abiertas" hint="El monitoreo no ha detectado novedades." />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  {overview.alerts.map((alert) => (
                    <div
                      key={alert.id}
                      style={{
                        borderLeft: `3px solid ${alert.severity === 'CRITICAL' ? 'var(--danger)' : 'var(--accent)'}`,
                        paddingLeft: '0.65rem',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                        <Badge tone={severityTone(alert.severity)}>{alert.severity}</Badge>
                        <strong style={{ fontSize: '0.84rem' }}>{alert.title}</strong>
                      </div>
                      <p style={{ margin: '0.25rem 0 0.2rem', fontSize: '0.8rem', color: 'var(--muted)' }}>
                        {alert.message}
                      </p>
                      <small>{dateTime(alert.created_at)}</small>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          <Card title="Contexto del cálculo" className="card">
            <div className="grid grid-4">
              <Metric label="Año analizado" value={String(selectedYear || '—')} />
              <Metric label="Niños en el filtro" value={num(overview.meta.children_total)} />
              <Metric
                label="Regiones"
                value={
                  overview.filters.region
                    ? String(overview.filters.region)
                    : `${overview.meta.regions.length} regiones`
                }
              />
              <Metric label="Generado" value={dateTime(overview.meta.generated_at)} />
            </div>
          </Card>
        </>
      )}
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: '0.72rem', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </div>
      <div style={{ fontWeight: 650, marginTop: '0.2rem' }}>{value}</div>
    </div>
  );
}

function decimalMetric(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return value.toFixed(3);
}

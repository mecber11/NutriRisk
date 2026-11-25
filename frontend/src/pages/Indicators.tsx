import { ExplainedChart, Interpretation } from '../components/Interpretation';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Bar as HistogramBar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
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
  KpiCard,
  Loading,
  MetricRow,
  PageHeader,
  decimal,
  num,
  pct,
  pctValue,
} from '../components/ui';
import type { Column } from '../components/ui';
import type {
  ChildListItem,
  ChildListPage,
  DashboardOptions,
  DistributionResponse,
  IndicatorRow,
  IndicatorSummary,
  Kpi,
  ReferenceIndicatorInfo,
} from '../types';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo cargar la información.';
}

function prevalenceSeverity(value: number): string {
  if (value >= 0.25) return 'critical';
  if (value >= 0.15) return 'warning';
  return 'ok';
}

function buildKpis(summary: IndicatorSummary): Kpi[] {
  return [
    {
      key: 'total_children',
      label: 'Niños evaluados',
      value: summary.total_children,
      unit: '',
      delta: null,
      trend: 'flat',
      description: 'Registros con antropometría válida en el filtro.',
      severity: 'neutral',
    },
    {
      key: 'stunting',
      label: 'Retraso del crecimiento',
      value: summary.stunting_prevalence * 100,
      unit: '%',
      delta: null,
      trend: 'flat',
      description: 'HAZ < -2 DE (OMS 2006).',
      severity: prevalenceSeverity(summary.stunting_prevalence),
    },
    {
      key: 'wasting',
      label: 'Emaciación',
      value: summary.wasting_prevalence * 100,
      unit: '%',
      delta: null,
      trend: 'flat',
      description: 'WHZ < -2 DE (OMS 2006).',
      severity: prevalenceSeverity(summary.wasting_prevalence),
    },
    {
      key: 'underweight',
      label: 'Bajo peso',
      value: summary.underweight_prevalence * 100,
      unit: '%',
      delta: null,
      trend: 'flat',
      description: 'WAZ < -2 DE (OMS 2006).',
      severity: prevalenceSeverity(summary.underweight_prevalence),
    },
    {
      key: 'severe_stunting',
      label: 'Retraso severo',
      value: summary.severe_stunting_prevalence * 100,
      unit: '%',
      delta: null,
      trend: 'flat',
      description: 'HAZ < -3 DE.',
      severity: summary.severe_stunting_prevalence >= 0.05 ? 'critical' : 'ok',
    },
  ];
}

function chartRows(rows: IndicatorRow[]) {
  return rows.map((row) => ({
    label: row.label,
    stuntingPct: row.stunting * 100,
    wastingPct: row.wasting * 100,
    underweightPct: row.underweight * 100,
    n: row.n,
  }));
}

export default function Indicators() {
  const [year, setYear] = useState<number | null>(null);
  const [region, setRegion] = useState('');
  const [sex, setSex] = useState('');
  const [ageGroup, setAgeGroup] = useState('');
  const [search, setSearch] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [stunting, setStunting] = useState('');
  const [page, setPage] = useState(1);

  const optionsQuery = useQuery({
    queryKey: ['dashboard', 'options'],
    queryFn: () => api.get<DashboardOptions>('/dashboard/options'),
  });

  const summaryQuery = useQuery({
    queryKey: ['indicators', 'summary', year, region, sex, ageGroup],
    queryFn: () =>
      api.get<IndicatorSummary>('/indicators/summary', {
        year: year ?? undefined,
        region: region || undefined,
        sex: sex || undefined,
        age_group: ageGroup || undefined,
      }),
  });

  const distributionQuery = useQuery({
    queryKey: ['indicators', 'distribution', 'haz'],
    queryFn: () => api.get<DistributionResponse>('/indicators/distribution', { indicator: 'haz' }),
  });

  const referenceQuery = useQuery({
    queryKey: ['indicators', 'reference'],
    queryFn: () => api.get<ReferenceIndicatorInfo>('/indicators/reference'),
  });

  const childrenQuery = useQuery({
    queryKey: ['indicators', 'children', year, region, stunting, appliedSearch, page],
    queryFn: () =>
      api.get<ChildListPage>('/indicators/children', {
        year: year ?? undefined,
        region: region || undefined,
        stunting: stunting === '' ? undefined : stunting === 'true',
        search: appliedSearch || undefined,
        page,
        page_size: 15,
      }),
  });

  const options = optionsQuery.data;
  const summary = summaryQuery.data;
  const distribution = distributionQuery.data;
  const children = childrenQuery.data;
  const years = options?.years ?? [];
  const selectedYear = year ?? (years.length ? years[years.length - 1] : '');

  const regionData = useMemo(() => chartRows(summary?.by_region ?? []), [summary]);
  const sexData = useMemo(() => chartRows(summary?.by_sex ?? []), [summary]);
  const quintileData = useMemo(() => chartRows(summary?.by_wealth_quintile ?? []), [summary]);
  const histogram = useMemo(
    () =>
      (distribution?.bins ?? []).map((bin) => ({
        mid: (bin.bin_start + bin.bin_end) / 2,
        label: `${bin.bin_start.toFixed(2)} a ${bin.bin_end.toFixed(2)}`,
        count: bin.count,
      })),
    [distribution],
  );

  const childColumns: Column<ChildListItem>[] = [
    {
      key: 'code',
      header: 'Código',
      render: (row) => <span className="mono">{row.child.code}</span>,
    },
    {
      key: 'territory',
      header: 'Territorio',
      render: (row) => (
        <div>
          <Link to={`/territorios/${row.territory.code}`}>{row.territory.name}</Link>
          <div style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>{row.territory.region}</div>
        </div>
      ),
    },
    { key: 'year', header: 'Año', align: 'right', render: (row) => row.child.period_year },
    {
      key: 'age',
      header: 'Edad',
      align: 'right',
      render: (row) => `${num(row.child.age_months)} m`,
    },
    {
      key: 'sex',
      header: 'Sexo',
      render: (row) => (row.child.sex === 'F' ? 'Femenino' : row.child.sex === 'M' ? 'Masculino' : row.child.sex),
    },
    { key: 'haz', header: 'HAZ', align: 'right', render: (row) => decimal(row.indicator.haz, 2) },
    { key: 'waz', header: 'WAZ', align: 'right', render: (row) => decimal(row.indicator.waz, 2) },
    { key: 'whz', header: 'WHZ', align: 'right', render: (row) => decimal(row.indicator.whz, 2) },
    {
      key: 'flags',
      header: 'Estado nutricional',
      render: (row) => (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.2rem' }}>
          <Badge tone={row.indicator.stunting ? (row.indicator.severe_stunting ? 'danger' : 'warning') : 'ok'}>
            {row.indicator.stunting ? 'Retraso' : 'Sin retraso'}
          </Badge>
          <Badge tone={row.indicator.wasting ? 'warning' : 'ok'}>
            {row.indicator.wasting ? 'Emaciación' : 'Sin emaciación'}
          </Badge>
          <Badge tone={row.indicator.underweight ? 'warning' : 'ok'}>
            {row.indicator.underweight ? 'Bajo peso' : 'Peso adecuado'}
          </Badge>
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Indicadores antropométricos"
        subtitle="Prevalencias, distribución de z-scores y referencia OMS 2006 para menores de cinco años."
        actions={
          summary?.reference_version ? <Badge tone="brand">Referencia {summary.reference_version}</Badge> : undefined
        }
      />

      <Card title="Filtros" subtitle="Se aplican al resumen, a los gráficos y a la tabla de niños.">
        <div className="filters">
          <Field label="Año">
            <select
              value={String(selectedYear)}
              disabled={!years.length}
              onChange={(event) => {
                setYear(Number(event.target.value));
                setPage(1);
              }}
            >
              {years.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Región">
            <select
              value={region}
              disabled={!options}
              onChange={(event) => {
                setRegion(event.target.value);
                setPage(1);
              }}
            >
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
              setPage(1);
            }}
          >
            Limpiar
          </button>
        </div>
      </Card>

      {summaryQuery.isError && <ErrorBox message={errorMessage(summaryQuery.error)} />}
      {summaryQuery.isLoading && <Loading label="Calculando indicadores OMS…" />}

      {summary && (
        <>
          <div className="kpi-grid" style={{ marginTop: '1rem' }}>
            {buildKpis(summary).map((kpi) => (
              <KpiCard key={kpi.key} kpi={kpi} />
            ))}
          </div>

          <div className="grid grid-3">
            <Card title="Prevalencias por región" subtitle="Porcentaje de niños evaluados.">
              {regionData.length === 0 ? (
                <Empty title="Sin datos regionales" />
              ) : (
                <ExplainedChart explanationId="prevalence" width="100%" height={260}>
                  <BarChart data={regionData} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} />
                    <YAxis tick={{ fontSize: 11 }} unit="%" />
                    <Tooltip formatter={(value) => pctValue(Number(value), 2)} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <HistogramBar dataKey="stuntingPct" name="Retraso" fill={CHART_COLORS[2]} radius={[3, 3, 0, 0]} />
                    <HistogramBar dataKey="wastingPct" name="Emaciación" fill={CHART_COLORS[1]} radius={[3, 3, 0, 0]} />
                    <HistogramBar dataKey="underweightPct" name="Bajo peso" fill={CHART_COLORS[0]} radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ExplainedChart>
              )}
            </Card>

            <Card title="Prevalencias por sexo" subtitle="Comparación entre niñas y niños.">
              {sexData.length === 0 ? (
                <Empty title="Sin datos por sexo" />
              ) : (
                <ExplainedChart explanationId="prevalence" width="100%" height={260}>
                  <BarChart data={sexData} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} unit="%" />
                    <Tooltip formatter={(value) => pctValue(Number(value), 2)} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <HistogramBar dataKey="stuntingPct" name="Retraso" fill={CHART_COLORS[2]} radius={[3, 3, 0, 0]} />
                    <HistogramBar dataKey="wastingPct" name="Emaciación" fill={CHART_COLORS[1]} radius={[3, 3, 0, 0]} />
                    <HistogramBar dataKey="underweightPct" name="Bajo peso" fill={CHART_COLORS[0]} radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ExplainedChart>
              )}
            </Card>

            <Card title="Retraso por quintil de riqueza" subtitle="Gradiente socioeconómico del retraso.">
              {quintileData.length === 0 ? (
                <Empty title="Sin datos por quintil" />
              ) : (
                <ExplainedChart explanationId="prevalence" width="100%" height={260}>
                  <BarChart data={quintileData} margin={{ top: 8, right: 8, bottom: 0, left: -14 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} />
                    <YAxis tick={{ fontSize: 11 }} unit="%" />
                    <Tooltip formatter={(value) => pctValue(Number(value), 2)} />
                    <HistogramBar dataKey="stuntingPct" name="Retraso" radius={[3, 3, 0, 0]}>
                      {quintileData.map((row, index) => (
                        <Cell key={row.label} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                      ))}
                    </HistogramBar>
                  </BarChart>
                </ExplainedChart>
              )}
            </Card>
          </div>

          <div className="grid grid-sidebar" style={{ marginTop: '1rem' }}>
            <Card
              title="Distribución de HAZ"
              subtitle="Histograma de puntuaciones z de talla para la edad; línea roja en -2 DE."
            >
              {distributionQuery.isError && <ErrorBox message={errorMessage(distributionQuery.error)} />}
              {distributionQuery.isLoading && <Loading label="Calculando distribución…" />}
              {distribution && (
                <>
                  <ExplainedChart explanationId="histogram" width="100%" height={300}>
                    <BarChart data={histogram} margin={{ top: 12, right: 18, bottom: 0, left: -8 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis
                        type="number"
                        dataKey="mid"
                        domain={['dataMin', 'dataMax']}
                        tick={{ fontSize: 11 }}
                        tickFormatter={(value) => Number(value).toFixed(1)}
                      />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip
                        labelFormatter={(label) => `HAZ ${Number(label).toFixed(2)}`}
                        formatter={(value) => [`${num(Number(value))} niños`, 'Frecuencia']}
                      />
                      <ReferenceLine x={distribution.reference_line} stroke="#dc2626" strokeWidth={2} label="-2 DE" />
                      <HistogramBar dataKey="count" name="Niños" fill={CHART_COLORS[0]} />
                    </BarChart>
                  </ExplainedChart>
                  <div className="legend">
                    <span>Media HAZ: {decimal(distribution.mean, 3)}</span>
                    <span>Desviación estándar: {decimal(distribution.sd, 3)}</span>
                    <span>Total: {num(distribution.total)} niños</span>
                    <span>Línea de referencia: {decimal(distribution.reference_line, 2)} DE</span>
                  </div>
                </>
              )}
            </Card>

            <Card
              title="Referencia OMS 2006"
              subtitle="Verificación de las tablas de crecimiento usadas en el cálculo."
              actions={
                referenceQuery.data ? (
                  <Badge tone={referenceQuery.data.self_check.passed ? 'ok' : 'danger'}>
                    {referenceQuery.data.self_check.passed ? 'Autoverificación superada' : 'Con desviaciones'}
                  </Badge>
                ) : undefined
              }
            >
              {referenceQuery.isError && <ErrorBox message={errorMessage(referenceQuery.error)} />}
              {referenceQuery.isLoading && <Loading label="Verificando referencia…" />}
              {referenceQuery.data && (
                <>
                  <MetricRow label="Versión" value={referenceQuery.data.version} />
                  <MetricRow label="Fuente" value={referenceQuery.data.source} />
                  {referenceQuery.data.age_months_range && (
                    <MetricRow
                      label="Rango de edad"
                      value={`${referenceQuery.data.age_months_range[0]}–${referenceQuery.data.age_months_range[1]} meses`}
                    />
                  )}
                  <MetricRow
                    label="Límite de z-score"
                    value={decimal(referenceQuery.data.zscore_limit, 1)}
                  />
                  <MetricRow
                    label="Cortes verificados"
                    value={num(referenceQuery.data.self_check.checked_cutoffs)}
                  />
                  <MetricRow
                    label="Desviación máxima"
                    value={`${decimal(referenceQuery.data.self_check.max_deviation_z, 4)} DE`}
                  />
                  <MetricRow
                    label="Tolerancia"
                    value={decimal(referenceQuery.data.self_check.tolerance, 3)}
                  />
                  {referenceQuery.data.indicators && (
                    <div style={{ marginTop: '0.6rem' }}>
                      <div style={{ fontSize: '0.72rem', color: 'var(--muted)', marginBottom: '0.3rem' }}>
                        Tablas disponibles
                      </div>
                      <div className="chip-row">
                        {Object.entries(referenceQuery.data.indicators).map(([key, value]) => (
                          <Badge key={key} tone="info">
                            {key.toUpperCase()} · {value.male_rows + value.female_rows} filas
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  <p style={{ marginTop: '0.7rem', marginBottom: 0, fontSize: '0.78rem', color: 'var(--muted)' }}>
                    La autoverificación compara los cortes calculados contra las tablas publicadas. Una
                    desviación máxima de {decimal(referenceQuery.data.self_check.max_deviation_z, 4)} DE
                    se considera dentro de tolerancia.
                  </p>
                </>
              )}
            </Card>
          </div>

          <Card
            title="Niños evaluados"
            subtitle="Registros individuales con indicadores antropométricos y clasificación nutricional."
            actions={<Badge tone="brand">{num(children?.total ?? 0)} registros</Badge>}
          >
            <form
              className="filters"
              style={{ marginBottom: '0.85rem' }}
              onSubmit={(event) => {
                event.preventDefault();
                setPage(1);
                setAppliedSearch(search.trim());
              }}
            >
              <Field label="Buscar por código">
                <input
                  type="search"
                  value={search}
                  placeholder="Ej.: CH-2021-T01-0001"
                  style={{ minWidth: 230 }}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </Field>
              <Field label="Estado de retraso">
                <select
                  value={stunting}
                  onChange={(event) => {
                    setStunting(event.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">Todos</option>
                  <option value="true">Solo con retraso</option>
                  <option value="false">Sin retraso</option>
                </select>
              </Field>
              <button type="submit" className="btn btn-primary btn-sm">
                Buscar
              </button>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => {
                  setSearch('');
                  setAppliedSearch('');
                  setStunting('');
                  setPage(1);
                }}
              >
                Restablecer
              </button>
            </form>

            {childrenQuery.isError && <ErrorBox message={errorMessage(childrenQuery.error)} />}
            {childrenQuery.isLoading && <Loading label="Cargando registros…" />}
            {children && children.items.length === 0 && (
              <Empty title="Sin niños que coincidan" hint="Ajuste el término de búsqueda o los filtros." />
            )}
            {children && children.items.length > 0 && (
              <>
                <DataTable interpretationId="records"
                  columns={childColumns}
                  rows={children.items}
                  getKey={(row) => row.child.id}
                  empty="Sin registros"
                />
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    marginTop: '0.75rem',
                    flexWrap: 'wrap',
                  }}
                >
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={page <= 1}
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                  >
                    ← Anterior
                  </button>
                  <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                    Página {children.page} de {children.pages || 1} · {num(children.total)} registros
                  </span>
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={page >= (children.pages || 1)}
                    onClick={() => setPage((current) => current + 1)}
                  >
                    Siguiente →
                  </button>
                </div>
              </>
            )}
          </Card>
        </>
      )}
    </>
  );
}

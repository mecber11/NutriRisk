import { Interpretation } from '../components/Interpretation';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import {
  Badge,
  Card,
  DataTable,
  Empty,
  ErrorBox,
  Field,
  Loading,
  PageHeader,
  RiskBadge,
  num,
  pct,
} from '../components/ui';
import type { Column } from '../components/ui';
import type { DashboardOptions, TerritoryRisk } from '../types';

interface RankingResponse {
  year: number;
  model_id: number | null;
  total: number;
  rows: TerritoryRisk[];
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo cargar el ranking territorial.';
}

export default function Territories() {
  const [year, setYear] = useState<number | null>(null);
  const [search, setSearch] = useState('');

  const optionsQuery = useQuery({
    queryKey: ['dashboard', 'options'],
    queryFn: () => api.get<DashboardOptions>('/dashboard/options'),
  });

  const rankingQuery = useQuery({
    queryKey: ['geo', 'ranking', year, 100],
    queryFn: () => api.get<RankingResponse>('/geo/ranking', { year: year ?? undefined, limit: 100 }),
  });

  const years = optionsQuery.data?.years ?? [];
  const ranking = rankingQuery.data;
  const selectedYear = year ?? ranking?.year ?? (years.length ? years[years.length - 1] : '');
  const needle = search.trim().toLowerCase();
  const rows = (ranking?.rows ?? []).filter((row) => {
    if (!needle) return true;
    return (
      row.name.toLowerCase().includes(needle) ||
      row.code.toLowerCase().includes(needle) ||
      row.region.toLowerCase().includes(needle)
    );
  });

  const critical = rows.filter((row) => row.risk_band === 'CRITICAL').length;
  const high = rows.filter((row) => row.risk_band === 'HIGH').length;
  const meanRisk = rows.length
    ? rows.reduce((total, row) => total + row.mean_risk, 0) / rows.length
    : 0;

  const columns: Column<TerritoryRisk>[] = [
    {
      key: 'priority_rank',
      header: 'Ranking',
      width: '80px',
      render: (row) => <span className="rank">#{row.priority_rank}</span>,
    },
    {
      key: 'name',
      header: 'Territorio',
      render: (row) => (
        <div>
          <Link to={`/territorios/${row.code}`}>{row.name}</Link>
          <div style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>{row.code}</div>
        </div>
      ),
    },
    { key: 'region', header: 'Región', render: (row) => row.region },
    {
      key: 'mean_risk',
      header: 'Riesgo medio',
      align: 'right',
      render: (row) => <span className="risk-pill">{pct(row.mean_risk)}</span>,
    },
    { key: 'risk_band', header: 'Banda', render: (row) => <RiskBadge band={row.risk_band} /> },
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

  return (
    <>
      <PageHeader
        title="Territorios priorizados"
        subtitle="Ranking de riesgo predicho por territorio. Abra una ficha para revisar historia, determinantes y generar el reporte."
        actions={<Link className="btn" to="/mapa">Ver mapa</Link>}
      />

      <Card
        title="Filtros"
        subtitle="El ranking se calcula con el modelo activo y el año seleccionado."
      >
        <div className="filters">
          <Field label="Año">
            <select
              value={String(selectedYear)}
              disabled={!years.length}
              onChange={(event) => setYear(Number(event.target.value))}
            >
              {years.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Buscar territorio">
            <input
              type="search"
              value={search}
              placeholder="Nombre, código o región…"
              style={{ minWidth: 240 }}
              onChange={(event) => setSearch(event.target.value)}
            />
          </Field>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
            <Badge tone="brand">{rows.length} territorios</Badge>
            {ranking?.model_id && <Badge>Modelo #{ranking.model_id}</Badge>}
          </div>
        </div>
      </Card>

      <div className="kpi-grid" style={{ marginTop: '1rem' }}>
        <div className="kpi" data-severity="neutral">
          <div className="kpi-label">Territorios en el ranking</div>
          <div className="kpi-value">{num(rows.length)}</div>
          <div className="kpi-foot">
            <span>{ranking ? `Año ${ranking.year}` : 'Sin periodo'}</span>
          </div>
        </div>
        <div className="kpi" data-severity="warning">
          <div className="kpi-label">Riesgo medio del conjunto</div>
          <div className="kpi-value">{pct(meanRisk)}</div>
          <div className="kpi-foot">
            <span>Promedio simple de los territorios filtrados</span>
          </div>
        </div>
        <div className="kpi" data-severity="critical">
          <div className="kpi-label">Riesgo alto o crítico</div>
          <div className="kpi-value">{num(high + critical)}</div>
          <div className="kpi-foot">
            <span>
              {num(critical)} críticos · {num(high)} altos
            </span>
          </div>
        </div>
        <div className="kpi" data-severity="ok">
          <div className="kpi-label">Niños evaluados</div>
          <div className="kpi-value">
            {num(rows.reduce((total, row) => total + row.children_screened, 0))}
          </div>
          <div className="kpi-foot">
            <span>Registros con antropometría válida</span>
          </div>
        </div>
      </div>

      <Card title="Ranking territorial" subtitle="Ordenado por prioridad nacional del modelo activo.">
        {rankingQuery.isError && <ErrorBox message={errorMessage(rankingQuery.error)} />}
        {rankingQuery.isLoading && <Loading label="Cargando ranking territorial…" />}
        {!rankingQuery.isLoading && !rankingQuery.isError && rows.length === 0 && (
          <Empty
            title="Sin territorios que coincidan"
            hint={needle ? 'Ajuste el término de búsqueda.' : 'No hay resultados para el año seleccionado.'}
          />
        )}
        {!rankingQuery.isLoading && rows.length > 0 && (
          <DataTable interpretationId="territories"
            columns={columns}
            rows={rows}
            getKey={(row) => row.territory_id}
            empty="Sin territorios"
          />
        )}
      </Card>
    </>
  );
}

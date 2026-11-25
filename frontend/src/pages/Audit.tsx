import { ExplainedChart, Interpretation } from '../components/Interpretation';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api, downloadFile } from '../api/client';
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
  num,
  pctValue,
} from '../components/ui';
import type { Column } from '../components/ui';
import type { AuditEntry, AuditSummary, NavigationEvent } from '../types';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo cargar la bitácora.';
}

function resultTone(result: string): 'ok' | 'warning' | 'danger' | 'neutral' {
  switch (result.toUpperCase()) {
    case 'SUCCESS':
      return 'ok';
    case 'DENIED':
    case 'FORBIDDEN':
      return 'warning';
    case 'FAILURE':
    case 'ERROR':
      return 'danger';
    default:
      return 'neutral';
  }
}

const ACTION_OPTIONS = ['create', 'read', 'update', 'delete', 'execute', 'export', 'login', 'use'];
const RESULT_OPTIONS = ['SUCCESS', 'FAILURE', 'ERROR', 'DENIED'];

export default function Audit() {
  const { user, can } = useAuth();
  const [days, setDays] = useState(30);
  const [search, setSearch] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [module, setModule] = useState('');
  const [action, setAction] = useState('');
  const [result, setResult] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const [exportError, setExportError] = useState<string | null>(null);

  const isAuditor = user?.role.code === 'AUDITOR';
  const canExport = can('audit', 'export');

  const summaryQuery = useQuery({
    queryKey: ['audit', 'summary', days],
    queryFn: () => api.get<AuditSummary>('/audit/summary', { days }),
  });

  const logsQuery = useQuery({
    queryKey: ['audit', 'logs', page, appliedSearch, module, action, result, dateFrom, dateTo],
    queryFn: () =>
      api.get<{ items: AuditEntry[]; total: number; page: number; page_size: number; pages: number }>(
        '/audit/logs',
        {
          page,
          page_size: 15,
          search: appliedSearch || undefined,
          module: module || undefined,
          action: action || undefined,
          result: result || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
        },
      ),
  });

  const navigationQuery = useQuery({
    queryKey: ['audit', 'navigation'],
    queryFn: () =>
      api.get<{ items: NavigationEvent[]; total: number; page: number; page_size: number; pages: number }>(
        '/audit/navigation',
        { page: 1, page_size: 10 },
      ),
  });

  const summary = summaryQuery.data;
  const logs = logsQuery.data;
  const modules = summary?.by_module.map((item) => item.module) ?? [];

  async function exportLogs(fmt: 'pdf' | 'docx' | 'xlsx') {
    setExportError(null);
    try {
      const query = new URLSearchParams({ fmt });
      if (appliedSearch) query.set('search', appliedSearch);
      if (module) query.set('module', module);
      if (action) query.set('action', action);
      if (result) query.set('result', result);
      if (dateFrom) query.set('date_from', dateFrom);
      if (dateTo) query.set('date_to', dateTo);
      const stamp = new Date().toISOString().slice(0, 10);
      await downloadFile(`/audit/export?${query.toString()}`, `bitacora_${stamp}.${fmt}`);
    } catch (error) {
      setExportError(errorMessage(error));
    }
  }

  const logColumns: Column<AuditEntry>[] = [
    { key: 'started_at', header: 'Fecha y hora', render: (row) => dateTime(row.started_at) },
    {
      key: 'user',
      header: 'Usuario',
      render: (row) => (
        <div>
          <div>{row.user_email ?? 'Sistema'}</div>
          <div style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>{row.role_code ?? '—'}</div>
        </div>
      ),
    },
    { key: 'module', header: 'Módulo' },
    { key: 'action', header: 'Acción' },
    {
      key: 'result',
      header: 'Resultado',
      render: (row) => <Badge tone={resultTone(row.result)}>{row.result}</Badge>,
    },
    {
      key: 'resource',
      header: 'Recurso',
      render: (row) =>
        row.resource_type
          ? `${row.resource_type}${row.resource_id ? ` #${row.resource_id}` : ''}`
          : '—',
    },
    { key: 'method', header: 'Método', render: (row) => row.method ?? '—' },
    {
      key: 'path',
      header: 'Ruta',
      render: (row) => (
        <span className="mono" style={{ fontSize: '0.72rem' }}>
          {row.path ?? '—'}
        </span>
      ),
    },
    {
      key: 'status_code',
      header: 'HTTP',
      align: 'right',
      render: (row) => (row.status_code !== null && row.status_code !== undefined ? row.status_code : '—'),
    },
    {
      key: 'duration_ms',
      header: 'Duración',
      align: 'right',
      render: (row) => `${num(row.duration_ms)} ms`,
    },
  ];

  const navigationColumns: Column<NavigationEvent>[] = [
    { key: 'occurred_at', header: 'Fecha y hora', render: (row) => dateTime(row.occurred_at) },
    { key: 'module', header: 'Módulo' },
    {
      key: 'event_type',
      header: 'Evento',
      render: (row) => <Badge tone={row.event_type === 'ENTER' ? 'info' : 'neutral'}>{row.event_type}</Badge>,
    },
    {
      key: 'path',
      header: 'Ruta',
      render: (row) => (
        <span className="mono" style={{ fontSize: '0.72rem' }}>
          {row.path ?? '—'}
        </span>
      ),
    },
    {
      key: 'session_id',
      header: 'Sesión',
      render: (row) => (
        <span className="mono" style={{ fontSize: '0.72rem' }}>
          {row.session_id ? row.session_id.slice(0, 12) : '—'}
        </span>
      ),
    },
    { key: 'ip', header: 'IP', render: (row) => row.ip_address ?? '—' },
  ];

  return (
    <>
      <PageHeader
        title="Bitácora y auditoría"
        subtitle="Registro inmutable de accesos, consultas y operaciones realizadas en el sistema."
        actions={
          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
            {canExport && (
              <>
                <button type="button" className="btn btn-sm" onClick={() => void exportLogs('pdf')}>
                  Exportar PDF
                </button>
                <button type="button" className="btn btn-sm" onClick={() => void exportLogs('docx')}>
                  Word
                </button>
                <button type="button" className="btn btn-sm" onClick={() => void exportLogs('xlsx')}>
                  Excel
                </button>
              </>
            )}
          </div>
        }
      />

      {isAuditor && (
        <div className="notice" data-tone="info">
          <span>
            <strong>Modo solo lectura.</strong> Su rol AUDITOR permite consultar y exportar la bitácora,
            pero no modificar registros del sistema.
          </span>
        </div>
      )}
      {exportError && <ErrorBox message={exportError} />}
      {summaryQuery.isError && <ErrorBox message={errorMessage(summaryQuery.error)} />}
      {summaryQuery.isLoading && <Loading label="Calculando resumen de auditoría…" />}

      {summary && (
        <>
          <div className="kpi-grid">
            <div className="kpi" data-severity="neutral">
              <div className="kpi-label">Eventos registrados</div>
              <div className="kpi-value">{num(summary.total_events)}</div>
              <div className="kpi-foot">
                <span>Últimos {summary.period_days} días</span>
              </div>
            </div>
            <div className="kpi" data-severity={summary.success_rate >= 95 ? 'ok' : 'warning'}>
              <div className="kpi-label">Tasa de éxito</div>
              <div className="kpi-value">{pctValue(summary.success_rate, 2)}</div>
              <div className="kpi-foot">
                <span>{num(summary.failed_events)} eventos fallidos</span>
              </div>
            </div>
            <div className="kpi" data-severity={summary.failed_events > 0 ? 'warning' : 'ok'}>
              <div className="kpi-label">Fallos</div>
              <div className="kpi-value">{num(summary.failed_events)}</div>
              <div className="kpi-foot">
                <span>Errores y accesos denegados</span>
              </div>
            </div>
            <div className="kpi" data-severity="neutral">
              <div className="kpi-label">Módulos con actividad</div>
              <div className="kpi-value">{num(summary.by_module.length)}</div>
              <div className="kpi-foot">
                <span>{navigationQuery.data?.total ?? 0} eventos de navegación</span>
              </div>
            </div>
          </div>

          <div className="grid grid-sidebar">
            <Card
              title="Eventos por módulo"
              subtitle="Distribución de la actividad auditada en el periodo."
              actions={
                <Field label="Periodo">
                  <select value={days} onChange={(event) => setDays(Number(event.target.value))}>
                    <option value={7}>7 días</option>
                    <option value={30}>30 días</option>
                    <option value={90}>90 días</option>
                    <option value={365}>365 días</option>
                  </select>
                </Field>
              }
            >
              <ExplainedChart explanationId="audit" width="100%" height={Math.max(260, summary.by_module.length * 26)}>
                <BarChart
                  data={summary.by_module}
                  layout="vertical"
                  margin={{ top: 5, right: 24, bottom: 5, left: 10 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="module" width={105} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(value) => [`${num(Number(value))} eventos`, 'Eventos']} />
                  <Bar dataKey="count" name="Eventos" fill={CHART_COLORS[0]} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ExplainedChart>
            </Card>

            <Card title="Usuarios más activos" subtitle="Volumen de eventos por cuenta.">
              {summary.top_users.length === 0 ? (
                <Empty title="Sin actividad registrada" />
              ) : (
                summary.top_users.map((item) => (
                  <MetricRow key={item.email} label={item.email} value={num(item.count)} />
                ))
              )}
              <div style={{ marginTop: '0.8rem' }}>
                <div style={{ fontSize: '0.73rem', color: 'var(--muted)', marginBottom: '0.3rem' }}>
                  Actividad por día
                </div>
                {summary.by_day.length === 0 ? (
                  <Badge>Sin datos</Badge>
                ) : (
                  summary.by_day.slice(-7).map((item) => (
                    <MetricRow key={item.date} label={item.date} value={num(item.count)} />
                  ))
                )}
              </div>
            </Card>
          </div>
        </>
      )}

      <Card title="Filtros de la bitácora" subtitle="Acote por texto, módulo, acción, resultado o rango de fechas.">
        <form
          className="filters"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setAppliedSearch(search.trim());
          }}
        >
          <Field label="Buscar">
            <input
              type="search"
              value={search}
              placeholder="Usuario, ruta o recurso…"
              style={{ minWidth: 210 }}
              onChange={(event) => setSearch(event.target.value)}
            />
          </Field>
          <Field label="Módulo">
            <select
              value={module}
              onChange={(event) => {
                setModule(event.target.value);
                setPage(1);
              }}
            >
              <option value="">Todos</option>
              {modules.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Acción">
            <select
              value={action}
              onChange={(event) => {
                setAction(event.target.value);
                setPage(1);
              }}
            >
              <option value="">Todas</option>
              {ACTION_OPTIONS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Resultado">
            <select
              value={result}
              onChange={(event) => {
                setResult(event.target.value);
                setPage(1);
              }}
            >
              <option value="">Todos</option>
              {RESULT_OPTIONS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Desde">
            <input
              type="datetime-local"
              value={dateFrom}
              onChange={(event) => {
                setDateFrom(event.target.value);
                setPage(1);
              }}
            />
          </Field>
          <Field label="Hasta">
            <input
              type="datetime-local"
              value={dateTo}
              onChange={(event) => {
                setDateTo(event.target.value);
                setPage(1);
              }}
            />
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
              setModule('');
              setAction('');
              setResult('');
              setDateFrom('');
              setDateTo('');
              setPage(1);
            }}
          >
            Limpiar
          </button>
        </form>
      </Card>

      <Card
        title="Registro de eventos"
        subtitle="Detalle de cada operación con usuario, ruta, resultado y duración."
        actions={<Badge tone="brand">{num(logs?.total ?? 0)} eventos</Badge>}
      >
        {logsQuery.isError && <ErrorBox message={errorMessage(logsQuery.error)} />}
        {logsQuery.isLoading && <Loading label="Cargando eventos…" />}
        {logs && logs.items.length === 0 && (
          <Empty title="Sin eventos que coincidan" hint="Ajuste los filtros o amplíe el rango de fechas." />
        )}
        {logs && logs.items.length > 0 && (
          <>
            <DataTable interpretationId="audit"
              columns={logColumns}
              rows={logs.items}
              getKey={(row) => row.id}
              empty="Sin eventos"
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.75rem' }}>
              <button
                type="button"
                className="btn btn-sm"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                ← Anterior
              </button>
              <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
                Página {logs.page} de {logs.pages || 1} · {num(logs.total)} eventos
              </span>
              <button
                type="button"
                className="btn btn-sm"
                disabled={page >= (logs.pages || 1)}
                onClick={() => setPage((current) => current + 1)}
              >
                Siguiente →
              </button>
            </div>
          </>
        )}
      </Card>

      <Card
        title="Navegación entre módulos"
        subtitle="Eventos ENTER/EXIT emitidos por el cliente con identificador de sesión."
        actions={<Badge tone="brand">{num(navigationQuery.data?.total ?? 0)}</Badge>}
      >
        {navigationQuery.isError && <ErrorBox message={errorMessage(navigationQuery.error)} />}
        {navigationQuery.isLoading && <Loading label="Cargando navegación…" />}
        {navigationQuery.data && (
          <DataTable interpretationId="audit"
            columns={navigationColumns}
            rows={navigationQuery.data.items}
            getKey={(row) => row.id}
            empty="Sin eventos de navegación"
          />
        )}
      </Card>
    </>
  );
}

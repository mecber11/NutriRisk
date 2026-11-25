import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Badge, Card, Empty, ErrorBox, Loading, PageHeader, dateTime, severityTone } from '../components/ui';
import type { AlertItem, AlertSummary, Page } from '../types';

const labels: Record<string, string> = { OPEN: 'Abierta', ACKNOWLEDGED: 'Reconocida', RESOLVED: 'Resuelta', CRITICAL: 'Crítica', WARNING: 'Advertencia', INFO: 'Informativa' };

export default function Alerts() {
  const { can } = useAuth();
  const client = useQueryClient();
  const [status, setStatus] = useState('');
  const [severity, setSeverity] = useState('');
  const [page, setPage] = useState(1);
  const summary = useQuery({ queryKey: ['alerts', 'summary'], queryFn: () => api.get<AlertSummary>('/alerts/summary') });
  const alerts = useQuery({ queryKey: ['alerts', 'list', status, severity, page], queryFn: () => api.get<Page<AlertItem>>('/alerts', { status, severity, page, page_size: 20 }) });
  const action = useMutation({
    mutationFn: (path: string) => api.post(path, {}),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ['alerts'] }); },
  });
  const error = alerts.error || summary.error || action.error;
  return <>
    <PageHeader title="Alertas y notificaciones" subtitle="Seguimiento de riesgos territoriales y reglas de vigilancia nutricional." actions={can('alerts', 'create') ? <button className="btn btn-primary" disabled={action.isPending} onClick={() => action.mutate('/alerts/evaluate')}>Evaluar reglas</button> : undefined} />
    {error && <ErrorBox message={error instanceof Error ? error.message : 'No se pudieron cargar las alertas.'} />}
    {summary.data && <div className="grid grid-3">{[['Abiertas', summary.data.open], ['Reconocidas', summary.data.acknowledged], ['Resueltas', summary.data.resolved]].map(([label, count]) => <Card key={label} title={String(label)}><strong style={{ fontSize: '2rem' }}>{count}</strong></Card>)}</div>}
    <Card title="Registro de alertas">
      <div className="chip-row" style={{ marginBottom: '1rem' }}>
        <label>Estado <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="">Todos</option>{['OPEN', 'ACKNOWLEDGED', 'RESOLVED'].map(value => <option key={value} value={value}>{labels[value]}</option>)}</select></label>
        <label>Severidad <select value={severity} onChange={e => { setSeverity(e.target.value); setPage(1); }}><option value="">Todas</option>{['CRITICAL', 'WARNING', 'INFO'].map(value => <option key={value} value={value}>{labels[value]}</option>)}</select></label>
      </div>
      {alerts.isLoading && <Loading label="Cargando alertas…" />}
      {alerts.data?.items.length === 0 && <Empty title="No hay alertas con estos filtros" />}
      {alerts.data?.items.map(alert => <article key={alert.id} style={{ padding: '1rem 0', borderBottom: '1px solid var(--border)' }}>
        <div className="chip-row"><Badge tone={severityTone(alert.severity)}>{labels[alert.severity] ?? alert.severity}</Badge><Badge>{labels[alert.status] ?? alert.status}</Badge><span>{dateTime(alert.created_at)}</span></div>
        <h3>{alert.title}</h3><p>{alert.message}</p>
        {can('alerts', 'update') && alert.status !== 'RESOLVED' && <div className="chip-row">
          {alert.status === 'OPEN' && <button className="btn btn-sm" disabled={action.isPending} onClick={() => action.mutate(`/alerts/${alert.id}/acknowledge`)}>Reconocer</button>}
          <button className="btn btn-sm" disabled={action.isPending} onClick={() => action.mutate(`/alerts/${alert.id}/resolve`)}>Resolver</button>
        </div>}
      </article>)}
      <div className="chip-row" style={{ marginTop: '1rem' }}><button className="btn btn-sm" disabled={page === 1 || alerts.isFetching} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="btn btn-sm" disabled={!alerts.data || page * 20 >= alerts.data.total || alerts.isFetching} onClick={() => setPage(page + 1)}>Siguiente</button></div>
    </Card>
  </>;
}

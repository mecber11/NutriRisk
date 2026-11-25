import { Interpretation } from '../components/Interpretation';
import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, downloadFile } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import {
  Badge,
  Card,
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
} from '../components/ui';
import type { Column } from '../components/ui';
import type {
  DashboardOptions,
  ModelComparison,
  Page,
  ReportItem,
  ReportKind,
  ReportScheduleInfo,
} from '../types';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo completar la operación.';
}

function formatSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function statusTone(status: string): 'ok' | 'warning' | 'danger' | 'neutral' {
  switch (status.toUpperCase()) {
    case 'READY':
      return 'ok';
    case 'QUEUED':
    case 'RUNNING':
      return 'warning';
    case 'FAILED':
    case 'ERROR':
      return 'danger';
    default:
      return 'neutral';
  }
}

interface ReportParamsState {
  year: string;
  territory_code: string;
  region: string;
  model_id: string;
  limit: string;
  date_from: string;
  date_to: string;
  module: string;
  action: string;
  search: string;
}

const EMPTY_PARAMS: ReportParamsState = {
  year: '',
  territory_code: '',
  region: '',
  model_id: '',
  limit: '',
  date_from: '',
  date_to: '',
  module: '',
  action: '',
  search: '',
};

const PARAM_LABELS: Record<string, string> = {
  year: 'Año',
  territory_code: 'Territorio',
  region: 'Región',
  model_id: 'Modelo',
  limit: 'Límite de registros',
  date_from: 'Desde',
  date_to: 'Hasta',
  module: 'Módulo',
  action: 'Acción',
  search: 'Búsqueda',
};

export default function Reports() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [kindCode, setKindCode] = useState('');
  const [fmt, setFmt] = useState('');
  const [title, setTitle] = useState('');
  const [params, setParams] = useState<ReportParamsState>(EMPTY_PARAMS);
  const [message, setMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const canCreate = can('reports', 'create');

  const kindsQuery = useQuery({
    queryKey: ['reports', 'kinds'],
    queryFn: () => api.get<ReportKind[]>('/reports/kinds'),
  });

  const reportsQuery = useQuery({
    queryKey: ['reports', 'list'],
    queryFn: () => api.get<Page<ReportItem>>('/reports', { page: 1, page_size: 50 }),
  });

  const optionsQuery = useQuery({
    queryKey: ['dashboard', 'options'],
    queryFn: () => api.get<DashboardOptions>('/dashboard/options'),
  });

  const modelsQuery = useQuery({
    queryKey: ['models', 'comparison'],
    queryFn: () => api.get<ModelComparison[]>('/models/comparison'),
  });

  const kinds = kindsQuery.data ?? [];
  const selectedKind = kinds.find((kind) => kind.code === kindCode) ?? kinds[0];
  const reports = reportsQuery.data?.items ?? [];

  useEffect(() => {
    if (!kindCode && kinds.length > 0) setKindCode(kinds[0].code);
  }, [kinds, kindCode]);

  useEffect(() => {
    if (selectedKind && !selectedKind.formats.includes(fmt)) {
      setFmt(selectedKind.formats[0] ?? 'pdf');
    }
  }, [selectedKind, fmt]);

  const generateMutation = useMutation({
    mutationFn: () => {
      if (!selectedKind) throw new Error('Seleccione un tipo de reporte.');
      const cleanParams: Record<string, string | number> = {};
      selectedKind.params.forEach((key) => {
        const value = params[key as keyof ReportParamsState];
        if (value === undefined || value === '') return;
        if (key === 'year' || key === 'model_id' || key === 'limit') {
          cleanParams[key] = Number(value);
        } else {
          cleanParams[key] = value;
        }
      });
      return api.post<ReportItem>('/reports/generate', {
        kind: selectedKind.code,
        fmt,
        title: title.trim() || undefined,
        params: cleanParams,
      });
    },
    onSuccess: (report) => {
      setActionError(null);
      setMessage(
        `Reporte generado: ${report.title} (${report.fmt.toUpperCase()}, ${formatSize(report.size_bytes)}).`,
      );
      void queryClient.invalidateQueries({ queryKey: ['reports', 'list'] });
    },
    onError: (error) => {
      setMessage(null);
      setActionError(errorMessage(error));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.del<unknown>(`/reports/${id}`),
    onSuccess: () => {
      setActionError(null);
      setMessage('Reporte eliminado.');
      void queryClient.invalidateQueries({ queryKey: ['reports', 'list'] });
    },
    onError: (error) => setActionError(errorMessage(error)),
  });

  const scheduleMutation = useMutation({
    mutationFn: () => api.post<ReportScheduleInfo>('/reports/schedule'),
    onError: (error) => setActionError(errorMessage(error)),
  });

  async function handleDownload(report: ReportItem) {
    setActionError(null);
    try {
      await downloadFile(
        `/reports/${report.id}/download`,
        report.file_name ?? `reporte-${report.id}.${report.fmt}`,
      );
    } catch (error) {
      setActionError(errorMessage(error));
    }
  }

  const visibleParams = selectedKind?.params ?? [];
  const years = optionsQuery.data?.years ?? [];
  const territories = optionsQuery.data?.territories ?? [];
  const regions = optionsQuery.data?.regions ?? [];
  const models = modelsQuery.data ?? [];

  const columns: Column<ReportItem>[] = useMemo(
    () => [
      {
        key: 'title',
        header: 'Reporte',
        render: (row) => (
          <div>
            <div style={{ fontWeight: 600 }}>{row.title}</div>
            <div style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>
              {row.kind} · {row.file_name ?? 'sin archivo'}
            </div>
          </div>
        ),
      },
      { key: 'fmt', header: 'Formato', render: (row) => <Badge tone="info">{row.fmt.toUpperCase()}</Badge> },
      { key: 'size', header: 'Tamaño', align: 'right', render: (row) => formatSize(row.size_bytes) },
      {
        key: 'status',
        header: 'Estado',
        render: (row) => <Badge tone={statusTone(row.status)}>{row.status}</Badge>,
      },
      { key: 'created_at', header: 'Generado', render: (row) => dateTime(row.created_at) },
      {
        key: 'actions',
        header: '',
        align: 'right',
        render: (row) => (
          <div style={{ display: 'flex', gap: '0.3rem', justifyContent: 'flex-end' }}>
            <button
              type="button"
              className="btn btn-sm"
              disabled={row.status !== 'READY'}
              onClick={() => void handleDownload(row)}
            >
              Descargar
            </button>
            {canCreate && (
              <button
                type="button"
                className="btn btn-sm btn-danger"
                disabled={deleteMutation.isPending}
                onClick={() => {
                  if (window.confirm(`¿Eliminar el reporte «${row.title}»?`)) {
                    deleteMutation.mutate(row.id);
                  }
                }}
              >
                Eliminar
              </button>
            )}
          </div>
        ),
      },
    ],
    [canCreate, deleteMutation],
  );

  function updateParam(key: keyof ReportParamsState, value: string) {
    setParams((current) => ({ ...current, [key]: value }));
  }

  function renderParamField(key: string) {
    const label = PARAM_LABELS[key] ?? key;
    if (key === 'year') {
      return (
        <Field key={key} label={label}>
          <select value={params.year} onChange={(event) => updateParam('year', event.target.value)}>
            <option value="">Último disponible</option>
            {years.map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
        </Field>
      );
    }
    if (key === 'territory_code') {
      return (
        <Field key={key} label={label}>
          <select
            value={params.territory_code}
            onChange={(event) => updateParam('territory_code', event.target.value)}
          >
            <option value="">Todos</option>
            {territories.map((territory) => (
              <option key={territory.code} value={territory.code}>
                {territory.code} · {territory.name}
              </option>
            ))}
          </select>
        </Field>
      );
    }
    if (key === 'region') {
      return (
        <Field key={key} label={label}>
          <select value={params.region} onChange={(event) => updateParam('region', event.target.value)}>
            <option value="">Todas</option>
            {regions.map((region) => (
              <option key={region} value={region}>
                {region}
              </option>
            ))}
          </select>
        </Field>
      );
    }
    if (key === 'model_id') {
      return (
        <Field key={key} label={label}>
          <select value={params.model_id} onChange={(event) => updateParam('model_id', event.target.value)}>
            <option value="">Modelo activo</option>
            {models.map((model) => (
              <option key={model.model_id} value={model.model_id}>
                #{model.model_id} · {model.name} v{model.version}
              </option>
            ))}
          </select>
        </Field>
      );
    }
    if (key === 'limit') {
      return (
        <Field key={key} label={label}>
          <input
            type="number"
            min={1}
            max={500}
            value={params.limit}
            placeholder="24"
            onChange={(event) => updateParam('limit', event.target.value)}
          />
        </Field>
      );
    }
    if (key === 'date_from' || key === 'date_to') {
      return (
        <Field key={key} label={label}>
          <input
            type="datetime-local"
            value={params[key]}
            onChange={(event) => updateParam(key, event.target.value)}
          />
        </Field>
      );
    }
    if (key === 'module' || key === 'action' || key === 'search') {
      return (
        <Field key={key} label={label}>
          <input
            type="text"
            value={params[key as keyof ReportParamsState]}
            placeholder={key === 'search' ? 'Texto libre' : key}
            onChange={(event) => updateParam(key as keyof ReportParamsState, event.target.value)}
          />
        </Field>
      );
    }
    return (
      <Field key={key} label={label}>
        <input
          type="text"
          value={params[key as keyof ReportParamsState] ?? ''}
          onChange={(event) => updateParam(key as keyof ReportParamsState, event.target.value)}
        />
      </Field>
    );
  }

  const scheduleInfo = scheduleMutation.data;

  return (
    <>
      <PageHeader
        title="Reportes institucionales"
        subtitle="Genere fichas, rankings, informes de equidad y exportaciones de bitácora en PDF, Word o Excel."
        actions={<Badge tone="brand">{reports.length} reportes</Badge>}
      />

      {actionError && <ErrorBox message={actionError} />}
      {message && (
        <div className="notice" data-tone="ok">
          {message}
        </div>
      )}

      <div className="grid grid-sidebar">
        <Card
          title="Generar reporte"
          subtitle="Elija el tipo, el formato y los parámetros del informe."
        >
          {!canCreate && (
            <div className="notice" data-tone="warning">
              Su rol permite consultar y descargar reportes, pero no generarlos.
            </div>
          )}
          {kindsQuery.isError && <ErrorBox message={errorMessage(kindsQuery.error)} />}
          {kindsQuery.isLoading && <Loading label="Cargando tipos de reporte…" />}
          {selectedKind && (
            <>
              <div className="filters">
                <Field label="Tipo de reporte">
                  <select
                    value={selectedKind.code}
                    onChange={(event) => setKindCode(event.target.value)}
                    style={{ minWidth: 250 }}
                  >
                    {kinds.map((kind) => (
                      <option key={kind.code} value={kind.code}>
                        {kind.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Formato">
                  <select value={fmt} onChange={(event) => setFmt(event.target.value)}>
                    {selectedKind.formats.map((format) => (
                      <option key={format} value={format}>
                        {format.toUpperCase()}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Título (opcional)">
                  <input
                    type="text"
                    value={title}
                    placeholder={selectedKind.label}
                    style={{ minWidth: 230 }}
                    onChange={(event) => setTitle(event.target.value)}
                  />
                </Field>
              </div>
              <p style={{ marginTop: '0.6rem', marginBottom: '0.6rem', fontSize: '0.8rem', color: 'var(--muted)' }}>
                {selectedKind.description}
              </p>
              <div className="filters">
                {visibleParams.map((key) => renderParamField(key))}
              </div>
              <button
                type="button"
                className="btn btn-primary"
                style={{ marginTop: '0.9rem' }}
                disabled={!canCreate || generateMutation.isPending}
                onClick={() => generateMutation.mutate()}
              >
                {generateMutation.isPending ? 'Generando reporte…' : 'Generar reporte'}
              </button>
              <small style={{ display: 'block', marginTop: '0.5rem' }}>
                Los reportes se almacenan con control de acceso y quedan registrados en la bitácora.
              </small>
            </>
          )}
        </Card>

        <Card
          title="Programación automática"
          subtitle="Los reportes recurrentes se orquestan con n8n."
          actions={<Badge tone="info">n8n</Badge>}
        >
          <p style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>
            Programe la generación semanal o mensual de reportes y su distribución por correo desde el
            flujo de n8n.
          </p>
          <button
            type="button"
            className="btn"
            disabled={!canCreate || scheduleMutation.isPending}
            onClick={() => scheduleMutation.mutate()}
          >
            {scheduleMutation.isPending ? 'Consultando…' : 'Programar reportes'}
          </button>
          {scheduleInfo && (
            <div style={{ marginTop: '0.75rem' }}>
              <div className="notice" data-tone="info">
                {scheduleInfo.message}
              </div>
              <MetricRow label="Webhook" value={<span className="mono">{scheduleInfo.webhook ?? '—'}</span>} />
              <MetricRow
                label="Endpoint de generación"
                value={<span className="mono">{scheduleInfo.api_endpoint ?? '—'}</span>}
              />
              {scheduleInfo.import_file && (
                <MetricRow label="Flujo de importación" value={scheduleInfo.import_file} />
              )}
              {scheduleInfo.cron_examples && (
                <div style={{ marginTop: '0.5rem' }}>
                  <div style={{ fontSize: '0.73rem', color: 'var(--muted)', marginBottom: '0.25rem' }}>
                    Expresiones cron de ejemplo
                  </div>
                  <div className="chip-row">
                    {scheduleInfo.cron_examples.map((cron) => (
                      <Badge key={cron} tone="neutral">
                        {cron}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          {scheduleMutation.isError && <ErrorBox message={errorMessage(scheduleMutation.error)} />}
          <div style={{ marginTop: '0.8rem' }}>
            <MetricRow label="Tipos disponibles" value={num(kinds.length)} />
            <MetricRow label="Formatos" value="PDF · Word · Excel" />
          </div>
        </Card>
      </div>

      <Card
        title="Historial de reportes"
        subtitle="Descargue o elimine los informes generados por el equipo."
        actions={<Badge tone="brand">{reports.length}</Badge>}
      >
        {reportsQuery.isError && <ErrorBox message={errorMessage(reportsQuery.error)} />}
        {reportsQuery.isLoading && <Loading label="Cargando historial…" />}
        {!reportsQuery.isLoading && reports.length === 0 && (
          <Empty title="Sin reportes generados" hint="Genere el primer informe con el formulario." />
        )}
        {reports.length > 0 && (
          <DataTable interpretationId="reports"
            columns={columns}
            rows={reports}
            getKey={(row) => row.id}
            empty="Sin reportes"
          />
        )}
        {reports.length > 0 && (
          <div style={{ marginTop: '0.6rem', fontSize: '0.75rem', color: 'var(--muted)' }}>
            Tamaño total: {formatSize(reports.reduce((total, report) => total + report.size_bytes, 0))} ·{' '}
            {num(reports.length)} documentos
          </div>
        )}
      </Card>
    </>
  );
}

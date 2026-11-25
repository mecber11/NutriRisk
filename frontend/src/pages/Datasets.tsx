import { Interpretation } from '../components/Interpretation';
import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
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
  pct,
} from '../components/ui';
import type { Column } from '../components/ui';
import type {
  Dataset,
  DatasetPreview,
  DatasetQualityResponse,
  DatasetSources,
  DatasetVariable,
  Page,
  UploadResult,
} from '../types';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo completar la operación.';
}

function qualityTone(score: number | undefined): 'ok' | 'warning' | 'danger' | 'neutral' {
  if (score === undefined || score === null) return 'neutral';
  if (score >= 90) return 'ok';
  if (score >= 70) return 'warning';
  return 'danger';
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? 'Sí' : 'No';
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export default function Datasets() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [name, setName] = useState('');
  const [source, setSource] = useState('CUSTOM');
  const [kind, setKind] = useState('CHILD');
  const [analysisUnit, setAnalysisUnit] = useState('CHILD');
  const [description, setDescription] = useState('');
  const [periodYear, setPeriodYear] = useState('');
  const [country, setCountry] = useState('');
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [templateError, setTemplateError] = useState<string | null>(null);

  const canUpload = can('datasets', 'create');

  const datasetsQuery = useQuery({
    queryKey: ['datasets', 'list'],
    queryFn: () => api.get<Page<Dataset>>('/datasets', { page: 1, page_size: 50 }),
  });

  const sourcesQuery = useQuery({
    queryKey: ['datasets', 'sources'],
    queryFn: () => api.get<DatasetSources>('/datasets/sources'),
  });

  const datasets = datasetsQuery.data?.items ?? [];
  const sources = sourcesQuery.data;

  useEffect(() => {
    if (selectedId === null && datasets.length > 0) setSelectedId(datasets[0].id);
  }, [datasets, selectedId]);

  const selected = datasets.find((dataset) => dataset.id === selectedId) ?? datasets[0];

  const qualityQuery = useQuery({
    queryKey: ['datasets', 'quality', selected?.id],
    queryFn: () => api.get<DatasetQualityResponse>(`/datasets/${selected?.id}/quality`),
    enabled: Boolean(selected?.id),
  });

  const variablesQuery = useQuery({
    queryKey: ['datasets', 'variables', selected?.id],
    queryFn: () => api.get<DatasetVariable[]>(`/datasets/${selected?.id}/variables`),
    enabled: Boolean(selected?.id),
  });

  const previewQuery = useQuery({
    queryKey: ['datasets', 'preview', selected?.id],
    queryFn: () => api.get<DatasetPreview>(`/datasets/${selected?.id}/preview`, { limit: 10 }),
    enabled: Boolean(selected?.id),
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('Seleccione un archivo para cargar.');
      if (!name.trim()) throw new Error('Ingrese un nombre para el dataset.');
      const formData = new FormData();
      formData.append('file', file);
      formData.append('name', name.trim());
      formData.append('source', source);
      formData.append('kind', kind);
      formData.append('analysis_unit', analysisUnit);
      if (description.trim()) formData.append('description', description.trim());
      if (periodYear.trim()) formData.append('period_year', periodYear.trim());
      if (country.trim()) formData.append('country', country.trim());
      return api.upload<UploadResult>('/datasets/upload', formData);
    },
    onSuccess: (result) => {
      setUploadError(null);
      setUploadMessage(
        `Dataset «${result.dataset.name}» cargado con ${num(result.dataset.rows)} filas y ${num(
          result.dataset.columns,
        )} columnas.`,
      );
      setName('');
      setDescription('');
      setPeriodYear('');
      setCountry('');
      setFile(null);
      setFileInputKey((current) => current + 1);
      setSelectedId(result.dataset.id);
      void queryClient.invalidateQueries({ queryKey: ['datasets'] });
    },
    onError: (error) => {
      setUploadMessage(null);
      setUploadError(errorMessage(error));
    },
  });

  async function handleTemplate() {
    setTemplateError(null);
    try {
      await downloadFile('/datasets/template', 'plantilla_dataset_nutririsk.csv');
    } catch (error) {
      setTemplateError(errorMessage(error));
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setUploadMessage(null);
    setUploadError(null);
    uploadMutation.mutate();
  }

  const datasetColumns: Column<Dataset>[] = [
    {
      key: 'name',
      header: 'Dataset',
      render: (row) => (
        <div>
          <div style={{ fontWeight: 600 }}>{row.name}</div>
          <div style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>
            {row.slug} · {row.period_year ?? 'sin periodo'}
          </div>
        </div>
      ),
    },
    {
      key: 'source',
      header: 'Fuente',
      render: (row) => <Badge tone={row.is_synthetic ? 'info' : 'neutral'}>{row.source}</Badge>,
    },
    { key: 'kind', header: 'Tipo', render: (row) => row.kind },
    { key: 'rows', header: 'Filas', align: 'right', render: (row) => num(row.rows) },
    { key: 'columns', header: 'Columnas', align: 'right', render: (row) => num(row.columns) },
    {
      key: 'quality',
      header: 'Calidad',
      align: 'right',
      render: (row) => (
        <Badge tone={qualityTone(row.quality_report?.score)}>
          {row.quality_report?.score !== undefined ? `${decimal(row.quality_report.score, 0)} / 100` : 'Sin evaluar'}
        </Badge>
      ),
    },
    {
      key: 'status',
      header: 'Estado',
      render: (row) => <Badge tone={row.status === 'READY' ? 'ok' : 'warning'}>{row.status}</Badge>,
    },
    { key: 'created_at', header: 'Creado', render: (row) => dateTime(row.created_at) },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (row) => (
        <button type="button" className="btn btn-sm" onClick={() => setSelectedId(row.id)}>
          {selected?.id === row.id ? 'Seleccionado' : 'Ver detalle'}
        </button>
      ),
    },
  ];

  const variableColumns: Column<DatasetVariable>[] = [
    { key: 'name', header: 'Variable', render: (row) => <span className="mono">{row.name}</span> },
    { key: 'label', header: 'Etiqueta', render: (row) => row.label ?? '—' },
    { key: 'dtype', header: 'Tipo', render: (row) => row.dtype ?? '—' },
    {
      key: 'required',
      header: 'Obligatoria',
      render: (row) => (row.is_required ? <Badge tone="warning">Sí</Badge> : <Badge>No</Badge>),
    },
    { key: 'missing', header: 'Faltantes', align: 'right', render: (row) => num(row.missing_count) },
    {
      key: 'unique',
      header: 'Únicos',
      align: 'right',
      render: (row) => num(row.stats?.unique),
    },
    {
      key: 'range',
      header: 'Rango',
      render: (row) =>
        row.min_value !== null && row.min_value !== undefined
          ? `${decimal(row.min_value, 2)} – ${decimal(row.max_value, 2)}`
          : '—',
    },
  ];

  const quality = qualityQuery.data?.quality_report;
  const preview = previewQuery.data;
  const previewRows = useMemo(() => preview?.rows.slice(0, 10) ?? [], [preview]);

  return (
    <>
      <PageHeader
        title="Datasets e ingesta"
        subtitle="Catálogo de fuentes, calidad de datos, variables y carga de nuevas encuestas."
        actions={
          <button type="button" className="btn" onClick={handleTemplate}>
            Descargar plantilla CSV
          </button>
        }
      />

      {templateError && <ErrorBox message={templateError} />}
      {uploadError && <ErrorBox message={uploadError} />}
      {uploadMessage && (
        <div className="notice" data-tone="ok">
          {uploadMessage}
        </div>
      )}

      {datasetsQuery.isError && <ErrorBox message={errorMessage(datasetsQuery.error)} />}
      {datasetsQuery.isLoading && <Loading label="Cargando catálogo de datasets…" />}

      <Card
        title="Catálogo de datasets"
        subtitle="Fuentes disponibles para entrenamiento, indicadores y reportería."
        actions={<Badge tone="brand">{datasets.length} datasets</Badge>}
      >
        <DataTable interpretationId="datasets"
          columns={datasetColumns}
          rows={datasets}
          getKey={(row) => row.id}
          empty="Sin datasets cargados"
        />
      </Card>

      {selected && (
        <div className="grid grid-sidebar" style={{ marginTop: '1rem' }}>
          <div>
            <Card
              title={selected.name}
              subtitle={`${selected.source} · ${selected.kind} · ${selected.analysis_unit}`}
              actions={<Badge tone={selected.status === 'READY' ? 'ok' : 'warning'}>{selected.status}</Badge>}
            >
              <div className="grid grid-2">
                <div>
                  <MetricRow label="Identificador" value={`#${selected.id}`} />
                  <MetricRow label="Periodo" value={selected.period_year ?? '—'} />
                  <MetricRow label="País" value={selected.country ?? '—'} />
                  <MetricRow label="Filas" value={num(selected.rows)} />
                  <MetricRow label="Columnas" value={num(selected.columns)} />
                </div>
                <div>
                  <MetricRow label="Archivo" value={selected.slug} />
                  <MetricRow label="Creado" value={dateTime(selected.created_at)} />
                  <MetricRow
                    label="Calidad"
                    value={
                      <Badge tone={qualityTone(selected.quality_report?.score)}>
                        {selected.quality_report?.score !== undefined
                          ? `${decimal(selected.quality_report.score, 0)} / 100`
                          : 'Sin evaluar'}
                      </Badge>
                    }
                  />
                  <MetricRow label="Sintético" value={selected.is_synthetic ? 'Sí' : 'No'} />
                </div>
              </div>
              {selected.description && (
                <p style={{ marginTop: '0.75rem', marginBottom: 0, fontSize: '0.82rem', color: 'var(--muted)' }}>
                  {selected.description}
                </p>
              )}
            </Card>

            <Card
              title="Reporte de calidad"
              subtitle="Duplicados, faltantes, atípicos y hallazgos del perfilado automático."
            >
              {qualityQuery.isError && <ErrorBox message={errorMessage(qualityQuery.error)} />}
              {qualityQuery.isLoading && <Loading label="Evaluando calidad…" />}
              {quality && (
                <>
                  <div className="grid grid-2">
                    <div>
                      <MetricRow label="Puntaje" value={decimal(quality.score, 0)} />
                      <MetricRow label="Filas" value={num(quality.rows ?? qualityQuery.data?.rows)} />
                      <MetricRow label="Columnas" value={num(quality.columns ?? qualityQuery.data?.columns)} />
                      <MetricRow label="Duplicados" value={num(quality.duplicate_rows)} />
                    </div>
                    <div>
                      <MetricRow label="Celdas faltantes" value={num(quality.missing_cells)} />
                      <MetricRow label="Proporción faltante" value={pct(quality.missing_ratio)} />
                      <MetricRow label="Atípicos" value={num(quality.outliers)} />
                      <MetricRow label="Verificado" value={dateTime(quality.checked_at)} />
                    </div>
                  </div>
                  <div style={{ marginTop: '0.7rem' }}>
                    <div style={{ fontSize: '0.73rem', color: 'var(--muted)', marginBottom: '0.3rem' }}>
                      Hallazgos
                    </div>
                    {quality.issues && quality.issues.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                        {quality.issues.map((issue) => (
                          <div key={`${issue.code}-${issue.message}`} style={{ fontSize: '0.8rem' }}>
                            <Badge tone={issue.severity === 'HIGH' ? 'danger' : 'warning'}>
                              {issue.severity}
                            </Badge>{' '}
                            {issue.message}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <Badge tone="ok">Sin hallazgos críticos</Badge>
                    )}
                  </div>
                </>
              )}
            </Card>

            <Card
              title="Vista previa"
              subtitle={`Primeras ${previewRows.length} filas de ${num(preview?.total_rows)}.`}
            >
              {previewQuery.isError && <ErrorBox message={errorMessage(previewQuery.error)} />}
              {previewQuery.isLoading && <Loading label="Cargando vista previa…" />}
              {preview && previewRows.length > 0 ? (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        {preview.columns.map((column) => (
                          <th key={column}>{column}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {previewRows.map((row, index) => (
                        <tr key={index}>
                          {preview.columns.map((column) => (
                            <td key={column}>{formatCell(row[column])}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
<Interpretation id="datasets" />
                </div>
              ) : (
                !previewQuery.isLoading && <Empty title="Sin filas para previsualizar" />
              )}
            </Card>
          </div>

          <div>
            {canUpload ? (
              <Card
                title="Cargar dataset"
                subtitle={`Formatos ${sources?.formats.join(', ') ?? 'CSV'} · máximo ${sources?.max_upload_mb ?? 80} MB`}
              >
                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  <Field label="Archivo">
                    <input
                      key={fileInputKey}
                      type="file"
                      accept=".csv,.xlsx,.xls,.json"
                      onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                    />
                  </Field>
                  <Field label="Nombre del dataset">
                    <input
                      type="text"
                      value={name}
                      placeholder="Encuesta nutricional 2024"
                      onChange={(event) => setName(event.target.value)}
                    />
                  </Field>
                  <div className="grid grid-2">
                    <Field label="Fuente">
                      <select value={source} onChange={(event) => setSource(event.target.value)}>
                        {(sources?.sources ?? [{ code: 'CUSTOM', label: 'Personalizada' }]).map((item) => (
                          <option key={item.code} value={item.code}>
                            {item.label}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Tipo">
                      <select value={kind} onChange={(event) => setKind(event.target.value)}>
                        <option value="CHILD">Niños</option>
                        <option value="HOUSEHOLD">Hogares</option>
                        <option value="TERRITORY">Territorios</option>
                      </select>
                    </Field>
                  </div>
                  <div className="grid grid-2">
                    <Field label="Unidad de análisis">
                      <select value={analysisUnit} onChange={(event) => setAnalysisUnit(event.target.value)}>
                        <option value="CHILD">Niño</option>
                        <option value="HOUSEHOLD">Hogar</option>
                        <option value="TERRITORY">Territorio</option>
                      </select>
                    </Field>
                    <Field label="Periodo">
                      <input
                        type="number"
                        min={2000}
                        max={2100}
                        value={periodYear}
                        placeholder="2024"
                        onChange={(event) => setPeriodYear(event.target.value)}
                      />
                    </Field>
                  </div>
                  <Field label="País">
                    <input
                      type="text"
                      value={country}
                      placeholder="República de Andara"
                      onChange={(event) => setCountry(event.target.value)}
                    />
                  </Field>
                  <Field label="Descripción">
                    <textarea
                      rows={3}
                      value={description}
                      placeholder="Origen, licencia y notas de la fuente…"
                      onChange={(event) => setDescription(event.target.value)}
                    />
                  </Field>
                  <button type="submit" className="btn btn-primary" disabled={uploadMutation.isPending}>
                    {uploadMutation.isPending ? 'Cargando y perfilando…' : 'Cargar dataset'}
                  </button>
                  <small style={{ color: 'var(--muted)' }}>
                    El archivo se valida contra las columnas canónicas y se genera un reporte de calidad
                    automático.
                  </small>
                </form>
              </Card>
            ) : (
              <Card title="Cargar dataset">
                <Empty
                  title="Su rol no permite cargar datasets"
                  hint="Solicite permisos de creación al administrador del sistema."
                />
              </Card>
            )}

            <Card title="Fuentes disponibles" subtitle="Orígenes soportados por la ingesta.">
              {sourcesQuery.isError && <ErrorBox message={errorMessage(sourcesQuery.error)} />}
              {sourcesQuery.isLoading && <Loading label="Cargando fuentes…" />}
              {sources && (
                <>
                  {sources.sources.map((item) => (
                    <div key={item.code} style={{ marginBottom: '0.5rem' }}>
                      <div style={{ fontWeight: 600, fontSize: '0.83rem' }}>{item.label}</div>
                      <div style={{ fontSize: '0.76rem', color: 'var(--muted)' }}>
                        {item.description ?? item.code}
                      </div>
                    </div>
                  ))}
                  {sources.canonical_columns.length > 0 && (
                    <details style={{ marginTop: '0.6rem' }}>
                      <summary style={{ cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600 }}>
                        Columnas canónicas ({sources.canonical_columns.length})
                      </summary>
                      <div className="chip-row" style={{ marginTop: '0.4rem' }}>
                        {sources.canonical_columns.map((column) => (
                          <Badge key={column} tone="info">
                            {column}
                          </Badge>
                        ))}
                      </div>
                    </details>
                  )}
                </>
              )}
            </Card>
          </div>
        </div>
      )}

      {selected && (
        <Card
          title="Variables del dataset"
          subtitle="Diccionario de columnas, tipos y completitud."
          actions={<Badge tone="brand">{variablesQuery.data?.length ?? 0} variables</Badge>}
        >
          {variablesQuery.isError && <ErrorBox message={errorMessage(variablesQuery.error)} />}
          {variablesQuery.isLoading && <Loading label="Cargando variables…" />}
          {variablesQuery.data && (
            <DataTable interpretationId="datasets"
              columns={variableColumns}
              rows={variablesQuery.data}
              getKey={(row) => row.id}
              empty="Sin variables registradas"
            />
          )}
        </Card>
      )}

      {datasets.length === 0 && !datasetsQuery.isLoading && (
        <Empty
          title="Sin datasets disponibles"
          hint="Cargue un archivo CSV para comenzar a operar el pipeline."
        />
      )}
    </>
  );
}


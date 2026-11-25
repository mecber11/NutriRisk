import { Interpretation } from '../components/Interpretation';
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
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
  pctValue,
} from '../components/ui';
import type { Column } from '../components/ui';
import type { SettingGroup, SystemInfo, SystemMonitoring } from '../types';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo guardar la configuración.';
}

export default function Settings() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const canUpdate = can('settings', 'update');

  const settingsQuery = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get<SettingGroup[]>('/settings'),
  });

  const systemQuery = useQuery({
    queryKey: ['system', 'info'],
    queryFn: () => api.get<SystemInfo>('/system/info'),
  });

  const monitoringQuery = useQuery({
    queryKey: ['system', 'monitoring'],
    queryFn: () => api.get<SystemMonitoring>('/system/monitoring'),
  });

  const settings = settingsQuery.data ?? [];

  useEffect(() => {
    if (!settingsQuery.data) return;
    setDrafts((current) => {
      const next = { ...current };
      settingsQuery.data.forEach((group) => {
        group.items.forEach((item) => {
          if (!(item.key in next)) {
            next[item.key] = JSON.stringify(item.value, null, 2);
          }
        });
      });
      return next;
    });
  }, [settingsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: ({ key, value }: { key: string; value: Record<string, unknown> }) =>
      api.put<unknown>(`/settings/${key}`, { value }),
    onSuccess: (_result, variables) => {
      setMessage(`Configuración «${variables.key}» actualizada.`);
      setErrors((current) => {
        const next = { ...current };
        delete next[variables.key];
        return next;
      });
      void queryClient.invalidateQueries({ queryKey: ['settings'] });
    },
    onError: (error, variables) => {
      setMessage(null);
      setErrors((current) => ({ ...current, [variables.key]: errorMessage(error) }));
    },
    onSettled: () => setSavingKey(null),
  });

  function save(key: string) {
    setMessage(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(drafts[key] ?? '');
    } catch {
      setErrors((current) => ({ ...current, [key]: 'El contenido no es un JSON válido.' }));
      return;
    }
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      setErrors((current) => ({
        ...current,
        [key]: 'El valor debe ser un objeto JSON (clave: valor).',
      }));
      return;
    }
    setSavingKey(key);
    saveMutation.mutate({ key, value: parsed as Record<string, unknown> });
  }

  const info = systemQuery.data;
  const monitoring = monitoringQuery.data;

  const eventColumns: Column<SystemMonitoring['latest_events'][number]>[] = [
    { key: 'started_at', header: 'Fecha y hora', render: (row) => dateTime(row.started_at) },
    { key: 'module', header: 'Módulo' },
    { key: 'action', header: 'Acción' },
    {
      key: 'result',
      header: 'Resultado',
      render: (row) => (
        <Badge tone={row.result === 'SUCCESS' ? 'ok' : 'danger'}>{row.result}</Badge>
      ),
    },
    { key: 'duration_ms', header: 'Duración', align: 'right', render: (row) => `${num(row.duration_ms)} ms` },
  ];

  return (
    <>
      <PageHeader
        title="Configuración del sistema"
        subtitle="Parámetros operativos, umbrales de alerta e información del entorno de ejecución."
        actions={<Badge tone={info?.demo_mode ? 'warning' : 'ok'}>{info?.demo_mode ? 'Modo demostración' : 'Producción'}</Badge>}
      />

      {message && (
        <div className="notice" data-tone="ok">
          {message}
        </div>
      )}

      <div className="notice" data-tone="info">
        Los valores se editan como JSON y se aplican de inmediato a los módulos correspondientes. Los
        cambios quedan registrados en la bitácora de auditoría.
      </div>

      {settingsQuery.isError && <ErrorBox message={errorMessage(settingsQuery.error)} />}
      {settingsQuery.isLoading && <Loading label="Cargando configuración…" />}

      {settings.length === 0 && !settingsQuery.isLoading && (
        <Empty title="Sin parámetros de configuración" />
      )}

      <div className="grid grid-2">
        {settings.map((group) => (
          <Card
            key={group.category}
            title={group.label}
            subtitle={`Categoría: ${group.category}`}
            actions={<Badge tone="info">{group.items.length} parámetros</Badge>}
          >
            {group.items.map((item) => (
              <div key={item.key} style={{ marginBottom: '0.7rem' }}>
                <Field label={item.key}>
                  <textarea
                    className="json-editor"
                    rows={Math.min(
                      12,
                      Math.max(5, (drafts[item.key] ?? '').split('\n').length + 1),
                    )}
                    value={drafts[item.key] ?? JSON.stringify(item.value, null, 2)}
                    readOnly={!canUpdate}
                    spellCheck={false}
                    onChange={(event) =>
                      setDrafts((current) => ({ ...current, [item.key]: event.target.value }))
                    }
                  />
                </Field>
                {item.description && (
                  <div style={{ fontSize: '0.76rem', color: 'var(--muted)', marginTop: '0.2rem' }}>
                    {item.description}
                  </div>
                )}
                {errors[item.key] && (
                  <div className="error-box" style={{ marginTop: '0.35rem' }}>
                    {errors[item.key]}
                  </div>
                )}
                {canUpdate && (
                  <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.4rem' }}>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      disabled={savingKey === item.key}
                      onClick={() => save(item.key)}
                    >
                      {savingKey === item.key ? 'Guardando…' : 'Guardar'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() =>
                        setDrafts((current) => ({
                          ...current,
                          [item.key]: JSON.stringify(item.value, null, 2),
                        }))
                      }
                    >
                      Restaurar
                    </button>
                  </div>
                )}
              </div>
            ))}
          </Card>
        ))}
      </div>

      <div className="grid grid-sidebar" style={{ marginTop: '1rem' }}>
        <Card title="Información del sistema" subtitle="Entorno, versión y componentes activos.">
          {systemQuery.isError && <ErrorBox message={errorMessage(systemQuery.error)} />}
          {systemQuery.isLoading && <Loading label="Consultando sistema…" />}
          {info && (
            <>
              <div className="grid grid-2">
                <div>
                  <MetricRow label="Aplicación" value={info.app} />
                  <MetricRow label="Versión" value={info.version} />
                  <MetricRow label="Entorno" value={info.environment} />
                  <MetricRow label="Base de datos" value={info.database} />
                  <MetricRow
                    label="Modo demostración"
                    value={<Badge tone={info.demo_mode ? 'warning' : 'ok'}>{info.demo_mode ? 'Sí' : 'No'}</Badge>}
                  />
                </div>
                <div>
                  <MetricRow label="Proveedor LLM" value={info.llm_provider} />
                  <MetricRow label="Referencia OMS" value={info.reference_version} />
                  <MetricRow label="Hora del servidor" value={dateTime(info.server_time)} />
                  <MetricRow
                    label="Modelo activo"
                    value={
                      info.active_model
                        ? `${info.active_model.name} v${info.active_model.version}`
                        : 'Sin modelo'
                    }
                  />
                  <MetricRow
                    label="AUC del modelo activo"
                    value={decimal(info.active_model?.auc, 4)}
                  />
                </div>
              </div>

              <div style={{ marginTop: '0.7rem' }}>
                <div style={{ fontSize: '0.73rem', color: 'var(--muted)', marginBottom: '0.3rem' }}>
                  Volúmenes de datos
                </div>
                <div className="grid grid-2">
                  {Object.entries(info.counts).map(([key, value]) => (
                    <MetricRow key={key} label={key} value={num(value)} />
                  ))}
                </div>
              </div>

              <div style={{ marginTop: '0.7rem' }}>
                <div style={{ fontSize: '0.73rem', color: 'var(--muted)', marginBottom: '0.3rem' }}>
                  Funcionalidades habilitadas
                </div>
                <div className="chip-row">
                  {Object.entries(info.features).map(([feature, enabled]) => (
                    <Badge key={feature} tone={enabled ? 'ok' : 'neutral'}>
                      {feature} {enabled ? '· activo' : '· inactivo'}
                    </Badge>
                  ))}
                </div>
              </div>
            </>
          )}
        </Card>

        <Card title="Monitoreo operativo" subtitle="Salud de la bitácora y actividad reciente.">
          {monitoringQuery.isError && <ErrorBox message={errorMessage(monitoringQuery.error)} />}
          {monitoringQuery.isLoading && <Loading label="Consultando monitoreo…" />}
          {monitoring && (
            <>
              <MetricRow label="Eventos auditados" value={num(monitoring.audit_events)} />
              <MetricRow label="Eventos fallidos" value={num(monitoring.failed_events)} />
              <MetricRow label="Eventos lentos" value={num(monitoring.slow_events)} />
              <MetricRow label="Tasa de éxito" value={pctValue(monitoring.success_rate, 2)} />
              <MetricRow label="Base de datos" value={monitoring.database} />
              <div style={{ marginTop: '0.55rem', fontSize: '0.72rem', color: 'var(--muted)', wordBreak: 'break-all' }}>
                <div>
                  <strong>Almacenamiento:</strong> <span className="mono">{monitoring.storage_dir}</span>
                </div>
                <div style={{ marginTop: '0.2rem' }}>
                  <strong>Artefactos:</strong> <span className="mono">{monitoring.artifacts_dir}</span>
                </div>
              </div>
              <div style={{ marginTop: '0.75rem' }}>
                <div style={{ fontSize: '0.73rem', color: 'var(--muted)', marginBottom: '0.3rem' }}>
                  Últimos eventos
                </div>
                <DataTable interpretationId="settings"
                  columns={eventColumns}
                  rows={monitoring.latest_events}
                  getKey={(row) => row.id}
                  empty="Sin eventos recientes"
                />
              </div>
            </>
          )}
        </Card>
      </div>
    </>
  );
}

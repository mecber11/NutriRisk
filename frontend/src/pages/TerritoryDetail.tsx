import { Interpretation } from '../components/Interpretation';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { GeoJSON, MapContainer, TileLayer } from 'react-leaflet';
import type { GeoJsonObject, Geometry } from 'geojson';
import type { PathOptions } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { api, downloadFile } from '../api/client';
import {
  Bar,
  Badge,
  Card,
  CHART_COLORS,
  DataTable,
  Empty,
  ErrorBox,
  KpiCard,
  Loading,
  MetricRow,
  PageHeader,
  RISK_COLORS,
  RiskBadge,
  decimal,
  num,
  pct,
} from '../components/ui';
import type { Column } from '../components/ui';
import type {
  Kpi,
  ReportItem,
  TerritoryExplanation,
  TerritoryHistoryPoint,
  TerritoryProfile,
} from '../types';

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo cargar la ficha territorial.';
}

function collectPoints(value: unknown, out: [number, number][]): void {
  if (Array.isArray(value)) {
    if (value.length === 2 && typeof value[0] === 'number' && typeof value[1] === 'number') {
      out.push([value[1], value[0]]);
      return;
    }
    value.forEach((child) => collectPoints(child, out));
  }
}

function geometryBounds(geometry: unknown): [[number, number], [number, number]] | null {
  const coordinates = (geometry as { coordinates?: unknown } | null)?.coordinates;
  if (!coordinates) return null;
  const points: [number, number][] = [];
  collectPoints(coordinates, points);
  if (!points.length) return null;
  const lats = points.map((point) => point[0]);
  const lngs = points.map((point) => point[1]);
  return [
    [Math.min(...lats), Math.min(...lngs)],
    [Math.max(...lats), Math.max(...lngs)],
  ];
}

interface Determinant {
  feature: string;
  label: string;
  value: number;
  share?: number;
}

export default function TerritoryDetail() {
  const { code } = useParams<{ code: string }>();
  const territoryCode = (code ?? '').toUpperCase();
  const [reportError, setReportError] = useState<string | null>(null);
  const [reportInfo, setReportInfo] = useState<string | null>(null);

  const profileQuery = useQuery({
    queryKey: ['geo', 'territory', territoryCode],
    queryFn: () => api.get<TerritoryProfile>(`/geo/territories/${territoryCode}`),
    enabled: Boolean(territoryCode),
  });

  const profile = profileQuery.data;
  const territoryId = profile?.territory.id;

  const xaiQuery = useQuery({
    queryKey: ['xai', 'territory', territoryId],
    queryFn: () => {
      if (!territoryId) throw new Error('Territorio no disponible.');
      return api.get<TerritoryExplanation>(`/xai/territory/${territoryId}`);
    },
    enabled: Boolean(territoryId),
  });

  const history = useMemo<TerritoryHistoryPoint[]>(() => {
    const byYear = new Map<number, TerritoryHistoryPoint>();
    (profile?.risk_history ?? []).forEach((point) => {
      const current = byYear.get(point.year);
      if (!current || (point.model_id ?? 0) > (current.model_id ?? 0)) {
        byYear.set(point.year, point);
      }
    });
    return Array.from(byYear.values()).sort((a, b) => b.year - a.year);
  }, [profile]);

  const latest = history[0];
  const latestYear = latest?.year;

  const determinants = useMemo<Determinant[]>(() => {
    if (xaiQuery.data?.features?.length) {
      return xaiQuery.data.features.map((feature) => ({
        feature: feature.feature,
        label: feature.label,
        value: feature.mean_abs_shap,
        share: feature.share,
      }));
    }
    return (latest?.top_features ?? []).map((feature) => ({
      feature: feature.feature,
      label: feature.label,
      value: feature.mean_abs_shap,
    }));
  }, [xaiQuery.data, latest]);

  const maxDeterminant = determinants.reduce((max, item) => Math.max(max, item.value), 0) || 1;
  const bounds = useMemo(() => geometryBounds(profile?.territory.geometry), [profile]);

  const reportMutation = useMutation({
    mutationFn: async () => {
      if (!profile) throw new Error('La ficha territorial aún no está cargada.');
      const report = await api.post<ReportItem>('/reports/generate', {
        kind: 'territory_profile',
        fmt: 'pdf',
        title: `Ficha de riesgo · ${profile.territory.name} (${latestYear ?? ''})`,
        params: { territory_code: profile.territory.code, year: latestYear },
      });
      await downloadFile(
        `/reports/${report.id}/download`,
        report.file_name ?? `ficha_${profile.territory.code}.pdf`,
      );
      return report;
    },
    onSuccess: (report) => {
      setReportError(null);
      setReportInfo(
        `Ficha PDF generada y descargada (${Math.max(1, Math.round(report.size_bytes / 1024))} KB).`,
      );
    },
    onError: (error) => {
      setReportInfo(null);
      setReportError(errorMessage(error));
    },
  });

  const kpis = useMemo<Kpi[]>(() => {
    if (!profile || !latest) return [];
    const severityByBand =
      latest.risk_band === 'CRITICAL'
        ? 'critical'
        : latest.risk_band === 'HIGH'
          ? 'warning'
          : latest.risk_band === 'MODERATE'
            ? 'warning'
            : 'ok';
    return [
      {
        key: 'population',
        label: 'Población total',
        value: profile.territory.population,
        unit: '',
        delta: null,
        trend: 'flat',
        description: 'Proyección demográfica sintética.',
        severity: 'neutral',
      },
      {
        key: 'population_u5',
        label: 'Población menor de 5 años',
        value: profile.territory.population_u5,
        unit: '',
        delta: null,
        trend: 'flat',
        description: 'Universo objetivo de la intervención.',
        severity: 'neutral',
      },
      {
        key: 'mean_risk',
        label: 'Riesgo medio predicho',
        value: latest.mean_risk * 100,
        unit: '%',
        delta: null,
        trend: 'flat',
        description: 'Probabilidad media del modelo activo.',
        severity: severityByBand,
      },
      {
        key: 'stunting',
        label: 'Prevalencia de retraso',
        value: latest.stunting_prevalence * 100,
        unit: '%',
        delta: null,
        trend: 'flat',
        description: 'HAZ < -2 DE (OMS 2006).',
        severity: latest.stunting_prevalence >= 0.3 ? 'critical' : 'warning',
      },
      {
        key: 'at_risk',
        label: 'Población en riesgo',
        value: latest.population_at_risk,
        unit: '',
        delta: null,
        trend: 'flat',
        description: 'Menores de 5 años ponderados por riesgo.',
        severity: 'warning',
      },
      {
        key: 'rank',
        label: 'Prioridad nacional',
        value: latest.priority_rank,
        unit: '#',
        delta: null,
        trend: 'flat',
        description: `${num(latest.children_screened)} niños evaluados.`,
        severity: latest.priority_rank <= 3 ? 'critical' : 'neutral',
      },
    ];
  }, [profile, latest]);

  const historyColumns: Column<TerritoryHistoryPoint>[] = [
    { key: 'year', header: 'Año', render: (row) => row.year },
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
      key: 'priority_rank',
      header: 'Prioridad',
      align: 'right',
      render: (row) => `#${row.priority_rank}`,
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
    {
      key: 'model_id',
      header: 'Modelo',
      align: 'right',
      render: (row) => (row.model_id ? `#${row.model_id}` : '—'),
    },
  ];

  const geometry = profile?.territory.geometry as Geometry | undefined;
  const riskColor = latest ? (RISK_COLORS[latest.risk_band] ?? '#0f766e') : '#0f766e';
  const polygonStyle: PathOptions = {
    fillColor: riskColor,
    fillOpacity: 0.5,
    color: '#0f766e',
    weight: 2,
  };

  return (
    <>
      <PageHeader
        title={profile ? profile.territory.name : `Territorio ${territoryCode}`}
        subtitle={
          profile
            ? `${profile.territory.code} · Región ${profile.territory.region} · ${
                profile.territory.climate_zone ?? 'clima sin dato'
              } · ${num(profile.territory.population)} habitantes`
            : 'Cargando la ficha del territorio…'
        }
        actions={
          <>
            <Link className="btn" to="/territorios">
              ← Volver al ranking
            </Link>
            <button
              type="button"
              className="btn btn-primary"
              disabled={!profile || reportMutation.isPending}
              onClick={() => reportMutation.mutate()}
            >
              {reportMutation.isPending ? 'Generando ficha…' : 'Generar ficha PDF'}
            </button>
          </>
        }
      />

      {reportError && <ErrorBox message={reportError} />}
      {reportInfo && (
        <div className="notice" data-tone="ok">
          {reportInfo}
        </div>
      )}

      {profileQuery.isError && <ErrorBox message={errorMessage(profileQuery.error)} />}
      {profileQuery.isLoading && <Loading label="Cargando ficha territorial…" />}

      {profile && (
        <>
          {kpis.length > 0 && (
            <div className="kpi-grid">
              {kpis.map((kpi) => (
                <KpiCard key={kpi.key} kpi={kpi} />
              ))}
            </div>
          )}

          {history.length === 0 && (
            <div className="notice" data-tone="warning">
              Este territorio no registra historia de riesgo para el modelo activo. Los indicadores se
              muestran a nivel descriptivo.
            </div>
          )}

          <div className="grid grid-sidebar">
            <Card
              title="Ubicación del territorio"
              subtitle="Polígono simplificado y banda de riesgo más reciente."
              actions={latest ? <RiskBadge band={latest.risk_band} /> : undefined}
            >
              {geometry && bounds ? (
                <>
                  <div className="map-shell" style={{ height: 380 }}>
                    <MapContainer
                      bounds={bounds}
                      center={[4.7, -73.8]}
                      zoom={7}
                      scrollWheelZoom
                      style={{ height: '100%', width: '100%' }}
                    >
                      <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
                        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                        subdomains="abcd"
                        maxZoom={19}
                      />
                      <GeoJSON
                        data={
                          {
                            type: 'FeatureCollection',
                            features: [
                              {
                                type: 'Feature',
                                properties: { code: profile.territory.code, name: profile.territory.name },
                                geometry,
                              },
                            ],
                          } as unknown as GeoJsonObject
                        }
                        style={polygonStyle}
                      />
                    </MapContainer>
                  </div>
                  <Interpretation id="territories" />
                  <div className="legend">
                    <span>
                      <span className="legend-swatch" style={{ background: riskColor }} />
                      Riesgo {latest ? pct(latest.mean_risk) : 'sin dato'}
                    </span>
                    <span>Fuente cartográfica: CARTO / OpenStreetMap</span>
                  </div>
                </>
              ) : (
                <Empty title="Geometría no disponible" hint="El territorio no tiene polígono registrado." />
              )}
            </Card>

            <Card title="Ficha descriptiva" subtitle="Determinantes estructurales del territorio.">
              <MetricRow label="Código" value={profile.territory.code} />
              <MetricRow label="Región" value={profile.territory.region} />
              <MetricRow label="Población total" value={num(profile.territory.population)} />
              <MetricRow label="Población menor de 5" value={num(profile.territory.population_u5)} />
              <MetricRow label="Área" value={`${num(profile.territory.area_km2, 0)} km²`} />
              <MetricRow
                label="Altitud"
                value={profile.territory.altitude_m !== null ? `${num(profile.territory.altitude_m)} m` : '—'}
              />
              <MetricRow label="Zona climática" value={profile.territory.climate_zone ?? '—'} />
              <MetricRow
                label="Precipitación"
                value={profile.territory.rainfall_mm !== null ? `${num(profile.territory.rainfall_mm)} mm` : '—'}
              />
              <MetricRow
                label="Temperatura"
                value={
                  profile.territory.temperature_c !== null
                    ? `${decimal(profile.territory.temperature_c, 1)} °C`
                    : '—'
                }
              />
              <MetricRow
                label="NDVI"
                value={profile.territory.ndvi !== null ? decimal(profile.territory.ndvi, 3) : '—'}
              />
              <MetricRow
                label="Inseguridad alimentaria"
                value={
                  profile.territory.food_insecurity_index !== null
                    ? pct(profile.territory.food_insecurity_index)
                    : '—'
                }
              />
              <MetricRow
                label="Cobertura de agua"
                value={profile.territory.water_coverage !== null ? pct(profile.territory.water_coverage) : '—'}
              />
              <MetricRow
                label="Cobertura de saneamiento"
                value={
                  profile.territory.sanitation_coverage !== null
                    ? pct(profile.territory.sanitation_coverage)
                    : '—'
                }
              />
              <MetricRow
                label="Territorios vecinos"
                value={profile.territory.neighbor_codes.length ? profile.territory.neighbor_codes.join(', ') : '—'}
              />
            </Card>
          </div>

          <div className="grid grid-2" style={{ marginTop: '1rem' }}>
            <Card
              title="Historia del riesgo"
              subtitle="Un registro por año; se usa el modelo más reciente disponible."
            >
              <DataTable interpretationId="trend"
                columns={historyColumns}
                rows={history}
                getKey={(row) => row.year}
                empty="Sin historia registrada"
              />
            </Card>

            <Card
              title="Determinantes del riesgo (SHAP)"
              subtitle="Contribución media absoluta de cada variable al riesgo territorial."
              actions={
                xaiQuery.data?.model_id ? <Badge tone="brand">Modelo #{xaiQuery.data.model_id}</Badge> : undefined
              }
            >
              {xaiQuery.isLoading && <Loading label="Calculando determinantes…" />}
              {xaiQuery.isError && !determinants.length && <ErrorBox message={errorMessage(xaiQuery.error)} />}
              {determinants.length === 0 ? (
                <Empty title="Sin determinantes disponibles" hint="El modelo activo no reporta valores SHAP." />
              ) : (
                <div>
                  {determinants.map((item) => (
                    <div key={item.feature} style={{ marginBottom: '0.6rem' }}>
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          gap: '0.5rem',
                          fontSize: '0.8rem',
                          marginBottom: '0.22rem',
                        }}
                      >
                        <span>{item.label}</span>
                        <span className="mono" style={{ color: 'var(--muted)' }}>
                          {decimal(item.value, 4)}
                          {item.share !== undefined ? ` · ${pct(item.share, 1)}` : ''}
                        </span>
                      </div>
                      <Bar value={item.value} max={maxDeterminant} color={CHART_COLORS[0]} />
                    </div>
                  ))}
                  <Interpretation id="shap" />
                </div>
              )}

              <p style={{ marginTop: '0.9rem', marginBottom: 0, fontSize: '0.83rem', color: 'var(--muted)' }}>
                {xaiQuery.data?.narrative ??
                  (determinants.length
                    ? `En ${profile.territory.name} los determinantes con mayor peso son ${determinants
                        .slice(0, 4)
                        .map((item) => item.label)
                        .join(', ')}. Interpretación basada en valores SHAP del modelo activo; no constituye diagnóstico clínico.`
                    : 'Sin narrativa disponible para este territorio.')}
              </p>
            </Card>
          </div>
        </>
      )}
    </>
  );
}

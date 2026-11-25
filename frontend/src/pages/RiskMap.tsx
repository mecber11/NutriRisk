import { Interpretation } from '../components/Interpretation';
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { GeoJSON, MapContainer, TileLayer } from 'react-leaflet';
import type { Feature, GeoJsonObject, GeoJsonProperties, Geometry } from 'geojson';
import type { Layer, PathOptions } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { api } from '../api/client';
import {
  Bar,
  Badge,
  Card,
  Empty,
  ErrorBox,
  Field,
  Loading,
  PageHeader,
  RISK_COLORS,
  RiskBadge,
  num,
  pct,
} from '../components/ui';
import type { DashboardOptions, MapCollection, TerritoryRisk } from '../types';

interface TerritoryFeatureProps {
  code: string;
  name: string;
  region: string;
  mean_risk: number;
  risk_band: string;
  stunting_prevalence: number;
  priority_rank: number;
  children_screened: number;
  population_at_risk: number;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'No se pudo cargar el mapa de riesgo.';
}

function asTerritoryProps(properties: GeoJsonProperties): TerritoryFeatureProps | null {
  if (!properties || typeof properties.code !== 'string') return null;
  return properties as unknown as TerritoryFeatureProps;
}

function collectPoints(value: unknown, out: [number, number][]): void {
  if (Array.isArray(value)) {
    if (
      value.length === 2 &&
      typeof value[0] === 'number' &&
      typeof value[1] === 'number'
    ) {
      out.push([value[1], value[0]]);
      return;
    }
    value.forEach((child) => collectPoints(child, out));
  }
}

function computeBounds(data?: MapCollection): [[number, number], [number, number]] | null {
  if (!data || !data.features.length) return null;
  const points: [number, number][] = [];
  data.features.forEach((feature) => collectPoints(feature.geometry.coordinates, points));
  if (!points.length) return null;
  const lats = points.map((point) => point[0]);
  const lngs = points.map((point) => point[1]);
  return [
    [Math.min(...lats), Math.min(...lngs)],
    [Math.max(...lats), Math.max(...lngs)],
  ];
}

function styleForFeature(feature?: Feature<Geometry, GeoJsonProperties>): PathOptions {
  const props = feature ? asTerritoryProps(feature.properties) : null;
  return {
    fillColor: RISK_COLORS[props?.risk_band ?? 'UNKNOWN'] ?? '#94a3b8',
    fillOpacity: 0.72,
    color: '#ffffff',
    weight: 1.2,
  };
}

function bindFeature(
  feature: Feature<Geometry, GeoJsonProperties>,
  layer: Layer,
  navigate: (path: string) => void,
): void {
  const props = asTerritoryProps(feature.properties);
  if (!props) return;

  const content = document.createElement('div');
  const title = document.createElement('strong');
  title.textContent = `${props.name} · ${props.region}`;
  content.appendChild(title);

  const risk = document.createElement('div');
  risk.textContent = `Riesgo medio: ${pct(props.mean_risk)} (${props.risk_band})`;
  content.appendChild(risk);

  const prevalence = document.createElement('div');
  prevalence.textContent = `Retraso del crecimiento: ${pct(props.stunting_prevalence)}`;
  content.appendChild(prevalence);

  const rank = document.createElement('div');
  rank.textContent = `Prioridad nacional: #${props.priority_rank} · ${num(props.children_screened)} niños evaluados`;
  content.appendChild(rank);

  const hint = document.createElement('div');
  hint.textContent = 'Clic para abrir la ficha territorial';
  hint.style.color = '#64748b';
  hint.style.fontSize = '0.72rem';
  content.appendChild(hint);

  layer.bindTooltip(content, { sticky: true, direction: 'top' });
  layer.on('click', () => navigate(`/territorios/${props.code}`));
}

export default function RiskMap() {
  const navigate = useNavigate();
  const [year, setYear] = useState<number | null>(null);

  const optionsQuery = useQuery({
    queryKey: ['dashboard', 'options'],
    queryFn: () => api.get<DashboardOptions>('/dashboard/options'),
  });

  const mapQuery = useQuery({
    queryKey: ['geo', 'map', year],
    queryFn: () => api.get<MapCollection>('/geo/map', { year: year ?? undefined }),
  });

  const rankingQuery = useQuery({
    queryKey: ['geo', 'ranking', year, 12],
    queryFn: () => api.get<{ year: number; model_id: number | null; total: number; rows: TerritoryRisk[] }>(
      '/geo/ranking',
      { year: year ?? undefined, limit: 12 },
    ),
  });

  const mapData = mapQuery.data;
  const bounds = useMemo(() => computeBounds(mapData), [mapData]);
  const years = optionsQuery.data?.years ?? [];
  const selectedYear = year ?? mapData?.year ?? (years.length ? years[years.length - 1] : '');
  const ranking = rankingQuery.data?.rows ?? [];

  return (
    <>
      <PageHeader
        title="Mapa de riesgo territorial"
        subtitle="Riesgo predicho por territorio con el modelo activo. Cada polígono se colorea según su banda de riesgo."
        actions={
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
            <Link className="btn btn-sm" to="/territorios">
              Ver ranking completo
            </Link>
          </div>
        }
      />

      <div className="notice" data-tone="info">
        <span>
          Haga clic sobre un territorio para abrir su ficha. El riesgo se calcula con{' '}
          {mapData?.model_id ? `el modelo #${mapData.model_id}` : 'el modelo activo'} y datos sintéticos
          de demostración.
        </span>
      </div>

      {mapQuery.isError && <ErrorBox message={errorMessage(mapQuery.error)} />}
      {mapQuery.isLoading && <Loading label="Cargando geometrías y riesgo territorial…" />}

      {mapData && mapData.features.length === 0 && (
        <Empty title="Sin territorios para el año seleccionado" hint="Pruebe con otro periodo." />
      )}

      {mapData && mapData.features.length > 0 && (
        <div className="grid grid-sidebar">
          <Card
            title="Riesgo medio por territorio"
            subtitle={`Año ${mapData.year} · ${mapData.features.length} territorios · banda de color según el modelo activo`}
            actions={<Badge tone="brand">{mapData.features.length} territorios</Badge>}
          >
            <div className="map-shell">
              <MapContainer
                bounds={bounds ?? undefined}
                center={[4.7, -73.8]}
                zoom={6}
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
                  key={`territories-${mapData.year}-${mapData.model_id ?? 'active'}`}
                  data={mapData as unknown as GeoJsonObject}
                  style={styleForFeature}
                  onEachFeature={(feature, layer) => bindFeature(feature, layer, navigate)}
                />
              </MapContainer>
            </div>
            <Interpretation id="territories" />
            <div className="legend">
              {mapData.legend.map((item) => (
                <span key={item.band}>
                  <span className="legend-swatch" style={{ background: item.color }} />
                  {item.label} ({pct(item.min, 0)}–{pct(item.max, 0)})
                </span>
              ))}
            </div>
          </Card>

          <Card
            title="Ranking de prioridad"
            subtitle="Territorios con mayor riesgo medio predicho."
            actions={<Badge tone="brand">{num(rankingQuery.data?.total ?? 0)}</Badge>}
          >
            {rankingQuery.isError && <ErrorBox message={errorMessage(rankingQuery.error)} />}
            {rankingQuery.isLoading && <Loading label="Cargando ranking…" />}
            {!rankingQuery.isLoading && ranking.length === 0 && <Empty title="Sin territorios en el ranking" />}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.7rem' }}>
              {ranking.map((row) => (
                <div key={row.territory_id}>
                  <div style={{ display: 'flex', gap: '0.45rem', alignItems: 'baseline' }}>
                    <span className="rank" style={{ minWidth: 26 }}>
                      #{row.priority_rank}
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <Link to={`/territorios/${row.code}`}>{row.name}</Link>
                      <div style={{ color: 'var(--muted)', fontSize: '0.72rem' }}>
                        {row.region} · {row.code}
                      </div>
                    </div>
                    <span className="risk-pill">{pct(row.mean_risk)}</span>
                  </div>
                  <div style={{ marginTop: '0.25rem' }}>
                    <Bar value={row.mean_risk} max={1} color={RISK_COLORS[row.risk_band] ?? '#94a3b8'} />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.2rem' }}>
                    <RiskBadge band={row.risk_band} />
                    <small>{num(row.population_at_risk)} en riesgo</small>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </>
  );
}

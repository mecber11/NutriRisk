import type { ReactNode } from 'react';
import type { Kpi } from '../types';
import { Interpretation } from './Interpretation';

export const CHART_COLORS = ['#0f766e', '#f59e0b', '#dc2626', '#0e7490', '#7c3aed', '#059669', '#64748b'];

export const RISK_LABELS: Record<string, string> = {
  LOW: 'Bajo',
  MODERATE: 'Moderado',
  HIGH: 'Alto',
  CRITICAL: 'Crítico',
  UNKNOWN: 'Sin dato',
};

export const RISK_COLORS: Record<string, string> = {
  LOW: '#0e7490',
  MODERATE: '#f59e0b',
  HIGH: '#f97316',
  CRITICAL: '#dc2626',
  UNKNOWN: '#94a3b8',
};

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${(value * 100).toFixed(digits)} %`;
}

export function pctValue(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${value.toFixed(digits)} %`;
}

export function num(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return new Intl.NumberFormat('es-CO', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
}

export function decimal(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toFixed(digits);
}

export function dateTime(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' });
}

export function dateOnly(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString('es-CO');
}

export function riskTone(band: string): 'ok' | 'info' | 'warning' | 'danger' | 'neutral' {
  switch (band) {
    case 'LOW':
      return 'info';
    case 'MODERATE':
      return 'warning';
    case 'HIGH':
      return 'warning';
    case 'CRITICAL':
      return 'danger';
    default:
      return 'neutral';
  }
}

export function severityTone(severity: string): 'ok' | 'info' | 'warning' | 'danger' | 'neutral' {
  switch (severity?.toUpperCase()) {
    case 'CRITICAL':
      return 'danger';
    case 'WARNING':
      return 'warning';
    case 'INFO':
      return 'info';
    default:
      return 'neutral';
  }
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <div className="subtitle">{subtitle}</div>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function Card({
  title,
  subtitle,
  actions,
  children,
  className,
}: {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className ?? ''}`}>
      {(title || actions) && (
        <div className="card-head">
          <div>
            {title && <div className="card-title">{title}</div>}
            {subtitle && <div className="card-subtitle">{subtitle}</div>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function KpiCard({ kpi }: { kpi: Kpi }) {
  const trendIcon = kpi.delta === null ? '' : kpi.delta > 0 ? '▲' : '▼';
  return (
    <div className="kpi" data-severity={kpi.severity}>
      <div className="kpi-label">{kpi.label}</div>
      <div className="kpi-value">
        {kpi.unit === '%' ? kpi.value.toFixed(1) : num(kpi.value, 0)}
        {kpi.unit && <span className="kpi-unit">{kpi.unit}</span>}
      </div>
      <div className="kpi-foot">
        {kpi.delta !== null && (
          <span style={{ color: kpi.delta > 0 ? 'var(--danger)' : 'var(--ok)', fontWeight: 600 }}>
            {trendIcon} {Math.abs(kpi.delta).toFixed(1)} %
          </span>
        )}
        {kpi.description && <span>{kpi.description}</span>}
      </div>
    </div>
  );
}

export function Badge({
  tone = 'neutral',
  children,
}: {
  tone?: 'ok' | 'info' | 'warning' | 'danger' | 'brand' | 'neutral';
  children: ReactNode;
}) {
  return (
    <span className="badge" data-tone={tone}>
      {children}
    </span>
  );
}

export function RiskBadge({ band }: { band: string }) {
  return <Badge tone={riskTone(band)}>{RISK_LABELS[band] ?? band}</Badge>;
}

export interface Column<T> {
  key: string;
  header: string;
  align?: 'left' | 'right';
  width?: string;
  render?: (row: T) => ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  empty = 'Sin registros',
  getKey,
  interpretationId,
}: {
  columns: Column<T>[];
  rows: T[];
  empty?: string;
  getKey?: (row: T, index: number) => string | number;
  interpretationId: string;
}) {
  if (!rows.length) {
    return <div className="table-wrap"><div className="table-empty">{empty}</div></div>;
  }
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={column.align === 'right' ? 'num' : undefined} style={column.width ? { width: column.width } : undefined}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={getKey ? getKey(row, index) : index}>
              {columns.map((column) => (
                <td key={column.key} className={column.align === 'right' ? 'num' : undefined}>
                  {column.render ? column.render(row) : String((row as Record<string, unknown>)[column.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <Interpretation id={interpretationId} />
    </div>
  );
}

export function Loading({ label = 'Cargando información…' }: { label?: string }) {
  return (
    <div className="state">
      <div className="spinner" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return <div className="error-box">{message}</div>;
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="state">
      <strong>{title}</strong>
      {hint && <span>{hint}</span>}
    </div>
  );
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
    </div>
  );
}

export function MetricRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="metric-row">
      <span>{label}</span>
      <span className="value">{value}</span>
    </div>
  );
}

export function Bar({ value, max = 1, color = 'var(--brand)' }: { value: number; max?: number; color?: string }) {
  const width = Math.max(2, Math.min(100, (value / max) * 100));
  return (
    <div style={{ background: 'var(--line)', borderRadius: 999, height: 7, width: '100%' }}>
      <div style={{ width: `${width}%`, background: color, height: 7, borderRadius: 999 }} />
    </div>
  );
}

export function Tabs<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div className="tabs">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`tab ${value === option.value ? 'active' : ''}`}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

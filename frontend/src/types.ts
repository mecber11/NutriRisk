/** Tipos compartidos de la API de NutriRisk AI. */

export type Role = 'ADMIN' | 'DATA_SCIENTIST' | 'PUBLIC_HEALTH_ANALYST' | 'MANAGER' | 'AUDITOR';

export interface RoleInfo {
  id: number;
  code: Role;
  name: string;
  description?: string | null;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: RoleInfo;
  is_active: boolean;
  organization?: string | null;
  position?: string | null;
  last_login_at?: string | null;
  must_change_password?: boolean;
  permissions?: Record<string, string[]>;
}

export interface Kpi {
  key: string;
  label: string;
  value: number;
  unit: string;
  delta: number | null;
  trend: string;
  description?: string | null;
  severity: string;
}

export interface TrendPoint {
  period: string;
  stunting: number;
  wasting: number;
  underweight: number;
  mean_risk: number | null;
  population_at_risk: number;
}

export interface ComparisonRow {
  key: string;
  label: string;
  stunting: number;
  wasting: number;
  underweight: number;
  mean_risk: number;
  n: number;
}

export interface TerritoryRisk {
  territory_id: number;
  code: string;
  name: string;
  region: string;
  year: number;
  mean_risk: number;
  risk_band: string;
  stunting_prevalence: number;
  children_screened: number;
  population_at_risk: number;
  priority_rank: number;
  top_features: { feature: string; label: string; mean_abs_shap: number }[];
}

export interface MapFeature {
  type: 'Feature';
  geometry: { type: string; coordinates: unknown };
  properties: {
    territory_id: number;
    code: string;
    name: string;
    region: string;
    mean_risk: number;
    risk_band: string;
    stunting_prevalence: number;
    priority_rank: number;
    children_screened: number;
    population_at_risk: number;
    population_u5: number;
    altitude_m: number | null;
    water_coverage: number | null;
    sanitation_coverage: number | null;
  };
}

export interface MapCollection {
  type: 'FeatureCollection';
  features: MapFeature[];
  year: number;
  model_id: number | null;
  legend: { band: string; color: string; label: string; min: number; max: number }[];
}

export interface Overview {
  kpis: Kpi[];
  trend: TrendPoint[];
  regions: ComparisonRow[];
  top_territories: TerritoryRisk[];
  model_performance: ModelPerformance[];
  risk_distribution: { band: string; label: string; count: number; population: number; share: number }[];
  alerts: { id: number; title: string; message: string; severity: string; status: string; created_at?: string }[];
  filters: Record<string, unknown>;
  meta: {
    active_model_id: number | null;
    active_model_algorithm: string | null;
    years: number[];
    regions: string[];
    age_groups: string[];
    generated_at: string;
    children_total: number;
    synthetic: boolean;
  };
}

export interface ModelPerformance {
  model_id: number;
  name: string;
  algorithm: string;
  auc?: number | null;
  f1?: number | null;
  precision?: number | null;
  recall?: number | null;
  accuracy?: number | null;
  is_active: boolean;
  trained_at?: string | null;
}

export interface ModelComparison {
  model_id: number;
  name: string;
  version: string;
  algorithm: string;
  auc: number | null;
  f1: number | null;
  f1_optimal: number | null;
  precision: number | null;
  recall: number | null;
  accuracy: number | null;
  brier: number | null;
  threshold: number | null;
  rmse: number | null;
  mae: number | null;
  r2: number | null;
  train_seconds: number | null;
  is_best: boolean;
}

export interface ShapFeature {
  feature: string;
  label: string;
  mean_abs_shap: number;
  share: number;
  direction: string;
}

export interface GlobalExplanation {
  model_id: number;
  model_name: string;
  algorithm: string;
  base_value: number;
  n_samples: number;
  features: ShapFeature[];
  beeswarm: { feature: string; value: number; shap: number }[];
}

export interface LocalExplanation {
  child_id: number;
  child_code: string;
  model_id: number;
  prediction: number;
  base_value: number;
  risk_band: string;
  contributions: { feature: string; label: string; value: number | null; contribution: number; direction: string }[];
  narrative: string;
  positive: { feature: string; label: string; contribution: number }[];
  negative: { feature: string; label: string; contribution: number }[];
}

export interface FairnessGroup {
  group: string;
  n: number;
  selection_rate: number;
  tpr: number | null;
  fpr: number | null;
  precision: number | null;
  recall: number | null;
  accuracy: number | null;
  auc: number | null;
  mean_score: number | null;
  stunting_rate: number | null;
}

export interface FairnessResult {
  model_id: number;
  sensitive_attribute: string;
  metric: string;
  groups: FairnessGroup[];
  max_disparity: number;
  ratio: number | null;
  is_acceptable: boolean;
  threshold: number;
  generated_at?: string | null;
}

export interface FairnessSummary {
  model_id: number;
  attributes: FairnessResult[];
  overall_acceptable: boolean;
  notes: string[];
}

export interface Dataset {
  id: number;
  name: string;
  slug: string;
  source: string;
  kind: string;
  analysis_unit: string;
  description?: string | null;
  period_year?: number | null;
  country?: string | null;
  rows: number;
  columns: number;
  status: string;
  is_synthetic: boolean;
  quality_report: {
    score?: number;
    missing_ratio?: number;
    duplicate_rows?: number;
    outliers?: number;
    issues?: { code: string; severity: string; message: string }[];
  };
  created_at?: string | null;
}

export interface ReportItem {
  id: number;
  kind: string;
  title: string;
  fmt: string;
  params: Record<string, unknown>;
  file_name?: string | null;
  size_bytes: number;
  status: string;
  error?: string | null;
  created_at?: string | null;
  download_url?: string | null;
}

export interface ReportKind {
  code: string;
  label: string;
  description: string;
  formats: string[];
  params: string[];
}

export interface AuditEntry {
  id: number;
  user_email?: string | null;
  role_code?: string | null;
  module: string;
  action: string;
  resource_type?: string | null;
  resource_id?: string | null;
  method?: string | null;
  path?: string | null;
  status_code?: number | null;
  result: string;
  ip_address?: string | null;
  duration_ms: number;
  started_at: string;
  detail?: Record<string, unknown> | null;
}

export interface AlertItem {
  id: number;
  rule_code: string;
  severity: string;
  title: string;
  message: string;
  status: string;
  value?: number | null;
  threshold?: number | null;
  created_at?: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AgentAnswer {
  session_id: number;
  answer: string;
  intent: string;
  tools_used: string[];
  data: Record<string, unknown>;
  suggestions: string[];
  provider: string;
}

export interface ChatSession {
  id: number;
  title: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SystemInfo {
  app: string;
  version: string;
  environment: string;
  database: string;
  demo_mode: boolean;
  llm_provider: string;
  reference_version: string;
  counts: Record<string, number>;
  active_model: { id: number; name: string; algorithm: string; version: string; auc?: number | null } | null;
  features: Record<string, boolean>;
  server_time: string;
}

export interface SettingGroup {
  category: string;
  label: string;
  items: { key: string; value: Record<string, unknown>; category: string; description?: string | null }[];
}

export interface HelpSection {
  code: string;
  title: string;
  content: string[];
  links: { label: string; href: string }[];
}

export interface TerritoryDetail {
  territory: {
    id: number;
    code: string;
    name: string;
    region: string;
    population: number;
    population_u5: number;
    area_km2: number | null;
    altitude_m: number | null;
    climate_zone: string | null;
    rainfall_mm: number | null;
    temperature_c: number | null;
    ndvi: number | null;
    food_insecurity_index: number | null;
    water_coverage: number | null;
    sanitation_coverage: number | null;
    neighbor_codes: string[];
    geometry: unknown;
  };
  risk_history: {
    year: number;
    mean_risk: number;
    risk_band: string;
    stunting_prevalence: number;
    priority_rank: number;
    population_at_risk: number;
    children_screened: number;
    top_features: { feature: string; label: string; mean_abs_shap: number }[];
  }[];
}

/* ------------------------------------------------------------------------- */
/* Tipos adicionales usados por las páginas                                   */
/* ------------------------------------------------------------------------- */

export interface DashboardOptions {
  regions: string[];
  years: number[];
  sexes: string[];
  age_groups: string[];
  territories: { id: number; code: string; name: string; region: string }[];
  total_children?: number;
  regions_meta?: { name: string; children: number }[];
}

export interface AlertSummary {
  open: number;
  acknowledged: number;
  resolved: number;
  critical: number;
  by_severity: Record<string, number>;
  latest: AlertItem[];
}

export interface TerritoryHistoryPoint {
  year: number;
  model_id?: number;
  mean_risk: number;
  risk_band: string;
  stunting_prevalence: number;
  priority_rank: number;
  population_at_risk: number;
  children_screened: number;
  top_features: { feature: string; label: string; mean_abs_shap: number }[];
}

export interface TerritoryProfile {
  territory: {
    id: number;
    code: string;
    name: string;
    region: string;
    urban_rural?: string | null;
    population: number;
    population_u5: number;
    area_km2: number | null;
    altitude_m: number | null;
    climate_zone: string | null;
    rainfall_mm: number | null;
    temperature_c: number | null;
    ndvi: number | null;
    food_insecurity_index: number | null;
    water_coverage: number | null;
    sanitation_coverage: number | null;
    neighbor_codes: string[];
    geometry: unknown;
  };
  risk_history: TerritoryHistoryPoint[];
}

export interface IndicatorRow {
  key: string;
  label: string;
  n: number;
  stunting: number;
  wasting: number;
  underweight: number;
  severe_stunting: number;
  mean_haz: number;
}

export interface IndicatorSummary {
  total_children: number;
  stunting_prevalence: number;
  wasting_prevalence: number;
  underweight_prevalence: number;
  severe_stunting_prevalence: number;
  mean_haz: number;
  mean_waz: number;
  mean_whz: number;
  by_year: IndicatorRow[];
  by_region: IndicatorRow[];
  by_sex: IndicatorRow[];
  by_age_group: IndicatorRow[];
  by_wealth_quintile: IndicatorRow[];
  reference_version?: string;
}

export interface DistributionBin {
  bin_start: number;
  bin_end: number;
  count: number;
}

export interface DistributionResponse {
  indicator: string;
  reference_line: number;
  bins: DistributionBin[];
  mean: number;
  sd: number;
  total: number;
}

export interface ReferenceIndicatorInfo {
  version: string;
  source: string;
  age_months_range?: number[];
  indicators?: Record<string, { male_rows: number; female_rows: number }>;
  zscore_limit?: number;
  self_check: {
    passed: boolean;
    max_deviation_z: number;
    checked_cutoffs?: number;
    tolerance?: number;
  };
  coverage?: string;
}

export interface ChildRecord {
  id: number;
  code: string;
  household_id?: number;
  territory_id: number;
  period_year: number;
  age_months: number;
  sex: string;
  weight_kg: number;
  height_cm: number;
  muac_cm?: number | null;
  edema?: boolean;
  minimum_diet_diversity?: boolean;
  vaccination_complete?: boolean;
  diarrhea_14d?: boolean;
  fever_14d?: boolean;
}

export interface ChildIndicatorRecord {
  id?: number;
  child_id: number;
  haz: number | null;
  waz: number | null;
  whz: number | null;
  baz?: number | null;
  stunting: boolean;
  severe_stunting: boolean;
  wasting: boolean;
  severe_wasting?: boolean;
  underweight: boolean;
  severe_underweight?: boolean;
  overweight?: boolean;
  edematous?: boolean;
  reference_version?: string;
  computed_at?: string;
}

export interface ChildListItem {
  child: ChildRecord;
  indicator: ChildIndicatorRecord;
  territory: { id: number; code: string; name: string; region: string };
  household: {
    id: number;
    wealth_quintile: number;
    maternal_education?: string | null;
    urban_rural?: string | null;
  };
}

export interface ChildListPage {
  items: ChildListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ModelMetrics {
  n?: number;
  positives?: number;
  prevalence?: number;
  accuracy?: number | null;
  precision?: number | null;
  recall?: number | null;
  f1?: number | null;
  auc?: number | null;
  average_precision?: number | null;
  brier?: number | null;
  log_loss?: number | null;
  confusion_matrix?: number[][];
  threshold_optimal?: number | null;
  f1_optimal?: number | null;
  precision_optimal?: number | null;
  recall_optimal?: number | null;
  screening_threshold?: number | null;
  f1_screening?: number | null;
  precision_screening?: number | null;
  recall_screening?: number | null;
  cv_strategy?: string;
  train_rows?: number;
  features?: number;
  duration_seconds?: number;
  scored_children?: number;
  scored_at?: string | null;
  rmse?: number | null;
  mae?: number | null;
  r2?: number | null;
  folds?: { fold?: number; [key: string]: unknown }[];
  operating_points?: unknown;
}

export interface ModelOut {
  id: number;
  name: string;
  version: string;
  algorithm: string;
  task?: string;
  target?: string;
  experiment_id?: number | null;
  metrics?: ModelMetrics;
  feature_importance?: Record<string, number>;
  shap_summary?: GlobalExplanation | null;
  hyperparams?: Record<string, unknown> | string;
  is_active: boolean;
  is_synthetic?: boolean;
  trained_at?: string | null;
}

export interface MoranDiagnostics {
  available: boolean;
  i?: number;
  expected_i?: number;
  z_score?: number;
  p_value?: number;
  interpretation?: string;
  units?: number;
}

export interface SpatialModels {
  available: boolean;
  n?: number;
  names?: string[];
  ols?: {
    r2?: number;
    coefficients?: Record<string, number>;
    moran_residuals?: { i?: number; p_value?: number };
  };
  sar?: {
    rho?: number;
    pseudo_r2?: number;
    log_likelihood?: number;
    coefficients?: Record<string, number>;
  };
  sem?: {
    lambda?: number;
    pseudo_r2?: number;
    log_likelihood?: number;
    coefficients?: Record<string, number>;
  };
  gwr?: {
    available?: boolean;
    bandwidth_km?: number;
    n?: number;
    mean_local_r2?: number;
    coefficients?: Record<string, { mean: number; min: number; max: number; sd: number }>;
    note?: string;
  };
}

export interface SpatialDiagnostics {
  moran?: MoranDiagnostics;
  models?: SpatialModels;
  n_territories?: number;
  summary?: string[];
  correction?: {
    available: boolean;
    rho?: number;
    before?: ModelMetrics;
    after?: ModelMetrics;
    delta_auc?: number;
  };
  sequence_shape?: number[];
  territories?: number;
  years?: number[];
  curves?: number[];
}

export interface ExperimentOut {
  id: number;
  name: string;
  algorithm: string;
  task?: string;
  target?: string;
  dataset_id?: number | null;
  cv_strategy?: string;
  seed?: number | null;
  metrics?: ModelMetrics;
  per_region_metrics?: Record<string, ModelMetrics>;
  per_group_metrics?: Record<string, { label?: string; groups?: Record<string, ModelMetrics> }>;
  spatial_diagnostics?: SpatialDiagnostics;
  feature_importance?: Record<string, number>;
  hyperparams?: unknown;
  status: string;
  notes?: string | null;
  duration_seconds?: number | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
}

export interface ExperimentAlgorithms {
  algorithms: { code: string; label: string; description: string }[];
  cv_strategies: { code: string; label: string; description: string }[];
  tasks: string[];
  targets: string[];
}

export interface RegionMetricsResponse {
  experiment_id: number;
  algorithm: string;
  cv_strategy: string;
  per_region: Record<string, ModelMetrics>;
  per_group?: Record<string, { label?: string; groups?: Record<string, ModelMetrics> }>;
  spatial_diagnostics?: SpatialDiagnostics;
}

export interface TerritoryExplanation {
  territory_id: number;
  territory_code: string;
  territory_name: string;
  region: string;
  model_id?: number;
  mean_risk: number;
  stunting_prevalence: number;
  children_screened: number;
  features: ShapFeature[];
  narrative: string;
}

export interface DependenceResponse {
  feature: string;
  label: string;
  model_id: number;
  points: { value: number | null; shap: number; group?: string | null }[];
}

export interface XaiModel {
  id: number;
  name: string;
  algorithm: string;
  is_active: boolean;
  version: string;
  has_shap: boolean;
}

export interface FairnessAttribute {
  code: string;
  label: string;
}

export interface FairnessAttributes {
  attributes: FairnessAttribute[];
  threshold: number;
}

export interface DatasetSource {
  code: string;
  label: string;
  description?: string | null;
}

export interface DatasetSources {
  sources: DatasetSource[];
  formats: string[];
  max_upload_mb: number;
  canonical_columns: string[];
}

export interface DatasetVariable {
  id: number;
  name: string;
  label?: string | null;
  dtype?: string | null;
  unit?: string | null;
  description?: string | null;
  allowed_values?: string[] | null;
  min_value?: number | null;
  max_value?: number | null;
  is_required?: boolean;
  is_identifier?: boolean;
  missing_count?: number;
  stats?: {
    dtype?: string;
    missing?: number;
    missing_ratio?: number;
    unique?: number;
    top_values?: Record<string, number>;
  } | null;
}

export interface DatasetQualityReport {
  rows?: number;
  columns?: number;
  duplicate_rows?: number;
  missing_cells?: number;
  missing_ratio?: number;
  outliers?: number;
  issues?: { code: string; severity: string; message: string }[];
  column_stats?: Record<string, DatasetVariable['stats']>;
  score?: number;
  checked_at?: string;
}

export interface DatasetQualityResponse {
  dataset_id: number;
  quality_report: DatasetQualityReport;
  rows: number;
  columns: number;
  status: string;
}

export interface DatasetPreview {
  columns: string[];
  rows: Record<string, unknown>[];
  total_rows: number;
}

export interface UploadResult {
  dataset: Dataset;
  run: Record<string, unknown>;
  preview?: Record<string, unknown>[];
  quality?: DatasetQualityReport | null;
}

export interface AuditSummary {
  period_days: number;
  total_events: number;
  failed_events: number;
  success_rate: number;
  by_module: { module: string; count: number }[];
  top_users: { email: string; count: number }[];
  by_day: { date: string; count: number }[];
}

export interface NavigationEvent {
  id: number;
  user_id?: number | null;
  session_id?: string | null;
  module: string;
  event_type: string;
  path?: string | null;
  ip_address?: string | null;
  occurred_at: string;
}

export interface AgentCapability {
  intent: string;
  description: string;
  examples: string[];
}

export interface AgentMessage {
  id: number;
  role: string;
  content: string;
  meta?: Record<string, unknown> | null;
  created_at?: string | null;
}

export interface AgentSessionDetail extends ChatSession {
  messages: AgentMessage[];
}

export interface UserPermissions {
  roles: RoleInfo[];
  modules: string[];
  actions: string[];
  matrix: Record<string, Record<string, string[]>>;
}

export interface SystemMonitoring {
  audit_events: number;
  failed_events: number;
  slow_events: number;
  success_rate: number;
  latest_events: {
    id: number;
    module: string;
    action: string;
    result: string;
    duration_ms: number;
    started_at: string;
  }[];
  storage_dir: string;
  artifacts_dir: string;
  database: string;
}

export interface HelpFaq {
  question: string;
  answer: string;
}

export interface ReportScheduleInfo {
  message: string;
  webhook?: string;
  api_endpoint?: string;
  cron_examples?: string[];
  import_file?: string;
}

"""ML, explainability, fairness, geospatial, dashboard and alert schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

# --------------------------------------------------------------------------- #
# Experiments and models
# --------------------------------------------------------------------------- #
ALGORITHMS = Literal["random_forest", "xgboost", "catboost", "spatial_xgboost", "cnn_lstm"]


class TrainRequest(BaseModel):
    algorithms: list[ALGORITHMS] = Field(default_factory=lambda: ["random_forest", "xgboost", "catboost"])
    task: Literal["classification", "regression"] = "classification"
    target: str = "stunting"
    cv_strategy: Literal["group_kfold_region", "leave_one_region_out", "stratified_kfold"] = "group_kfold_region"
    test_size: float = Field(default=0.2, ge=0.1, le=0.4)
    dataset_id: int | None = None
    notes: str | None = None
    include_spatial: bool = True
    include_cnn_lstm: bool = False
    hyperparams: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ExperimentOut(ORMModel):
    id: int
    name: str
    algorithm: str
    task: str
    target: str
    dataset_id: int | None = None
    cv_strategy: str
    seed: int
    metrics: dict = Field(default_factory=dict)
    per_region_metrics: dict = Field(default_factory=dict)
    per_group_metrics: dict = Field(default_factory=dict)
    spatial_diagnostics: dict = Field(default_factory=dict)
    feature_importance: dict = Field(default_factory=dict)
    hyperparams: dict = Field(default_factory=dict)
    status: str
    notes: str | None = None
    duration_seconds: float | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None


class ModelOut(ORMModel):
    id: int
    name: str
    version: str
    algorithm: str
    task: str
    target: str
    experiment_id: int | None = None
    metrics: dict = Field(default_factory=dict)
    feature_importance: dict = Field(default_factory=dict)
    shap_summary: dict = Field(default_factory=dict)
    hyperparams: dict = Field(default_factory=dict)
    is_active: bool
    is_synthetic: bool
    trained_at: datetime | None = None


class ModelComparisonRow(BaseModel):
    model_id: int
    name: str
    version: str
    algorithm: str
    auc: float | None = None
    f1: float | None = None
    precision: float | None = None
    recall: float | None = None
    accuracy: float | None = None
    brier: float | None = None
    rmse: float | None = None
    mae: float | None = None
    train_seconds: float | None = None
    is_best: bool = False


class TrainingJobAccepted(BaseModel):
    message: str
    experiment_ids: list[int]
    task: str
    algorithms: list[str]


# --------------------------------------------------------------------------- #
# Explainability
# --------------------------------------------------------------------------- #
class ShapFeature(BaseModel):
    feature: str
    label: str
    mean_abs_shap: float
    share: float = 0.0
    direction: str = "positive"


class GlobalExplanation(BaseModel):
    model_id: int
    model_name: str
    algorithm: str
    base_value: float
    n_samples: int
    features: list[ShapFeature]
    beeswarm: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime | None = None


class ShapContribution(BaseModel):
    feature: str
    label: str
    value: float | None = None
    contribution: float
    direction: str


class LocalExplanation(BaseModel):
    child_id: int
    child_code: str
    model_id: int
    prediction: float
    base_value: float
    risk_band: str
    contributions: list[ShapContribution]
    narrative: str
    positive: list[ShapContribution] = Field(default_factory=list)
    negative: list[ShapContribution] = Field(default_factory=list)


class TerritoryExplanation(BaseModel):
    territory_id: int
    territory_code: str
    territory_name: str
    region: str
    model_id: int
    mean_risk: float
    stunting_prevalence: float
    children_screened: int
    features: list[ShapFeature]
    narrative: str


class DependencePoint(BaseModel):
    value: float
    shap: float
    group: str | None = None


class DependenceResponse(BaseModel):
    feature: str
    label: str
    model_id: int
    points: list[DependencePoint]


# --------------------------------------------------------------------------- #
# Fairness
# --------------------------------------------------------------------------- #
class FairnessGroupMetrics(BaseModel):
    group: str
    n: int
    selection_rate: float
    tpr: float | None = None
    fpr: float | None = None
    precision: float | None = None
    recall: float | None = None
    accuracy: float | None = None
    auc: float | None = None
    mean_score: float | None = None
    stunting_rate: float | None = None


class FairnessResult(BaseModel):
    model_id: int
    sensitive_attribute: str
    metric: str
    groups: list[FairnessGroupMetrics]
    max_disparity: float
    ratio: float | None = None
    is_acceptable: bool
    threshold: float = 0.2
    generated_at: datetime | None = None


class FairnessSummary(BaseModel):
    model_id: int
    attributes: list[FairnessResult]
    overall_acceptable: bool
    notes: list[str] = Field(default_factory=list)


class FairnessRunRequest(BaseModel):
    model_id: int
    attributes: list[str] = Field(default_factory=lambda: ["sex", "wealth_quintile", "urban_rural", "region"])
    threshold: float = 0.2


# --------------------------------------------------------------------------- #
# Geospatial
# --------------------------------------------------------------------------- #
class TerritoryRiskOut(BaseModel):
    territory_id: int
    code: str
    name: str
    region: str
    year: int
    mean_risk: float
    risk_band: str
    stunting_prevalence: float
    children_screened: int
    population_at_risk: int
    priority_rank: int
    top_features: list[dict[str, Any]] = Field(default_factory=list)


class MapProperties(BaseModel):
    territory_id: int
    code: str
    name: str
    region: str
    urban_rural: str
    population: int
    population_u5: int
    mean_risk: float
    risk_band: str
    stunting_prevalence: float
    priority_rank: int
    children_screened: int
    population_at_risk: int
    altitude_m: float | None = None
    food_insecurity_index: float | None = None
    water_coverage: float | None = None
    sanitation_coverage: float | None = None


class MapFeature(BaseModel):
    type: str = "Feature"
    geometry: dict[str, Any]
    properties: MapProperties


class MapCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[MapFeature]
    year: int
    model_id: int | None = None
    legend: list[dict[str, Any]] = Field(default_factory=list)


class RankingResponse(BaseModel):
    year: int
    model_id: int | None = None
    total: int
    rows: list[TerritoryRiskOut]


class RiskDistributionItem(BaseModel):
    band: str
    label: str
    count: int
    population: int
    share: float


class GeoLayerPoint(BaseModel):
    code: str
    name: str
    value: float | None = None
    population: int = 0


class GeoLayersResponse(BaseModel):
    layer: str
    label: str
    unit: str | None = None
    points: list[GeoLayerPoint]


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
class KpiItem(BaseModel):
    key: str
    label: str
    value: float
    unit: str = "%"
    delta: float | None = None
    trend: str = "flat"
    description: str | None = None
    severity: str = "neutral"


class DashboardKpis(BaseModel):
    kpis: list[KpiItem]
    filters: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime | None = None


class TrendPoint(BaseModel):
    period: str
    stunting: float
    wasting: float
    underweight: float
    mean_risk: float | None = None
    population_at_risk: int = 0


class TrendResponse(BaseModel):
    series: list[TrendPoint]
    metric: str = "prevalence"


class ComparisonRow(BaseModel):
    key: str
    label: str
    stunting: float
    wasting: float
    underweight: float
    mean_risk: float
    n: int


class ComparisonResponse(BaseModel):
    dimension: str
    rows: list[ComparisonRow]


class RiskDistributionResponse(BaseModel):
    bands: list[RiskDistributionItem]
    total_children: int
    total_population: int


class ModelPerformanceRow(BaseModel):
    model_id: int
    name: str
    algorithm: str
    auc: float | None = None
    f1: float | None = None
    precision: float | None = None
    recall: float | None = None
    accuracy: float | None = None
    is_active: bool = False
    trained_at: datetime | None = None


class ModelPerformanceResponse(BaseModel):
    models: list[ModelPerformanceRow]


class DashboardOverview(BaseModel):
    kpis: list[KpiItem]
    trend: list[TrendPoint]
    regions: list[ComparisonRow]
    top_territories: list[TerritoryRiskOut]
    model_performance: list[ModelPerformanceRow]
    risk_distribution: list[RiskDistributionItem]
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #
class AlertOut(ORMModel):
    id: int
    rule_code: str
    severity: str
    title: str
    message: str
    module: str
    territory_id: int | None = None
    value: float | None = None
    threshold: float | None = None
    status: str
    context: dict = Field(default_factory=dict)
    created_at: datetime | None = None
    acknowledged_at: datetime | None = None


class AlertCreate(BaseModel):
    rule_code: str = "MANUAL"
    severity: Literal["INFO", "WARNING", "CRITICAL"] = "WARNING"
    title: str
    message: str
    territory_id: int | None = None
    value: float | None = None
    threshold: float | None = None


class AlertSummary(BaseModel):
    open: int
    acknowledged: int
    resolved: int
    critical: int
    by_severity: dict[str, int] = Field(default_factory=dict)
    latest: list[AlertOut] = Field(default_factory=list)


class AlertEvaluationResult(BaseModel):
    created: int
    skipped: int
    rules: list[dict[str, Any]] = Field(default_factory=list)

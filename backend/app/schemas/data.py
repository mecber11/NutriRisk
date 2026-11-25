"""Dataset catalogue, ingestion, territory and child schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ORMModel


class VariableOut(ORMModel):
    id: int
    name: str
    label: str
    dtype: str
    unit: str | None = None
    description: str | None = None
    allowed_values: list | None = None
    min_value: float | None = None
    max_value: float | None = None
    is_required: bool
    is_identifier: bool
    missing_count: int
    stats: dict = Field(default_factory=dict)


class DatasetOut(ORMModel):
    id: int
    name: str
    slug: str
    source: str
    kind: str
    analysis_unit: str
    description: str | None = None
    period_year: int | None = None
    country: str | None = None
    license: str | None = None
    file_name: str | None = None
    file_format: str | None = None
    checksum_sha256: str | None = None
    rows: int
    columns: int
    status: str
    is_synthetic: bool
    quality_report: dict = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DatasetDetail(DatasetOut):
    variables: list[VariableOut] = Field(default_factory=list)


class DatasetCreate(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    source: Literal["DHS", "WORLD_BANK", "UNICEF", "WORLDPOP", "SYNTHETIC", "CUSTOM"] = "CUSTOM"
    kind: Literal["CHILD", "HOUSEHOLD", "TERRITORY", "MIXED"] = "CHILD"
    analysis_unit: Literal["CHILD", "HOUSEHOLD", "TERRITORY"] = "CHILD"
    description: str | None = None
    period_year: int | None = Field(default=None, ge=1990, le=2100)
    country: str | None = None
    license: str | None = None


class QualityIssue(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    count: int = 0
    column: str | None = None


class QualityReport(BaseModel):
    rows: int = 0
    columns: int = 0
    duplicate_rows: int = 0
    missing_cells: int = 0
    missing_ratio: float = 0.0
    outliers: int = 0
    issues: list[QualityIssue] = Field(default_factory=list)
    column_stats: dict[str, dict[str, Any]] = Field(default_factory=dict)
    score: float = 100.0
    checked_at: datetime | None = None


class IngestionRunOut(ORMModel):
    id: int
    dataset_id: int
    status: str
    trigger: str
    rows_in: int
    rows_loaded: int
    rows_rejected: int
    errors: list = Field(default_factory=list)
    warnings: list = Field(default_factory=list)
    quality_report: dict = Field(default_factory=dict)
    duration_ms: int
    started_at: datetime | None = None
    finished_at: datetime | None = None


class UploadResult(BaseModel):
    dataset: DatasetOut
    run: IngestionRunOut
    preview: list[dict[str, Any]] = Field(default_factory=list)
    quality: QualityReport | None = None


class TerritoryOut(ORMModel):
    id: int
    code: str
    name: str
    level: str
    parent_code: str | None = None
    region: str
    urban_rural: str
    population: int
    population_u5: int
    area_km2: float | None = None
    altitude_m: float | None = None
    climate_zone: str | None = None
    rainfall_mm: float | None = None
    temperature_c: float | None = None
    ndvi: float | None = None
    food_insecurity_index: float | None = None
    water_coverage: float | None = None
    sanitation_coverage: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    neighbor_codes: list = Field(default_factory=list)
    is_synthetic: bool = True


class TerritoryDetail(TerritoryOut):
    geometry: dict | None = None


class HouseholdOut(ORMModel):
    id: int
    code: str
    territory_id: int
    period_year: int
    wealth_quintile: int
    wealth_index: float
    maternal_education: str
    maternal_age: int | None = None
    water_source: str
    sanitation: str
    electricity: bool
    cooking_fuel: str
    assets_count: int
    household_size: int
    food_insecurity_score: float
    urban_rural: str


class ChildOut(ORMModel):
    id: int
    code: str
    household_id: int
    territory_id: int
    period_year: int
    age_months: int
    sex: str
    weight_kg: float
    height_cm: float
    muac_cm: float | None = None
    edema: bool
    minimum_diet_diversity: bool
    vaccination_complete: bool
    diarrhea_14d: bool
    fever_14d: bool


class IndicatorOut(ORMModel):
    id: int
    child_id: int
    haz: float | None = None
    waz: float | None = None
    whz: float | None = None
    baz: float | None = None
    stunting: bool
    severe_stunting: bool
    wasting: bool
    severe_wasting: bool
    underweight: bool
    severe_underweight: bool
    overweight: bool
    edematous: bool
    reference_version: str
    computed_at: datetime | None = None


class ChildRecord(BaseModel):
    child: ChildOut
    household: HouseholdOut | None = None
    territory: TerritoryOut | None = None
    indicator: IndicatorOut | None = None


class PrevalenceRow(BaseModel):
    key: str
    label: str
    n: int
    stunting: float
    wasting: float
    underweight: float
    severe_stunting: float = 0.0
    mean_haz: float | None = None


class IndicatorSummary(BaseModel):
    total_children: int
    stunting_prevalence: float
    wasting_prevalence: float
    underweight_prevalence: float
    severe_stunting_prevalence: float
    mean_haz: float
    mean_waz: float
    mean_whz: float
    by_year: list[PrevalenceRow] = Field(default_factory=list)
    by_region: list[PrevalenceRow] = Field(default_factory=list)
    by_sex: list[PrevalenceRow] = Field(default_factory=list)
    by_age_group: list[PrevalenceRow] = Field(default_factory=list)
    by_wealth_quintile: list[PrevalenceRow] = Field(default_factory=list)
    reference_version: str = "WHO-2006"


class RecomputeRequest(BaseModel):
    year: int | None = None
    territory_id: int | None = None
    recompute_all: bool = True


class RecomputeResult(BaseModel):
    processed: int
    failed: int
    errors: list[dict[str, Any]] = Field(default_factory=list)


class HistogramBin(BaseModel):
    bin_start: float
    bin_end: float
    count: int


class DistributionResponse(BaseModel):
    indicator: str
    reference_line: float | None = None
    bins: list[HistogramBin]
    mean: float | None = None
    sd: float | None = None
    total: int = 0


class OptionSets(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    regions: list[str] = Field(default_factory=list)
    years: list[int] = Field(default_factory=list)
    sexes: list[str] = Field(default_factory=list)
    age_groups: list[str] = Field(default_factory=list)
    territories: list[dict[str, Any]] = Field(default_factory=list)

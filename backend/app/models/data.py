"""Data catalogue, territories, households, children and anthropometry."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, utcnow


class Dataset(Base, IdMixin, TimestampMixin):
    """Catalogue entry for an ingested source file."""

    __tablename__ = "datasets"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # DHS | WORLD_BANK | UNICEF | WORLDPOP | SYNTHETIC
    kind: Mapped[str] = mapped_column(String(30), default="CHILD", nullable=False)  # CHILD | HOUSEHOLD | TERRITORY
    analysis_unit: Mapped[str] = mapped_column(String(20), default="CHILD", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    period_year: Mapped[int | None] = mapped_column(Integer, index=True)
    country: Mapped[str | None] = mapped_column(String(80))
    license: Mapped[str | None] = mapped_column(String(120))
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(Text)
    file_format: Mapped[str | None] = mapped_column(String(20))
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    columns: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="READY", nullable=False, index=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    schema_definition: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    quality_report: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    metadata_extra: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    variables: Mapped[list["VariableDefinition"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    runs: Mapped[list["IngestionRun"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")


class VariableDefinition(Base, IdMixin):
    """Variable dictionary row (label, type, unit, range) for a dataset."""

    __tablename__ = "variable_definitions"
    __table_args__ = (UniqueConstraint("dataset_id", "name", name="uq_variable_dataset_name"),)

    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    dtype: Mapped[str] = mapped_column(String(30), default="string", nullable=False)
    unit: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(Text)
    allowed_values: Mapped[list | None] = mapped_column(JSON)
    min_value: Mapped[float | None] = mapped_column(Float)
    max_value: Mapped[float | None] = mapped_column(Float)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_identifier: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    missing_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stats: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    dataset: Mapped[Dataset] = relationship(back_populates="variables")


class IngestionRun(Base, IdMixin):
    """One execution of the ingestion pipeline for a dataset."""

    __tablename__ = "ingestion_runs"

    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(20), default="UPLOAD", nullable=False)  # UPLOAD | SCHEDULE | API
    rows_in: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_loaded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    warnings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    quality_report: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    triggered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    dataset: Mapped[Dataset] = relationship(back_populates="runs")


class Territory(Base, IdMixin, TimestampMixin):
    """Administrative unit with an optional GeoJSON footprint."""

    __tablename__ = "territories"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(30), default="DEPARTMENT", nullable=False)  # REGION | DEPARTMENT | MUNICIPALITY
    parent_code: Mapped[str | None] = mapped_column(String(40))
    region: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    urban_rural: Mapped[str] = mapped_column(String(10), default="MIXED", nullable=False)
    population: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    population_u5: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    area_km2: Mapped[float | None] = mapped_column(Float)
    altitude_m: Mapped[float | None] = mapped_column(Float)
    climate_zone: Mapped[str | None] = mapped_column(String(40))
    rainfall_mm: Mapped[float | None] = mapped_column(Float)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    ndvi: Mapped[float | None] = mapped_column(Float)
    food_insecurity_index: Mapped[float | None] = mapped_column(Float)
    water_coverage: Mapped[float | None] = mapped_column(Float)
    sanitation_coverage: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    geometry: Mapped[dict | None] = mapped_column(JSON)
    neighbor_codes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    households: Mapped[list["Household"]] = relationship(back_populates="territory")


class Household(Base, IdMixin, TimestampMixin):
    """Household-level socioeconomic and WASH determinants."""

    __tablename__ = "households"
    __table_args__ = (Index("ix_households_territory_year", "territory_id", "period_year"),)

    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    territory_id: Mapped[int] = mapped_column(ForeignKey("territories.id"), nullable=False, index=True)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    wealth_quintile: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 (poorest) .. 5 (richest)
    wealth_index: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    maternal_education: Mapped[str] = mapped_column(String(20), default="PRIMARY", nullable=False)
    maternal_age: Mapped[int | None] = mapped_column(Integer)
    water_source: Mapped[str] = mapped_column(String(30), default="IMPROVED", nullable=False)
    sanitation: Mapped[str] = mapped_column(String(30), default="IMPROVED", nullable=False)
    electricity: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cooking_fuel: Mapped[str] = mapped_column(String(30), default="GAS", nullable=False)
    assets_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    household_size: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    food_insecurity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    urban_rural: Mapped[str] = mapped_column(String(10), default="RURAL", nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_extra: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    territory: Mapped[Territory] = relationship(back_populates="households")
    children: Mapped[list["Child"]] = relationship(back_populates="household")


class Child(Base, IdMixin, TimestampMixin):
    """Analysis unit: child under five with anthropometric measurements."""

    __tablename__ = "children"
    __table_args__ = (
        Index("ix_children_territory_year", "territory_id", "period_year"),
        Index("ix_children_sex_year", "sex", "period_year"),
    )

    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    territory_id: Mapped[int] = mapped_column(ForeignKey("territories.id"), nullable=False, index=True)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    age_months: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sex: Mapped[str] = mapped_column(String(1), nullable=False, index=True)  # M | F
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    height_cm: Mapped[float] = mapped_column(Float, nullable=False)
    muac_cm: Mapped[float | None] = mapped_column(Float)
    edema: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    birth_weight_g: Mapped[float | None] = mapped_column(Float)
    breastfeeding_months: Mapped[int | None] = mapped_column(Integer)
    minimum_diet_diversity: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vaccination_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    diarrhea_14d: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fever_14d: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_extra: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    household: Mapped[Household] = relationship(back_populates="children")
    territory: Mapped[Territory] = relationship()
    indicator: Mapped["AnthropometricIndicator | None"] = relationship(
        back_populates="child", uselist=False, cascade="all, delete-orphan"
    )


class AnthropometricIndicator(Base, IdMixin):
    """WHO 2006 z-scores and nutritional status classification."""

    __tablename__ = "anthropometric_indicators"
    __table_args__ = (Index("ix_indicators_status", "stunting", "wasting", "underweight"),)

    child_id: Mapped[int] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    haz: Mapped[float | None] = mapped_column(Float)
    waz: Mapped[float | None] = mapped_column(Float)
    whz: Mapped[float | None] = mapped_column(Float)
    baz: Mapped[float | None] = mapped_column(Float)
    stunting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    severe_stunting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    wasting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    severe_wasting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    underweight: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    severe_underweight: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    overweight: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    edematous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reference_version: Mapped[str] = mapped_column(String(40), default="WHO-2006", nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    child: Mapped[Child] = relationship(back_populates="indicator")

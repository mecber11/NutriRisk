"""Experiments, trained models, predictions, explainability, fairness and alerts."""

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


class ModelExperiment(Base, IdMixin, TimestampMixin):
    """A reproducible training run (one algorithm, one configuration)."""

    __tablename__ = "model_experiments"
    __table_args__ = (Index("ix_experiments_algo_task", "algorithm", "task"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    task: Mapped[str] = mapped_column(String(30), default="CLASSIFICATION", nullable=False)
    target: Mapped[str] = mapped_column(String(60), default="stunting", nullable=False)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"))
    cv_strategy: Mapped[str] = mapped_column(String(40), default="GROUP_KFOLD_REGION", nullable=False)
    seed: Mapped[int] = mapped_column(Integer, default=42, nullable=False)
    hyperparams: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    per_region_metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    per_group_metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    spatial_diagnostics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    feature_importance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    models: Mapped[list["MLModel"]] = relationship(back_populates="experiment")


class MLModel(Base, IdMixin, TimestampMixin):
    """Versioned model artifact ready to score children and territories."""

    __tablename__ = "models"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_model_name_version"),)

    experiment_id: Mapped[int | None] = mapped_column(ForeignKey("model_experiments.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    task: Mapped[str] = mapped_column(String(30), default="CLASSIFICATION", nullable=False)
    target: Mapped[str] = mapped_column(String(60), default="stunting", nullable=False)
    artifact_path: Mapped[str] = mapped_column(Text, nullable=False)
    feature_names: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    feature_importance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    shap_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    hyperparams: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    experiment: Mapped[ModelExperiment | None] = relationship(back_populates="models")


class Prediction(Base, IdMixin):
    """Child-level risk score produced by a model."""

    __tablename__ = "predictions"
    __table_args__ = (
        Index("ix_predictions_model_territory", "model_id", "territory_id"),
        Index("ix_predictions_model_year", "model_id", "period_year"),
    )

    model_id: Mapped[int] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), nullable=False, index=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"), nullable=False, index=True)
    territory_id: Mapped[int] = mapped_column(ForeignKey("territories.id"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_label: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    risk_band: Mapped[str] = mapped_column(String(20), default="LOW", nullable=False, index=True)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    explanation: Mapped["PredictionExplanation | None"] = relationship(
        back_populates="prediction", uselist=False, cascade="all, delete-orphan"
    )


class PredictionExplanation(Base, IdMixin):
    """Local SHAP explanation for a single child prediction."""

    __tablename__ = "prediction_explanations"

    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    base_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    contributions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    narrative: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    prediction: Mapped[Prediction] = relationship(back_populates="explanation")


class TerritoryRisk(Base, IdMixin):
    """Aggregated predicted risk and priority ranking per territory/period."""

    __tablename__ = "territory_risk"
    __table_args__ = (
        UniqueConstraint("model_id", "territory_id", "period_year", name="uq_risk_model_territory_year"),
        Index("ix_territory_risk_rank", "period_year", "priority_rank"),
    )

    model_id: Mapped[int] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), nullable=False, index=True)
    territory_id: Mapped[int] = mapped_column(ForeignKey("territories.id"), nullable=False, index=True)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mean_risk: Mapped[float] = mapped_column(Float, nullable=False)
    risk_band: Mapped[str] = mapped_column(String(20), default="LOW", nullable=False)
    stunting_prevalence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    children_screened: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    population_at_risk: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    priority_rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    top_features: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class FairnessReport(Base, IdMixin):
    """Fairlearn group metrics for a sensitive attribute."""

    __tablename__ = "fairness_reports"

    model_id: Mapped[int] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), nullable=False, index=True)
    sensitive_attribute: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(40), default="equalized_odds", nullable=False)
    results: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    disparity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_acceptable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Alert(Base, IdMixin):
    """Operational alert generated by rules or n8n."""

    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_status_severity", "status", "severity"),)

    rule_code: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="INFO", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    module: Mapped[str] = mapped_column(String(40), default="alerts", nullable=False)
    territory_id: Mapped[int | None] = mapped_column(ForeignKey("territories.id", ondelete="SET NULL"))
    value: Mapped[float | None] = mapped_column(Float)
    threshold: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False, index=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

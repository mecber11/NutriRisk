"""SQLAlchemy models registry (import side effects register all tables)."""

from app.models.audit import AuditLog, NavigationEvent
from app.models.data import AnthropometricIndicator, Child, Dataset, Household, IngestionRun, Territory, VariableDefinition
from app.models.ml import (
    Alert,
    FairnessReport,
    MLModel,
    ModelExperiment,
    Prediction,
    PredictionExplanation,
    TerritoryRisk,
)
from app.models.system import ChatMessage, ChatSession, Report, SystemSetting
from app.models.user import PasswordResetToken, RefreshToken, Role, RolePermission, User

__all__ = [
    "Alert",
    "AnthropometricIndicator",
    "AuditLog",
    "ChatMessage",
    "ChatSession",
    "Child",
    "Dataset",
    "FairnessReport",
    "Household",
    "IngestionRun",
    "MLModel",
    "ModelExperiment",
    "NavigationEvent",
    "PasswordResetToken",
    "Prediction",
    "PredictionExplanation",
    "RefreshToken",
    "Report",
    "Role",
    "RolePermission",
    "SystemSetting",
    "Territory",
    "TerritoryRisk",
    "User",
    "VariableDefinition",
]


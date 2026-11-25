"""Reports, agent, settings, audit, help and system schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
ReportKind = Literal[
    "territory_profile",
    "priority_ranking",
    "model_performance",
    "fairness",
    "audit_log",
    "prevalence_summary",
]
ReportFormat = Literal["pdf", "docx", "xlsx"]


class ReportRequest(BaseModel):
    kind: ReportKind
    fmt: ReportFormat = "pdf"
    title: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class ReportOut(ORMModel):
    id: int
    kind: str
    title: str
    fmt: str
    params: dict = Field(default_factory=dict)
    file_name: str | None = None
    size_bytes: int
    status: str
    error: str | None = None
    created_at: datetime | None = None
    download_url: str | None = None


class ReportKindInfo(BaseModel):
    code: str
    label: str
    description: str
    formats: list[str]
    params: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #
class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)
    session_id: int | None = None


class ChatMessageOut(ORMModel):
    id: int
    role: str
    content: str
    meta: dict = Field(default_factory=dict)
    created_at: datetime | None = None


class ChatSessionOut(ORMModel):
    id: int
    title: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChatSessionDetail(ChatSessionOut):
    messages: list[ChatMessageOut] = Field(default_factory=list)


class AgentAnswer(BaseModel):
    session_id: int
    answer: str
    intent: str
    tools_used: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    suggestions: list[str] = Field(default_factory=list)
    provider: str = "deterministic"


class AgentCapability(BaseModel):
    intent: str
    description: str
    examples: list[str]


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
class SettingOut(ORMModel):
    key: str
    value: dict
    category: str
    description: str | None = None
    updated_at: datetime | None = None


class SettingUpdate(BaseModel):
    value: dict[str, Any]


class SettingsGroup(BaseModel):
    category: str
    label: str
    items: list[SettingOut]


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
class AuditLogOut(BaseModel):
    id: int
    user_id: int | None = None
    user_email: str | None = None
    role_code: str | None = None
    module: str
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    method: str | None = None
    path: str | None = None
    status_code: int | None = None
    result: str
    detail: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    session_id: str | None = None
    started_at: datetime
    finished_at: datetime
    duration_ms: int


class NavigationEventCreate(BaseModel):
    module: str = Field(min_length=2, max_length=40)
    event_type: Literal["ENTER", "EXIT"]
    path: str | None = None
    session_id: str | None = None


class NavigationEventOut(ORMModel):
    id: int
    user_id: int | None = None
    session_id: str | None = None
    module: str
    event_type: str
    path: str | None = None
    ip_address: str | None = None
    occurred_at: datetime


class AuditSummary(BaseModel):
    period_days: int
    total_events: int
    failed_events: int
    success_rate: float
    by_module: list[dict[str, Any]]
    top_users: list[dict[str, Any]]
    by_day: list[dict[str, Any]]


# --------------------------------------------------------------------------- #
# Help and system
# --------------------------------------------------------------------------- #
class HelpSection(BaseModel):
    code: str
    title: str
    content: list[str]
    links: list[dict[str, str]] = Field(default_factory=list)


class FaqItem(BaseModel):
    question: str
    answer: str


class SystemInfo(BaseModel):
    app: str
    version: str
    environment: str
    api_prefix: str
    database: str
    demo_mode: bool
    llm_provider: str
    reference_version: str
    counts: dict[str, int] = Field(default_factory=dict)
    active_model: dict[str, Any] | None = None
    features: dict[str, bool] = Field(default_factory=dict)
    server_time: datetime

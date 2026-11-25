"""Audit trail: immutable access log and module navigation events."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, utcnow


class AuditLog(Base, IdMixin):
    """Append-only access log. UPDATE/DELETE are blocked by DB triggers."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_started_at", "started_at"),
        Index("ix_audit_logs_module_action", "module", "action"),
        Index("ix_audit_logs_user_started", "user_id", "started_at"),
    )

    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    user_email: Mapped[str | None] = mapped_column(String(255), index=True)
    role_code: Mapped[str | None] = mapped_column(String(40))
    module: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(60))
    resource_id: Mapped[str | None] = mapped_column(String(80))
    method: Mapped[str | None] = mapped_column(String(10))
    path: Mapped[str | None] = mapped_column(Text)
    status_code: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[str] = mapped_column(String(20), default="SUCCESS", nullable=False, index=True)
    detail: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64), index=True)
    user_agent: Mapped[str | None] = mapped_column(String(400))
    session_id: Mapped[str | None] = mapped_column(String(80), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class NavigationEvent(Base, IdMixin):
    """Explicit module entry/exit marks sent by the React client."""

    __tablename__ = "navigation_events"
    __table_args__ = (Index("ix_navigation_events_user_time", "user_id", "occurred_at"),)

    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    session_id: Mapped[str | None] = mapped_column(String(80), index=True)
    module: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(10), nullable=False)  # ENTER | EXIT
    path: Mapped[str | None] = mapped_column(String(400))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

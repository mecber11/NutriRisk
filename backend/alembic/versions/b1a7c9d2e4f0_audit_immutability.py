"""Audit immutability triggers and PostGIS/index hardening.

Revision ID: b1a7c9d2e4f0
Revises: d0b55539871d
Create Date: 2026-11-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b1a7c9d2e4f0"
down_revision: str | None = "d0b55539871d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SQLITE_TRIGGERS = (
    """
    CREATE TRIGGER IF NOT EXISTS audit_logs_block_update
    BEFORE UPDATE ON audit_logs
    BEGIN
        SELECT RAISE(ABORT, 'audit_logs es de solo inserción (append-only)');
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS audit_logs_block_delete
    BEFORE DELETE ON audit_logs
    BEGIN
        SELECT RAISE(ABORT, 'audit_logs es de solo inserción (append-only)');
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS navigation_events_block_update
    BEFORE UPDATE ON navigation_events
    BEGIN
        SELECT RAISE(ABORT, 'navigation_events es de solo inserción (append-only)');
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS navigation_events_block_delete
    BEFORE DELETE ON navigation_events
    BEGIN
        SELECT RAISE(ABORT, 'navigation_events es de solo inserción (append-only)');
    END;
    """,
)

POSTGRES_TRIGGERS = (
    """
    CREATE OR REPLACE FUNCTION nutririsk_forbid_mutation() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'Registro inmutable: % no admite %', TG_TABLE_NAME, TG_OP;
    END;
    $$ LANGUAGE plpgsql;
    """,
    """
    DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs;
    CREATE TRIGGER audit_logs_immutable
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION nutririsk_forbid_mutation();
    """,
    """
    DROP TRIGGER IF EXISTS navigation_events_immutable ON navigation_events;
    CREATE TRIGGER navigation_events_immutable
    BEFORE UPDATE OR DELETE ON navigation_events
    FOR EACH ROW EXECUTE FUNCTION nutririsk_forbid_mutation();
    """,
)

GEO_INDEXES = (
    """
    CREATE INDEX IF NOT EXISTS ix_territories_geom_gist
    ON territories
    USING GIST (ST_SetSRID(ST_GeomFromGeoJSON(geometry::text), 4326));
    """,
    "CREATE INDEX IF NOT EXISTS ix_children_age_year ON children (age_months, period_year);",
    "CREATE INDEX IF NOT EXISTS ix_predictions_risk_band ON predictions (risk_band);",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_started_module ON audit_logs (started_at DESC, module);",
)


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for statement in SQLITE_TRIGGERS:
            op.execute(statement)
    elif dialect == "postgresql":
        for statement in POSTGRES_TRIGGERS:
            op.execute(statement)
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        for statement in GEO_INDEXES:
            try:
                op.execute(statement)
            except Exception:  # noqa: BLE001 - geometry column types vary by deployment
                pass


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for name in (
            "audit_logs_block_update",
            "audit_logs_block_delete",
            "navigation_events_block_update",
            "navigation_events_block_delete",
        ):
            op.execute(f"DROP TRIGGER IF EXISTS {name};")
    elif dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs;")
        op.execute("DROP TRIGGER IF EXISTS navigation_events_immutable ON navigation_events;")
        op.execute("DROP FUNCTION IF EXISTS nutririsk_forbid_mutation();")

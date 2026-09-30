"""Insights (phase 4).

Revision ID: 0003_insights
Revises: 0002_runs
Create Date: 2026-09-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.base import JSONType, UTCDateTime

revision = "0003_insights"
down_revision = "0002_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "insights",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("entity_ref", JSONType, nullable=True),
        sa.Column("evidence", JSONType, nullable=False),
        sa.Column("message_key", sa.String(120), nullable=False),
        sa.Column("message_params", JSONType, nullable=False),
        sa.Column("suggested_changes", JSONType, nullable=True),
        sa.Column("dismissed", sa.Boolean(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_insights"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["optimization_runs.id"], name="fk_insights_run_id_optimization_runs", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_insights_run_severity", "insights", ["run_id", "severity"])


def downgrade() -> None:
    op.drop_index("ix_insights_run_severity", table_name="insights")
    op.drop_table("insights")

"""Frozen reports (phase 13).

Revision ID: 0006_reports
Revises: 0005_copilot
Create Date: 2026-10-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.base import JSONType, UTCDateTime

revision = "0006_reports"
down_revision = "0005_copilot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("spec", JSONType, nullable=False),
        sa.Column("snapshot", JSONType, nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_reports"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_reports_workspace_id_workspaces", ondelete="CASCADE"),
    )
    op.create_index("ix_reports_workspace_id", "reports", ["workspace_id"])
    op.create_index("ix_reports_run_id", "reports", ["run_id"])
    op.create_index("ix_reports_workspace_created", "reports", ["workspace_id", "created_at"])


def downgrade() -> None:
    for name in ("ix_reports_workspace_created", "ix_reports_run_id", "ix_reports_workspace_id"):
        op.drop_index(name, table_name="reports")
    op.drop_table("reports")

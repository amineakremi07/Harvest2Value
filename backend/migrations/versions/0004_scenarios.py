"""Scenarios and scenario changes (phase 5); foreign key optimization_runs.scenario_id.

Revision ID: 0004_scenarios
Revises: 0003_insights
Create Date: 2026-09-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.base import JSONType, UTCDateTime

revision = "0004_scenarios"
down_revision = "0003_insights"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("dataset_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_version_id", sa.String(36), nullable=False),
        sa.Column("parent_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("tags", JSONType, nullable=True),
        sa.Column("latest_run_id", sa.String(36), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_scenarios"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name="fk_scenarios_workspace_id_workspaces", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], name="fk_scenarios_dataset_id_datasets", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["base_version_id"],
            ["dataset_versions.id"],
            name="fk_scenarios_base_version_id_dataset_versions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["scenarios.id"], name="fk_scenarios_parent_id_scenarios", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["latest_run_id"],
            ["optimization_runs.id"],
            name="fk_scenarios_latest_run_id_optimization_runs",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_scenarios_workspace_id", "scenarios", ["workspace_id"])
    op.create_index("ix_scenarios_dataset_id", "scenarios", ["dataset_id"])
    op.create_index("ix_scenarios_base_version_id", "scenarios", ["base_version_id"])
    op.create_index("ix_scenarios_parent_id", "scenarios", ["parent_id"])
    op.create_index("ix_scenarios_workspace_updated", "scenarios", ["workspace_id", "updated_at"])

    op.create_table(
        "scenario_changes",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("scenario_id", sa.String(36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("op", sa.String(32), nullable=False),
        sa.Column("target", JSONType, nullable=True),
        sa.Column("params", JSONType, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_scenario_changes"),
        sa.ForeignKeyConstraint(
            ["scenario_id"], ["scenarios.id"], name="fk_scenario_changes_scenario_id_scenarios", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("scenario_id", "position", name="uq_scenario_changes_scenario_id"),
    )

    # Circular reference: added once both tables exist (batch mode recreates the table on SQLite).
    with op.batch_alter_table("optimization_runs") as batch:
        batch.create_foreign_key(
            "fk_optimization_runs_scenario_id_scenarios", "scenarios", ["scenario_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("optimization_runs") as batch:
        batch.drop_constraint("fk_optimization_runs_scenario_id_scenarios", type_="foreignkey")
    op.drop_table("scenario_changes")
    for name in (
        "ix_scenarios_workspace_updated",
        "ix_scenarios_parent_id",
        "ix_scenarios_base_version_id",
        "ix_scenarios_dataset_id",
        "ix_scenarios_workspace_id",
    ):
        op.drop_index(name, table_name="scenarios")
    op.drop_table("scenarios")

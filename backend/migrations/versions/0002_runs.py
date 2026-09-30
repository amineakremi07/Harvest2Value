"""Optimization runs and results (phase 3).

Revision ID: 0002_runs
Revises: 0001_initial
Create Date: 2026-09-30

`optimization_runs.scenario_id` gets its foreign key in 0004, once `scenarios` exists.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.base import JSONType, UTCDateTime

revision = "0002_runs"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "optimization_runs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("dataset_id", sa.String(36), nullable=False),
        sa.Column("dataset_version_id", sa.String(36), nullable=False),
        sa.Column("scenario_id", sa.String(36), nullable=True),
        sa.Column("config", JSONType, nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("effective_input_hash", sa.String(64), nullable=False),
        sa.Column("effective_input", JSONType, nullable=False),
        sa.Column("applied_changes", JSONType, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("solver_outcome", sa.String(20), nullable=True),
        sa.Column("mip_gap", sa.Float(), nullable=True),
        sa.Column("started_at", UTCDateTime(), nullable=True),
        sa.Column("finished_at", UTCDateTime(), nullable=True),
        sa.Column("solve_seconds", sa.Float(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("label", sa.String(120), nullable=True),
        sa.Column("warnings", JSONType, nullable=True),
        sa.Column("diagnostics", JSONType, nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_optimization_runs"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name="fk_optimization_runs_workspace_id_workspaces", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["datasets.id"], name="fk_optimization_runs_dataset_id_datasets", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["dataset_versions.id"],
            name="fk_optimization_runs_dataset_version_id_dataset_versions",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_optimization_runs_workspace_id", "optimization_runs", ["workspace_id"])
    op.create_index("ix_optimization_runs_dataset_id", "optimization_runs", ["dataset_id"])
    op.create_index("ix_optimization_runs_dataset_version_id", "optimization_runs", ["dataset_version_id"])
    op.create_index("ix_optimization_runs_scenario_id", "optimization_runs", ["scenario_id"])
    op.create_index("ix_optimization_runs_status", "optimization_runs", ["status"])
    op.create_index("ix_optimization_runs_workspace_created", "optimization_runs", ["workspace_id", "created_at"])
    op.create_index("ix_optimization_runs_cache", "optimization_runs", ["effective_input_hash", "config_hash"])

    op.create_table(
        "optimization_results",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("meta", JSONType, nullable=False),
        sa.Column("kpis", JSONType, nullable=False),
        sa.Column("buyers", JSONType, nullable=False),
        sa.Column("allocations", JSONType, nullable=False),
        sa.Column("inventory", JSONType, nullable=False),
        sa.Column("trips", JSONType, nullable=False),
        sa.Column("waste", JSONType, nullable=False),
        sa.Column("constraints", JSONType, nullable=False),
        sa.Column("warnings", JSONType, nullable=False),
        sa.Column("sensitivity", JSONType, nullable=True),
        sa.Column("explanation", JSONType, nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_optimization_results"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["optimization_runs.id"], name="fk_optimization_results_run_id_optimization_runs", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("run_id", name="uq_optimization_results_run_id"),
    )


def downgrade() -> None:
    op.drop_table("optimization_results")
    for name in (
        "ix_optimization_runs_cache",
        "ix_optimization_runs_workspace_created",
        "ix_optimization_runs_status",
        "ix_optimization_runs_scenario_id",
        "ix_optimization_runs_dataset_version_id",
        "ix_optimization_runs_dataset_id",
        "ix_optimization_runs_workspace_id",
    ):
        op.drop_index(name, table_name="optimization_runs")
    op.drop_table("optimization_runs")

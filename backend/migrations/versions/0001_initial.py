"""Initial schema: workspaces, datasets, dataset_versions.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.base import JSONType, UTCDateTime

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("locale", sa.String(10), nullable=False),
        sa.Column("settings", JSONType, nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("template_key", sa.String(64), nullable=True),
        sa.Column("current_version_id", sa.String(36), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_datasets"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name="fk_datasets_workspace_id_workspaces", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_datasets_workspace_id", "datasets", ["workspace_id"])
    op.create_index("ix_datasets_workspace_updated", "datasets", ["workspace_id", "updated_at"])

    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("dataset_id", sa.String(36), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(10), nullable=False),
        sa.Column("payload", JSONType, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("validation", JSONType, nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_versions"),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["datasets.id"], name="fk_dataset_versions_dataset_id_datasets", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("dataset_id", "version_no", name="uq_dataset_versions_dataset_id"),
    )
    op.create_index("ix_dataset_versions_content_hash", "dataset_versions", ["content_hash"])

    # Circular reference: added once both tables exist (batch mode recreates the table on SQLite).
    with op.batch_alter_table("datasets") as batch:
        batch.create_foreign_key(
            "fk_datasets_current_version_id_dataset_versions",
            "dataset_versions",
            ["current_version_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("datasets") as batch:
        batch.drop_constraint("fk_datasets_current_version_id_dataset_versions", type_="foreignkey")
    op.drop_index("ix_dataset_versions_content_hash", table_name="dataset_versions")
    op.drop_table("dataset_versions")
    op.drop_index("ix_datasets_workspace_updated", table_name="datasets")
    op.drop_index("ix_datasets_workspace_id", table_name="datasets")
    op.drop_table("datasets")
    op.drop_table("workspaces")

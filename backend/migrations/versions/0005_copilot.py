"""Copilot: conversations, messages and proposed actions (phase 11).

Revision ID: 0005_copilot
Revises: 0004_scenarios
Create Date: 2026-10-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.base import JSONType, UTCDateTime

revision = "0005_copilot"
down_revision = "0004_scenarios"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("context", JSONType, nullable=True),
        sa.Column("aliases", JSONType, nullable=True),
        sa.Column("refs", JSONType, nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_conversations"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name="fk_conversations_workspace_id_workspaces", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_conversations_workspace_id", "conversations", ["workspace_id"])
    op.create_index("ix_conversations_workspace_updated", "conversations", ["workspace_id", "updated_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("rendered", sa.Text(), nullable=True),
        sa.Column("verification", JSONType, nullable=True),
        sa.Column("tool_trace", JSONType, nullable=True),
        sa.Column("context", JSONType, nullable=True),
        sa.Column("prompt_id", sa.String(64), nullable=True),
        sa.Column("model", sa.String(120), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], name="fk_messages_conversation_id_conversations", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("conversation_id", "seq", name="uq_messages_conversation_id_seq"),
    )
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])

    op.create_table(
        "copilot_actions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("message_id", sa.String(36), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("payload", JSONType, nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("result", JSONType, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("expires_at", UTCDateTime(), nullable=False),
        sa.Column("decided_at", UTCDateTime(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_copilot_actions"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_copilot_actions_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["messages.id"], name="fk_copilot_actions_message_id_messages", ondelete="SET NULL"
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_copilot_actions_idempotency_key"),
    )
    op.create_index("ix_copilot_actions_conversation_id", "copilot_actions", ["conversation_id"])
    op.create_index("ix_copilot_actions_status", "copilot_actions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_copilot_actions_status", table_name="copilot_actions")
    op.drop_index("ix_copilot_actions_conversation_id", table_name="copilot_actions")
    op.drop_table("copilot_actions")
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_workspace_updated", table_name="conversations")
    op.drop_index("ix_conversations_workspace_id", table_name="conversations")
    op.drop_table("conversations")

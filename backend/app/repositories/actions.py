"""Copilot actions (proposals awaiting the user's decision)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Conversation, CopilotAction


class ActionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, action_id: str, workspace_id: str) -> CopilotAction | None:
        row = self.session.get(CopilotAction, action_id)
        if row is None:
            return None
        conversation = self.session.get(Conversation, row.conversation_id)
        return row if conversation is not None and conversation.workspace_id == workspace_id else None

    def get_for_update(self, action_id: str, workspace_id: str) -> CopilotAction | None:
        """Row lock on PostgreSQL (SQLite serializes writers anyway) so a double click cannot run twice."""
        row = self.session.scalars(select(CopilotAction).where(CopilotAction.id == action_id).with_for_update()).first()
        if row is None:
            return None
        conversation = self.session.get(Conversation, row.conversation_id)
        return row if conversation is not None and conversation.workspace_id == workspace_id else None

    def by_idempotency_key(self, key: str) -> CopilotAction | None:
        return self.session.scalars(select(CopilotAction).where(CopilotAction.idempotency_key == key)).first()

    def for_conversation(self, conversation_id: str) -> list[CopilotAction]:
        query = select(CopilotAction).where(CopilotAction.conversation_id == conversation_id)
        return list(self.session.scalars(query.order_by(CopilotAction.created_at, CopilotAction.id)).all())

    def add(self, action: CopilotAction) -> CopilotAction:
        self.session.add(action)
        self.session.flush()
        return action

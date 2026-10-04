"""Copilot conversations and their messages."""

from __future__ import annotations

import builtins

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import Conversation, Message


class ConversationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, conversation_id: str, workspace_id: str) -> Conversation | None:
        row = self.session.get(Conversation, conversation_id)
        return row if row is not None and row.workspace_id == workspace_id else None

    def list(self, workspace_id: str, *, page: int, page_size: int) -> tuple[list[Conversation], int]:
        query = select(Conversation).where(Conversation.workspace_id == workspace_id)
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.session.scalars(
            query.order_by(Conversation.updated_at.desc(), Conversation.id).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return list(rows), total

    def add(self, conversation: Conversation) -> Conversation:
        self.session.add(conversation)
        self.session.flush()
        return conversation

    def delete(self, conversation: Conversation) -> None:
        self.session.delete(conversation)
        self.session.flush()

    def messages(self, conversation_id: str, *, limit: int | None = None) -> builtins.list[Message]:
        query = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.seq)
        rows = list(self.session.scalars(query).all())
        return rows[-limit:] if limit else rows

    def add_message(self, message: Message) -> Message:
        last = self.session.scalar(select(func.max(Message.seq)).where(Message.conversation_id == message.conversation_id))
        message.seq = (last or 0) + 1
        self.session.add(message)
        self.session.flush()
        return message

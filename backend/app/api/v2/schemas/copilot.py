"""Copilot, narrative and text-to-scenario DTOs (phase 11)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from ....ai.context import PageContext
from ....ai.rendering import Locale
from ....db.models import Conversation, CopilotAction, Message


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    context: PageContext | None = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, row: Conversation) -> ConversationSummary:
        return cls(id=row.id, title=row.title, created_at=row.created_at, updated_at=row.updated_at)


class ActionView(BaseModel):
    id: str
    message_id: str | None
    kind: Literal["create_scenario", "run_optimization", "generate_report"]
    summary: str
    status: Literal["pending", "executed", "rejected", "expired", "failed"]
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    expires_at: datetime
    decided_at: datetime | None

    @classmethod
    def of(cls, row: CopilotAction) -> ActionView:
        return cls.model_validate(row, from_attributes=True)


class MessageView(BaseModel):
    id: str
    role: Literal["user", "assistant", "error"]
    content: str = Field(description="User text, or the assistant answer with numbers rendered by the backend (⟦?…⟧ = unverified)")
    verification: dict[str, Any] | None = None
    tool_trace: list[dict[str, Any]] | None = None
    model: str | None = None
    prompt_id: str | None = None
    created_at: datetime

    @classmethod
    def of(cls, row: Message) -> MessageView:
        content = row.rendered if row.role == "assistant" and row.rendered is not None else row.content
        return cls(
            id=row.id,
            role=row.role,  # type: ignore[arg-type]
            content=content,
            verification=row.verification,
            tool_trace=row.tool_trace,
            model=row.model,
            prompt_id=row.prompt_id,
            created_at=row.created_at,
        )


class ConversationDetail(ConversationSummary):
    context: PageContext | None
    messages: list[MessageView]
    actions: list[ActionView]


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    context: PageContext | None = Field(default=None, description="What the user has on screen; default: the conversation's last context")


class TurnResponse(BaseModel):
    user_message: MessageView
    message: MessageView
    actions: list[ActionView]


class ToolInfo(BaseModel):
    name: str
    description: str
    kind: Literal["read", "proposal"]
    parameters: dict[str, Any]


class ToolsResponse(BaseModel):
    tools: list[ToolInfo]
    llm_configured: bool


class NarrativeRequest(BaseModel):
    locale: Locale = "fr"


class ComparisonNarrativeRequest(BaseModel):
    baseline_run_id: str
    run_ids: list[str] = Field(min_length=1, max_length=3)
    locale: Locale = "fr"


class NarrativeResponse(BaseModel):
    text: str = Field(description="Numbers rendered by the backend; ⟦?…⟧ marks anything unverified")
    verification: dict[str, Any]
    locale: Locale
    model: str
    prompt: str

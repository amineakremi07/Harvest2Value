"""Provider-neutral message, tool and reply types, and the LLMProvider protocol."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

ResponseFormat = Literal["text", "json_object"]


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: str = Field(description="Raw JSON string, validated by the tool layer, never trusted as-is")


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class ToolSpec(BaseModel):
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    description: str
    parameters: dict[str, Any] = Field(description="JSON Schema of the arguments object")


class LLMUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMReply(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    finish_reason: str | None = None
    model: str
    usage: LLMUsage | None = None


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ToolSpec] | None = None,
        response_format: ResponseFormat | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMReply: ...

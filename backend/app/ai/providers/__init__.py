"""Provider-agnostic access to OpenAI-compatible chat completion APIs (Groq, NVIDIA NIM) and a mock."""

from .base import ChatMessage, LLMProvider, LLMReply, LLMUsage, ResponseFormat, ToolCall, ToolSpec
from .factory import describe_llm, get_provider

__all__ = [
    "ChatMessage",
    "LLMProvider",
    "LLMReply",
    "LLMUsage",
    "ResponseFormat",
    "ToolCall",
    "ToolSpec",
    "describe_llm",
    "get_provider",
]

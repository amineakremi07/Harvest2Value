"""Generic response shapes."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


# OpenAPI `responses=` of a route (FastAPI expects str | int keys).
Responses = dict[int | str, dict[str, Any]]

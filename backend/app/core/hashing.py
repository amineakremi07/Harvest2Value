"""Stable hashing of JSON-like data, used to fingerprint datasets and run configurations."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def _normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    # bool is an int subclass: keep it as-is before the float check.
    if isinstance(value, float) and value.is_integer():
        return int(value)  # 5000 and 5000.0 must hash identically
    return value


def canonical_json(value: Any) -> str:
    """Key-order independent JSON. Raises ValueError on NaN/Infinity, which have no JSON form."""
    return json.dumps(
        _normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_of(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

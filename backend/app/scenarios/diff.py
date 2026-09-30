"""Field-level diff between the base and the effective payload of a scenario."""

from __future__ import annotations

from typing import Any

from ..domain.diff import FieldDiff, payload_diff


def scenario_diff(base: dict[str, Any], effective: dict[str, Any]) -> list[FieldDiff]:
    """Same matching rules as dataset version diffs: entities by id, routes by buyer_id."""
    return payload_diff(base, effective)

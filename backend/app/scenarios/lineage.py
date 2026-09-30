"""Scenario lineage: a child applies its ancestors' changes first (root -> ... -> scenario)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

from ..core.errors import ValidationFailed

MAX_DEPTH = 20


class HasParent(Protocol):
    id: str
    parent_id: str | None


S = TypeVar("S", bound=HasParent)


def resolve_chain(scenario: S, get_parent: Callable[[str], S | None]) -> list[S]:
    """[root, ..., scenario]. Rejects cycles and chains deeper than MAX_DEPTH."""
    chain = [scenario]
    seen = {scenario.id}
    current = scenario
    while current.parent_id is not None:
        parent = get_parent(current.parent_id)
        if parent is None:
            break  # parent deleted: the chain starts here
        if parent.id in seen:
            raise ValidationFailed("Scenario lineage contains a cycle.", code="SCENARIO_LINEAGE_ERROR")
        if len(chain) >= MAX_DEPTH:
            raise ValidationFailed(f"Scenario lineage is deeper than {MAX_DEPTH}.", code="SCENARIO_LINEAGE_ERROR")
        chain.append(parent)
        seen.add(parent.id)
        current = parent
    chain.reverse()
    return chain

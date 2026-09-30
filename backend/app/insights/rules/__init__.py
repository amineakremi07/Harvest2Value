"""The 12 insight rules of plan §16, one module per family."""

from __future__ import annotations

from ..base import InsightRule
from . import buyers, concentration, logistics, shelf_life, storage, waste

ALL_RULES: list[InsightRule] = [
    *waste.RULES,
    *shelf_life.RULES,
    *storage.RULES,
    *buyers.RULES,
    *logistics.RULES,
    *concentration.RULES,
]
RULES_BY_ID: dict[str, InsightRule] = {rule.id: rule for rule in ALL_RULES}

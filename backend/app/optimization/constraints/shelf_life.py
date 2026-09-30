"""Shelf life. Sales after a lot's last shelf-life day are impossible by construction (no
variable exists); what is still in stock at the end of that day is recorded as expired.
When the shelf life extends past the horizon, the remaining stock is ending inventory instead."""

from __future__ import annotations

from pulp import LpProblem

from ..instance import ProblemInstance
from ..keys import ConstraintKey, ConstraintRegistry
from ..variables import VarSet


def add(problem: LpProblem, inst: ProblemInstance, v: VarSet, registry: ConstraintRegistry) -> None:
    for (lot_id, facility_id), expired in v.expired.items():
        last = inst.last_day[(lot_id, facility_id)]
        registry.add(
            problem,
            ConstraintKey("shelf_life", (lot_id, facility_id)),
            expired == v.inv[(lot_id, facility_id, last)],
        )

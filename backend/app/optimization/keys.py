"""Business identity of every constraint: `family|entity|day` plus a readable label.

PuLP names are opaque (`c0`, `c1`, ...) so ids with any characters never collide; the
registry maps them back to ConstraintKeys for post-processing and explainability.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from pulp import LpConstraint, LpProblem

# family -> (entity roles, label template, reported in results)
FAMILIES: dict[str, tuple[tuple[str, ...], str, bool]] = {
    "lot_split": (("lot",), "Split of lot {lot} between direct sale and storage", False),
    "direct_sale": (("lot",), "Harvest-day sale of lot {lot}", False),
    "balance": (("lot", "facility"), "Stock of lot {lot} in {facility}", False),
    "shelf_life": (("lot", "facility"), "Shelf life of lot {lot} in {facility}", False),
    "storage_capacity": (("facility",), "Capacity of {facility}", True),
    "demand_max": (("buyer",), "Maximum demand of {buyer}", True),
    "demand_day": (("buyer",), "Daily demand limit of {buyer}", True),
    "demand_min": (("buyer",), "Contracted minimum of {buyer}", True),
    "moq_min": (("buyer",), "Minimum order of {buyer}", True),
    "trip_capacity": (("buyer",), "Truck capacity sent to {buyer}", True),
    "fleet_time": (("vehicle",), "Driving hours of the {vehicle} fleet", True),
    "fleet_trips": (("vehicle",), "Trips per day of the {vehicle} fleet", True),
    "trip_duration": (("buyer", "vehicle"), "Round trip to {buyer} is too long for {vehicle}", True),
    "cold_chain_vehicle": (("buyer", "vehicle"), "Cold chain: {vehicle} cannot deliver to {buyer}", True),
    "cold_chain_storage": (("facility",), "Cold chain: {facility} is not refrigerated", True),
    "service_level": ((), "Minimum share of the harvest to sell", True),
    "min_profit": ((), "Minimum realized profit", True),
}

SENSES = {-1: "<=", 1: ">=", 0: "=="}


@dataclass(frozen=True)
class ConstraintKey:
    family: str
    entity: tuple[str, ...] = ()
    day: int | None = None

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"Unknown constraint family '{self.family}'")

    def __str__(self) -> str:
        return f"{self.family}|{','.join(self.entity)}|{'' if self.day is None else self.day}"

    @property
    def reportable(self) -> bool:
        return FAMILIES[self.family][2]

    def label(self, name_of: Callable[[str], str] = str) -> str:
        roles, template, _ = FAMILIES[self.family]
        text = template.format(**{role: name_of(value) for role, value in zip(roles, self.entity, strict=True)})
        return f"{text} (day {self.day})" if self.day is not None else text


@dataclass
class RegisteredConstraint:
    name: str
    key: ConstraintKey
    constraint: LpConstraint

    @property
    def sense(self) -> str:
        return SENSES[self.constraint.sense]


@dataclass
class ConstraintRegistry:
    items: dict[str, RegisteredConstraint] = field(default_factory=dict)
    by_key: dict[ConstraintKey, RegisteredConstraint] = field(default_factory=dict)
    # A constraint without variables that can never hold (e.g. a contract minimum for a buyer
    # nobody can reach): the model is infeasible without calling the solver.
    trivially_infeasible: list[ConstraintKey] = field(default_factory=list)
    # How far each of those constraints is from holding (used by infeasibility diagnostics).
    trivial_violations: dict[ConstraintKey, float] = field(default_factory=dict)

    def add(self, problem: LpProblem, key: ConstraintKey, constraint: LpConstraint) -> RegisteredConstraint | None:
        if key in self.by_key:
            raise ValueError(f"Duplicate constraint key {key}")
        if len(constraint) == 0:  # no variables left: check the constant instead of sending it to CBC
            if not _constant_holds(constraint):
                self.trivially_infeasible.append(key)
                self.trivial_violations[key] = abs(constraint.constant)
            return None
        name = f"c{len(self.items)}"
        problem += constraint, name
        registered = RegisteredConstraint(name, key, constraint)
        self.items[name] = registered
        self.by_key[key] = registered
        return registered

    def __iter__(self) -> Iterator[RegisteredConstraint]:
        return iter(self.items.values())

    def families(self) -> set[str]:
        return {r.key.family for r in self}


def _constant_holds(constraint: LpConstraint, tol: float = 1e-9) -> bool:
    # PuLP stores `lhs (sense) rhs` as `lhs - rhs (sense) 0`; with no variables only the constant remains.
    value = constraint.constant
    return {-1: value <= tol, 1: value >= -tol, 0: abs(value) <= tol}[constraint.sense]

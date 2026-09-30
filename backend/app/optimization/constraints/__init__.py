"""Constraint modules. Each exposes `add(problem, inst, vars, registry)` and names every
constraint with a ConstraintKey (family|entity|day)."""

from typing import Protocol

from pulp import LpProblem

from ..instance import ProblemInstance
from ..keys import ConstraintRegistry
from ..variables import VarSet


class ConstraintModule(Protocol):
    def __call__(self, problem: LpProblem, inst: ProblemInstance, v: VarSet, registry: ConstraintRegistry) -> None: ...

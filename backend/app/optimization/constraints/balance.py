"""Mass balance of every lot.

- lot_split:   each lot is placed either "direct" (sold on its harvest day) or in a facility;
- direct_sale: what is placed direct and not sold on the harvest day is lost that day;
- balance:     in a facility, end-of-day stock = previous stock x (1 - daily loss) - sales
               (on the harvest day the stock is what was placed; storage sales start the next day).
"""

from __future__ import annotations

from pulp import LpProblem, lpSum

from ..instance import DIRECT, ProblemInstance
from ..keys import ConstraintKey, ConstraintRegistry
from ..variables import VarSet


def add(problem: LpProblem, inst: ProblemInstance, v: VarSet, registry: ConstraintRegistry) -> None:
    for lot in inst.lots:
        placed = [v.z[(lot.id, DIRECT)], *(v.z[(lot.id, f.id)] for f in inst.facilities)]
        registry.add(problem, ConstraintKey("lot_split", (lot.id,)), lpSum(placed) == lot.quantity)

        direct_sales = v.sales_by_stock_day.get((lot.id, DIRECT, lot.day), [])
        registry.add(
            problem,
            ConstraintKey("direct_sale", (lot.id,)),
            v.unsold[lot.id] == v.z[(lot.id, DIRECT)] - lpSum(direct_sales),
        )

        for f in inst.facilities:
            keep = 1.0 - f.loss_rate
            for t in range(lot.day, inst.last_day[(lot.id, f.id)] + 1):
                stock = v.inv[(lot.id, f.id, t)]
                if t == lot.day:
                    rhs = v.z[(lot.id, f.id)]
                else:
                    sales = v.sales_by_stock_day.get((lot.id, f.id, t), [])
                    rhs = keep * v.inv[(lot.id, f.id, t - 1)] - lpSum(sales)
                registry.add(problem, ConstraintKey("balance", (lot.id, f.id), t), stock == rhs)

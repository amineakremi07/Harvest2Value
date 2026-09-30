"""Binding constraints, bottlenecks and the scenario change that relaxes each of them."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ..analytics.context import RunContext
from ..domain.explanation import Bottleneck
from ..domain.results import ConstraintInfo

# Always binding by construction (a forbidden combination is `<= 0`): shown, never ranked.
STRUCTURAL = frozenset({"cold_chain_vehicle", "cold_chain_storage", "trip_duration"})
# Binding whenever trucks leave full: a symptom of the fleet or demand limits, not a cause.
NOT_BOTTLENECK = STRUCTURAL | {"trip_capacity"}


def really_binding(c: ConstraintInfo, ctx: RunContext) -> bool:
    """With a served-buyer binary y, `sold <= max x y` and `sold >= MOQ x y` read 0 = 0 when the
    buyer is not served: tight on paper, but no limit was reached."""
    if not c.binding:
        return False
    if c.family in ("demand_max", "moq_min") and c.entity:
        buyer = ctx.buyers.get(c.entity[0])
        if buyer is None:
            return True
        if c.family == "moq_min":
            return buyer.sold_kg > 0
        return buyer.sold_kg >= buyer.max_demand_kg * (1 - 1e-6) - 1e-3
    return True


def binding_constraints(ctx: RunContext) -> list[ConstraintInfo]:
    return [c for c in ctx.result.constraints if really_binding(c, ctx)]


def group_key(c: ConstraintInfo) -> str:
    return f"{c.family}|{','.join(c.entity)}|"


@dataclass(frozen=True)
class Relaxation:
    label: str
    change: dict[str, Any]


def relaxation_for(family: str, entity: list[str], ctx: RunContext) -> Relaxation | None:
    """The concrete scenario change a probe applies to relax a bottleneck (plan §15, method 2)."""
    target = entity[0] if entity else None
    name = ctx.name_of(target) if target else ""
    if family == "storage_capacity" and target:
        return Relaxation(
            f"+1 000 kg of capacity at {name}",
            {"op": "storage_capacity", "target": target, "params": {"mode": "delta", "value": 1000}},
        )
    if family == "demand_max" and target:
        return Relaxation(
            f"+10 % maximum demand at {name}",
            {"op": "buyer_demand", "target": target, "params": {"field": "max_demand_kg", "mode": "relative_pct", "value": 10}},
        )
    if family == "demand_day" and target:
        return Relaxation(
            f"+10 % daily demand limit at {name}",
            {"op": "buyer_demand", "target": target, "params": {"field": "max_per_day_kg", "mode": "relative_pct", "value": 10}},
        )
    if family in ("fleet_time", "fleet_trips") and target:
        return Relaxation(
            f"+1 vehicle of type {name}",
            {"op": "vehicle_count", "target": target, "params": {"mode": "delta", "value": 1}},
        )
    if family == "demand_min" and target:
        return Relaxation(
            f"-10 % contracted minimum at {name}",
            {"op": "buyer_demand", "target": target, "params": {"field": "min_contract_kg", "mode": "relative_pct", "value": -10}},
        )
    return None


def shelf_life_relaxation(ctx: RunContext) -> Relaxation | None:
    """+1 day of shelf life when stock expired (shelf life is an equality, not a reported constraint)."""
    if ctx.waste_by_kind.get("expired", 0.0) <= 0:
        return None
    crop = ctx.payload.crop(ctx.result.crop_id)
    return Relaxation(
        f"+1 day of ambient shelf life for {crop.name}",
        {"op": "shelf_life", "target": crop.id, "params": {"field": "ambient", "mode": "delta", "value": 1}},
    )


def bottlenecks(ctx: RunContext) -> list[Bottleneck]:
    """Binding constraints grouped by (family, entity) over days, ranked by probe gain, then by
    the largest reliable dual, then by the number of binding days."""
    groups: dict[str, list[ConstraintInfo]] = defaultdict(list)
    for c in ctx.result.constraints:
        if c.family not in NOT_BOTTLENECK and really_binding(c, ctx):
            groups[group_key(c)].append(c)

    probes = {p.constraint_key: p for p in (ctx.sensitivity.probes if ctx.sensitivity else []) if p.constraint_key and p.significant}
    items: list[Bottleneck] = []
    for key, rows in groups.items():
        first = rows[0]
        reliable = [c.dual for c in rows if c.dual is not None and c.dual_reliable]
        dual = max(reliable, key=abs) if reliable else None
        probe = probes.get(key)
        relaxation = relaxation_for(first.family, first.entity, ctx)
        label = first.label.split(" (day ")[0]
        items.append(
            Bottleneck(
                key=key,
                family=first.family,
                entity=first.entity,
                label=label,
                binding_days=sorted({c.day for c in rows}, key=lambda d: -1 if d is None else d),
                dual=dual,
                probe_gain=probe.delta_objective if probe else None,
                suggested_change=relaxation.change if relaxation else None,
                suggested_label=relaxation.label if relaxation else None,
            )
        )

    def score(b: Bottleneck) -> tuple[float, float, int]:
        return (
            -(b.probe_gain if b.probe_gain is not None else float("-inf")),
            -(abs(b.dual) if b.dual is not None else -1.0),
            -len(b.binding_days),
        )

    items.sort(key=lambda b: (*score(b), b.key))
    for rank, b in enumerate(items, start=1):
        b.rank = rank
    return items

"""ExplanationBuilder: decision cards for buyers, storage and losses, binding constraints,
ranked bottlenecks and trade-offs. Deterministic: every number comes from the run."""

from __future__ import annotations

from ..analytics.context import RunContext
from ..domain.explanation import DecisionCard, LimitingFactor, MarginalValue, RunExplanation
from ..domain.results import ProbeResult
from .alternatives import best_alternative, tradeoffs
from .binding import binding_constraints, bottlenecks
from .limiting import limiting_factor


def _probe_values(probes: list[ProbeResult], match: str) -> list[MarginalValue]:
    return [
        MarginalValue(kind="probe", label=p.label, delta_objective=p.delta_objective, change=p.change, reliable=p.significant)
        for p in probes
        if p.delta_objective is not None and p.constraint_key is not None and p.constraint_key.startswith(match)
    ]


class ExplanationBuilder:
    def build(self, ctx: RunContext) -> RunExplanation:
        probes = ctx.sensitivity.probes if ctx.sensitivity else []
        cards = [*self._buyer_cards(ctx, probes), *self._storage_cards(ctx, probes), self._waste_card(ctx, probes)]
        return RunExplanation(
            run_id=ctx.run_id,
            decisions=cards,
            binding=binding_constraints(ctx),
            bottlenecks=bottlenecks(ctx),
            tradeoffs=tradeoffs(ctx),
            sensitivity_computed=bool(ctx.sensitivity and ctx.sensitivity.probes_computed),
        )

    def _buyer_cards(self, ctx: RunContext, probes: list[ProbeResult]) -> list[DecisionCard]:
        cards = []
        for b in sorted(ctx.result.buyers, key=lambda b: (-b.sold_kg, b.buyer_id)):
            market = ctx.market_rows.get(b.buyer_id)
            values = [
                *_probe_values(probes, f"demand_max|{b.buyer_id}|"),
                *_probe_values(probes, f"demand_day|{b.buyer_id}|"),
                *_probe_values(probes, f"demand_min|{b.buyer_id}|"),
            ]
            for c in ctx.result.constraints:
                if c.family in ("demand_max", "demand_day") and c.entity[:1] == [b.buyer_id] and c.dual and c.dual_reliable:
                    values.append(
                        MarginalValue(kind="dual", label=f"+1 kg: {c.label}", delta_objective=c.dual, reliable=True)
                    )
            cards.append(
                DecisionCard(
                    kind="buyer",
                    entity_id=b.buyer_id,
                    name=b.buyer_name,
                    decision=f"{b.sold_kg:,.0f} kg allocated" if b.sold_kg > 0 else "Not served",
                    metrics={
                        "sold_kg": b.sold_kg,
                        "max_demand_kg": b.max_demand_kg,
                        "remaining_demand_kg": round(max(0.0, b.max_demand_kg - b.sold_kg), 2),
                        "fulfillment_pct": b.fulfillment_pct,
                        "revenue": b.revenue,
                        "transport_cost": b.transport_cost,
                        "net_price_per_kg": b.net_price_per_kg,
                        "estimated_net_price_per_kg": market.net_price_per_kg if market else None,
                        "market_rank": market.rank if market else None,
                    },
                    limiting_factor=limiting_factor(ctx, b.buyer_id),
                    marginal_values=values,
                    alternative=best_alternative(ctx, b.buyer_id),
                )
            )
        return cards

    def _storage_cards(self, ctx: RunContext, probes: list[ProbeResult]) -> list[DecisionCard]:
        cards = []
        for usage in ctx.facility_usage:
            binding = ctx.binding("storage_capacity", usage.facility_id)
            limiting = None
            if binding:
                limiting = LimitingFactor(
                    code="STORAGE_CAP",
                    message=f"{usage.name} was full on {len(binding)} day(s).",
                    evidence={"full_days": [c.day for c in binding], "capacity_kg": usage.capacity_kg},
                    constraint_keys=[c.key for c in binding],
                )
            values = _probe_values(probes, f"storage_capacity|{usage.facility_id}|")
            values += [
                MarginalValue(kind="dual", label=f"+1 kg: {c.label}", delta_objective=c.dual, reliable=True)
                for c in binding
                if c.dual and c.dual_reliable
            ]
            cards.append(
                DecisionCard(
                    kind="storage",
                    entity_id=usage.facility_id,
                    name=usage.name,
                    decision=f"{usage.stored_kg:,.0f} kg stored" if usage.stored_kg > 0 else "Not used",
                    metrics={
                        "stored_kg": usage.stored_kg,
                        "capacity_kg": usage.capacity_kg,
                        "peak_pct": usage.peak_pct,
                        "avg_pct": usage.avg_pct,
                        "cost": usage.cost,
                        "usable": "yes" if usage.usable else "no (not refrigerated)",
                    },
                    limiting_factor=limiting,
                    marginal_values=values,
                )
            )
        return cards

    def _waste_card(self, ctx: RunContext, probes: list[ProbeResult]) -> DecisionCard:
        k = ctx.result.kpis
        values = [
            MarginalValue(kind="probe", label=p.label, delta_objective=p.delta_objective, change=p.change, reliable=p.significant)
            for p in probes
            if p.delta_objective is not None and p.change.get("op") == "shelf_life"
        ]
        return DecisionCard(
            kind="waste",
            entity_id="waste",
            name="Losses",
            decision=f"{k.lost_kg:,.0f} kg lost ({k.waste_rate_pct:.1f} % of the harvest)" if k.lost_kg > 0 else "No losses",
            metrics={
                "lost_kg": k.lost_kg,
                "waste_rate_pct": k.waste_rate_pct,
                "lost_value": k.lost_value,
                **{f"{kind}_kg": kg for kind, kg in sorted(ctx.waste_by_kind.items())},
            },
            marginal_values=values,
        )

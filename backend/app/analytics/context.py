"""Everything the deterministic layers (analytics, explain, insights) read about one succeeded run."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property

from ..domain.dataset import DatasetPayload
from ..domain.results import BuyerSummary, ConstraintInfo, OptimizationResultModel, SensitivityReport
from ..domain.run_config import RunConfig
from ..optimization.instance import ProblemInstance, build_instance
from .market import MarketAnalysis, MarketRow, analyze_market


@dataclass(frozen=True)
class FacilityUsage:
    facility_id: str
    name: str
    capacity_kg: float
    usable: bool
    stored_kg: float  # kg placed in the facility (sum over lots)
    peak_kg: float
    peak_pct: float | None
    avg_pct: float | None
    full_days: list[int]
    cost: float


@dataclass
class RunContext:
    run_id: str
    payload: DatasetPayload
    config: RunConfig
    result: OptimizationResultModel
    instance: ProblemInstance
    market: MarketAnalysis
    sensitivity: SensitivityReport | None = None

    @classmethod
    def build(
        cls,
        run_id: str,
        payload: DatasetPayload,
        config: RunConfig,
        result: OptimizationResultModel,
        sensitivity: SensitivityReport | None = None,
    ) -> RunContext:
        return cls(
            run_id=run_id,
            payload=payload,
            config=config,
            result=result,
            instance=build_instance(payload, config),
            market=analyze_market(payload, result.crop_id),
            sensitivity=sensitivity,
        )

    # ---- lookups ----

    @cached_property
    def buyers(self) -> dict[str, BuyerSummary]:
        return {b.buyer_id: b for b in self.result.buyers}

    @cached_property
    def market_rows(self) -> dict[str, MarketRow]:
        return {r.buyer_id: r for r in self.market.rows}

    @cached_property
    def binding_by_family(self) -> dict[str, list[ConstraintInfo]]:
        grouped: dict[str, list[ConstraintInfo]] = defaultdict(list)
        for c in self.result.constraints:
            if c.binding:
                grouped[c.family].append(c)
        return grouped

    def binding(self, family: str, entity: str | None = None) -> list[ConstraintInfo]:
        rows = self.binding_by_family.get(family, [])
        return [c for c in rows if entity is None or (c.entity and c.entity[0] == entity)]

    @cached_property
    def waste_by_kind(self) -> dict[str, float]:
        totals: dict[str, float] = defaultdict(float)
        for w in self.result.waste:
            totals[w.kind] += w.kg
        return {k: round(v, 2) for k, v in totals.items()}

    @cached_property
    def stored_by_facility(self) -> dict[str, float]:
        """kg placed in each facility: stock at the end of each lot's harvest day."""
        lots = {lot.id: lot.day for lot in self.instance.lots}
        placed: dict[str, float] = defaultdict(float)
        for row in self.result.inventory:
            if row.day == lots.get(row.lot_id):
                placed[row.facility_id] += row.kg_end
        return placed

    @cached_property
    def facility_usage(self) -> list[FacilityUsage]:
        stock: dict[tuple[str, int], float] = defaultdict(float)
        cost: dict[str, float] = defaultdict(float)
        for row in self.result.inventory:
            stock[(row.facility_id, row.day)] += row.kg_end
            cost[row.facility_id] += row.cost
        usage = []
        for f in self.instance.facilities:
            daily = [stock.get((f.id, t), 0.0) for t in range(self.instance.horizon)]
            peak = max(daily, default=0.0)
            usage.append(
                FacilityUsage(
                    facility_id=f.id,
                    name=f.name,
                    capacity_kg=f.capacity,
                    usable=f.usable,
                    stored_kg=round(self.stored_by_facility.get(f.id, 0.0), 2),
                    peak_kg=round(peak, 2),
                    peak_pct=round(100 * peak / f.capacity, 2) if f.capacity > 0 else None,
                    avg_pct=round(100 * sum(daily) / (len(daily) * f.capacity), 2) if f.capacity > 0 and daily else None,
                    full_days=[t for t, kg in enumerate(daily) if f.capacity > 0 and kg >= f.capacity * (1 - 1e-6) - 1e-4],
                    cost=round(cost.get(f.id, 0.0), 2),
                )
            )
        return usage

    @cached_property
    def sold_by_day(self) -> dict[int, float]:
        totals: dict[int, float] = defaultdict(float)
        for a in self.result.allocations:
            totals[a.day] += a.kg
        return totals

    @cached_property
    def stock_by_day(self) -> dict[int, float]:
        totals: dict[int, float] = defaultdict(float)
        for row in self.result.inventory:
            totals[row.day] += row.kg_end
        return totals

    @cached_property
    def lost_by_day(self) -> dict[int, float]:
        totals: dict[int, float] = defaultdict(float)
        for w in self.result.waste:
            totals[w.day] += w.kg
        return totals

    def name_of(self, entity_id: str) -> str:
        return self.instance.name_of(entity_id)

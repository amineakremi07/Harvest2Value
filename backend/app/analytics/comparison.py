"""compare(baseline, runs) -> ComparisonResult: KPI table with deltas, buyer matrix (buyers added or
removed by scenarios included), daily series and rule-based notable changes. All numbers are
computed here from stored results; nothing is estimated."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from ..domain.comparison import (
    BuyerCell,
    BuyerRow,
    ComparisonResult,
    Delta,
    KpiRow,
    NotableChange,
    RunRef,
    SeriesPoint,
)
from ..domain.dataset import DatasetPayload
from ..domain.results import OptimizationResultModel

Better = Literal["higher", "lower", "neutral"]

KPI_SPECS: tuple[tuple[str, str, str, Better], ...] = (
    ("realized_profit", "Realized profit", "currency", "higher"),
    ("realized_revenue", "Realized revenue", "currency", "higher"),
    ("total_cost", "Total cost", "currency", "lower"),
    ("transport_cost", "Transport cost", "currency", "lower"),
    ("storage_cost", "Storage cost", "currency", "lower"),
    ("disposal_cost", "Disposal cost", "currency", "lower"),
    ("margin_pct", "Margin", "%", "higher"),
    ("economic_value", "Economic value (profit + ending stock value)", "currency", "higher"),
    ("sold_kg", "Sold", "kg", "higher"),
    ("lost_kg", "Lost", "kg", "lower"),
    ("waste_rate_pct", "Waste rate", "%", "lower"),
    ("ending_inventory_kg", "Ending inventory", "kg", "neutral"),
    ("storage_rate_pct", "Share stored", "%", "neutral"),
    ("fulfillment_rate_pct", "Demand fulfillment", "%", "higher"),
    ("trips", "Trips", "trips", "lower"),
    ("vehicle_utilization_pct", "Vehicle utilization", "%", "neutral"),
    ("storage_utilization_peak_pct", "Peak storage utilization", "%", "neutral"),
    ("avg_transport_cost_per_kg", "Transport cost per kg", "currency/kg", "lower"),
)

BUYER_KG_MIN = 500.0  # notable if a buyer's volume moves by at least this many kg ...
BUYER_SHARE_MIN = 0.10  # ... or by 10 % of the baseline sold kg, whichever is larger
WASTE_PP_MIN = 2.0  # waste rate change in percentage points
PROFIT_PCT_MIN = 1.0


@dataclass(frozen=True)
class ComparedRun:
    run_id: str
    label: str | None
    scenario_id: str | None
    result: OptimizationResultModel
    payload: DatasetPayload


def _delta(value: float | None, base: float | None) -> Delta:
    if value is None or base is None:
        return Delta(abs=None, pct=None)
    return Delta(abs=round(value - base, 4), pct=round(100 * (value - base) / abs(base), 2) if base != 0 else None)


def _best(values: dict[str, float | None], better: Better) -> str | None:
    known = {k: v for k, v in values.items() if v is not None}
    if better == "neutral" or not known or len(set(known.values())) == 1:
        return None
    best_value = max(known.values()) if better == "higher" else min(known.values())
    winners = [k for k, v in known.items() if v == best_value]
    return winners[0] if len(winners) == 1 else None  # a tie names no winner


def _kpi_table(baseline: ComparedRun, runs: list[ComparedRun]) -> list[KpiRow]:
    rows = []
    for kpi, label, unit, better in KPI_SPECS:
        values: dict[str, float | None] = {r.run_id: getattr(r.result.kpis, kpi) for r in [baseline, *runs]}
        base = values[baseline.run_id]
        rows.append(
            KpiRow(
                kpi=kpi,
                label=label,
                unit=unit,
                better=better,
                values=values,
                deltas={r.run_id: _delta(values[r.run_id], base) for r in runs},
                best_run_id=_best(values, better),
            )
        )
    return rows


def _buyer_matrix(baseline: ComparedRun, runs: list[ComparedRun]) -> list[BuyerRow]:
    names: dict[str, str] = {}
    present: dict[str, set[str]] = {}
    sold: dict[str, dict[str, float]] = {}
    for r in [baseline, *runs]:
        present[r.run_id] = {b.id for b in r.payload.buyers if r.result.crop_id in b.crop_ids}
        names.update({b.id: b.name for b in r.payload.buyers})
        sold[r.run_id] = {b.buyer_id: b.sold_kg for b in r.result.buyers}

    base_ids = present[baseline.run_id]
    rows = []
    for buyer_id in sorted(set().union(*present.values()), key=lambda b: (b not in base_ids, b)):
        cells = {}
        base_kg = sold[baseline.run_id].get(buyer_id) if buyer_id in base_ids else None
        for r in [baseline, *runs]:
            here = buyer_id in present[r.run_id]
            kg = sold[r.run_id].get(buyer_id, 0.0) if here else None
            if r is baseline:
                status = "common" if here else "absent"
            elif here and buyer_id not in base_ids:
                status = "added"
            elif not here and buyer_id in base_ids:
                status = "removed"
            else:
                status = "common" if here else "absent"
            cells[r.run_id] = BuyerCell(
                status=status,
                sold_kg=kg,
                delta_kg=None if r is baseline else round((kg or 0.0) - (base_kg or 0.0), 2),
            )
        rows.append(BuyerRow(buyer_id=buyer_id, buyer_name=names[buyer_id], cells=cells))
    return rows


def _series(baseline: ComparedRun, runs: list[ComparedRun]) -> dict[str, list[SeriesPoint]]:
    sold: dict[int, dict[str, float]] = defaultdict(dict)
    stock: dict[int, dict[str, float]] = defaultdict(dict)
    horizon = max(r.result.horizon_days for r in [baseline, *runs])
    for r in [baseline, *runs]:
        per_day_sold: dict[int, float] = defaultdict(float)
        per_day_stock: dict[int, float] = defaultdict(float)
        for a in r.result.allocations:
            per_day_sold[a.day] += a.kg
        for i in r.result.inventory:
            per_day_stock[i.day] += i.kg_end
        for t in range(horizon):
            sold[t][r.run_id] = round(per_day_sold.get(t, 0.0), 2)
            stock[t][r.run_id] = round(per_day_stock.get(t, 0.0), 2)
    return {
        "sold_kg_by_day": [SeriesPoint(day=t, values=sold[t]) for t in range(horizon)],
        "stock_kg_by_day": [SeriesPoint(day=t, values=stock[t]) for t in range(horizon)],
    }


def _notable(baseline: ComparedRun, runs: list[ComparedRun], matrix: list[BuyerRow]) -> list[NotableChange]:
    base_k = baseline.result.kpis
    threshold_kg = max(BUYER_KG_MIN, BUYER_SHARE_MIN * base_k.sold_kg)
    changes: list[NotableChange] = []
    for r in runs:
        k = r.result.kpis
        profit_delta = k.realized_profit - base_k.realized_profit
        pct = 100 * profit_delta / abs(base_k.realized_profit) if base_k.realized_profit else None
        if abs(profit_delta) > 0 and (pct is None or abs(pct) >= PROFIT_PCT_MIN):
            direction = "rises" if profit_delta > 0 else "falls"
            changes.append(
                NotableChange(
                    code="PROFIT_CHANGE",
                    run_id=r.run_id,
                    message=f"Realized profit {direction} by {abs(profit_delta):,.2f}"
                    + (f" ({pct:+.1f} %)" if pct is not None else "")
                    + f": {k.realized_profit:,.2f} (was {base_k.realized_profit:,.2f}).",
                    params={"delta": round(profit_delta, 2), "pct": None if pct is None else round(pct, 2), "was": base_k.realized_profit, "now": k.realized_profit},
                    magnitude=abs(profit_delta),
                )
            )
        waste_pp = k.waste_rate_pct - base_k.waste_rate_pct
        if abs(waste_pp) >= WASTE_PP_MIN:
            changes.append(
                NotableChange(
                    code="WASTE_CHANGE",
                    run_id=r.run_id,
                    message=f"Waste rate {'rises' if waste_pp > 0 else 'falls'} to {k.waste_rate_pct:.1f} % (was {base_k.waste_rate_pct:.1f} %).",
                    params={"delta_pp": round(waste_pp, 2), "was": base_k.waste_rate_pct, "now": k.waste_rate_pct},
                    magnitude=abs(waste_pp),
                )
            )
        for row in matrix:
            cell = row.cells[r.run_id]
            base_cell = row.cells[baseline.run_id]
            if cell.status == "added":
                changes.append(
                    NotableChange(
                        code="BUYER_ADDED",
                        run_id=r.run_id,
                        message=f"New buyer {row.buyer_name} receives {cell.sold_kg or 0:,.0f} kg.",
                        params={"buyer_id": row.buyer_id, "sold_kg": cell.sold_kg},
                        magnitude=cell.sold_kg or 0.0,
                    )
                )
            elif cell.status == "removed":
                changes.append(
                    NotableChange(
                        code="BUYER_REMOVED",
                        run_id=r.run_id,
                        message=f"Buyer {row.buyer_name} is removed (it received {base_cell.sold_kg or 0:,.0f} kg).",
                        params={"buyer_id": row.buyer_id, "was_kg": base_cell.sold_kg},
                        magnitude=base_cell.sold_kg or 0.0,
                    )
                )
            elif cell.status == "common" and cell.delta_kg is not None and abs(cell.delta_kg) >= threshold_kg:
                verb = "gets" if cell.delta_kg > 0 else "loses"
                changes.append(
                    NotableChange(
                        code="BUYER_VOLUME_CHANGE",
                        run_id=r.run_id,
                        message=f"{row.buyer_name} {verb} {abs(cell.delta_kg):,.0f} kg: {cell.sold_kg or 0:,.0f} kg (was {base_cell.sold_kg or 0:,.0f} kg).",
                        params={"buyer_id": row.buyer_id, "delta_kg": cell.delta_kg, "was_kg": base_cell.sold_kg, "now_kg": cell.sold_kg},
                        magnitude=abs(cell.delta_kg),
                    )
                )
        storage_delta = k.storage_rate_pct - base_k.storage_rate_pct
        if abs(storage_delta) >= WASTE_PP_MIN:
            changes.append(
                NotableChange(
                    code="STORAGE_USE_CHANGE",
                    run_id=r.run_id,
                    message=f"Share of the harvest stored {'rises' if storage_delta > 0 else 'falls'} to {k.storage_rate_pct:.1f} % (was {base_k.storage_rate_pct:.1f} %).",
                    params={"delta_pp": round(storage_delta, 2), "was": base_k.storage_rate_pct, "now": k.storage_rate_pct},
                    magnitude=abs(storage_delta),
                )
            )
        if k.trips != base_k.trips:
            changes.append(
                NotableChange(
                    code="TRIPS_CHANGE",
                    run_id=r.run_id,
                    message=f"{k.trips} trips instead of {base_k.trips}.",
                    params={"was": base_k.trips, "now": k.trips},
                    magnitude=abs(k.trips - base_k.trips),
                )
            )
    order = {"PROFIT_CHANGE": 0, "BUYER_ADDED": 1, "BUYER_REMOVED": 1, "BUYER_VOLUME_CHANGE": 2, "WASTE_CHANGE": 3, "STORAGE_USE_CHANGE": 4, "TRIPS_CHANGE": 5}
    return sorted(changes, key=lambda c: (order[c.code], -c.magnitude, c.run_id))


def compare(baseline: ComparedRun, runs: list[ComparedRun]) -> ComparisonResult:
    matrix = _buyer_matrix(baseline, runs)
    return ComparisonResult(
        baseline_run_id=baseline.run_id,
        run_ids=[r.run_id for r in runs],
        runs=[
            RunRef(run_id=r.run_id, label=r.label, scenario_id=r.scenario_id, objective=r.result.objective)
            for r in [baseline, *runs]
        ],
        crop_id=baseline.result.crop_id,
        kpi_table=_kpi_table(baseline, runs),
        buyer_matrix=matrix,
        series=_series(baseline, runs),
        notable_changes=_notable(baseline, runs, matrix),
    )

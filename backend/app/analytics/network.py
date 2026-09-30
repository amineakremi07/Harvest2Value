"""Supply-chain graph of a plan: producer -> lots -> storage (or direct sale) -> buyers, plus the
vehicles serving each buyer. Edge values are solver quantities; `day` restricts flows to one day."""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel

from ..optimization.instance import DIRECT
from .context import RunContext

NodeKind = Literal["producer", "lot", "storage", "direct", "vehicle", "buyer"]


class NetworkNode(BaseModel):
    id: str
    kind: NodeKind
    label: str
    metrics: dict[str, float | int | str | None]


class NetworkEdge(BaseModel):
    source: str
    target: str
    kind: Literal["harvest", "placement", "sale", "transport"]
    kg: float
    value: float | None = None
    trips: int | None = None


class NetworkGraph(BaseModel):
    run_id: str
    day: int | None
    nodes: list[NetworkNode]
    edges: list[NetworkEdge]


def _node_id(kind: str, entity: str) -> str:
    return f"{kind}:{entity}"


def network(ctx: RunContext, day: int | None = None) -> NetworkGraph:
    inst = ctx.instance
    producer = _node_id("producer", "farm")
    nodes = [NetworkNode(id=producer, kind="producer", label=ctx.payload.producer.name, metrics={"harvest_kg": ctx.result.kpis.harvest_kg})]
    edges: list[NetworkEdge] = []

    lots_by_day = {lot.id: lot.day for lot in inst.lots}
    for lot in inst.lots:
        if day is not None and lot.day != day:
            continue
        nodes.append(NetworkNode(id=_node_id("lot", lot.id), kind="lot", label=lot.id, metrics={"quantity_kg": lot.quantity, "day": lot.day}))
        edges.append(NetworkEdge(source=producer, target=_node_id("lot", lot.id), kind="harvest", kg=lot.quantity))

    usage = {u.facility_id: u for u in ctx.facility_usage}
    for f in inst.facilities:
        u = usage[f.id]
        nodes.append(
            NetworkNode(
                id=_node_id("storage", f.id),
                kind="storage",
                label=f.name,
                metrics={
                    "capacity_kg": f.capacity,
                    "refrigerated": "yes" if f.refrigerated else "no",
                    "peak_pct": u.peak_pct,
                    "stock_end_kg": round(sum(r.kg_end for r in ctx.result.inventory if r.facility_id == f.id and r.day == day), 2)
                    if day is not None
                    else u.peak_kg,
                },
            )
        )
    nodes.append(NetworkNode(id=_node_id("direct", DIRECT), kind="direct", label="Direct sale (harvest day)", metrics={}))

    placement: dict[tuple[str, str], float] = defaultdict(float)
    for row in ctx.result.inventory:
        if row.day == lots_by_day.get(row.lot_id) and (day is None or row.day == day):
            placement[(row.lot_id, row.facility_id)] += row.kg_end
    for (lot_id, facility_id), kg in sorted(placement.items()):
        edges.append(NetworkEdge(source=_node_id("lot", lot_id), target=_node_id("storage", facility_id), kind="placement", kg=round(kg, 2)))

    sales: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    direct: dict[tuple[str, str], float] = defaultdict(float)
    for a in ctx.result.allocations:
        if day is not None and a.day != day:
            continue
        origin = _node_id("storage", a.facility_id) if a.facility_id else _node_id("direct", DIRECT)
        sales[(origin, a.buyer_id)][0] += a.kg
        sales[(origin, a.buyer_id)][1] += a.revenue
        if a.facility_id is None:
            direct[(a.lot_id, DIRECT)] += a.kg
    for (lot_id, _), kg in sorted(direct.items()):
        edges.append(NetworkEdge(source=_node_id("lot", lot_id), target=_node_id("direct", DIRECT), kind="placement", kg=round(kg, 2)))
    for (origin, buyer_id), (kg, revenue) in sorted(sales.items()):
        edges.append(NetworkEdge(source=origin, target=_node_id("buyer", buyer_id), kind="sale", kg=round(kg, 2), value=round(revenue, 2)))

    transport: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0, 0.0, 0.0])
    for t in ctx.result.trips:
        if day is not None and t.day != day:
            continue
        entry = transport[(t.vehicle_type_id, t.buyer_id)]
        entry[0] += t.trips
        entry[1] += t.capacity_kg
        entry[2] += t.cost
    for v in inst.vehicles:
        nodes.append(
            NetworkNode(id=_node_id("vehicle", v.id), kind="vehicle", label=v.name, metrics={"count": v.count, "capacity_kg": v.capacity})
        )
    for (vehicle_id, buyer_id), (trips, capacity, cost) in sorted(transport.items()):
        edges.append(
            NetworkEdge(
                source=_node_id("vehicle", vehicle_id),
                target=_node_id("buyer", buyer_id),
                kind="transport",
                kg=round(capacity, 2),
                value=round(cost, 2),
                trips=int(trips),
            )
        )

    for b in ctx.result.buyers:
        nodes.append(
            NetworkNode(
                id=_node_id("buyer", b.buyer_id),
                kind="buyer",
                label=b.buyer_name,
                metrics={"sold_kg": b.sold_kg, "revenue": b.revenue, "fulfillment_pct": b.fulfillment_pct},
            )
        )
    return NetworkGraph(run_id=ctx.run_id, day=day, nodes=nodes, edges=edges)

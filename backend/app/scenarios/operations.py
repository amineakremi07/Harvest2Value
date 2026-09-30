"""Registry of scenario operations (plan §12).

Each operation has `validate(payload, change)` (raises ChangeError with a readable reason) and
`apply(payload, change) -> summary`, which mutates a working copy of the payload (a plain dict in
schema v2 shape). `apply_changes` re-validates the whole document after every change, so
cross-field rules (min <= max, references, unique ids) are enforced by `DatasetPayload` too.

Values leaving a field's bounds are rejected, never clamped.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..domain.enums import ChangeMode, RoadCondition
from ..domain.scenario import (
    ALL,
    AddBuyerChange,
    AddStorageChange,
    BuyerDemandChange,
    BuyerPriceChange,
    ColdChainChange,
    HarvestQuantityChange,
    HarvestTimingChange,
    RemoveBuyerChange,
    RemoveStorageChange,
    RouteChange,
    ShelfLifeChange,
    StorageCapacityChange,
    StorageCostChange,
    TransportCostChange,
    VehicleCapacityChange,
    VehicleCountChange,
    _Change,
)

Payload = dict[str, Any]


class ChangeError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def compute(old: float | None, mode: ChangeMode | str, value: float, *, field: str) -> float:
    """absolute: value; relative_pct: old x (1 + value/100); delta: old + value (rounded to 1e-6)."""
    mode = ChangeMode(mode)
    if mode == ChangeMode.ABSOLUTE:
        return round(float(value), 6)
    if old is None:
        raise ChangeError(f"{field} has no current value: use mode 'absolute'")
    if mode == ChangeMode.RELATIVE_PCT:
        return round(old * (1 + value / 100.0), 6)
    return round(old + value, 6)


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _check(value: float, *, field: str, minimum: float = 0.0, strict: bool = False, maximum: float | None = None) -> None:
    if strict and value <= minimum:
        raise ChangeError(f"{field} would become {_fmt(value)}; it must be > {_fmt(minimum)}")
    if not strict and value < minimum:
        raise ChangeError(f"{field} would become {_fmt(value)}; it must be >= {_fmt(minimum)}")
    if maximum is not None and value > maximum:
        raise ChangeError(f"{field} would become {_fmt(value)}; it must be <= {_fmt(maximum)}")


def _items(payload: Payload, collection: str, target: str | None, *, key: str = "id", label: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = payload[collection]
    if target == ALL:
        if not items:
            raise ChangeError(f"there is no {label} to change")
        return items
    for item in items:
        if item[key] == target:
            return [item]
    raise ChangeError(f"{label} '{target}' does not exist (it may have been removed by an earlier change)")


# ---------------------------------------------------------------- numeric field helper


def _numeric(
    payload: Payload,
    change: _Change,
    *,
    collection: str,
    field: str,
    label: str,
    mode: ChangeMode | str,
    value: float,
    minimum: float = 0.0,
    strict: bool = False,
    maximum: float | None = None,
    integer: bool = False,
    dry_run: bool,
) -> str:
    parts = []
    for item in _items(payload, collection, change.target, label=label):
        old = item.get(field)
        new = compute(old, mode, value, field=f"{label} '{item['id']}'.{field}")
        if integer:
            new = int(round(new))
        _check(new, field=f"{label} '{item['id']}'.{field}", minimum=minimum, strict=strict, maximum=maximum)
        if not dry_run:
            item[field] = new
        parts.append(f"{item['id']}: {_fmt(old)} -> {_fmt(new)}")
    return f"{field} " + ", ".join(parts)


# ---------------------------------------------------------------- operations


def _buyer_price(payload: Payload, change: BuyerPriceChange, dry_run: bool) -> str:
    p = change.params
    parts = []
    for buyer in _items(payload, "buyers", change.target, label="buyer"):
        old = buyer["price_per_kg"]
        new = compute(old, p.mode, p.value, field=f"buyer '{buyer['id']}'.price_per_kg")
        _check(new, field=f"buyer '{buyer['id']}'.price_per_kg", maximum=1e4)
        schedule = buyer.get("price_schedule") or []
        new_points = []
        for point in schedule:
            new_price = compute(point["price"], p.mode, p.value, field=f"buyer '{buyer['id']}' price on day {point['day']}")
            _check(new_price, field=f"buyer '{buyer['id']}' price on day {point['day']}", maximum=1e4)
            new_points.append({**point, "price": new_price})
        if not dry_run:
            buyer["price_per_kg"] = new
            if schedule:
                buyer["price_schedule"] = new_points
        parts.append(f"{buyer['id']}: {_fmt(old)} -> {_fmt(new)}" + (f" (+{len(schedule)} scheduled prices)" if schedule else ""))
    return "price_per_kg " + ", ".join(parts)


def _buyer_demand(payload: Payload, change: BuyerDemandChange, dry_run: bool) -> str:
    p = change.params
    field = p.field
    parts = []
    for buyer in _items(payload, "buyers", change.target, label="buyer"):
        old = buyer.get(field)
        if field == "min_contract_kg" and old is None:
            old = 0.0
        name = f"buyer '{buyer['id']}'.{field}"
        new = compute(old, p.mode, p.value, field=name)
        if field == "min_contract_kg":
            _check(new, field=name)
            limit = buyer["max_demand_kg"]
            if new > limit:
                raise ChangeError(f"{name} would become {_fmt(new)}, above max_demand_kg ({_fmt(limit)})")
        else:
            _check(new, field=name, strict=True, maximum=1e8)
            floors = [buyer.get("min_contract_kg") or 0.0, buyer.get("min_order_kg") or 0.0] if field == "max_demand_kg" else []
            if floors and new < max(floors):
                raise ChangeError(f"{name} would become {_fmt(new)}, below the buyer's minimum ({_fmt(max(floors))})")
        if not dry_run:
            buyer[field] = new
        parts.append(f"{buyer['id']}: {_fmt(old)} -> {_fmt(new)}")
    return f"{field} " + ", ".join(parts)


def _harvest_quantity(payload: Payload, change: HarvestQuantityChange, dry_run: bool) -> str:
    return _numeric(
        payload, change, collection="harvest_lots", field="quantity_kg", label="harvest lot",
        mode=change.params.mode, value=change.params.value, strict=True, maximum=1e8, dry_run=dry_run,
    )


def _harvest_timing(payload: Payload, change: HarvestTimingChange, dry_run: bool) -> str:
    (lot,) = _items(payload, "harvest_lots", change.target, label="harvest lot")
    old = lot["available_day"]
    new = old + change.params.shift_days
    _check(new, field=f"harvest lot '{lot['id']}'.available_day", maximum=365)
    if not dry_run:
        lot["available_day"] = new
    return f"available_day {lot['id']}: {old} -> {new}"


def _storage_capacity(payload: Payload, change: StorageCapacityChange, dry_run: bool) -> str:
    return _numeric(
        payload, change, collection="storage_facilities", field="capacity_kg", label="storage facility",
        mode=change.params.mode, value=change.params.value, maximum=1e8, dry_run=dry_run,
    )


def _storage_cost(payload: Payload, change: StorageCostChange, dry_run: bool) -> str:
    return _numeric(
        payload, change, collection="storage_facilities", field="cost_per_kg_per_day", label="storage facility",
        mode=change.params.mode, value=change.params.value, maximum=1e3, dry_run=dry_run,
    )


def _add_storage(payload: Payload, change: AddStorageChange, dry_run: bool) -> str:
    facility = change.params.facility.model_dump(mode="json")
    if any(f["id"] == facility["id"] for f in payload["storage_facilities"]):
        raise ChangeError(f"storage facility '{facility['id']}' already exists")
    if not dry_run:
        payload["storage_facilities"].append(facility)
    kind = "refrigerated" if facility["refrigerated"] else "ambient"
    return f"added {kind} storage '{facility['id']}' ({_fmt(facility['capacity_kg'])} kg)"


def _remove_storage(payload: Payload, change: RemoveStorageChange, dry_run: bool) -> str:
    (facility,) = _items(payload, "storage_facilities", change.target, label="storage facility")
    if not dry_run:
        payload["storage_facilities"].remove(facility)
    return f"removed storage '{facility['id']}'"


def _transport_cost(payload: Payload, change: TransportCostChange, dry_run: bool) -> str:
    return _numeric(
        payload, change, collection="vehicle_types", field=change.params.field, label="vehicle type",
        mode=change.params.mode, value=change.params.value,
        maximum=1e4 if change.params.field == "cost_per_km" else 1e6, dry_run=dry_run,
    )


def _vehicle_count(payload: Payload, change: VehicleCountChange, dry_run: bool) -> str:
    return _numeric(
        payload, change, collection="vehicle_types", field="count", label="vehicle type",
        mode=change.params.mode, value=change.params.value, maximum=1000, integer=True, dry_run=dry_run,
    )


def _vehicle_capacity(payload: Payload, change: VehicleCapacityChange, dry_run: bool) -> str:
    return _numeric(
        payload, change, collection="vehicle_types", field="capacity_kg", label="vehicle type",
        mode=change.params.mode, value=change.params.value, strict=True, maximum=1e6, dry_run=dry_run,
    )


def _shelf_life(payload: Payload, change: ShelfLifeChange, dry_run: bool) -> str:
    (crop,) = _items(payload, "crops", change.target, label="crop")
    field = "shelf_life_ambient_days" if change.params.field == "ambient" else "shelf_life_cold_days"
    old = crop.get(field)
    name = f"crop '{crop['id']}'.{field}"
    raw = compute(old, change.params.mode, change.params.value, field=name)
    new = int(round(raw))
    _check(new, field=name, minimum=1, maximum=730)
    ambient = new if field == "shelf_life_ambient_days" else crop["shelf_life_ambient_days"]
    cold = new if field == "shelf_life_cold_days" else crop.get("shelf_life_cold_days")
    if cold is not None and cold < ambient:
        raise ChangeError(f"cold shelf life ({cold}) would be shorter than ambient shelf life ({ambient})")
    if not dry_run:
        crop[field] = new
    rounded = " (rounded to whole days)" if abs(raw - new) > 1e-9 else ""
    return f"{field} {crop['id']}: {_fmt(old)} -> {new}{rounded}"


def _add_buyer(payload: Payload, change: AddBuyerChange, dry_run: bool) -> str:
    buyer = change.params.buyer.model_dump(mode="json")
    route = change.params.route.model_dump(mode="json")
    if any(b["id"] == buyer["id"] for b in payload["buyers"]):
        raise ChangeError(f"buyer '{buyer['id']}' already exists")
    known_crops = {c["id"] for c in payload["crops"]}
    unknown = sorted(set(buyer["crop_ids"]) - known_crops)
    if unknown:
        raise ChangeError(f"buyer '{buyer['id']}' accepts unknown crop(s) {unknown}")
    if not dry_run:
        payload["buyers"].append(buyer)
        payload["routes"].append(route)
    return f"added buyer '{buyer['id']}' in {buyer['location']} at {_fmt(buyer['price_per_kg'])}/kg"


def _remove_buyer(payload: Payload, change: RemoveBuyerChange, dry_run: bool) -> str:
    (buyer,) = _items(payload, "buyers", change.target, label="buyer")
    if len(payload["buyers"]) <= 1:
        raise ChangeError("at least one buyer must remain")
    if not dry_run:
        payload["buyers"].remove(buyer)
        payload["routes"] = [r for r in payload["routes"] if r["buyer_id"] != buyer["id"]]
    return f"removed buyer '{buyer['id']}' and its route"


def _route(payload: Payload, change: RouteChange, dry_run: bool) -> str:
    p = change.params
    (route,) = _items(payload, "routes", change.target, key="buyer_id", label="route of buyer")
    old = route.get(p.field)
    name = f"route '{change.target}'.{p.field}"
    if p.field == "road_condition":
        new: Any = RoadCondition(p.value).value
    else:
        base = old if old is not None or p.field != "toll_per_trip" else 0.0
        new = compute(base, p.mode or ChangeMode.ABSOLUTE, float(p.value), field=name)  # type: ignore[arg-type]
        _check(new, field=name, maximum=5000 if p.field == "distance_km" else 1e5)
    if not dry_run:
        route[p.field] = new
    return f"{p.field} to {change.target}: {_fmt(old)} -> {_fmt(new)}"


def _cold_chain(payload: Payload, change: ColdChainChange, dry_run: bool) -> str:
    collection, label = ("buyers", "buyer") if change.params.entity == "buyer" else ("crops", "crop")
    (item,) = _items(payload, collection, change.target, label=label)
    old = item.get("requires_cold_chain", False)
    if not dry_run:
        item["requires_cold_chain"] = change.params.required
    return f"requires_cold_chain {label} {item['id']}: {old} -> {change.params.required}"


@dataclass(frozen=True)
class Operation:
    op: str
    handler: Callable[[Payload, Any, bool], str]
    description: str

    def validate(self, payload: Payload, change: _Change) -> None:
        """Raise ChangeError if `change` cannot be applied to `payload` (payload is left untouched)."""
        self.handler(payload, change, True)

    def apply(self, payload: Payload, change: _Change) -> str:
        """Mutate `payload` and return a one-line summary with before/after values."""
        return self.handler(payload, change, False)


OPERATIONS: dict[str, Operation] = {
    op.op: op
    for op in (
        Operation("buyer_price", _buyer_price, "Buyer price (and price schedule)"),
        Operation("buyer_demand", _buyer_demand, "Buyer demand: max_demand_kg, max_per_day_kg or min_contract_kg"),
        Operation("harvest_quantity", _harvest_quantity, "Quantity of a harvest lot"),
        Operation("harvest_timing", _harvest_timing, "Shift the day a harvest lot becomes available"),
        Operation("storage_capacity", _storage_capacity, "Capacity of a storage facility"),
        Operation("storage_cost", _storage_cost, "Storage cost per kg per day"),
        Operation("add_storage", _add_storage, "Add a storage facility"),
        Operation("remove_storage", _remove_storage, "Remove a storage facility"),
        Operation("transport_cost", _transport_cost, "Vehicle cost per km (fuel proxy) or fixed cost per trip"),
        Operation("vehicle_count", _vehicle_count, "Number of vehicles of a type"),
        Operation("vehicle_capacity", _vehicle_capacity, "Capacity of a vehicle type"),
        Operation("shelf_life", _shelf_life, "Ambient or cold shelf life of a crop"),
        Operation("add_buyer", _add_buyer, "Add a buyer and its route"),
        Operation("remove_buyer", _remove_buyer, "Remove a buyer and its route"),
        Operation("route", _route, "Route distance, road condition or toll"),
        Operation("cold_chain", _cold_chain, "Cold-chain requirement of a buyer or a crop"),
    )
}

"""Scenario changes (plan §12): typed operations, applied in order to a dataset payload.

Common shape: `{op, target, params}`. Numeric params use `{mode, value}` where
  absolute     -> new = value
  relative_pct -> new = old x (1 + value / 100)
  delta        -> new = old + value
Every value is computed by the backend (`app.scenarios.operations`), never by the caller or an LLM.
`target` is an entity id, `"*"` (every entity, where allowed) or null (add_* operations).
"""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal, Union, get_args

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from .dataset import Buyer, DomainModel, Route, StorageFacility
from .enums import ChangeMode, ChangeSource, RoadCondition

ALL = "*"

Target = Annotated[str, StringConstraints(pattern=r"^(\*|[A-Za-z0-9_.\-]{1,64})$")]
Amount = Annotated[float, Field(ge=-1e8, le=1e8)]


class NumericParams(DomainModel):
    mode: ChangeMode
    value: Amount


class BuyerDemandParams(NumericParams):
    field: Literal["max_demand_kg", "max_per_day_kg", "min_contract_kg"]


class TimingParams(DomainModel):
    shift_days: int = Field(ge=-365, le=365)


class TransportCostParams(NumericParams):
    field: Literal["cost_per_km", "fixed_cost_per_trip"]


class VehicleCountParams(DomainModel):
    mode: Literal["absolute", "delta"]
    value: int = Field(ge=-1000, le=1000)


class ShelfLifeParams(NumericParams):
    field: Literal["ambient", "cold"]


class AddStorageParams(DomainModel):
    facility: StorageFacility


class AddBuyerParams(DomainModel):
    buyer: Buyer
    route: Route

    @model_validator(mode="after")
    def _route_matches(self) -> AddBuyerParams:
        if self.route.buyer_id != self.buyer.id:
            raise ValueError(f"route.buyer_id ('{self.route.buyer_id}') must equal buyer.id ('{self.buyer.id}')")
        return self


class RouteParams(DomainModel):
    field: Literal["distance_km", "road_condition", "toll_per_trip"]
    mode: ChangeMode | None = None
    value: RoadCondition | Amount

    @model_validator(mode="after")
    def _value_matches_field(self) -> RouteParams:
        if self.field == "road_condition":
            if not isinstance(self.value, RoadCondition):
                raise ValueError("road_condition takes one of: good, fair, poor")
            if self.mode not in (None, ChangeMode.ABSOLUTE):
                raise ValueError("road_condition can only be set (mode absolute)")
        elif isinstance(self.value, RoadCondition):
            raise ValueError(f"{self.field} takes a number")
        return self


class ColdChainParams(DomainModel):
    required: bool
    entity: Literal["buyer", "crop"] = "buyer"


class EmptyParams(DomainModel):
    pass


class _Change(DomainModel):
    """Fields shared by every operation. Subclasses declare how `target` is used."""

    target_kind: ClassVar[Literal["one", "one_or_all", "none"]] = "one"

    target: Target | None = None
    enabled: bool = True
    source: ChangeSource = ChangeSource.MANUAL
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _target_shape(self) -> _Change:
        kind = type(self).target_kind
        if kind == "none" and self.target is not None:
            raise ValueError("this operation takes no target")
        if kind != "none" and self.target is None:
            raise ValueError("target is required")
        if kind == "one" and self.target == ALL:
            raise ValueError("this operation cannot target '*'")
        return self


class BuyerPriceChange(_Change):
    target_kind: ClassVar = "one_or_all"
    op: Literal["buyer_price"] = "buyer_price"
    params: NumericParams


class BuyerDemandChange(_Change):
    target_kind: ClassVar = "one_or_all"
    op: Literal["buyer_demand"] = "buyer_demand"
    params: BuyerDemandParams


class HarvestQuantityChange(_Change):
    target_kind: ClassVar = "one_or_all"
    op: Literal["harvest_quantity"] = "harvest_quantity"
    params: NumericParams


class HarvestTimingChange(_Change):
    op: Literal["harvest_timing"] = "harvest_timing"
    params: TimingParams


class StorageCapacityChange(_Change):
    op: Literal["storage_capacity"] = "storage_capacity"
    params: NumericParams


class StorageCostChange(_Change):
    target_kind: ClassVar = "one_or_all"
    op: Literal["storage_cost"] = "storage_cost"
    params: NumericParams


class AddStorageChange(_Change):
    target_kind: ClassVar = "none"
    op: Literal["add_storage"] = "add_storage"
    params: AddStorageParams


class RemoveStorageChange(_Change):
    op: Literal["remove_storage"] = "remove_storage"
    params: EmptyParams = Field(default_factory=EmptyParams)


class TransportCostChange(_Change):
    target_kind: ClassVar = "one_or_all"
    op: Literal["transport_cost"] = "transport_cost"
    params: TransportCostParams


class VehicleCountChange(_Change):
    op: Literal["vehicle_count"] = "vehicle_count"
    params: VehicleCountParams


class VehicleCapacityChange(_Change):
    op: Literal["vehicle_capacity"] = "vehicle_capacity"
    params: NumericParams


class ShelfLifeChange(_Change):
    op: Literal["shelf_life"] = "shelf_life"
    params: ShelfLifeParams


class AddBuyerChange(_Change):
    target_kind: ClassVar = "none"
    op: Literal["add_buyer"] = "add_buyer"
    params: AddBuyerParams


class RemoveBuyerChange(_Change):
    op: Literal["remove_buyer"] = "remove_buyer"
    params: EmptyParams = Field(default_factory=EmptyParams)


class RouteChange(_Change):
    op: Literal["route"] = "route"
    params: RouteParams


class ColdChainChange(_Change):
    op: Literal["cold_chain"] = "cold_chain"
    params: ColdChainParams


ScenarioChangeModel = Annotated[
    Union[
        BuyerPriceChange,
        BuyerDemandChange,
        HarvestQuantityChange,
        HarvestTimingChange,
        StorageCapacityChange,
        StorageCostChange,
        AddStorageChange,
        RemoveStorageChange,
        TransportCostChange,
        VehicleCountChange,
        VehicleCapacityChange,
        ShelfLifeChange,
        AddBuyerChange,
        RemoveBuyerChange,
        RouteChange,
        ColdChainChange,
    ],
    Field(discriminator="op"),
]

CHANGE_ADAPTER: TypeAdapter[ScenarioChangeModel] = TypeAdapter(ScenarioChangeModel)
CHANGE_TYPES: dict[str, type[_Change]] = {
    t.model_fields["op"].default: t for t in get_args(get_args(ScenarioChangeModel)[0])
}


def parse_change(data: dict[str, Any]) -> ScenarioChangeModel:
    return CHANGE_ADAPTER.validate_python(data)


class AppliedChange(DomainModel):
    """One change as applied to the working payload, in application order."""

    index: int = Field(description="Position in the full chain (ancestors first)")
    op: str
    target: str | None
    summary: str = Field(description="What changed, with the before/after values computed by the backend")
    scenario_id: str | None = None
    change_id: str | None = None

"""Business validation of a structurally valid dataset: errors block optimization,
warnings flag likely surprises, assumptions list the defaults the model will apply."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from .dataset import DatasetPayload, trip_hours

IssueLevel = Literal["error", "warning", "assumption"]


class ValidationIssue(BaseModel):
    code: str
    message: str
    path: str | None = None


class ValidationReport(BaseModel):
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    assumptions: list[ValidationIssue] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def add(self, level: IssueLevel, code: str, message: str, path: str | None = None) -> None:
        issue = ValidationIssue(code=code, message=message, path=path)
        {"error": self.errors, "warning": self.warnings, "assumption": self.assumptions}[level].append(issue)


def report_from_validation_error(exc: ValidationError) -> ValidationReport:
    """Structural (Pydantic) errors expressed as a report, for draft validation."""
    report = ValidationReport()
    for err in exc.errors():
        path = ".".join(str(p) for p in err.get("loc", ()))
        report.add("error", "SCHEMA_ERROR", err.get("msg", "Invalid value"), path or None)
    return report


def validate_business(payload: DatasetPayload) -> ValidationReport:
    report = ValidationReport()
    active_vehicles = [v for v in payload.vehicle_types if v.count > 0]
    reefers = [v for v in active_vehicles if v.refrigerated]

    if not active_vehicles:
        report.add("error", "NO_VEHICLE", "No vehicle type has count > 0: nothing can be delivered.", "vehicle_types")

    harvested = {c.id: 0.0 for c in payload.crops}
    for lot in payload.harvest_lots:
        harvested[lot.crop_id] += lot.quantity_kg

    for crop in payload.crops:
        if harvested[crop.id] == 0:
            continue
        buyers = [b for b in payload.buyers if crop.id in b.crop_ids]
        if not buyers:
            report.add("error", "NO_BUYER_FOR_CROP", f"No buyer accepts crop '{crop.id}'.", f"crops[{crop.id}]")
            continue
        if crop.requires_cold_chain and not reefers:
            report.add(
                "error",
                "COLD_CHAIN_NO_VEHICLE",
                f"Crop '{crop.id}' requires a cold chain but no refrigerated vehicle is available.",
                f"crops[{crop.id}]",
            )
        demand = sum(b.max_demand_kg for b in buyers)
        if demand < harvested[crop.id]:
            report.add(
                "warning",
                "DEMAND_BELOW_HARVEST",
                f"Total buyer demand for '{crop.id}' ({demand:,.0f} kg) is below the harvest "
                f"({harvested[crop.id]:,.0f} kg): the rest can only be stored or lost.",
                f"crops[{crop.id}]",
            )
        contracted = sum(b.min_contract_kg or 0.0 for b in buyers)
        if contracted > harvested[crop.id]:
            report.add(
                "warning",
                "CONTRACTS_EXCEED_HARVEST",
                f"Contracted minimums for '{crop.id}' ({contracted:,.0f} kg) exceed the harvest "
                f"({harvested[crop.id]:,.0f} kg): optimization will be infeasible.",
                f"crops[{crop.id}]",
            )
        if crop.requires_cold_chain:
            for facility in payload.storage_facilities:
                if not facility.refrigerated:
                    report.add(
                        "warning",
                        "AMBIENT_STORAGE_UNUSABLE",
                        f"Storage '{facility.id}' is not refrigerated and cannot hold cold-chain crop '{crop.id}'.",
                        f"storage_facilities[{facility.id}]",
                    )
        has_cold_storage = any(f.refrigerated for f in payload.storage_facilities)
        if has_cold_storage and crop.shelf_life_cold_days is None:
            report.add(
                "assumption",
                "COLD_SHELF_LIFE_DEFAULT",
                f"Crop '{crop.id}' has no cold shelf life: refrigerated storage uses the ambient shelf life "
                f"({crop.shelf_life_ambient_days} days).",
                f"crops[{crop.id}]",
            )

    for buyer in payload.buyers:
        route = payload.route_for(buyer.id)
        cold = buyer.requires_cold_chain or any(
            payload.crop(c).requires_cold_chain for c in buyer.crop_ids
        )
        usable = reefers if cold else active_vehicles
        if cold and not reefers:
            report.add(
                "warning",
                "BUYER_UNREACHABLE_COLD_CHAIN",
                f"Buyer '{buyer.id}' needs a refrigerated vehicle and none is available.",
                f"buyers[{buyer.id}]",
            )
            continue
        reachable = [v for v in usable if v.hours_per_day is None or trip_hours(route, v) <= v.hours_per_day]
        if usable and not reachable:
            longest = min(trip_hours(route, v) for v in usable)
            report.add(
                "warning",
                "TRIP_TOO_LONG",
                f"A round trip to '{buyer.id}' takes {longest:.1f} h, more than a vehicle's working day: "
                "this buyer cannot be served.",
                f"routes[{buyer.id}]",
            )

    for facility in payload.storage_facilities:
        if facility.capacity_kg == 0:
            report.add("warning", "STORAGE_ZERO_CAPACITY", f"Storage '{facility.id}' has no capacity.", f"storage_facilities[{facility.id}]")

    default_factor_routes = [r.buyer_id for r in payload.routes if r.road_factor_override is None]
    if default_factor_routes:
        report.add(
            "assumption",
            "ROAD_FACTOR_DEFAULT",
            "Default road factors (good 1.00, fair 1.15, poor 1.35) are applied to distances for "
            f"routes to {default_factor_routes}.",
            "routes",
        )
    legacy = [r.buyer_id for r in payload.routes if r.legacy_cost_per_kg_per_km is not None]
    if legacy:
        report.add(
            "assumption",
            "LEGACY_TRANSPORT_COST",
            f"Routes to {legacy} also charge a v1 cost per kg per km on delivered kg.",
            "routes",
        )
    unlimited = [v.id for v in payload.vehicle_types if v.hours_per_day is None]
    if unlimited:
        report.add(
            "assumption",
            "UNLIMITED_DRIVING_HOURS",
            f"Vehicle types {unlimited} have no daily driving-time limit.",
            "vehicle_types",
        )
    if payload.currency is None:
        report.add("assumption", "CURRENCY_DEFAULT", "No currency set: the workspace currency is used.", "currency")

    return report

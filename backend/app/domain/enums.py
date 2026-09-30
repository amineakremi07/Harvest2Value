"""Enumerations shared across the V2 domain."""

from enum import StrEnum


class CropType(StrEnum):
    PERISHABLE = "perishable"
    SEMI_PERISHABLE = "semi_perishable"
    DURABLE = "durable"


class RoadCondition(StrEnum):
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class BuyerPriority(StrEnum):
    CONTRACT = "contract"
    SPOT = "spot"


class ObjectiveKind(StrEnum):
    PROFIT = "profit"
    REVENUE = "revenue"
    WASTE = "waste"
    COST = "cost"
    WEIGHTED = "weighted"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class SolverOutcome(StrEnum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"  # stopped at the time limit with a solution
    INFEASIBLE = "infeasible"
    UNBOUNDED = "unbounded"
    NOT_SOLVED = "not_solved"  # stopped at the time limit without a solution
    ERROR = "error"

    @property
    def has_solution(self) -> bool:
        return self in (SolverOutcome.OPTIMAL, SolverOutcome.FEASIBLE)


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class InsightCategory(StrEnum):
    RISK = "risk"
    OPPORTUNITY = "opportunity"
    INFO = "info"


class ChangeOp(StrEnum):
    """Scenario operations (plan §12), implemented in `app.scenarios.operations`."""

    BUYER_PRICE = "buyer_price"
    BUYER_DEMAND = "buyer_demand"
    HARVEST_QUANTITY = "harvest_quantity"
    HARVEST_TIMING = "harvest_timing"
    STORAGE_CAPACITY = "storage_capacity"
    STORAGE_COST = "storage_cost"
    ADD_STORAGE = "add_storage"
    REMOVE_STORAGE = "remove_storage"
    TRANSPORT_COST = "transport_cost"
    VEHICLE_COUNT = "vehicle_count"
    VEHICLE_CAPACITY = "vehicle_capacity"
    SHELF_LIFE = "shelf_life"
    ADD_BUYER = "add_buyer"
    REMOVE_BUYER = "remove_buyer"
    ROUTE = "route"
    COLD_CHAIN = "cold_chain"


class ChangeMode(StrEnum):
    ABSOLUTE = "absolute"
    RELATIVE_PCT = "relative_pct"
    DELTA = "delta"


class ChangeSource(StrEnum):
    MANUAL = "manual"
    AI_PROPOSED = "ai_proposed"
    RECOMMENDATION = "recommendation"


class ScenarioStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    STALE = "stale"
    ARCHIVED = "archived"

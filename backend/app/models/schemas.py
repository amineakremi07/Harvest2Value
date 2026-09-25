"""Pydantic models for Harvest2Value API request/response schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---- Request models ----

class ProducerIn(BaseModel):
    id: str
    name: str
    region: str
    country: str
    harvest_kg: float = Field(..., gt=0)
    storage_capacity_kg: float = Field(..., ge=0)
    storage_cost_per_kg_per_day: float = 0.05
    shelf_life_days: int = Field(..., ge=1)


class BuyerIn(BaseModel):
    id: str
    name: str
    location: str
    max_demand_kg: float = Field(..., gt=0)
    price_per_kg: float = Field(..., ge=0)
    distance_km: float = Field(..., ge=0)
    transport_cost_per_kg_per_km: float = Field(..., ge=0)


class LogisticsIn(BaseModel):
    available_vehicles: int = Field(..., ge=1)
    vehicle_capacity_kg: float = Field(..., gt=0)
    refrigerated_required: bool = False
    road_condition: str = Field(default="fair", pattern="^(good|fair|poor)$")


class CropIn(BaseModel):
    name: str
    type: str = Field(..., pattern="^(perishable|semi_perishable|durable)$")
    unit: str = "kg"


class OptimizeRequest(BaseModel):
    producer: ProducerIn
    buyers: List[BuyerIn] = Field(..., min_length=1)
    crop: CropIn
    logistics: LogisticsIn


class ScenarioRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language What-If query")
    data: Dict[str, Any]


class ExplainRequest(BaseModel):
    result: Dict[str, Any]
    data: Dict[str, Any]


# ---- Response models ----

class AllocationDetail(BaseModel):
    buyer_name: str
    allocated_kg: int
    unit_price: float
    revenue: float
    transport_cost: float
    net_profit: float
    distance_km: float


class OptimizeResponse(BaseModel):
    status: str
    total_harvest_kg: float
    allocated_kg: float
    stored_kg: float
    wasted_kg: float
    total_revenue: float
    total_transport_cost: float
    net_profit: float
    allocation: Dict[str, AllocationDetail]
    solver_time_seconds: float
    metadata: Dict[str, Any]


class ExplainResponse(BaseModel):
    explanation: str

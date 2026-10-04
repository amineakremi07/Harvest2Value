"""Analytics endpoints (plan §8): dashboard, run sections, supply-chain network, market ranking."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...analytics.buyers import BuyersSection
from ...analytics.crops import CropsSection
from ...analytics.financial import FinancialSection
from ...analytics.logistics import LogisticsSection
from ...analytics.market import MarketAnalysis
from ...analytics.network import NetworkGraph
from ...analytics.operational import OperationalSection
from ...db.session import get_session
from ...services.analytics import AnalyticsService, DashboardData
from .schemas.common import Responses

router = APIRouter(tags=["analytics"])

NOT_READY: Responses = {404: {"description": "Run not found"}, 409: {"description": "RUN_NOT_FINISHED, RUN_INFEASIBLE or RUN_NO_RESULT"}}


def get_service(session: Session = Depends(get_session, scope="function")) -> AnalyticsService:
    return AnalyticsService(session)


Service = Annotated[AnalyticsService, Depends(get_service)]


@router.get("/analytics/dashboard", response_model=DashboardData, responses={404: {"description": "NO_RUN or run not found"}})
def dashboard(service: Service, run_id: str | None = None) -> DashboardData:
    """Executive view of a run (default: the latest succeeded run), with deltas against the latest
    baseline run of the same dataset when the run belongs to a scenario."""
    return service.dashboard(run_id)


@router.get("/analytics/runs/{run_id}/financial", response_model=FinancialSection, responses=NOT_READY)
def financial(run_id: str, service: Service) -> FinancialSection:
    return service.financial(run_id)


@router.get("/analytics/runs/{run_id}/operational", response_model=OperationalSection, responses=NOT_READY)
def operational(run_id: str, service: Service) -> OperationalSection:
    return service.operational(run_id)


@router.get("/analytics/runs/{run_id}/buyers", response_model=BuyersSection, responses=NOT_READY)
def buyers(run_id: str, service: Service) -> BuyersSection:
    return service.buyers(run_id)


@router.get("/analytics/runs/{run_id}/logistics", response_model=LogisticsSection, responses=NOT_READY)
def logistics(run_id: str, service: Service) -> LogisticsSection:
    return service.logistics(run_id)


@router.get("/analytics/runs/{run_id}/crops", response_model=CropsSection, responses=NOT_READY)
def crops(run_id: str, service: Service) -> CropsSection:
    return service.crops(run_id)


@router.get("/runs/{run_id}/network", response_model=NetworkGraph, responses=NOT_READY, tags=["runs"])
def run_network(run_id: str, service: Service, day: Annotated[int | None, Query(ge=0, le=365)] = None) -> NetworkGraph:
    return service.network(run_id, day)


@router.get(
    "/datasets/{dataset_id}/market",
    response_model=MarketAnalysis,
    responses={404: {"description": "Dataset or version not found"}, 422: {"description": "CONFIG_INVALID (crop)"}},
    tags=["datasets"],
)
def market(
    dataset_id: str,
    service: Service,
    version: Annotated[int | None, Query(ge=1)] = None,
    crop_id: str | None = None,
) -> MarketAnalysis:
    """Buyers ranked by estimated net price per kg, before any optimization."""
    return service.market(dataset_id, version_no=version, crop_id=crop_id)

"""Analytics endpoints: sections of a run, executive dashboard, network, pre-optimization market."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..analytics.buyers import BuyersSection, buyers
from ..analytics.context import RunContext
from ..analytics.crops import CropsSection, crops
from ..analytics.financial import FinancialSection, financial
from ..analytics.logistics import LogisticsSection, logistics
from ..analytics.market import MarketAnalysis, analyze_market
from ..analytics.network import NetworkGraph, network
from ..analytics.operational import OperationalSection, operational
from ..core.errors import NotFound
from ..db.models import DEFAULT_WORKSPACE_ID, OptimizationRun
from ..domain.comparison import Delta
from ..domain.dataset import DatasetPayload
from ..domain.explanation import Bottleneck
from ..domain.results import Kpis
from ..explain.binding import bottlenecks
from ..repositories.datasets import DatasetRepository
from .insights import InsightService, InsightView
from .optimization import OptimizationService

DASHBOARD_KPIS = (
    "realized_revenue",
    "transport_cost",
    "storage_cost",
    "realized_profit",
    "margin_pct",
    "sold_kg",
    "ending_inventory_kg",
    "lost_kg",
    "ending_inventory_value",
    "vehicle_utilization_pct",
    "storage_utilization_peak_pct",
)


class RunHeadline(BaseModel):
    run_id: str
    label: str | None
    scenario_id: str | None
    created_at: datetime
    objective: str
    realized_profit: float | None
    waste_rate_pct: float | None
    sold_kg: float | None


class BestBuyer(BaseModel):
    buyer_id: str
    buyer_name: str
    net_revenue: float
    sold_kg: float


class DashboardSeriesPoint(BaseModel):
    day: int
    sold_kg: float
    stock_end_kg: float
    lost_kg: float


class DashboardData(BaseModel):
    run: RunHeadline
    dataset_id: str
    baseline_run_id: str | None
    kpis: Kpis
    kpi_deltas: dict[str, Delta]
    top_insights: list[InsightView]
    best_buyer: BestBuyer | None
    main_bottleneck: Bottleneck | None
    series: list[DashboardSeriesPoint]
    history: list[RunHeadline]


def _delta(value: float | None, base: float | None) -> Delta:
    if value is None or base is None:
        return Delta(abs=None, pct=None)
    return Delta(abs=round(value - base, 4), pct=round(100 * (value - base) / abs(base), 2) if base else None)


class AnalyticsService:
    def __init__(self, session: Session, *, workspace_id: str = DEFAULT_WORKSPACE_ID) -> None:
        self.session = session
        self.workspace_id = workspace_id
        self.runs = OptimizationService(session, workspace_id=workspace_id)

    def context(self, run_id: str) -> RunContext:
        return self.runs.context(run_id)

    def financial(self, run_id: str) -> FinancialSection:
        return financial(self.context(run_id))

    def operational(self, run_id: str) -> OperationalSection:
        return operational(self.context(run_id))

    def buyers(self, run_id: str) -> BuyersSection:
        return buyers(self.context(run_id))

    def logistics(self, run_id: str) -> LogisticsSection:
        return logistics(self.context(run_id))

    def crops(self, run_id: str) -> CropsSection:
        return crops(self.context(run_id))

    def network(self, run_id: str, day: int | None) -> NetworkGraph:
        return network(self.context(run_id), day)

    def market(self, dataset_id: str, *, version_no: int | None, crop_id: str | None) -> MarketAnalysis:
        repo = DatasetRepository(self.session)
        dataset = repo.get(dataset_id, self.workspace_id)
        if dataset is None:
            raise NotFound(f"Dataset '{dataset_id}' does not exist.", details={"dataset_id": dataset_id})
        version = (
            repo.get_version(dataset_id, version_no)
            if version_no is not None
            else repo.get_version_by_id(dataset.current_version_id or "")
        )
        if version is None:
            raise NotFound(f"Version {version_no} does not exist.", details={"version_no": version_no})
        return analyze_market(DatasetPayload.model_validate(version.payload), crop_id)

    def _headline(self, run: OptimizationRun) -> RunHeadline:
        row = self.runs.runs.get_result(run.id)
        kpis = row.kpis if row else {}
        return RunHeadline(
            run_id=run.id,
            label=run.label,
            scenario_id=run.scenario_id,
            created_at=run.created_at,
            objective=str(run.config.get("objective", "profit")),
            realized_profit=kpis.get("realized_profit"),
            waste_rate_pct=kpis.get("waste_rate_pct"),
            sold_kg=kpis.get("sold_kg"),
        )

    def dashboard(self, run_id: str | None) -> DashboardData:
        if run_id is None:
            latest = self.runs.runs.latest_succeeded(self.workspace_id)
            if latest is None:
                raise NotFound("No succeeded run yet: launch an optimization first.", code="NO_RUN")
            run_id = latest.id
        ctx = self.context(run_id)
        run = self.runs.get(run_id)

        baseline = None
        if run.scenario_id is not None:
            baseline = self.runs.runs.latest_succeeded(self.workspace_id, dataset_id=run.dataset_id, baseline_only=True)
        base_kpis = self.runs.result(baseline.id).kpis if baseline is not None else None
        deltas = {
            k: _delta(getattr(ctx.result.kpis, k), getattr(base_kpis, k) if base_kpis else None)
            for k in DASHBOARD_KPIS
        } if base_kpis else {}

        active = [b for b in ctx.result.buyers if b.sold_kg > 0]
        best = max(active, key=lambda b: (b.net_revenue, b.buyer_id)) if active else None
        ranked = bottlenecks(ctx)
        history_rows, _ = self.runs.runs.list(self.workspace_id, dataset_id=run.dataset_id, status="succeeded", limit=10)
        return DashboardData(
            run=self._headline(run),
            dataset_id=run.dataset_id,
            baseline_run_id=baseline.id if baseline else None,
            kpis=ctx.result.kpis,
            kpi_deltas=deltas,
            top_insights=InsightService(self.session, workspace_id=self.workspace_id).list(run_id)[:5],
            best_buyer=BestBuyer(buyer_id=best.buyer_id, buyer_name=best.buyer_name, net_revenue=best.net_revenue, sold_kg=best.sold_kg)
            if best
            else None,
            main_bottleneck=ranked[0] if ranked else None,
            series=[
                DashboardSeriesPoint(
                    day=t,
                    sold_kg=round(ctx.sold_by_day.get(t, 0.0), 2),
                    stock_end_kg=round(ctx.stock_by_day.get(t, 0.0), 2),
                    lost_kg=round(ctx.lost_by_day.get(t, 0.0), 2),
                )
                for t in range(ctx.result.horizon_days)
            ],
            history=[self._headline(r) for r in history_rows],
        )

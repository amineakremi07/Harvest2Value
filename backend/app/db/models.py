"""ORM tables (plan §7.1): workspaces, datasets, dataset_versions (phase 1), optimization runs
and results (phase 3), insights (phase 4), scenarios and their changes (phase 5).

Producer, crops, lots, buyers, storage, vehicles and routes are not tables: they live in
the immutable `dataset_versions.payload` JSON document (validated by `domain.dataset`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, JSONType, TimestampMixin, UTCDateTime

DEFAULT_WORKSPACE_ID = "00000000-0000-4000-8000-000000000001"


class Workspace(IdMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TND")
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="fr")
    settings: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)


class Dataset(IdMixin, TimestampMixin, Base):
    __tablename__ = "datasets"
    __table_args__ = (Index("ix_datasets_workspace_updated", "workspace_id", "updated_at"),)

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # template | import | manual | duplicate
    template_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Circular with dataset_versions.dataset_id: created after both tables (use_alter).
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("dataset_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DatasetVersion(IdMixin, TimestampMixin, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version_no"),)

    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(10), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    validation: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class OptimizationRun(IdMixin, TimestampMixin, Base):
    """One optimization request. `effective_input` is a frozen copy of the data actually solved
    (dataset version + scenario changes), so a run stays reproducible after later edits."""

    __tablename__ = "optimization_runs"
    __table_args__ = (
        Index("ix_optimization_runs_workspace_created", "workspace_id", "created_at"),
        Index("ix_optimization_runs_cache", "effective_input_hash", "config_hash"),
    )

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Circular with scenarios.latest_run_id: the FK is added once both tables exist (use_alter).
    scenario_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("scenarios.id", ondelete="SET NULL", use_alter=True), nullable=True, index=True
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_input: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    applied_changes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    solver_outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mip_gap: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    solve_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)  # internal, never returned as-is
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    warnings: Mapped[list[str] | None] = mapped_column(JSONType, nullable=True)
    diagnostics: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)  # infeasible runs only


class OptimizationResult(IdMixin, TimestampMixin, Base):
    """Result of a succeeded run (one row per run)."""

    __tablename__ = "optimization_results"

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("optimization_runs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    meta: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)  # outcome label, gap, objective, crop, horizon
    kpis: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    buyers: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)
    allocations: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)
    inventory: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)
    trips: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)
    waste: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)
    constraints: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSONType, nullable=False)
    sensitivity: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    explanation: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)  # cache


class Insight(IdMixin, TimestampMixin, Base):
    __tablename__ = "insights"
    __table_args__ = (Index("ix_insights_run_severity", "run_id", "severity"),)

    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("optimization_runs.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)  # risk | opportunity | info
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # info | warning | critical
    entity_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    message_key: Mapped[str] = mapped_column(String(120), nullable=False)
    message_params: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    suggested_changes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType, nullable=True)
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Scenario(IdMixin, TimestampMixin, Base):
    __tablename__ = "scenarios"
    __table_args__ = (Index("ix_scenarios_workspace_updated", "workspace_id", "updated_at"),)

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # draft | ready | stale | archived
    tags: Mapped[list[str] | None] = mapped_column(JSONType, nullable=True)
    latest_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("optimization_runs.id", ondelete="SET NULL"), nullable=True
    )


class ScenarioChange(IdMixin, TimestampMixin, Base):
    __tablename__ = "scenario_changes"
    __table_args__ = (UniqueConstraint("scenario_id", "position"),)

    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    op: Mapped[str] = mapped_column(String(32), nullable=False)
    target: Mapped[str | None] = mapped_column(JSONType, nullable=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # manual | ai_proposed | recommendation
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

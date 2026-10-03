"""Report definition (phase 13): which sections, which runs, narrative on or off."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

ReportSection = Literal["summary", "financial", "operational", "buyers", "logistics", "crops", "insights", "comparison"]
REPORT_SECTIONS: tuple[ReportSection, ...] = ("summary", "financial", "operational", "buyers", "logistics", "crops", "insights", "comparison")


class ReportSpec(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    run_id: str = Field(max_length=64, description="Main run of the report")
    compare_run_ids: list[str] = Field(default_factory=list, max_length=3, description="Runs compared with the main run")
    sections: list[ReportSection] = Field(default_factory=lambda: ["summary", "financial", "buyers", "insights"], min_length=1)
    include_narrative: bool = False

    @model_validator(mode="after")
    def _consistent(self) -> ReportSpec:
        if len(set(self.sections)) != len(self.sections):
            raise ValueError("sections must be unique")
        if "comparison" in self.sections and not self.compare_run_ids:
            raise ValueError("the 'comparison' section needs compare_run_ids")
        if self.run_id in self.compare_run_ids:
            raise ValueError("compare_run_ids cannot contain run_id")
        return self

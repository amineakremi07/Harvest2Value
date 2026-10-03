// Readable aliases over the types generated from the backend OpenAPI document.
// Regenerate with: backend `scripts/export_openapi.py`, then `npm run gen:api`.
import type { components } from "./schema.gen";

type S = components["schemas"];

export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

// System
export type MetaResponse = S["MetaResponse"];
export type ChangeOpInfo = S["ChangeOpInfo"];
/** Error envelope body `{error: ErrorDetail}` (backend `api/errors.py`, not in the OpenAPI document). */
export interface ErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  request_id?: string | null;
}

// Datasets
export type TemplateInfo = S["TemplateInfo"];
export type DatasetSummary = S["DatasetSummary"];
export type DatasetDetail = S["DatasetDetail"];
export type DatasetPayload = S["DatasetPayload"];
export type DatasetVersionOut = S["DatasetVersionOut"];
export type ValidationReport = S["ValidationReport"];

// Runs
export type ObjectiveKind = S["ObjectiveKind"];
export type RunStatus = S["RunStatus"];
export type RunConfig = S["RunConfig"];
export type ObjectiveWeights = S["ObjectiveWeights"];
export type RunCreate = S["RunCreate"];
export type RunSummary = S["RunSummary"];
export type RunDetail = S["RunDetail"];
export type OptimizationResult = S["OptimizationResultModel"];
export type Kpis = S["Kpis"];
export type BuyerSummary = S["BuyerSummary"];
export type AllocationRow = S["AllocationRow"];
export type InventoryRow = S["InventoryRow"];
export type TripRow = S["TripRow"];
export type WasteRow = S["WasteRow"];
export type Diagnostics = S["Diagnostics"];
export type LogisticsSection = S["LogisticsSection"];

// Explainability & network
export type RunExplanation = S["RunExplanation"];
export type DecisionCard = S["DecisionCard"];
export type MarginalValue = S["MarginalValue"];
export type ConstraintInfo = S["ConstraintInfo"];
export type SensitivityReport = S["SensitivityReport"];
export type MarginalValuesStatus = S["MarginalValuesStatus"];
export type NetworkGraph = S["NetworkGraph"];
export type NetworkNode = S["NetworkNode"];
export type NetworkEdge = S["NetworkEdge"];

// Insights & analytics
export type InsightView = S["InsightView"];
export type TryInsightResult = S["TryInsightResult"];
export type DashboardData = S["DashboardData"];
export type Delta = S["Delta"];
export type Bottleneck = S["Bottleneck"];

// Scenarios
export type ScenarioSummary = S["ScenarioSummary"];
export type ScenarioDetail = S["ScenarioDetail"];
export type ScenarioChangeOut = S["ScenarioChangeOut"];
export type ScenarioPreview = S["ScenarioPreview"];
export type ScenarioCreate = S["ScenarioCreate"];
export type ScenarioRun = S["ScenarioRun"];
export type FieldDiff = S["FieldDiff"];
export type AppliedChange = S["AppliedChange"];
export type ChangeTargetKind = ChangeOpInfo["target"];

/** A scenario change as sent to the API: the backend validates `params` against the op's schema. */
export interface ChangeInput {
  op: string;
  target: string | null;
  params: Record<string, unknown>;
  note?: string | null;
  source?: "manual" | "ai_proposed" | "recommendation";
}

/** POST /scenarios body with untyped-params changes (validated by the backend). */
export type ScenarioCreateInput = Omit<ScenarioCreate, "changes"> & { changes?: ChangeInput[] };

// Comparisons
export type ComparisonResult = S["ComparisonResult"];
export type KpiRow = S["KpiRow"];
export type BuyerRow = S["BuyerRow"];
export type NotableChange = S["NotableChange"];

export const TERMINAL_STATUSES: readonly RunStatus[] = [
  "succeeded",
  "infeasible",
  "timeout",
  "failed",
  "cancelled",
  "interrupted",
];

export function isTerminal(status: RunStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

// Analytics sections
export type FinancialSection = S["FinancialSection"];
export type OperationalSection = S["OperationalSection"];
export type BuyersSection = S["BuyersSection"];
export type BuyerAnalytics = S["BuyerAnalytics"];
export type CropsSection = S["CropsSection"];

// Copilot & AI text
export type PageContext = S["PageContext"];
export type ConversationSummary = S["ConversationSummary"];
export type ConversationDetail = S["ConversationDetail"];
export type MessageView = S["MessageView"];
export type ActionView = S["ActionView"];
export type TurnResponse = S["TurnResponse"];
export type ToolsResponse = S["ToolsResponse"];
export type NarrativeResponse = S["NarrativeResponse"];
export type ParseResult = S["ParseResult"];
export type ProposedChange = S["ProposedChange"];
export type RejectedChange = S["RejectedChange"];

/** `verification` of an assistant message or a narrative (backend `VerificationReport.to_json`). */
export interface Verification {
  status: "verified" | "unverified";
  unknown_refs: string[];
  unverified_numbers: string[];
  checked_numbers: number;
  regenerated: boolean;
}

// Reports
export type ReportSpec = S["ReportSpec"];
export type ReportSection = NonNullable<ReportSpec["sections"]>[number];
export type ReportSummary = S["ReportSummary"];
export type ReportDetail = S["ReportDetail"];

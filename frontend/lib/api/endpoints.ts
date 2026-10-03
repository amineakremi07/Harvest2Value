// One typed function per /api/v2 endpoint used by the frontend.
import { API_V2, request } from "./client";
import type {
  ActionView,
  Bottleneck,
  BuyersSection,
  ConversationDetail,
  ConversationSummary,
  CropsSection,
  FinancialSection,
  NarrativeResponse,
  OperationalSection,
  PageContext,
  ParseResult,
  ReportDetail,
  ReportSpec,
  ReportSummary,
  ToolsResponse,
  TurnResponse,
  ChangeInput,
  ConstraintInfo,
  ComparisonResult,
  DashboardData,
  DatasetDetail,
  DatasetSummary,
  DatasetVersionOut,
  InsightView,
  LogisticsSection,
  MarginalValuesStatus,
  NetworkGraph,
  MetaResponse,
  OptimizationResult,
  Page,
  RunConfig,
  RunCreate,
  RunDetail,
  RunExplanation,
  RunStatus,
  RunSummary,
  ScenarioCreateInput,
  ScenarioDetail,
  ScenarioPreview,
  ScenarioSummary,
  SensitivityReport,
  TemplateInfo,
  TryInsightResult,
} from "./types";

export const api = {
  meta: () => request<MetaResponse>("/meta"),

  // Datasets
  templates: () => request<TemplateInfo[]>("/templates"),
  datasets: (query: { page_size?: number; q?: string } = {}) =>
    request<Page<DatasetSummary>>("/datasets", { query: { page_size: 100, ...query } }),
  dataset: (id: string) => request<DatasetDetail>(`/datasets/${id}`),
  datasetVersion: (id: string, versionNo: number) => request<DatasetVersionOut>(`/datasets/${id}/versions/${versionNo}`),
  createDatasetFromTemplate: (template_key: string, name?: string) =>
    request<DatasetDetail>("/datasets", { method: "POST", body: { template_key, name } }),

  // Runs
  createRun: (body: RunCreate, wait = 0) => request<RunDetail>("/runs", { method: "POST", body, query: { wait } }),
  runs: (query: { dataset_id?: string; scenario_id?: string; status?: RunStatus; page?: number; page_size?: number } = {}) =>
    request<Page<RunSummary>>("/runs", { query }),
  run: (id: string, signal?: AbortSignal) => request<RunDetail>(`/runs/${id}`, { signal }),
  runResult: (id: string) => request<OptimizationResult>(`/runs/${id}/result`),
  cancelRun: (id: string) => request<RunSummary>(`/runs/${id}/cancel`, { method: "POST" }),
  deleteRun: (id: string) => request<void>(`/runs/${id}`, { method: "DELETE" }),
  runLogistics: (id: string) => request<LogisticsSection>(`/analytics/runs/${id}/logistics`),

  // Explainability & network
  explanation: (id: string) => request<RunExplanation>(`/runs/${id}/explanation`),
  bindingConstraints: (id: string) => request<ConstraintInfo[]>(`/runs/${id}/constraints`, { query: { binding_only: true } }),
  bottlenecks: (id: string) => request<Bottleneck[]>(`/runs/${id}/bottlenecks`),
  startMarginalValues: (id: string, wait = 0) =>
    request<MarginalValuesStatus>(`/runs/${id}/marginal-values`, { method: "POST", query: { wait } }),
  marginalValues: (id: string) => request<SensitivityReport>(`/runs/${id}/marginal-values`),
  network: (id: string, day?: number | null) => request<NetworkGraph>(`/runs/${id}/network`, { query: { day: day ?? undefined } }),

  // Insights & analytics
  runInsights: (id: string, include_dismissed = false) =>
    request<InsightView[]>(`/runs/${id}/insights`, { query: { include_dismissed } }),
  dismissInsight: (id: string) => request<InsightView>(`/insights/${id}/dismiss`, { method: "POST" }),
  restoreInsight: (id: string) => request<InsightView>(`/insights/${id}/restore`, { method: "POST" }),
  tryInsight: (id: string) => request<TryInsightResult>(`/insights/${id}/try`, { method: "POST" }),
  dashboard: (run_id?: string) => request<DashboardData>("/analytics/dashboard", { query: { run_id } }),

  // Scenarios
  scenarios: (query: { dataset_id?: string; page_size?: number } = {}) =>
    request<Page<ScenarioSummary>>("/scenarios", { query: { page_size: 100, ...query } }),
  scenario: (id: string) => request<ScenarioDetail>(`/scenarios/${id}`),
  createScenario: (body: ScenarioCreateInput) => request<ScenarioDetail>("/scenarios", { method: "POST", body }),
  deleteScenario: (id: string, cascade = false) =>
    request<void>(`/scenarios/${id}`, { method: "DELETE", query: { cascade } }),
  duplicateScenario: (id: string, name?: string) =>
    request<ScenarioDetail>(`/scenarios/${id}/duplicate`, { method: "POST", body: name ? { name } : undefined }),
  branchScenario: (id: string, name: string, description?: string) =>
    request<ScenarioDetail>(`/scenarios/${id}/branch`, { method: "POST", body: { name, description } }),
  rebaseScenario: (id: string) => request<ScenarioDetail>(`/scenarios/${id}/rebase`, { method: "POST" }),
  addChange: (id: string, change: ChangeInput) =>
    request<ScenarioDetail>(`/scenarios/${id}/changes`, { method: "POST", body: change }),
  patchChange: (id: string, changeId: string, patch: { enabled?: boolean; params?: Record<string, unknown>; note?: string | null }) =>
    request<ScenarioDetail>(`/scenarios/${id}/changes/${changeId}`, { method: "PATCH", body: patch }),
  deleteChange: (id: string, changeId: string) =>
    request<ScenarioDetail>(`/scenarios/${id}/changes/${changeId}`, { method: "DELETE" }),
  reorderChanges: (id: string, ids: string[]) =>
    request<ScenarioDetail>(`/scenarios/${id}/changes/order`, { method: "PUT", body: { ids } }),
  previewScenario: (id: string) => request<ScenarioPreview>(`/scenarios/${id}/preview`, { method: "POST" }),
  runScenario: (id: string, config: RunConfig, label?: string) =>
    request<RunDetail>(`/scenarios/${id}/run`, { method: "POST", body: { config, label } }),

  // Comparisons
  compare: (baseline_run_id: string, run_ids: string[]) =>
    request<ComparisonResult>("/comparisons", { method: "POST", body: { baseline_run_id, run_ids } }),

  // Analytics Center
  financial: (id: string) => request<FinancialSection>(`/analytics/runs/${id}/financial`),
  operational: (id: string) => request<OperationalSection>(`/analytics/runs/${id}/operational`),
  buyers: (id: string) => request<BuyersSection>(`/analytics/runs/${id}/buyers`),
  crops: (id: string) => request<CropsSection>(`/analytics/runs/${id}/crops`),

  // Copilot & AI text (503 LLM_NOT_CONFIGURED when the AI is disabled)
  conversations: () => request<Page<ConversationSummary>>("/copilot/conversations", { query: { page_size: 50 } }),
  conversation: (id: string) => request<ConversationDetail>(`/copilot/conversations/${id}`),
  createConversation: (context?: PageContext) =>
    request<ConversationDetail>("/copilot/conversations", { method: "POST", body: context ? { context } : {} }),
  deleteConversation: (id: string) => request<void>(`/copilot/conversations/${id}`, { method: "DELETE" }),
  sendMessage: (id: string, content: string, context?: PageContext) =>
    request<TurnResponse>(`/copilot/conversations/${id}/messages`, { method: "POST", body: { content, context }, query: { stream: false } }),
  confirmAction: (id: string) => request<ActionView>(`/copilot/actions/${id}/confirm`, { method: "POST" }),
  rejectAction: (id: string) => request<ActionView>(`/copilot/actions/${id}/reject`, { method: "POST" }),
  copilotTools: () => request<ToolsResponse>("/copilot/tools"),
  runNarrative: (id: string, locale: "fr" | "en" = "fr") =>
    request<NarrativeResponse>(`/runs/${id}/explanation/narrative`, { method: "POST", body: { locale } }),
  comparisonNarrative: (baseline_run_id: string, run_ids: string[], locale: "fr" | "en" = "fr") =>
    request<NarrativeResponse>("/comparisons/narrative", { method: "POST", body: { baseline_run_id, run_ids, locale } }),
  parseScenarioText: (text: string, target: { dataset_id?: string; scenario_id?: string }) =>
    request<ParseResult>("/scenarios/parse", { method: "POST", body: { text, ...target } }),

  // Reports (frozen snapshots)
  reports: (run_id?: string) => request<Page<ReportSummary>>("/reports", { query: { run_id, page_size: 100 } }),
  report: (id: string) => request<ReportDetail>(`/reports/${id}`),
  createReport: (spec: ReportSpec) => request<ReportDetail>("/reports", { method: "POST", body: spec }),
  deleteReport: (id: string) => request<void>(`/reports/${id}`, { method: "DELETE" }),
};

/** Download URLs (plain links: the browser saves the file). */
export const downloads = {
  reportJson: (id: string) => `${API_V2}/reports/${id}/export.json`,
  reportCsv: (id: string, section: string, table?: string) =>
    `${API_V2}/reports/${id}/export.csv?${new URLSearchParams(table ? { section, table } : { section }).toString()}`,
};

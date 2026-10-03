// Real API responses captured from the backend (template tunisia_olives, scenario "Prix -10 %").
// Regenerate with backend/scripts/capture_frontend_fixtures.py (backend running).
import type {
  BuyersSection,
  ComparisonResult,
  CropsSection,
  FinancialSection,
  LogisticsSection,
  OperationalSection,
  ReportDetail,
  DatasetPayload,
  InsightView,
  MetaResponse,
  NetworkGraph,
  RunExplanation,
  SensitivityReport,
  OptimizationResult,
  RunDetail,
  ScenarioDetail,
  ScenarioPreview,
} from "@/lib/api/types";
import analyticsBuyers from "./olives_analytics_buyers.json";
import analyticsCrops from "./olives_analytics_crops.json";
import analyticsFinancial from "./olives_analytics_financial.json";
import analyticsLogistics from "./olives_analytics_logistics.json";
import analyticsOperational from "./olives_analytics_operational.json";
import comparison from "./olives_comparison.json";
import report from "./olives_report.json";
import explanation from "./olives_explanation.json";
import marginal from "./olives_marginal_values.json";
import network from "./olives_network.json";
import networkDay0 from "./olives_network_day0.json";
import wheatInsights from "./wheat_insights.json";
import meta from "./meta.json";
import payload from "./olives_payload.json";
import preview from "./olives_preview.json";
import result from "./olives_result.json";
import run from "./olives_run.json";
import scenario from "./olives_scenario.json";

export const META = meta as unknown as MetaResponse;
export const OLIVES_PAYLOAD = payload as unknown as DatasetPayload;
export const OLIVES_RUN = run as unknown as RunDetail;
export const OLIVES_RESULT = result as unknown as OptimizationResult;
export const OLIVES_COMPARISON = comparison as unknown as ComparisonResult;
export const OLIVES_SCENARIO = scenario as unknown as ScenarioDetail;
export const OLIVES_PREVIEW = preview as unknown as ScenarioPreview;
export const OLIVES_EXPLANATION = explanation as unknown as RunExplanation;
export const OLIVES_MARGINAL = marginal as unknown as SensitivityReport;
export const OLIVES_NETWORK = network as unknown as NetworkGraph;
export const OLIVES_NETWORK_DAY0 = networkDay0 as unknown as NetworkGraph;
export const WHEAT_INSIGHTS = wheatInsights as unknown as InsightView[];

// Phases 12-13: analytics sections of the reference run, and a frozen report (vs "Prix -10 %").
export const OLIVES_FINANCIAL = analyticsFinancial as unknown as FinancialSection;
export const OLIVES_OPERATIONAL = analyticsOperational as unknown as OperationalSection;
export const OLIVES_BUYERS = analyticsBuyers as unknown as BuyersSection;
export const OLIVES_LOGISTICS = analyticsLogistics as unknown as LogisticsSection;
export const OLIVES_CROPS = analyticsCrops as unknown as CropsSection;
export const OLIVES_REPORT = report as unknown as ReportDetail;

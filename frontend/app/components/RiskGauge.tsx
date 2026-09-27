import { ShieldCheck, ShieldAlert, ShieldX, Recycle } from "lucide-react";
import type { OptimizeResponse } from "@/app/lib/api";

export interface RiskGaugeProps {
  result: OptimizeResponse;
}

export type RiskLevel = "low" | "medium" | "high";

interface RiskConfig {
  label: string;
  icon: typeof ShieldCheck;
  ringColor: string;
  textColor: string;
  glowClass: string;
  badgeClasses: string;
}

export const RISK_CONFIG: Record<RiskLevel, RiskConfig> = {
  low: {
    label: "Low Risk",
    icon: ShieldCheck,
    ringColor: "#10B981",
    textColor: "text-[#10B981]",
    glowClass: "drop-shadow-[0_0_18px_rgba(16,185,129,0.65)]",
    badgeClasses: "bg-[#10B981]/15 border-[#10B981]/30 text-[#10B981]",
  },
  medium: {
    label: "Medium Risk",
    icon: ShieldAlert,
    ringColor: "#f59e0b",
    textColor: "text-amber-400",
    glowClass: "drop-shadow-[0_0_18px_rgba(245,158,11,0.65)]",
    badgeClasses: "bg-amber-500/15 border-amber-500/30 text-amber-400",
  },
  high: {
    label: "High Risk",
    icon: ShieldX,
    ringColor: "#f43f5e",
    textColor: "text-rose-400",
    glowClass: "drop-shadow-[0_0_18px_rgba(244,63,94,0.65)]",
    badgeClasses: "bg-rose-500/15 border-rose-500/30 text-rose-400",
  },
};

export function getRiskLevel(ratio: number): RiskLevel {
  if (ratio < 0.15) return "low";
  if (ratio < 0.3) return "medium";
  return "high";
}

export function getWasteRatio(result: OptimizeResponse): number {
  return result.total_harvest_kg > 0 ? result.wasted_kg / result.total_harvest_kg : 0;
}

const card = "bg-[#131B2E] border border-[#1E293B] rounded-xl p-6";

// Locale-independent "12,000.5" formatting (up to 3 decimals, like en-US) so the
// server render and client hydration always produce identical text.
function formatNumber(value: number): string {
  const rounded = Math.round(value * 1000) / 1000;
  const [integerPart, fractionPart] = Math.abs(rounded).toString().split(".");
  const grouped = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${rounded < 0 ? "-" : ""}${grouped}${fractionPart ? `.${fractionPart}` : ""}`;
}

const RADIUS = 54;
const STROKE_WIDTH = 10;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export default function RiskGauge({ result }: RiskGaugeProps) {
  const ratio = getWasteRatio(result);
  const percent = ratio * 100;
  const clampedPercent = Math.min(100, Math.max(0, percent));
  const level = getRiskLevel(ratio);
  const config = RISK_CONFIG[level];
  const Icon = config.icon;
  // TEMP-DIAG
  console.log("[H2V-DIAG] RiskGauge render", { total_harvest_kg: result.total_harvest_kg, wasted_kg: result.wasted_kg, percent });

  const dashOffset = CIRCUMFERENCE * (1 - clampedPercent / 100);

  return (
    <div className={card}>
      <div className="mb-6 flex items-center gap-2 text-slate-400">
        <Recycle className="h-5 w-5 text-[#10B981]" aria-hidden="true" />
        <span className="text-sm font-semibold uppercase tracking-wider">Waste Risk</span>
      </div>

      <div className="flex flex-col items-center">
        <div className="relative h-40 w-40">
          <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
            <circle
              cx="60"
              cy="60"
              r={RADIUS}
              fill="none"
              stroke="#1E293B"
              strokeWidth={STROKE_WIDTH}
            />
            <circle
              cx="60"
              cy="60"
              r={RADIUS}
              fill="none"
              stroke={config.ringColor}
              strokeWidth={STROKE_WIDTH}
              strokeLinecap="round"
              strokeDasharray={CIRCUMFERENCE}
              strokeDashoffset={dashOffset}
              className="transition-[stroke-dashoffset] duration-500 ease-out"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span
              className={`${config.glowClass} font-mono text-3xl font-bold tabular-nums text-white md:text-4.5xl`}
              aria-hidden="true"
            >
              {percent.toFixed(1)}%
            </span>
            <span className="text-sm font-medium text-slate-400">wasted</span>
          </div>
        </div>

        <div
          role="status"
          className={`mt-6 inline-flex min-h-[44px] items-center gap-2 rounded-full border px-4 py-2 text-lg font-bold ${config.badgeClasses}`}
        >
          <Icon className="h-4 w-4" aria-hidden="true" />
          <span>{config.label}</span>
          <span className="sr-only">
            : {percent.toFixed(1)} percent of harvest wasted (
            {formatNumber(result.wasted_kg)} kg of {formatNumber(result.total_harvest_kg)}{" "}
            kg)
          </span>
        </div>

        <p className={`mt-3 text-center font-mono text-sm font-semibold tabular-nums ${config.textColor}`}>
          {formatNumber(result.wasted_kg)} kg wasted of{" "}
          {formatNumber(result.total_harvest_kg)} kg harvested
        </p>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-2 border-t border-[#1E293B] pt-4 sm:grid-cols-3">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <ShieldCheck className="h-5 w-5 text-[#10B981]" aria-hidden="true" />
          <span>Low: &lt; 15%</span>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <ShieldAlert className="h-5 w-5 text-amber-500" aria-hidden="true" />
          <span>Medium: &lt; 30%</span>
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <ShieldX className="h-5 w-5 text-rose-500" aria-hidden="true" />
          <span>High: &ge; 30%</span>
        </div>
      </div>
    </div>
  );
}

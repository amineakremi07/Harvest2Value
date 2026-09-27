import { ShieldCheck, ShieldAlert, ShieldX, Recycle } from "lucide-react";
import type { OptimizeResponse } from "@/app/lib/api";

export interface RiskGaugeProps {
  result: OptimizeResponse;
}

type RiskLevel = "low" | "medium" | "high";

interface RiskConfig {
  label: string;
  icon: typeof ShieldCheck;
  ringColor: string;
  textColor: string;
  badgeClasses: string;
}

const RISK_CONFIG: Record<RiskLevel, RiskConfig> = {
  low: {
    label: "Low Risk",
    icon: ShieldCheck,
    ringColor: "#10b981", // emerald-500
    textColor: "text-emerald-500",
    badgeClasses: "bg-emerald-950 text-emerald-300 border-emerald-700",
  },
  medium: {
    label: "Medium Risk",
    icon: ShieldAlert,
    ringColor: "#f59e0b", // amber-500
    textColor: "text-amber-500",
    badgeClasses: "bg-amber-950 text-amber-300 border-amber-700",
  },
  high: {
    label: "High Risk",
    icon: ShieldX,
    ringColor: "#f43f5e", // rose-500
    textColor: "text-rose-500",
    badgeClasses: "bg-rose-950 text-rose-300 border-rose-700",
  },
};

function getRiskLevel(ratio: number): RiskLevel {
  if (ratio < 0.05) return "low";
  if (ratio < 0.15) return "medium";
  return "high";
}

const RADIUS = 54;
const STROKE_WIDTH = 12;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export default function RiskGauge({ result }: RiskGaugeProps) {
  const ratio =
    result.total_harvest_kg > 0 ? result.wasted_kg / result.total_harvest_kg : 0;
  const percent = ratio * 100;
  const clampedPercent = Math.min(100, Math.max(0, percent));
  const level = getRiskLevel(ratio);
  const config = RISK_CONFIG[level];
  const Icon = config.icon;

  const dashOffset = CIRCUMFERENCE * (1 - clampedPercent / 100);

  return (
    <div className="rounded-2xl border border-slate-700 bg-slate-900 p-4 shadow-lg md:p-6">
      <h2 className="mb-6 inline-flex items-center gap-2 text-lg font-bold text-slate-100">
        <Recycle className="h-6 w-6 text-emerald-500" aria-hidden="true" />
        <span>Waste Risk</span>
      </h2>

      <div className="flex flex-col items-center">
        <div className="relative h-40 w-40">
          <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
            <circle
              cx="60"
              cy="60"
              r={RADIUS}
              fill="none"
              stroke="#334155" /* slate-700 */
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
              className="font-mono text-4xl font-bold tabular-nums text-slate-100 md:text-5xl"
              aria-hidden="true"
            >
              {percent.toFixed(1)}%
            </span>
            <span className="text-base font-medium text-slate-400">wasted</span>
          </div>
        </div>

        <div
          role="status"
          className={`mt-6 inline-flex min-h-[44px] items-center gap-2 rounded-full border px-4 py-2 text-lg font-bold ${config.badgeClasses}`}
        >
          <Icon className="h-6 w-6" aria-hidden="true" />
          <span>{config.label}</span>
          <span className="sr-only">
            : {percent.toFixed(1)} percent of harvest wasted (
            {result.wasted_kg.toLocaleString()} kg of {result.total_harvest_kg.toLocaleString()}{" "}
            kg)
          </span>
        </div>

        <p className={`mt-3 text-center text-base font-semibold ${config.textColor}`}>
          {result.wasted_kg.toLocaleString()} kg wasted of{" "}
          {result.total_harvest_kg.toLocaleString()} kg harvested
        </p>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-2 border-t border-slate-800 pt-4 sm:grid-cols-3">
        <div className="inline-flex items-center gap-2 text-base text-slate-300">
          <ShieldCheck className="h-5 w-5 text-emerald-500" aria-hidden="true" />
          <span>Low: &lt; 5%</span>
        </div>
        <div className="inline-flex items-center gap-2 text-base text-slate-300">
          <ShieldAlert className="h-5 w-5 text-amber-500" aria-hidden="true" />
          <span>Medium: &lt; 15%</span>
        </div>
        <div className="inline-flex items-center gap-2 text-base text-slate-300">
          <ShieldX className="h-5 w-5 text-rose-500" aria-hidden="true" />
          <span>High: &ge; 15%</span>
        </div>
      </div>
    </div>
  );
}

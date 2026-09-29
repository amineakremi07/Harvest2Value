import type { LucideIcon } from "lucide-react";
import { glassCard } from "@/app/components/styles";

interface KpiCardProps {
  icon: LucideIcon;
  label: string;
  value: string;
  /** Small unit or context shown next to the value, e.g. "t" or "/ 100". */
  suffix?: string;
  /** Left accent bar colour (CSS colour). Defaults to the theme accent. */
  accentColor?: string;
}

export default function KpiCard({ icon: Icon, label, value, suffix, accentColor }: KpiCardProps) {
  return (
    <div
      className={`${glassCard} border-l-4`}
      style={{ borderLeftColor: accentColor ?? "var(--accent)" }}
    >
      <div className="mb-3 flex items-center gap-2 text-text-secondary">
        <Icon className="h-4 w-4" aria-hidden="true" />
        <span className="text-xs font-semibold uppercase tracking-wider">{label}</span>
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="font-mono text-[28px] font-bold tabular-nums text-text-primary">{value}</span>
        {suffix && <span className="font-mono text-sm text-text-secondary">{suffix}</span>}
      </div>
    </div>
  );
}

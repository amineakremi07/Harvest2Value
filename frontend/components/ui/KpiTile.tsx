import type { ReactNode } from "react";
import { cx } from "./primitives";

export function KpiTile({
  label,
  value,
  sub,
  accent = "#10B981",
  delta,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  accent?: string;
  delta?: { text: string; good: boolean | null };
}) {
  return (
    <div className="rounded-xl border border-card-border border-l-4 bg-card-surface px-4 py-3" style={{ borderLeftColor: accent }}>
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{label}</p>
      <p className="mt-1 font-mono text-xl font-bold tabular-nums text-white">{value}</p>
      <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs">
        {delta && (
          <span
            className={cx(
              "font-mono font-semibold",
              delta.good === null ? "text-slate-400" : delta.good ? "text-emerald-300" : "text-rose-300",
            )}
          >
            {delta.text}
          </span>
        )}
        {sub && <span className="text-slate-500">{sub}</span>}
      </div>
    </div>
  );
}

import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import type { DeltaValue } from "@/types";

const QUALITY_CLASS: Record<DeltaValue["quality"], string> = {
  good: "bg-success/15 text-success",
  bad: "bg-danger/15 text-danger",
  neutral: "bg-text-secondary/15 text-text-secondary",
};

const DIRECTION_WORD = { up: "up", down: "down", flat: "unchanged" } as const;

/** Period-over-period change. Colour reflects good/bad, the arrow reflects direction. */
export default function DeltaBadge({ label, delta }: { label: string; delta: DeltaValue }) {
  const Icon = delta.direction === "up" ? ArrowUp : delta.direction === "down" ? ArrowDown : Minus;
  const text = delta.pct === null ? "—" : `${Math.abs(delta.pct).toFixed(1)}%`;
  const spoken =
    delta.pct === null
      ? `${label}: no previous period`
      : `${label}: ${DIRECTION_WORD[delta.direction]} ${text}, ${delta.quality}`;

  return (
    <span
      aria-label={spoken}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-xs font-semibold tabular-nums ${QUALITY_CLASS[delta.quality]}`}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {text}
    </span>
  );
}

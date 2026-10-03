import { KpiTile } from "@/components/ui/KpiTile";
import { fmtKg, fmtMoney, fmtPct, fmtSigned } from "@/lib/format";
import type { Delta, Kpis } from "@/lib/api/types";

type Better = "higher" | "lower";

const TILES: { key: keyof Kpis; label: string; format: (v: number | null) => string; better: Better; accent: string }[] = [
  { key: "realized_profit", label: "Profit réalisé", format: (v) => fmtMoney(v), better: "higher", accent: "#10B981" },
  { key: "realized_revenue", label: "Chiffre d'affaires", format: (v) => fmtMoney(v), better: "higher", accent: "#06B6D4" },
  { key: "sold_kg", label: "Vendu", format: fmtKg, better: "higher", accent: "#38BDF8" },
  { key: "waste_rate_pct", label: "Taux de pertes", format: fmtPct, better: "lower", accent: "#F43F5E" },
  { key: "total_cost", label: "Coûts totaux", format: (v) => fmtMoney(v), better: "lower", accent: "#F59E0B" },
];

export function deltaBadge(delta: Delta | undefined, better: Better): { text: string; good: boolean | null } | undefined {
  if (!delta || delta.abs == null) return undefined;
  const text = delta.pct != null ? fmtSigned(delta.pct, " %") : fmtSigned(delta.abs);
  if (delta.abs === 0) return { text, good: null };
  return { text, good: better === "higher" ? delta.abs > 0 : delta.abs < 0 };
}

export function ExecutiveKpis({ kpis, deltas, hasBaseline }: { kpis: Kpis; deltas: Record<string, Delta>; hasBaseline: boolean }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5" aria-label="Indicateurs exécutifs">
      {TILES.map((t) => {
        const value = kpis[t.key];
        return (
          <KpiTile
            key={t.key}
            label={t.label}
            value={t.format(typeof value === "number" ? value : null)}
            accent={t.accent}
            delta={deltaBadge(deltas[t.key], t.better)}
            sub={hasBaseline && deltas[t.key] ? "vs référence" : undefined}
          />
        );
      })}
    </div>
  );
}

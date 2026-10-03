import { Badge } from "@/components/ui/primitives";
import { InfoTip } from "@/components/ui/InfoTip";
import { fmtSigned } from "@/lib/format";
import type { MarginalValue } from "@/lib/api/types";
import { DUAL_TOOLTIP, PROBE_TOOLTIP } from "./labels";

/** Probes (exact re-optimization) first, then duals; the first probe is the headline value. */
export function sortMarginalValues(values: MarginalValue[]): { probes: MarginalValue[]; duals: MarginalValue[] } {
  const probes = values.filter((v) => v.kind === "probe").sort((a, b) => Math.abs(b.delta_objective) - Math.abs(a.delta_objective));
  const duals = values.filter((v) => v.kind === "dual");
  return { probes, duals };
}

/**
 * The perturbation (measured effect of a real change, re-optimized) is the main value; the dual
 * value is shown as a "local indicator" with a tooltip on its limits.
 */
export function MarginalValues({ values, currency = "TND" }: { values: MarginalValue[]; currency?: string }) {
  const { probes, duals } = sortMarginalValues(values);
  if (probes.length === 0 && duals.length === 0) return null;
  return (
    <div className="space-y-2" data-testid="marginal-values">
      {probes.map((p, i) => (
        <div key={`p-${i}`} className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2">
          <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-emerald-300">
            Effet mesuré <InfoTip label="À propos de l'effet mesuré">{PROBE_TOOLTIP}</InfoTip>
          </p>
          <p className="mt-1 text-sm text-slate-200">
            {p.label} :{" "}
            <span className="font-mono text-lg font-bold text-white" data-kind="probe">
              {fmtSigned(p.delta_objective)} {currency}
            </span>{" "}
            {!p.reliable && <Badge>non significatif</Badge>}
          </p>
        </div>
      ))}
      {duals.map((d, i) => (
        <p key={`d-${i}`} className="flex flex-wrap items-center gap-1 text-xs text-slate-400">
          <span className="font-semibold">Indicateur local</span>
          <InfoTip label="Limites de l'indicateur local">{DUAL_TOOLTIP}</InfoTip>: {d.label} ≈{" "}
          <span className="font-mono" data-kind="dual">
            {fmtSigned(d.delta_objective)} {currency}
          </span>
        </p>
      ))}
    </div>
  );
}

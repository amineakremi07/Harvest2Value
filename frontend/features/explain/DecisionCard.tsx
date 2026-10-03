import { ArrowRightLeft, Ban, CircleHelp, Package, Trash2, Users } from "lucide-react";
import { Badge } from "@/components/ui/primitives";
import { fmtKg, fmtMoney, fmtNum, fmtPct } from "@/lib/format";
import type { DecisionCard as DecisionCardData } from "@/lib/api/types";
import { LIMITING_LABEL } from "./labels";
import { MarginalValues } from "./MarginalValues";

type Metrics = DecisionCardData["metrics"];

function num(metrics: Metrics, key: string): number | null {
  const v = metrics[key];
  return typeof v === "number" ? v : null;
}

/** "Pourquoi" lines of a buyer card, from the backend metrics. */
export function buyerWhy(metrics: Metrics, currency?: string): string[] {
  const lines: string[] = [];
  const net = num(metrics, "net_price_per_kg");
  const estimated = num(metrics, "estimated_net_price_per_kg");
  const rank = num(metrics, "market_rank");
  if (net !== null) lines.push(`Prix net obtenu : ${fmtNum(net)} ${currency ?? "TND"}/kg (après transport).`);
  else if (estimated !== null) lines.push(`Prix net estimé : ${fmtNum(estimated)} ${currency ?? "TND"}/kg.`);
  if (rank !== null) lines.push(`Rang n°${rank} du marché par prix net estimé.`);
  const fulfillment = num(metrics, "fulfillment_pct");
  const max = num(metrics, "max_demand_kg");
  if (fulfillment !== null && max !== null) lines.push(`Demande servie : ${fmtPct(fulfillment)} de ${fmtKg(max)}.`);
  return lines;
}

const ICON = { buyer: Users, storage: Package, waste: Trash2 } as const;

export function DecisionCard({ card, currency }: { card: DecisionCardData; currency?: string }) {
  const Icon = ICON[card.kind];
  const m = card.metrics;
  const served = card.kind !== "buyer" || (num(m, "sold_kg") ?? 0) > 0;

  return (
    <article
      className="flex flex-col gap-3 rounded-xl border border-card-border bg-card-surface p-4"
      aria-label={`Décision : ${card.name}`}
      data-testid={`decision-${card.kind}-${card.entity_id}`}
    >
      <header className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-emerald-accent" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-white">{card.name}</h3>
        </div>
        <Badge tone={served ? "success" : "neutral"}>{card.decision}</Badge>
      </header>

      {card.kind === "buyer" && (
        <>
          <section aria-label="Pourquoi">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Pourquoi</h4>
            <ul className="mt-1 space-y-0.5 text-sm text-slate-300">
              {buyerWhy(m, currency).map((l) => (
                <li key={l}>{l}</li>
              ))}
              {num(m, "revenue") !== null && served && (
                <li>
                  Revenu {fmtMoney(num(m, "revenue"), currency)}, transport {fmtMoney(num(m, "transport_cost"), currency)}.
                </li>
              )}
            </ul>
          </section>
          <section aria-label={served ? "Pourquoi pas plus" : "Pourquoi pas servi"}>
            <h4 className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-slate-400">
              {served ? <CircleHelp className="h-3.5 w-3.5" aria-hidden="true" /> : <Ban className="h-3.5 w-3.5" aria-hidden="true" />}
              {served ? "Pourquoi pas plus" : "Pourquoi pas servi"}
            </h4>
            {card.limiting_factor ? (
              <p className="mt-1 text-sm text-slate-200">
                <Badge tone="warning">{LIMITING_LABEL[card.limiting_factor.code]}</Badge> {card.limiting_factor.message}
              </p>
            ) : (
              <p className="mt-1 text-sm text-slate-400">Aucune limite active.</p>
            )}
          </section>
        </>
      )}

      {card.kind === "storage" && (
        <p className="text-sm text-slate-300">
          {fmtKg(num(m, "stored_kg"))} stockés · capacité {fmtKg(num(m, "capacity_kg"))} · pic {fmtPct(num(m, "peak_pct"))} · coût{" "}
          {fmtMoney(num(m, "cost"), currency)}
          {card.limiting_factor && <span className="block text-amber-200">{card.limiting_factor.message}</span>}
        </p>
      )}

      {card.kind === "waste" && (
        <p className="text-sm text-slate-300">
          {fmtKg(num(m, "lost_kg"))} perdus ({fmtPct(num(m, "waste_rate_pct"))}), valeur {fmtMoney(num(m, "lost_value"), currency)}.
        </p>
      )}

      {card.alternative && (
        <p className="flex items-start gap-2 text-xs text-slate-400">
          <ArrowRightLeft className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {card.alternative.message}
        </p>
      )}

      <MarginalValues values={card.marginal_values ?? []} currency={currency} />
    </article>
  );
}

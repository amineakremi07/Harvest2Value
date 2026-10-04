"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Card, cx, EmptyState, ErrorBanner, Field, inputClass, Loading, numClass, PageHeader, Table, tdClass, thClass } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { useApi } from "@/lib/hooks/useApi";
import type { BuyersSection, CropsSection, FinancialSection, LogisticsSection, OperationalSection, RunSummary } from "@/lib/api/types";
import { DEFAULT_CURRENCY, fmtDate, fmtSigned, fmtUnit, shortId } from "@/lib/format";
import { BuyersPanel, CropPanel, FinancialPanel, LogisticsPanel, OperationalPanel, SECTIONS, type SectionKey } from "./sections";

type SectionData = {
  financial: FinancialSection;
  operational: OperationalSection;
  buyers: BuyersSection;
  logistics: LogisticsSection;
  crops: CropsSection;
};

const LOADERS: { [K in SectionKey]: (runId: string) => Promise<SectionData[K]> } = {
  financial: (id) => api.financial(id),
  operational: (id) => api.operational(id),
  buyers: (id) => api.buyers(id),
  logistics: (id) => api.runLogistics(id),
  crops: (id) => api.crops(id),
};

export type Headline = { key: string; label: string; value: number | null; unit: string; better: "up" | "down" };

/** The figures compared between two runs for each section (values straight from the API). */
export function headlines<K extends SectionKey>(key: K, data: SectionData[K]): Headline[] {
  switch (key) {
    case "financial": {
      const d = data as FinancialSection;
      return [
        { key: "realized_profit", label: "Profit réalisé", value: d.realized_profit, unit: "currency", better: "up" },
        { key: "realized_revenue", label: "Chiffre d'affaires", value: d.realized_revenue, unit: "currency", better: "up" },
        { key: "total_cost", label: "Coûts totaux", value: d.costs.total, unit: "currency", better: "down" },
        { key: "lost_value", label: "Valeur perdue", value: d.lost_value, unit: "currency", better: "down" },
      ];
    }
    case "operational": {
      const d = data as OperationalSection;
      return [
        { key: "sold_kg", label: "Vendu", value: d.sold_kg, unit: "kg", better: "up" },
        { key: "lost_kg", label: "Pertes", value: d.lost_kg, unit: "kg", better: "down" },
        { key: "waste_rate_pct", label: "Taux de perte", value: d.rates.waste_rate_pct, unit: "%", better: "down" },
        { key: "fulfillment_rate_pct", label: "Demande servie", value: d.rates.fulfillment_rate_pct ?? null, unit: "%", better: "up" },
      ];
    }
    case "buyers": {
      const d = data as BuyersSection;
      return d.buyers.map((b) => ({ key: b.buyer_id, label: `Vendu à ${b.buyer_name}`, value: b.sold_kg, unit: "kg", better: "up" as const }));
    }
    case "logistics": {
      const d = data as LogisticsSection;
      return [
        { key: "trips", label: "Trajets", value: d.trips, unit: "trajets", better: "down" },
        { key: "transport_cost", label: "Coût du transport", value: d.transport_cost, unit: "currency", better: "down" },
        { key: "cost_per_kg", label: "Coût par kg", value: d.cost_per_kg ?? null, unit: "currency/kg", better: "down" },
        { key: "load_factor_pct", label: "Remplissage", value: d.load_factor_pct ?? null, unit: "%", better: "up" },
      ];
    }
    case "crops": {
      const d = data as CropsSection;
      const sold = d.lots.reduce((s, l) => s + l.sold_kg, 0);
      const lost = d.lots.reduce((s, l) => s + l.lost_kg, 0);
      return [
        { key: "lots_sold_kg", label: "Lots vendus", value: sold, unit: "kg", better: "up" },
        { key: "lots_lost_kg", label: "Lots perdus", value: lost, unit: "kg", better: "down" },
      ];
    }
    default:
      return [];
  }
}

function runName(run: RunSummary | undefined, id: string): string {
  return run?.label || `Exécution ${shortId(id)}`;
}

function useSection<K extends SectionKey>(key: K, runId: string | null) {
  return useApi<SectionData[K]>(runId ? () => LOADERS[key](runId) : null, [key, runId]);
}

function SectionBody<K extends SectionKey>({ section, data, currency }: { section: K; data: SectionData[K]; currency: string }) {
  switch (section) {
    case "financial":
      return <FinancialPanel data={data as FinancialSection} currency={currency} />;
    case "operational":
      return <OperationalPanel data={data as OperationalSection} />;
    case "buyers":
      return <BuyersPanel data={data as BuyersSection} currency={currency} />;
    case "logistics":
      return <LogisticsPanel data={data as LogisticsSection} currency={currency} />;
    default:
      return <CropPanel data={data as CropsSection} currency={currency} />;
  }
}

function ComparedHeadlines({ base, other, baseLabel, otherLabel, currency }: { base: Headline[]; other: Headline[]; baseLabel: string; otherLabel: string; currency: string }) {
  const keys = [...new Set([...base, ...other].map((h) => h.key))];
  return (
    <Card title="Écarts">
      <Table label="Écarts entre les deux exécutions">
        <thead>
          <tr>
            <th className={thClass}>Indicateur</th>
            <th className={`${thClass} ${numClass}`}>{baseLabel}</th>
            <th className={`${thClass} ${numClass}`}>{otherLabel}</th>
            <th className={`${thClass} ${numClass}`}>Écart</th>
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => {
            const a = base.find((h) => h.key === k);
            const b = other.find((h) => h.key === k);
            const h = (a ?? b) as Headline;
            const delta = a?.value != null && b?.value != null ? b.value - a.value : null;
            const good = delta == null || Math.abs(delta) < 1e-9 ? null : (delta > 0) === (h.better === "up");
            return (
              <tr key={k}>
                <td className={tdClass}>{h.label}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtUnit(a?.value, h.unit, currency)}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtUnit(b?.value, h.unit, currency)}</td>
                <td className={cx(tdClass, numClass, good === null ? "text-slate-400" : good ? "text-emerald-300" : "text-rose-300")}>
                  {fmtSigned(delta)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </Table>
    </Card>
  );
}

/** Analytics Center: five sections for one run, optionally side by side with a second run. */
export function AnalyticsCenter({ initialRun, initialCompare }: { initialRun?: string; initialCompare?: string }) {
  const router = useRouter();
  const runs = useApi(() => api.runs({ status: "succeeded", page_size: 100 }), []);
  const [section, setSection] = useState<SectionKey>("financial");
  const [chosenRun, setChosenRun] = useState<string | null>(initialRun ?? null);
  const [compareId, setCompareId] = useState<string | null>(initialCompare ?? null);
  const items = runs.data?.items ?? [];
  const runId = chosenRun ?? items[0]?.id ?? null;

  const main = useSection(section, runId);
  const other = useSection(section, compareId && compareId !== runId ? compareId : null);
  const money = useSection("financial", runId);
  const currency = money.data?.currency ?? DEFAULT_CURRENCY;

  const update = (run: string | null, compare: string | null) => {
    setChosenRun(run);
    setCompareId(compare);
    const params = new URLSearchParams();
    if (run) params.set("run", run);
    if (compare) params.set("compare", compare);
    router.replace(`/analytics${params.size ? `?${params.toString()}` : ""}`);
  };

  const byId = (id: string | null) => items.find((r) => r.id === id);
  const comparing = compareId !== null && compareId !== runId;

  return (
    <>
      <PageHeader title="Analyses" subtitle="Financier, opérationnel, acheteurs, logistique et culture d'une exécution — seule ou face à une autre." />
      {runs.loading && !runs.data ? (
        <Loading />
      ) : runs.error ? (
        <ErrorBanner message={errorMessage(runs.error)} onRetry={runs.reload} />
      ) : items.length === 0 ? (
        <EmptyState title="Aucune exécution terminée.">Lancez une optimisation pour obtenir des analyses.</EmptyState>
      ) : (
        <div className="space-y-6">
          <Card>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2" role="group" aria-label="Filtre des exécutions">
              <Field label="Exécution" htmlFor="analytics-run">
                <select id="analytics-run" className={inputClass} value={runId ?? ""} onChange={(e) => update(e.target.value, compareId === e.target.value ? null : compareId)}>
                  {items.map((r) => (
                    <option key={r.id} value={r.id}>
                      {runName(r, r.id)} · {fmtDate(r.created_at)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Comparer avec" htmlFor="analytics-compare" hint="Vue comparée : les deux exécutions côte à côte.">
                <select id="analytics-compare" className={inputClass} value={compareId ?? ""} onChange={(e) => update(runId, e.target.value || null)}>
                  <option value="">— Aucune —</option>
                  {items
                    .filter((r) => r.id !== runId)
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        {runName(r, r.id)} · {fmtDate(r.created_at)}
                      </option>
                    ))}
                </select>
              </Field>
            </div>
          </Card>

          <div role="tablist" aria-label="Sections d'analyse" className="flex flex-wrap gap-1 border-b border-card-border">
            {SECTIONS.map((s) => (
              <button
                key={s.key}
                type="button"
                role="tab"
                aria-selected={section === s.key}
                onClick={() => setSection(s.key)}
                className={cx(
                  "border-b-2 px-3 py-2 text-sm font-semibold",
                  section === s.key ? "border-emerald-accent text-white" : "border-transparent text-slate-400 hover:text-slate-200",
                )}
              >
                {s.label}
              </button>
            ))}
          </div>

          <div role="tabpanel" aria-label={SECTIONS.find((s) => s.key === section)?.label}>
            {main.error ? (
              <ErrorBanner message={errorMessage(main.error)} onRetry={main.reload} />
            ) : !main.data || main.loading ? (
              <Loading />
            ) : comparing ? (
              <div className="space-y-6">
                {other.data && !other.loading ? (
                  <ComparedHeadlines
                    base={headlines(section, main.data)}
                    other={headlines(section, other.data)}
                    baseLabel={runName(byId(runId), runId as string)}
                    otherLabel={runName(byId(compareId), compareId as string)}
                    currency={currency}
                  />
                ) : other.error ? (
                  <ErrorBanner message={errorMessage(other.error)} onRetry={other.reload} />
                ) : (
                  <Loading />
                )}
                <div className="grid grid-cols-1 gap-6 2xl:grid-cols-2">
                  <section aria-label={`Analyse : ${runName(byId(runId), runId as string)}`}>
                    <h2 className="mb-3 text-sm font-semibold text-slate-300">{runName(byId(runId), runId as string)}</h2>
                    <SectionBody section={section} data={main.data} currency={currency} />
                  </section>
                  {other.data && !other.loading && (
                    <section aria-label={`Analyse : ${runName(byId(compareId), compareId as string)}`}>
                      <h2 className="mb-3 text-sm font-semibold text-slate-300">{runName(byId(compareId), compareId as string)}</h2>
                      <SectionBody section={section} data={other.data} currency={currency} />
                    </section>
                  )}
                </div>
              </div>
            ) : (
              <SectionBody section={section} data={main.data} currency={currency} />
            )}
          </div>
        </div>
      )}
    </>
  );
}

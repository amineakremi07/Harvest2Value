import type { ReactNode } from "react";
import type { ReportSection } from "@/lib/api/types";
import { fmtDate, fmtKg, fmtMoney, fmtNum, fmtPct, fmtUnit } from "@/lib/format";
import { splitVerified } from "@/features/copilot/VerifiedText";

/** Section -> exportable tables (same as backend `services/reports.py::TABLES`). */
export const REPORT_TABLES: Record<ReportSection, { table: string; path: string; label: string }[]> = {
  summary: [{ table: "kpis", path: "kpis", label: "Indicateurs" }],
  financial: [
    { table: "by_buyer", path: "by_buyer", label: "Par acheteur" },
    { table: "daily", path: "daily", label: "Par jour" },
    { table: "waterfall", path: "waterfall", label: "Du chiffre d'affaires au profit" },
  ],
  operational: [
    { table: "daily", path: "daily", label: "Flux par jour" },
    { table: "storage", path: "storage", label: "Stockage" },
  ],
  buyers: [{ table: "buyers", path: "buyers", label: "Acheteurs" }],
  logistics: [
    { table: "vehicles", path: "vehicles", label: "Véhicules" },
    { table: "routes", path: "routes", label: "Routes" },
    { table: "daily", path: "daily", label: "Trajets par jour" },
  ],
  crops: [{ table: "lots", path: "lots", label: "Lots" }],
  insights: [{ table: "insights", path: "items", label: "Alertes" }],
  comparison: [
    { table: "kpis", path: "kpi_rows", label: "Indicateurs comparés" },
    { table: "buyers", path: "buyer_rows", label: "Acheteurs comparés" },
    { table: "notable_changes", path: "notable_changes", label: "Changements notables" },
  ],
};

export const SECTION_LABEL: Record<ReportSection, string> = {
  summary: "Synthèse",
  financial: "Financier",
  operational: "Opérationnel",
  buyers: "Acheteurs",
  logistics: "Logistique",
  crops: "Culture",
  insights: "Alertes",
  comparison: "Comparaison",
};

export const SECTION_ORDER: ReportSection[] = ["summary", "financial", "operational", "buyers", "logistics", "crops", "insights", "comparison"];

const COLUMN_LABEL: Record<string, string> = {
  kpi: "Indicateur",
  value: "Valeur",
  label: "Libellé",
  unit: "Unité",
  better: "Meilleur si",
  buyer_id: "Id acheteur",
  buyer_name: "Acheteur",
  name: "Nom",
  day: "Jour",
  revenue: "Revenu",
  net_revenue: "Revenu net",
  transport_cost: "Transport",
  storage_cost: "Stockage",
  disposal_cost: "Élimination",
  share_of_revenue_pct: "Part du CA",
  share_of_sales_pct: "Part des ventes",
  sold_kg: "Vendu",
  lost_kg: "Perdu",
  stock_end_kg: "Stock fin de jour",
  price_per_kg: "Prix",
  net_price_per_kg: "Prix net",
  estimated_net_price_per_kg: "Prix net estimé",
  fulfillment_pct: "Demande servie",
  market_rank: "Rang",
  distance_km: "Distance (km)",
  max_demand_kg: "Demande max.",
  location: "Lieu",
  served_days: "Jours servis",
  trips: "Trajets",
  cost: "Coût",
  hours: "Heures",
  utilization_pct: "Utilisation",
  binding_days: "Jours saturés",
  delivered_kg: "Livré",
  cost_per_kg: "Coût / kg",
  lot_id: "Lot",
  available_day: "Disponible (jour)",
  quantity_kg: "Quantité",
  ending_kg: "Restant",
  severity: "Gravité",
  category: "Catégorie",
  rule_id: "Règle",
  message: "Message",
  run: "Exécution",
  kind: "Type",
  capacity_kg: "Capacité",
  stored_kg: "Stocké",
  peak_kg: "Pic",
  peak_pct: "Pic %",
  avg_pct: "Moyenne %",
};

type Row = Record<string, unknown>;

export function columnsOf(rows: Row[]): string[] {
  const out: string[] = [];
  for (const row of rows) for (const key of Object.keys(row)) if (!out.includes(key)) out.push(key);
  return out;
}

/** A frozen cell, formatted from its column name (the snapshot stores raw values). */
export function formatCell(column: string, value: unknown, currency: string): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "oui" : "non";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  if (typeof value !== "number") return String(value);
  const c = column.toLowerCase();
  if (c.includes("δ %") || c.endsWith("_pct") || c.endsWith("pct")) return fmtPct(value);
  if (c.includes("per_kg") || c.includes("price") || c.includes("/ kg")) return fmtUnit(value, "currency/kg", currency);
  if (c.endsWith("_kg") || c.endsWith(" kg") || c.includes("kg")) return fmtKg(value);
  if (["revenue", "cost", "profit", "value", "disposal", "storage", "transport"].some((w) => c.includes(w))) return fmtMoney(value, currency);
  return fmtNum(value);
}

/** Cell text: Δ % columns, KPI rows (unit from the KPI name or the row's `unit`), else by column. */
export function cellText(row: Row, column: string, currency: string): string {
  const value = row[column];
  if (typeof value === "number") {
    if (column.includes("Δ %")) return fmtPct(value);
    if (column === "value" && typeof row.kpi === "string") return formatCell(row.kpi, value, currency);
    if (typeof row.unit === "string" && column !== "unit") return fmtUnit(value, row.unit, currency);
  }
  return formatCell(column, value, currency);
}

export function SnapshotTable({ rows, label, currency }: { rows: Row[]; label: string; currency: string }) {
  if (rows.length === 0) return <p className="text-sm text-slate-500 print:text-slate-600">Aucune ligne.</p>;
  const columns = columnsOf(rows);
  return (
    <div className="overflow-x-auto">
      <table aria-label={label} className="report-table w-full border-collapse text-left text-sm">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c} className="border-b border-card-border px-2 py-1.5 text-xs font-semibold text-slate-400 print:border-slate-300 print:text-slate-600">
                {COLUMN_LABEL[c] ?? c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td
                  key={c}
                  className={`border-b border-card-border/60 px-2 py-1 print:border-slate-200 ${typeof row[c] === "number" ? "text-right font-mono tabular-nums" : ""}`}
                >
                  {cellText(row, c, currency)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export interface Snapshot {
  title: string;
  generated_at: string;
  currency: string;
  run: Record<string, unknown> & { id: string; label?: string | null; dataset_name?: string | null; version_no?: number | null; scenario_name?: string | null; producer?: string | null; region?: string | null; objective?: string };
  compared_runs: { id: string; label: string | null }[];
  sections: Partial<Record<ReportSection, Record<string, unknown>>>;
  narrative: { status: "ok" | "unavailable"; text?: string; reason?: string; model?: string } | null;
}

export function asSnapshot(value: Record<string, unknown>): Snapshot {
  return value as unknown as Snapshot;
}

export function rowsAt(section: Record<string, unknown> | undefined, path: string): Row[] {
  const value = section?.[path];
  return Array.isArray(value) ? (value as Row[]) : [];
}

/**
 * The frozen report: everything comes from the snapshot stored at creation. Shared by the screen
 * view and the print page; `tableActions` adds the CSV links on screen.
 */
export function ReportDocument({ snapshot, hash, tableActions }: { snapshot: Snapshot; hash?: string; tableActions?: (section: ReportSection, table: string) => ReactNode }) {
  const run = snapshot.run;
  const sections = SECTION_ORDER.filter((s) => snapshot.sections[s] !== undefined);
  return (
    <article aria-label={`Rapport : ${snapshot.title}`} className="report-document space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold">{snapshot.title}</h1>
        <p className="text-sm text-slate-400 print:text-slate-600">
          Copie figée le {fmtDate(snapshot.generated_at)} · {run.label || "Exécution"} · données « {run.dataset_name ?? "—"} » v{run.version_no ?? "?"}
          {run.scenario_name ? ` · scénario « ${run.scenario_name} »` : ""}
          {run.producer ? ` · ${run.producer}${run.region ? ` (${run.region})` : ""}` : ""}
        </p>
        {snapshot.compared_runs.length > 0 && (
          <p className="text-sm text-slate-400 print:text-slate-600">Comparée à : {snapshot.compared_runs.map((r) => r.label || r.id.slice(0, 8)).join(", ")}</p>
        )}
        {hash && <p className="font-mono text-[10px] text-slate-600">Empreinte : {hash}</p>}
      </header>

      {snapshot.narrative && (
        <section aria-label="Récit" className="report-section rounded-xl border border-card-border p-4 print:border-slate-300">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-300 print:text-slate-700">Récit</h2>
          {snapshot.narrative.status === "ok" && snapshot.narrative.text ? (
            <p className="whitespace-pre-wrap text-sm">
              {splitVerified(snapshot.narrative.text).map((s, i) =>
                s.unverified ? (
                  <mark key={i} data-unverified="true" className="bg-amber-200/30">
                    {s.text}
                  </mark>
                ) : (
                  <span key={i}>{s.text}</span>
                ),
              )}
            </p>
          ) : (
            <p className="text-sm text-slate-400">Récit indisponible : {snapshot.narrative.reason ?? "IA désactivée"}.</p>
          )}
        </section>
      )}

      {sections.map((section) => {
        const data = snapshot.sections[section];
        return (
          <section key={section} aria-label={SECTION_LABEL[section]} className="report-section space-y-3 rounded-xl border border-card-border p-4 print:border-slate-300">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 print:text-slate-700">{SECTION_LABEL[section]}</h2>
            {section === "summary" && data && (
              <p className="text-sm">
                {String(data.outcome_label ?? "")} · objectif {String(data.objective ?? "")} · horizon {String(data.horizon_days ?? "")} j
              </p>
            )}
            {REPORT_TABLES[section].map((t) => (
              <div key={t.table} className="space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold text-slate-400 print:text-slate-600">{t.label}</h3>
                  {tableActions?.(section, t.table)}
                </div>
                <SnapshotTable rows={rowsAt(data, t.path)} label={`${SECTION_LABEL[section]} — ${t.label}`} currency={snapshot.currency} />
              </div>
            ))}
          </section>
        );
      })}
    </article>
  );
}

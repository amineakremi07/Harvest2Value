import { KpiTile } from "@/components/ui/KpiTile";
import { fmtKg, fmtMoney, fmtNum, fmtPct } from "@/lib/format";
import type { Kpis } from "@/lib/api/types";

/** Headline KPIs of a finished run. Realized profit and ending-stock value are kept separate. */
export function RunKpis({ kpis, currency }: { kpis: Kpis; currency?: string }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5" aria-label="Indicateurs clés">
      <KpiTile label="Profit réalisé" value={fmtMoney(kpis.realized_profit, currency)} sub={`Marge ${fmtPct(kpis.margin_pct)}`} />
      <KpiTile label="Chiffre d'affaires" value={fmtMoney(kpis.realized_revenue, currency)} accent="#06B6D4" />
      <KpiTile
        label="Coûts"
        value={fmtMoney(kpis.total_cost, currency)}
        sub={`Transport ${fmtMoney(kpis.transport_cost, currency)} · Stockage ${fmtMoney(kpis.storage_cost, currency)}`}
        accent="#F59E0B"
      />
      <KpiTile label="Vendu" value={fmtKg(kpis.sold_kg)} sub={`${fmtPct(kpis.sold_rate_pct)} de ${fmtKg(kpis.harvest_kg)}`} />
      <KpiTile label="Pertes" value={fmtKg(kpis.lost_kg)} sub={`Taux ${fmtPct(kpis.waste_rate_pct)}`} accent="#F43F5E" />
      <KpiTile
        label="Stock final"
        value={fmtKg(kpis.ending_inventory_kg)}
        sub={`Valeur ${fmtMoney(kpis.ending_inventory_value, currency)}`}
        accent="#A78BFA"
      />
      <KpiTile
        label="Valeur économique"
        value={fmtMoney(kpis.economic_value, currency)}
        sub="Profit + valeur du stock (pas un profit)"
        accent="#A78BFA"
      />
      <KpiTile label="Demande servie" value={fmtPct(kpis.fulfillment_rate_pct)} accent="#06B6D4" />
      <KpiTile label="Trajets" value={fmtNum(kpis.trips)} sub={`Remplissage ${fmtPct(kpis.load_factor_pct)}`} accent="#38BDF8" />
      <KpiTile
        label="Passé en stockage"
        value={fmtPct(kpis.storage_rate_pct)}
        sub={`Pic ${fmtPct(kpis.storage_utilization_peak_pct)}`}
        accent="#F59E0B"
      />
    </div>
  );
}

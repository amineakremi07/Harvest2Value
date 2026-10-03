"use client";

import { StackedTimeline } from "@/components/charts/StackedTimeline";
import { CHART } from "@/components/charts/theme";
import { WaterfallChart, type WaterfallStep } from "@/components/charts/WaterfallChart";
import { KpiTile } from "@/components/ui/KpiTile";
import { Badge, Card, numClass, Table, tdClass, thClass, type Tone } from "@/components/ui/primitives";
import type { BuyersSection, CropsSection, FinancialSection, LogisticsSection, OperationalSection } from "@/lib/api/types";
import { fmtKg, fmtMoney, fmtNum, fmtPct, fmtUnit } from "@/lib/format";

export type SectionKey = "financial" | "operational" | "buyers" | "logistics" | "crops";

export const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: "financial", label: "Financier" },
  { key: "operational", label: "Opérationnel" },
  { key: "buyers", label: "Acheteurs" },
  { key: "logistics", label: "Logistique" },
  { key: "crops", label: "Culture" },
];

/** Backend waterfall (start / decrease / total) -> chart steps (total / delta). */
export function financialSteps(section: FinancialSection): WaterfallStep[] {
  const label: Record<string, string> = { "Realized revenue": "Chiffre d'affaires", Transport: "Transport", Storage: "Stockage", Disposal: "Élimination", "Realized profit": "Profit réalisé" };
  return section.waterfall.map((s) => ({ label: label[s.label] ?? s.label, kind: s.kind === "decrease" ? "delta" : "total", value: s.value }));
}

function Tiles({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-3 md:grid-cols-3">{children}</div>;
}

export function FinancialPanel({ data, currency }: { data: FinancialSection; currency: string }) {
  const c = data.currency ?? currency;
  return (
    <div className="space-y-4">
      <Tiles>
        <KpiTile label="Profit réalisé" value={fmtMoney(data.realized_profit, c)} sub={data.margin_pct != null ? `marge ${fmtPct(data.margin_pct)}` : undefined} />
        <KpiTile label="Chiffre d'affaires" value={fmtMoney(data.realized_revenue, c)} accent="#38BDF8" />
        <KpiTile label="Coûts totaux" value={fmtMoney(data.costs.total, c)} accent="#F59E0B" />
        <KpiTile label="Valeur économique" value={fmtMoney(data.economic_value, c)} sub="profit + stock final" accent="#A78BFA" />
        <KpiTile label="Valeur du stock final" value={fmtMoney(data.ending_inventory_value, c)} accent="#A78BFA" />
        <KpiTile label="Valeur perdue" value={fmtMoney(data.lost_value, c)} accent="#F43F5E" />
      </Tiles>
      <Card title="Du chiffre d'affaires au profit">
        <WaterfallChart steps={financialSteps(data)} ariaLabel="Passage du chiffre d'affaires au profit réalisé" formatValue={(v) => fmtMoney(v, c)} height={240} />
      </Card>
      <Card title="Par acheteur">
        <Table label="Revenus par acheteur">
          <thead>
            <tr>
              <th className={thClass}>Acheteur</th>
              <th className={`${thClass} ${numClass}`}>Revenu</th>
              <th className={`${thClass} ${numClass}`}>Transport</th>
              <th className={`${thClass} ${numClass}`}>Revenu net</th>
              <th className={`${thClass} ${numClass}`}>Part du CA</th>
            </tr>
          </thead>
          <tbody>
            {data.by_buyer.map((b) => (
              <tr key={b.buyer_id}>
                <td className={tdClass}>{b.buyer_name}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtMoney(b.revenue, c)}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtMoney(b.transport_cost, c)}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtMoney(b.net_revenue, c)}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtPct(b.share_of_revenue_pct)}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
    </div>
  );
}

export function OperationalPanel({ data }: { data: OperationalSection }) {
  const r = data.rates;
  return (
    <div className="space-y-4">
      <Tiles>
        <KpiTile label="Récolte" value={fmtKg(data.harvest_kg)} accent="#38BDF8" />
        <KpiTile label="Vendu" value={fmtKg(data.sold_kg)} sub={fmtPct(r.sold_rate_pct)} />
        <KpiTile label="Pertes" value={fmtKg(data.lost_kg)} sub={`taux ${fmtPct(r.waste_rate_pct)}`} accent="#F43F5E" />
        <KpiTile label="Stock final" value={fmtKg(data.ending_inventory_kg)} accent="#F59E0B" />
        <KpiTile label="Demande servie" value={fmtPct(r.fulfillment_rate_pct)} accent="#38BDF8" />
        <KpiTile label="Utilisation du stockage" value={fmtPct(r.storage_utilization_avg_pct)} sub={`pic ${fmtPct(r.storage_utilization_peak_pct)}`} accent="#F59E0B" />
      </Tiles>
      <Card title="Flux par jour">
        <StackedTimeline
          ariaLabel="Ventes, stock et pertes par jour"
          data={data.daily.map((p) => ({ day: p.day, stock: p.stock_end_kg, sold: p.sold_kg, lost: p.lost_kg }))}
          series={[
            { key: "stock", label: "Stock fin de jour", kind: "area", color: "#F59E0B" },
            { key: "sold", label: "Vendu", kind: "bar", color: "#38BDF8" },
            { key: "lost", label: "Pertes", kind: "line", color: CHART.negative },
          ]}
          height={240}
        />
      </Card>
      <Card title="Stockage">
        {data.storage.length === 0 ? (
          <p className="text-sm text-slate-400">Aucun lieu de stockage.</p>
        ) : (
          <Table label="Utilisation du stockage">
            <thead>
              <tr>
                <th className={thClass}>Lieu</th>
                <th className={`${thClass} ${numClass}`}>Capacité</th>
                <th className={`${thClass} ${numClass}`}>Stocké</th>
                <th className={`${thClass} ${numClass}`}>Pic</th>
                <th className={`${thClass} ${numClass}`}>Moyenne</th>
                <th className={`${thClass} ${numClass}`}>Jours pleins</th>
              </tr>
            </thead>
            <tbody>
              {data.storage.map((s) => (
                <tr key={s.facility_id}>
                  <td className={tdClass}>
                    {s.name} {!s.usable && <Badge tone="warning">inutilisable</Badge>}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>{fmtKg(s.capacity_kg)}</td>
                  <td className={`${tdClass} ${numClass}`}>{fmtKg(s.stored_kg)}</td>
                  <td className={`${tdClass} ${numClass}`}>{fmtPct(s.peak_pct)}</td>
                  <td className={`${tdClass} ${numClass}`}>{fmtPct(s.avg_pct)}</td>
                  <td className={`${tdClass} ${numClass}`}>{s.full_days.length}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}

export function BuyersPanel({ data, currency }: { data: BuyersSection; currency: string }) {
  const buyers = [...data.buyers].sort((a, b) => (a.market_rank ?? 99) - (b.market_rank ?? 99));
  return (
    <Card title="Acheteurs (classés par prix net estimé)">
      <Table label="Analyse des acheteurs">
        <thead>
          <tr>
            <th className={thClass}>Rang</th>
            <th className={thClass}>Acheteur</th>
            <th className={`${thClass} ${numClass}`}>Prix</th>
            <th className={`${thClass} ${numClass}`}>Prix net</th>
            <th className={`${thClass} ${numClass}`}>Vendu</th>
            <th className={`${thClass} ${numClass}`}>Demande servie</th>
            <th className={`${thClass} ${numClass}`}>Part des ventes</th>
            <th className={`${thClass} ${numClass}`}>Revenu net</th>
            <th className={`${thClass} ${numClass}`}>Distance</th>
          </tr>
        </thead>
        <tbody>
          {buyers.map((b) => (
            <tr key={b.buyer_id}>
              <td className={tdClass}>{b.market_rank != null ? `n°${b.market_rank}` : "—"}</td>
              <td className={tdClass}>
                {b.buyer_name}
                {b.buyer_id === data.best_buyer_id && (
                  <span className="ml-2">
                    <Badge tone="success">meilleur</Badge>
                  </span>
                )}
                <span className="block text-xs text-slate-500">{b.location}</span>
              </td>
              <td className={`${tdClass} ${numClass}`}>{fmtUnit(b.price_per_kg, "currency/kg", currency)}</td>
              <td className={`${tdClass} ${numClass}`}>{fmtUnit(b.net_price_per_kg ?? b.estimated_net_price_per_kg, "currency/kg", currency)}</td>
              <td className={`${tdClass} ${numClass}`}>{fmtKg(b.sold_kg)}</td>
              <td className={`${tdClass} ${numClass}`}>{fmtPct(b.fulfillment_pct)}</td>
              <td className={`${tdClass} ${numClass}`}>{fmtPct(b.share_of_sales_pct)}</td>
              <td className={`${tdClass} ${numClass}`}>{fmtMoney(b.net_revenue, currency)}</td>
              <td className={`${tdClass} ${numClass}`}>{fmtNum(b.distance_km)} km</td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}

export function LogisticsPanel({ data, currency }: { data: LogisticsSection; currency: string }) {
  return (
    <div className="space-y-4">
      <Tiles>
        <KpiTile label="Trajets" value={fmtNum(data.trips)} accent="#38BDF8" />
        <KpiTile label="Coût du transport" value={fmtMoney(data.transport_cost, currency)} accent="#F59E0B" />
        <KpiTile label="Coût par kg" value={fmtUnit(data.cost_per_kg, "currency/kg", currency)} sub={data.cost_per_trip != null ? `${fmtMoney(data.cost_per_trip, currency)} / trajet` : undefined} accent="#F59E0B" />
        <KpiTile label="Remplissage" value={fmtPct(data.load_factor_pct)} />
        <KpiTile label="Utilisation de la flotte" value={fmtPct(data.vehicle_utilization_pct)} />
      </Tiles>
      <Card title="Véhicules">
        <Table label="Utilisation des véhicules">
          <thead>
            <tr>
              <th className={thClass}>Type</th>
              <th className={`${thClass} ${numClass}`}>Nombre</th>
              <th className={`${thClass} ${numClass}`}>Trajets</th>
              <th className={`${thClass} ${numClass}`}>Heures</th>
              <th className={`${thClass} ${numClass}`}>Utilisation</th>
              <th className={`${thClass} ${numClass}`}>Coût</th>
              <th className={`${thClass} ${numClass}`}>Jours saturés</th>
            </tr>
          </thead>
          <tbody>
            {data.vehicles.map((v) => (
              <tr key={v.vehicle_type_id}>
                <td className={tdClass}>
                  {v.name} {v.refrigerated && <Badge tone="info">frigorifique</Badge>}
                </td>
                <td className={`${tdClass} ${numClass}`}>{v.count}</td>
                <td className={`${tdClass} ${numClass}`}>{v.trips}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtNum(v.hours)} h</td>
                <td className={`${tdClass} ${numClass}`}>{fmtPct(v.utilization_pct)}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtMoney(v.cost, currency)}</td>
                <td className={`${tdClass} ${numClass}`}>{v.binding_days.length}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
      <Card title="Routes">
        <Table label="Routes utilisées">
          <thead>
            <tr>
              <th className={thClass}>Acheteur</th>
              <th className={`${thClass} ${numClass}`}>Distance</th>
              <th className={`${thClass} ${numClass}`}>Trajets</th>
              <th className={`${thClass} ${numClass}`}>Livré</th>
              <th className={`${thClass} ${numClass}`}>Coût</th>
              <th className={`${thClass} ${numClass}`}>Coût / kg</th>
            </tr>
          </thead>
          <tbody>
            {data.routes.map((r) => (
              <tr key={r.buyer_id}>
                <td className={tdClass}>{r.buyer_name}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtNum(r.distance_km)} km</td>
                <td className={`${tdClass} ${numClass}`}>{r.trips}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtKg(r.delivered_kg)}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtMoney(r.cost, currency)}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtUnit(r.cost_per_kg, "currency/kg", currency)}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
    </div>
  );
}

const RISK: Record<string, { label: string; tone: Tone }> = {
  low: { label: "Risque faible", tone: "success" },
  medium: { label: "Risque moyen", tone: "warning" },
  high: { label: "Risque élevé", tone: "danger" },
};

export function CropPanel({ data, currency }: { data: CropsSection; currency: string }) {
  const risk = RISK[data.risk_level] ?? { label: data.risk_level, tone: "neutral" as Tone };
  return (
    <div className="space-y-4">
      <Card title={data.crop_name} actions={<Badge tone={risk.tone}>{risk.label}</Badge>}>
        <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
          <div>
            <dt className="text-xs text-slate-500">Conservation ambiante</dt>
            <dd className="font-mono text-slate-200">{data.shelf_life_ambient_days} j</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Conservation au froid</dt>
            <dd className="font-mono text-slate-200">{data.shelf_life_cold_days != null ? `${data.shelf_life_cold_days} j` : "—"}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Perte / jour (ambiant)</dt>
            <dd className="font-mono text-slate-200">{fmtPct(data.loss_rate_pct_per_day_ambient)}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Prix de référence</dt>
            <dd className="font-mono text-slate-200">{fmtUnit(data.reference_price_per_kg, "currency/kg", currency)}</dd>
          </div>
        </dl>
        {data.risk_reasons.length > 0 && (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-300">
            {data.risk_reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="Lots récoltés">
        <Table label="Devenir des lots">
          <thead>
            <tr>
              <th className={thClass}>Lot</th>
              <th className={`${thClass} ${numClass}`}>Disponible</th>
              <th className={`${thClass} ${numClass}`}>Quantité</th>
              <th className={`${thClass} ${numClass}`}>Vendu</th>
              <th className={`${thClass} ${numClass}`}>Perdu</th>
              <th className={`${thClass} ${numClass}`}>Restant</th>
            </tr>
          </thead>
          <tbody>
            {data.lots.map((l) => (
              <tr key={l.lot_id}>
                <td className={tdClass}>{l.lot_id}</td>
                <td className={`${tdClass} ${numClass}`}>J{l.available_day}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtKg(l.quantity_kg)}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtKg(l.sold_kg)}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtKg(l.lost_kg)}</td>
                <td className={`${tdClass} ${numClass}`}>{fmtKg(l.ending_kg)}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
    </div>
  );
}

"use client";

import { useState } from "react";
import { SankeyChart } from "@/components/charts/SankeyChart";
import { Button, Card, cx, ErrorBanner, Loading, numClass, Table, tdClass, thClass } from "@/components/ui/primitives";
import { errorMessage } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { fmtKg, fmtMoney, fmtNum, fmtPct } from "@/lib/format";
import { useApi } from "@/lib/hooks/useApi";
import type { BuyerSummary, WasteRow } from "@/lib/api/types";
import { AllocationMatrix } from "./AllocationMatrix";
import { InventoryTimeline } from "./InventoryTimeline";
import { nameOf, type NameIndex } from "./names";
import { RunKpis } from "./RunKpis";
import { useRunView } from "./RunContext";
import { WithResult } from "./RunShell";
import { supplyFlow } from "./supplyFlow";
import { TripsTable } from "./TripsTable";

function BuyerTable({ buyers, currency }: { buyers: BuyerSummary[]; currency?: string }) {
  return (
    <Table label="Synthèse par acheteur">
      <thead>
        <tr>
          <th className={thClass}>Acheteur</th>
          <th className={cx(thClass, "text-right")}>Vendu</th>
          <th className={cx(thClass, "text-right")}>Revenu</th>
          <th className={cx(thClass, "text-right")}>Transport</th>
          <th className={cx(thClass, "text-right")}>Revenu net</th>
          <th className={cx(thClass, "text-right")}>Prix net /kg</th>
          <th className={cx(thClass, "text-right")}>Demande servie</th>
        </tr>
      </thead>
      <tbody>
        {[...buyers]
          .sort((a, b) => b.net_revenue - a.net_revenue)
          .map((b) => (
            <tr key={b.buyer_id}>
              <td className={tdClass}>{b.buyer_name}</td>
              <td className={cx(tdClass, numClass)}>{fmtKg(b.sold_kg)}</td>
              <td className={cx(tdClass, numClass)}>{fmtMoney(b.revenue, currency)}</td>
              <td className={cx(tdClass, numClass)}>{fmtMoney(b.transport_cost, currency)}</td>
              <td className={cx(tdClass, numClass)}>{fmtMoney(b.net_revenue, currency)}</td>
              <td className={cx(tdClass, numClass)}>{fmtNum(b.net_price_per_kg)}</td>
              <td className={cx(tdClass, numClass)}>{fmtPct(b.fulfillment_pct)}</td>
            </tr>
          ))}
      </tbody>
    </Table>
  );
}

export function SummaryPanel() {
  const { names, currency } = useRunView();
  return (
    <WithResult>
      {(result) => (
        <div className="space-y-6">
          <p className="text-sm text-slate-400" data-testid="outcome-label">
            {result.outcome_label}
          </p>
          <RunKpis kpis={result.kpis} currency={currency} />
          <Card title="Flux de la récolte">
            <SankeyChart graph={supplyFlow(result, names)} />
          </Card>
          <Card title="Acheteurs">
            <BuyerTable buyers={result.buyers} currency={currency} />
          </Card>
        </div>
      )}
    </WithResult>
  );
}

export function AllocationPanel() {
  const { names } = useRunView();
  return (
    <WithResult>
      {(result) => (
        <Card title="Allocation acheteur × jour (kg)">
          <AllocationMatrix allocations={result.allocations} buyers={result.buyers} names={names} />
        </Card>
      )}
    </WithResult>
  );
}

function WasteTable({ waste, names, currency }: { waste: WasteRow[]; names: NameIndex; currency?: string }) {
  const KIND: Record<WasteRow["kind"], string> = { unsold_direct: "Invendu (récolte)", daily_loss: "Perte de stockage", expired: "Périmé" };
  if (waste.length === 0) return <p className="py-4 text-sm text-slate-400">Aucune perte.</p>;
  return (
    <Table label="Pertes">
      <thead>
        <tr>
          <th className={thClass}>Jour</th>
          <th className={thClass}>Lot</th>
          <th className={thClass}>Lieu</th>
          <th className={thClass}>Type</th>
          <th className={cx(thClass, "text-right")}>Quantité</th>
          <th className={cx(thClass, "text-right")}>Valeur perdue</th>
        </tr>
      </thead>
      <tbody>
        {waste.map((w, i) => (
          <tr key={i}>
            <td className={tdClass}>J{w.day}</td>
            <td className={tdClass}>{nameOf(names.lots, w.lot_id)}</td>
            <td className={tdClass}>{w.facility_id ? nameOf(names.facilities, w.facility_id) : "—"}</td>
            <td className={tdClass}>{KIND[w.kind]}</td>
            <td className={cx(tdClass, numClass)}>{fmtKg(w.kg)}</td>
            <td className={cx(tdClass, numClass)}>{fmtMoney(w.value_lost, currency)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

export function InventoryPanel() {
  const { names, currency } = useRunView();
  return (
    <WithResult>
      {(result) => (
        <div className="space-y-6">
          <Card title="Stock, ventes et pertes par jour">
            <InventoryTimeline result={result} names={names} />
          </Card>
          <Card title="Pertes">
            <WasteTable waste={result.waste} names={names} currency={currency} />
          </Card>
        </div>
      )}
    </WithResult>
  );
}

function VehicleUsage({ runId, currency }: { runId: string; currency?: string }) {
  const { data, error, loading } = useApi(() => api.runLogistics(runId), [runId]);
  if (loading) return <Loading />;
  if (error || !data) return <ErrorBanner message={errorMessage(error)} />;
  return (
    <Table label="Utilisation de la flotte">
      <thead>
        <tr>
          <th className={thClass}>Véhicule</th>
          <th className={cx(thClass, "text-right")}>Nombre</th>
          <th className={cx(thClass, "text-right")}>Trajets</th>
          <th className={cx(thClass, "text-right")}>Coût</th>
          <th className={cx(thClass, "text-right")}>Heures</th>
          <th className={cx(thClass, "text-right")}>Utilisation</th>
        </tr>
      </thead>
      <tbody>
        {data.vehicles.map((v) => (
          <tr key={v.vehicle_type_id}>
            <td className={tdClass}>
              {v.name}
              {v.refrigerated && <span className="ml-2 text-xs text-cyan-300">frigo</span>}
            </td>
            <td className={cx(tdClass, numClass)}>{v.count}</td>
            <td className={cx(tdClass, numClass)}>{v.trips}</td>
            <td className={cx(tdClass, numClass)}>{fmtMoney(v.cost, currency)}</td>
            <td className={cx(tdClass, numClass)}>{fmtNum(v.hours)}</td>
            <td className={cx(tdClass, numClass)}>{fmtPct(v.utilization_pct)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

export function LogisticsPanel() {
  const { names, currency, runId } = useRunView();
  return (
    <WithResult>
      {(result) => (
        <div className="space-y-6">
          <Card title="Flotte">
            <VehicleUsage runId={runId} currency={currency} />
          </Card>
          <Card title="Trajets">
            <TripsTable trips={result.trips} names={names} currency={currency} />
          </Card>
        </div>
      )}
    </WithResult>
  );
}

export function RawPanel() {
  const { run, result } = useRunView();
  const [copied, setCopied] = useState(false);
  if (!run) return null;
  const json = JSON.stringify({ run, result: result ?? null }, null, 2);
  const download = () => {
    const url = URL.createObjectURL(new Blob([json], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `run-${run.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <Card
      title="Exécution et résultat (JSON)"
      actions={
        <>
          <Button
            onClick={() => {
              void navigator.clipboard?.writeText(json).then(() => setCopied(true));
            }}
          >
            {copied ? "Copié" : "Copier"}
          </Button>
          <Button onClick={download}>Télécharger</Button>
        </>
      }
    >
      <pre className="max-h-[70vh] overflow-auto rounded-lg bg-navy-deep p-4 font-mono text-xs text-slate-300">{json}</pre>
    </Card>
  );
}

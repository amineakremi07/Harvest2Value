"use client";

import { AlertTriangle, CheckCircle2, Gauge, Snowflake, Warehouse } from "lucide-react";
import KpiCard from "@/app/components/KpiCard";
import PageTitle from "@/app/components/PageTitle";
import StorageRiskCard, { KIND_LABEL, fillTone } from "@/app/components/StorageRiskCard";
import { decimalFormatter, glassCard, numberFormatter } from "@/app/components/styles";
import { useDelegation } from "@/app/context/DelegationProvider";
import { computeRegionStats } from "@/app/lib/regionStats";
import { facilityFillPct } from "@/types";

export default function StoragePage() {
  const { selected, farmers, facilities } = useDelegation();
  const stats = computeRegionStats(farmers, facilities);
  const cold = facilities.filter((f) => f.kind === "cold_storage");
  const coldMax = cold.reduce((s, f) => s + f.maxCapacityKg, 0);
  const coldStock = cold.reduce((s, f) => s + f.currentStockKg, 0);

  return (
    <>
      <PageTitle
        title="Storage Facilities"
        subtitle={`Silo, cold storage and warehouse capacity in ${selected.name}.`}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard icon={Warehouse} label="Total Capacity" value={numberFormatter.format(stats.maxKg / 1000)} suffix="tons" />
        <KpiCard icon={Gauge} label="Current Stock" value={numberFormatter.format(stats.stockKg / 1000)} suffix="tons" />
        <KpiCard
          icon={Snowflake}
          label="Cold Storage Fill"
          value={coldMax > 0 ? ((coldStock / coldMax) * 100).toFixed(0) : "—"}
          suffix={coldMax > 0 ? "%" : undefined}
        />
        <KpiCard
          icon={AlertTriangle}
          label="Critical Facilities"
          value={String(stats.criticalFacilities)}
          suffix={`of ${facilities.length}`}
          accentColor={stats.criticalFacilities > 0 ? "var(--danger)" : "var(--success)"}
        />
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-5">
          <StorageRiskCard facilities={facilities} delegationId={selected.id} />
        </div>

        <section aria-labelledby="facility-table-title" className={`${glassCard} col-span-12 overflow-hidden lg:col-span-7`}>
          <h2 id="facility-table-title" className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
            Facility Status
          </h2>
          {facilities.length === 0 ? (
            <p className="py-8 text-center text-sm text-text-secondary">No storage facilities registered.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-left text-sm">
                <thead>
                  <tr className="border-b border-card-border text-xs uppercase tracking-wider text-text-secondary">
                    <th scope="col" className="pb-2 pr-3 font-semibold">Facility</th>
                    <th scope="col" className="pb-2 pr-3 font-semibold">Type</th>
                    <th scope="col" className="pb-2 pr-3 text-right font-semibold">Stock / Max (t)</th>
                    <th scope="col" className="pb-2 pr-3 text-right font-semibold">Fill</th>
                    <th scope="col" className="pb-2 font-semibold">Risk</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-card-border">
                  {facilities.map((f) => {
                    const pct = facilityFillPct(f);
                    const tone = fillTone(pct);
                    const Icon = tone.label === "Healthy" ? CheckCircle2 : AlertTriangle;
                    return (
                      <tr key={f.id}>
                        <th scope="row" className="py-3 pr-3 font-medium text-text-primary">{f.name}</th>
                        <td className="py-3 pr-3 text-text-secondary">{KIND_LABEL[f.kind]}</td>
                        <td className="py-3 pr-3 text-right font-mono tabular-nums">
                          {decimalFormatter.format(f.currentStockKg / 1000)} / {decimalFormatter.format(f.maxCapacityKg / 1000)}
                        </td>
                        <td className="py-3 pr-3 text-right font-mono tabular-nums">{decimalFormatter.format(pct)}%</td>
                        <td className="py-3">
                          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-text-primary">
                            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                            {tone.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

"use client";

import { Fragment, useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight, Pencil } from "lucide-react";
import DeltaBadge from "@/app/components/DeltaBadge";
import { decimalFormatter, glassCard, numberFormatter } from "@/app/components/styles";
import {
  CROPS,
  CROP_COLORS,
  farmerDelta,
  snapshotFromCrops,
  wastePercent,
  type Farmer,
} from "@/types";

interface FarmersTableProps {
  farmers: Farmer[];
  delegationName: string;
  /** Omit for a read-only table (no edit column). */
  onEdit?: (farmer: Farmer) => void;
  /** Makes each farmer name a button that opens their analytics. */
  onSelect?: (farmer: Farmer) => void;
  /** Adds an "Analytics" toggle per row that expands this content under the row. */
  renderExpanded?: (farmer: Farmer) => ReactNode;
}

export default function FarmersTable({ farmers, delegationName, onEdit, onSelect, renderExpanded }: FarmersTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const columnCount = 8 + (renderExpanded ? 1 : 0) + (onEdit ? 1 : 0);

  return (
    <section id="farmers" aria-labelledby="farmers-title" className={`${glassCard} overflow-hidden`}>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="farmers-title" className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          Farmers · {delegationName}
        </h2>
        <span className="text-xs text-text-secondary">Δ vs previous period</span>
      </div>

      {farmers.length === 0 ? (
        <p className="py-8 text-center text-sm text-text-secondary">No farmers registered yet.</p>
      ) : (
        <div className="-mx-5 overflow-x-auto px-5">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="border-b border-card-border text-xs uppercase tracking-wider text-text-secondary">
                <th scope="col" className="pb-2 pr-3 font-semibold">Farmer</th>
                <th scope="col" className="pb-2 pr-3 font-semibold">Crops</th>
                <th scope="col" className="pb-2 pr-3 text-right font-semibold">Yield (t)</th>
                <th scope="col" className="pb-2 pr-3 text-right font-semibold">Waste</th>
                <th scope="col" className="pb-2 pr-3 text-right font-semibold">Income (TND)</th>
                <th scope="col" className="pb-2 pr-3 font-semibold">Δ Income</th>
                <th scope="col" className="pb-2 pr-3 font-semibold">Δ Waste</th>
                <th scope="col" className="pb-2 pr-3 text-right font-semibold">Storage (t)</th>
                {renderExpanded && (
                  <th scope="col" className="pb-2 pr-3 font-semibold">Analytics</th>
                )}
                {onEdit && (
                  <th scope="col" className="pb-2 font-semibold"><span className="sr-only">Actions</span></th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-card-border">
              {farmers.map((f) => {
                const now = snapshotFromCrops(f.crops, "current");
                const delta = farmerDelta(f);
                return (
                  <Fragment key={f.id}>
                  <tr className="transition-colors hover:bg-accent/5">
                    <th scope="row" className="py-3 pr-3 font-medium text-text-primary">
                      {onSelect ? (
                        <button
                          type="button"
                          onClick={() => onSelect(f)}
                          aria-label={`View analytics for ${f.name}`}
                          className="rounded-md text-left font-medium text-accent-text outline-none hover:underline focus-visible:ring-2 focus-visible:ring-accent"
                        >
                          {f.name}
                        </button>
                      ) : (
                        f.name
                      )}
                    </th>
                    <td className="py-3 pr-3">
                      <div className="flex flex-wrap gap-1">
                        {f.crops.map((c) => (
                          <span
                            key={c.crop}
                            className="inline-flex items-center gap-1 rounded-full border border-card-border px-2 py-0.5 text-xs text-text-primary"
                          >
                            <span
                              className="h-1.5 w-1.5 rounded-full"
                              style={{ backgroundColor: CROP_COLORS[c.crop] }}
                              aria-hidden="true"
                            />
                            {CROPS[c.crop].label}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 pr-3 text-right font-mono tabular-nums">{decimalFormatter.format(now.yieldKg / 1000)}</td>
                    <td className="py-3 pr-3 text-right font-mono tabular-nums text-text-secondary">
                      {decimalFormatter.format(wastePercent(now.yieldKg, now.wasteKg))}%
                    </td>
                    <td className="py-3 pr-3 text-right font-mono tabular-nums">{numberFormatter.format(now.incomeTnd)}</td>
                    <td className="py-3 pr-3"><DeltaBadge label="Income change" delta={delta.income} /></td>
                    <td className="py-3 pr-3"><DeltaBadge label="Waste change" delta={delta.waste} /></td>
                    <td className="py-3 pr-3 text-right font-mono tabular-nums">{decimalFormatter.format(f.storageCapacityKg / 1000)}</td>
                    {renderExpanded && (
                      <td className="py-3 pr-3">
                        <button
                          type="button"
                          onClick={() => setExpandedId(expandedId === f.id ? null : f.id)}
                          aria-expanded={expandedId === f.id}
                          aria-controls={`farmer-panel-${f.id}`}
                          aria-label={`${expandedId === f.id ? "Hide" : "Show"} analytics for ${f.name}`}
                          className="inline-flex items-center gap-1 rounded-full border border-card-border px-2.5 py-1 text-xs font-semibold text-accent-text outline-none hover:border-accent/50 focus-visible:ring-2 focus-visible:ring-accent"
                        >
                          {expandedId === f.id ? (
                            <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
                          ) : (
                            <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
                          )}
                          Analytics
                        </button>
                      </td>
                    )}
                    {onEdit && (
                      <td className="py-3 text-right">
                        <button
                          type="button"
                          onClick={() => onEdit(f)}
                          aria-label={`Edit ${f.name}`}
                          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary outline-none transition-colors hover:bg-accent/10 hover:text-accent-text focus-visible:ring-2 focus-visible:ring-accent"
                        >
                          <Pencil className="h-4 w-4" aria-hidden="true" />
                        </button>
                      </td>
                    )}
                  </tr>
                  {renderExpanded && expandedId === f.id && (
                    <tr id={`farmer-panel-${f.id}`} className="bg-app-bg/60">
                      <td colSpan={columnCount} className="px-3 pb-3">
                        {renderExpanded(f)}
                      </td>
                    </tr>
                  )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

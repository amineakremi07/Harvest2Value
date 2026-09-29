import { Warehouse, Trophy, Users, Truck, CheckCircle } from "lucide-react";
import type { AllocationDetail, OptimizeResponse } from "@/app/lib/api";

export interface AllocationTableProps {
  result: OptimizeResponse;
}

interface AllocationRow extends AllocationDetail {
  buyerId: string;
}

const numberFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

function formatKg(value: number): string {
  return `${numberFormatter.format(value)} kg`;
}

function formatMoney(value: number): string {
  return `${numberFormatter.format(value)} DT`;
}

// 1. Reduced container padding from p-4 md:p-6 to p-3 md:p-4
const card = "bg-white dark:bg-card-surface border border-card-border dark:border-card-border rounded-xl p-3 md:p-4 w-full";

function Badge({
  icon: Icon,
  label,
  tone,
}: {
  icon: typeof CheckCircle;
  label: string;
  tone: "emerald" | "amber";
}) {
  const toneClasses =
    tone === "emerald"
      ? "bg-accent/15 dark:bg-accent/15 border-accent/30 dark:border-accent/30 text-accent-text dark:text-accent-text"
      : "bg-amber-500/15 border-amber-500/30 text-amber-600 dark:text-amber-400";

  return (
    // 2. Compacted badge padding and font size
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium leading-none whitespace-nowrap ${toneClasses}`}
    >
      <Icon className="h-2.5 w-2.5 shrink-0" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

export default function AllocationTable({ result }: AllocationTableProps) {
  const rows: AllocationRow[] = Object.entries(result.allocation)
    .map(([buyerId, detail]) => ({ buyerId, ...detail }))
    .sort((a, b) => b.net_profit - a.net_profit);

  return (
    <div className={card}>
      <div className="mb-3 flex items-center gap-2 text-text-secondary dark:text-slate-400">
        <Trophy className="h-4 w-4 text-accent-text dark:text-accent-text" aria-hidden="true" />
        <span className="text-xs font-semibold uppercase tracking-wider">Allocation Results</span>
      </div>

      <div className="w-full overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-card-border dark:border-card-border">
              <th className="pb-2 px-0.5 text-[9px] font-semibold uppercase tracking-tight text-text-secondary dark:text-slate-400 whitespace-nowrap">
                Buyer
              </th>
              <th className="pb-2 px-0.5 text-right text-[9px] font-semibold uppercase tracking-tight text-text-secondary dark:text-slate-400 whitespace-nowrap">
                Allocated
              </th>
              <th className="pb-2 px-0.5 text-right text-[9px] font-semibold uppercase tracking-tight text-text-secondary dark:text-slate-400 whitespace-nowrap">
                Unit Price
              </th>
              <th className="pb-2 px-0.5 text-right text-[9px] font-semibold uppercase tracking-tight text-text-secondary dark:text-slate-400 whitespace-nowrap">
                Revenue
              </th>
              <th className="pb-2 px-0.5 text-right text-[9px] font-semibold uppercase tracking-tight text-text-secondary dark:text-slate-400 whitespace-nowrap">
                Transport
              </th>
              <th className="pb-2 px-0.5 text-right text-[9px] font-semibold uppercase tracking-tight text-text-secondary dark:text-slate-400 whitespace-nowrap">
                Net Profit
              </th>
              <th className="pb-2 px-0.5 text-center text-[9px] font-semibold uppercase tracking-tight text-text-secondary dark:text-slate-400 whitespace-nowrap">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-card-border">
            {rows.length > 0 ? (
              rows.map((row, index) => (
                <tr key={row.buyerId} className="transition-colors hover:bg-[#F1F5F9]/40 dark:hover:bg-accent/10">
                  <td className="py-2 px-0.5">
                    <div className="flex items-center gap-1">
                      <Users className="h-3 w-3 text-text-secondary dark:text-slate-400 shrink-0" aria-hidden="true" />
                      <span className="font-medium text-text-primary dark:text-white text-xs truncate max-w-[100px]">{row.buyer_name}</span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-1 text-[10px] text-text-secondary dark:text-slate-400">
                      <Truck className="h-2.5 w-2.5 shrink-0" aria-hidden="true" />
                      <span className="whitespace-nowrap">{numberFormatter.format(row.distance_km)} km away</span>
                    </div>
                  </td>
                  <td className="py-2 px-0.5 text-right font-mono tabular-nums text-text-primary dark:text-white text-xs whitespace-nowrap">
                    {formatKg(row.allocated_kg)}
                  </td>
                  <td className="py-2 px-0.5 text-right font-mono tabular-nums text-text-primary dark:text-white text-xs whitespace-nowrap">
                    {formatMoney(row.unit_price)}
                  </td>
                  <td className="py-2 px-0.5 text-right font-mono tabular-nums text-accent-text dark:text-accent-text text-xs whitespace-nowrap">
                    {formatMoney(row.revenue)}
                  </td>
                  <td className="py-2 px-0.5 text-right font-mono tabular-nums text-text-secondary dark:text-slate-400 text-xs whitespace-nowrap">
                    {formatMoney(row.transport_cost)}
                  </td>
                  <td className="py-2 px-0.5 text-right font-mono text-xs font-semibold tabular-nums text-accent-text dark:text-accent-text whitespace-nowrap">
                    {formatMoney(row.net_profit)}
                  </td>
                  <td className="py-2 px-0.5 text-center whitespace-nowrap">
                    {index === 0 ? (
                      <Badge icon={Trophy} label="Top Match" tone="emerald" />
                    ) : (
                      <Badge icon={CheckCircle} label="Allocated" tone="amber" />
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className="py-6 text-center text-xs text-text-secondary dark:text-slate-400">
                  No allocations yet — run an optimization to see results here.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-card-border dark:border-card-border pt-3">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-600 dark:text-amber-400">
          <Warehouse className="h-3 w-3" aria-hidden="true" />
          <span>
            Stored: <span className="font-mono tabular-nums">{formatKg(result.stored_kg)}</span>
          </span>
        </span>
        <div className="text-right">
          <div className="text-[9px] font-semibold uppercase tracking-wider text-text-secondary dark:text-slate-400">
            Total Net Profit
          </div>
          <div className="font-mono text-lg sm:text-xl font-bold tabular-nums text-accent-text dark:text-accent-text">
            {formatMoney(result.net_profit)}
          </div>
        </div>
      </div>
    </div>
  );
}
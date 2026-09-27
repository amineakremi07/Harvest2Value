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

const card = "bg-[#131B2E] border border-[#1E293B] rounded-xl p-4 md:p-6 w-full";

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
      ? "bg-[#10B981]/15 border-[#10B981]/30 text-[#10B981]"
      : "bg-amber-500/15 border-amber-500/30 text-amber-400";

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${toneClasses}`}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
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
      <div className="mb-4 flex items-center gap-2 text-slate-400">
        <Trophy className="h-5 w-5 text-[#10B981]" aria-hidden="true" />
        <span className="text-xs font-semibold uppercase tracking-wider">Allocation Results</span>
      </div>

      <div className="w-full overflow-x-auto">
        <table className="w-full border-collapse text-left text-xs sm:text-sm">
          <thead>
            <tr className="border-b border-[#1E293B]">
              <th className="pb-2.5 px-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Buyer
              </th>
              <th className="pb-2.5 px-2 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Allocated
              </th>
              <th className="pb-2.5 px-2 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Unit Price
              </th>
              <th className="pb-2.5 px-2 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Revenue
              </th>
              <th className="pb-2.5 px-2 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Transport
              </th>
              <th className="pb-2.5 px-2 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Net Profit
              </th>
              <th className="pb-2.5 px-2 text-center text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1E293B]/60">
            {rows.length > 0 ? (
              rows.map((row, index) => (
                <tr key={row.buyerId} className="transition-colors hover:bg-[#1E293B]/40">
                  <td className="py-2.5 px-2">
                    <div className="flex items-center gap-1.5">
                      <Users className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                      <span className="font-medium text-white text-xs sm:text-sm">{row.buyer_name}</span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-1 text-[11px] text-slate-400">
                      <Truck className="h-3 w-3" aria-hidden="true" />
                      <span>{numberFormatter.format(row.distance_km)} km away</span>
                    </div>
                  </td>
                  <td className="py-2.5 px-2 text-right font-mono tabular-nums text-white text-xs sm:text-sm">
                    {formatKg(row.allocated_kg)}
                  </td>
                  <td className="py-2.5 px-2 text-right font-mono tabular-nums text-white text-xs sm:text-sm">
                    {formatMoney(row.unit_price)}
                  </td>
                  <td className="py-2.5 px-2 text-right font-mono tabular-nums text-[#10B981] text-xs sm:text-sm">
                    {formatMoney(row.revenue)}
                  </td>
                  <td className="py-2.5 px-2 text-right font-mono tabular-nums text-slate-400 text-xs sm:text-sm">
                    {formatMoney(row.transport_cost)}
                  </td>
                  <td className="py-2.5 px-2 text-right font-mono text-xs sm:text-sm font-semibold tabular-nums text-[#10B981]">
                    {formatMoney(row.net_profit)}
                  </td>
                  <td className="py-2.5 px-2 text-center">
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
                <td colSpan={7} className="py-6 text-center text-xs text-slate-400">
                  No allocations yet — run an optimization to see results here.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[#1E293B] pt-4">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/15 px-2.5 py-0.5 text-xs font-medium text-amber-400">
          <Warehouse className="h-3.5 w-3.5" aria-hidden="true" />
          <span>
            Stored: <span className="font-mono tabular-nums">{formatKg(result.stored_kg)}</span>
          </span>
        </span>
        <div className="text-right">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Total Net Profit
          </div>
          <div className="font-mono text-xl sm:text-2xl font-bold tabular-nums text-[#10B981]">
            {formatMoney(result.net_profit)}
          </div>
        </div>
      </div>
    </div>
  );
}
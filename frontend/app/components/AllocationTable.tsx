import { Warehouse, CheckCircle2, TrendingUp, Truck, Users } from "lucide-react";
import type { AllocationDetail, OptimizeResponse } from "@/app/lib/api";

export interface AllocationTableProps {
  result: OptimizeResponse;
}

interface AllocationRow extends AllocationDetail {
  buyerId: string;
}

const numberFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

function formatKg(value: number): string {
  return `${numberFormatter.format(value)} kg`;
}

function formatMoney(value: number): string {
  return currencyFormatter.format(value);
}

function StatusBadge({
  icon: Icon,
  label,
  tone,
}: {
  icon: typeof CheckCircle2;
  label: string;
  tone: "allocated" | "stored";
}) {
  const toneClasses =
    tone === "allocated"
      ? "bg-emerald-950 text-emerald-300 border-emerald-700"
      : "bg-amber-950 text-amber-300 border-amber-700";

  return (
    <span
      className={`inline-flex min-h-[32px] items-center gap-2 rounded-full border px-3 py-1 text-base font-medium ${toneClasses}`}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

export default function AllocationTable({ result }: AllocationTableProps) {
  const rows: AllocationRow[] = Object.entries(result.allocation)
    .map(([buyerId, detail]) => ({ buyerId, ...detail }))
    .sort((a, b) => b.net_profit - a.net_profit);

  return (
    <div className="rounded-2xl border border-slate-700 bg-slate-900 p-4 shadow-lg md:p-6">
      <h2 className="mb-6 inline-flex items-center gap-2 text-lg font-bold text-slate-100">
        <TrendingUp className="h-6 w-6 text-emerald-500" aria-hidden="true" />
        <span>Allocation Results</span>
      </h2>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-separate border-spacing-0 text-base">
          <thead>
            <tr>
              <th className="border-b-2 border-slate-700 px-4 py-3 text-left font-semibold text-slate-100">
                <span className="inline-flex items-center gap-2">
                  <Users className="h-5 w-5 text-emerald-500" aria-hidden="true" />
                  Buyer
                </span>
              </th>
              <th className="border-b-2 border-slate-700 px-4 py-3 text-right font-semibold text-slate-100">
                <span className="inline-flex items-center justify-end gap-2">
                  <Warehouse className="h-5 w-5 text-emerald-500" aria-hidden="true" />
                  Allocated
                </span>
              </th>
              <th className="border-b-2 border-slate-700 px-4 py-3 text-right font-semibold text-slate-100">
                Unit Price
              </th>
              <th className="border-b-2 border-slate-700 px-4 py-3 text-right font-semibold text-slate-100">
                Revenue
              </th>
              <th className="border-b-2 border-slate-700 px-4 py-3 text-right font-semibold text-slate-100">
                <span className="inline-flex items-center justify-end gap-2">
                  <Truck className="h-5 w-5 text-emerald-500" aria-hidden="true" />
                  Transport
                </span>
              </th>
              <th className="border-b-2 border-slate-700 px-4 py-3 text-right font-semibold text-slate-100">
                Net Profit
              </th>
              <th className="border-b-2 border-slate-700 px-4 py-3 text-left font-semibold text-slate-100">
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr
                key={row.buyerId}
                className={index % 2 === 0 ? "bg-slate-900" : "bg-slate-800/50"}
              >
                <td className="border-b border-slate-800 px-4 py-3 text-slate-100">
                  {row.buyer_name}
                </td>
                <td className="border-b border-slate-800 px-4 py-3 text-right font-mono text-slate-100">
                  {formatKg(row.allocated_kg)}
                </td>
                <td className="border-b border-slate-800 px-4 py-3 text-right font-mono text-emerald-400">
                  {formatMoney(row.unit_price)}
                </td>
                <td className="border-b border-slate-800 px-4 py-3 text-right font-mono text-emerald-400">
                  {formatMoney(row.revenue)}
                </td>
                <td className="border-b border-slate-800 px-4 py-3 text-right font-mono text-slate-100">
                  {formatMoney(row.transport_cost)}
                </td>
                <td className="border-b border-slate-800 px-4 py-3 text-right font-mono text-emerald-400">
                  {formatMoney(row.net_profit)}
                </td>
                <td className="border-b border-slate-800 px-4 py-3">
                  <StatusBadge icon={CheckCircle2} label="Allocated" tone="allocated" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rows.length === 0 && (
        <p className="mt-4 text-base text-slate-400">
          No allocations yet — run an optimization to see buyer-by-buyer results here.
        </p>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-4 border-t border-slate-800 pt-4">
        <StatusBadge icon={Warehouse} label={`Stored: ${formatKg(result.stored_kg)}`} tone="stored" />
        <span className="inline-flex items-center gap-2 text-base font-medium text-slate-100">
          <TrendingUp className="h-5 w-5 text-emerald-500" aria-hidden="true" />
          Total Net Profit:{" "}
          <span className="font-mono text-emerald-400">{formatMoney(result.net_profit)}</span>
        </span>
      </div>
    </div>
  );
}

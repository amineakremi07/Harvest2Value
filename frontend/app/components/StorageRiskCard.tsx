import { Droplets, Thermometer } from "lucide-react";
import { decimalFormatter, glassCard, numberFormatter } from "@/app/components/styles";
import { facilityFillPct, type FacilityKind, type StorageFacility } from "@/types";

export const KIND_LABEL: Record<FacilityKind, string> = {
  silo: "Silo",
  cold_storage: "Cold storage",
  warehouse: "Warehouse",
};

/** Mock sensor readings per delegation until a telemetry endpoint exists. */
const MOCK_CLIMATE: Record<string, { tempC: number; humidityPct: number }> = {
  mornag: { tempC: 27.5, humidityPct: 61 },
  tebourba: { tempC: 29.1, humidityPct: 48 },
  kelibia: { tempC: 25.8, humidityPct: 72 },
};

export function fillTone(pct: number): { bar: string; label: string } {
  if (pct >= 90) return { bar: "bg-danger", label: "Critical" };
  if (pct >= 75) return { bar: "bg-warning", label: "Filling" };
  return { bar: "bg-success", label: "Healthy" };
}

export default function StorageRiskCard({
  facilities,
  delegationId,
}: {
  facilities: StorageFacility[];
  delegationId: string;
}) {
  const climate = MOCK_CLIMATE[delegationId];

  return (
    <section id="storage" aria-labelledby="storage-title" className={glassCard}>
      <h2 id="storage-title" className="mb-4 text-sm font-semibold uppercase tracking-wider text-text-secondary">
        Storage &amp; Risk
      </h2>

      {facilities.length === 0 ? (
        <p className="py-6 text-center text-sm text-text-secondary">No storage facilities registered.</p>
      ) : (
        <ul className="space-y-4">
          {facilities.map((f) => {
            const pct = facilityFillPct(f);
            const tone = fillTone(pct);
            return (
              <li key={f.id}>
                <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate font-medium text-text-primary">
                    {f.name} <span className="text-xs font-normal text-text-secondary">· {KIND_LABEL[f.kind]}</span>
                  </span>
                  <span className="shrink-0 font-mono text-xs tabular-nums text-text-secondary">
                    {numberFormatter.format(f.currentStockKg / 1000)} / {numberFormatter.format(f.maxCapacityKg / 1000)} t
                  </span>
                </div>
                <div
                  role="progressbar"
                  aria-label={`${f.name} fill level`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(pct)}
                  aria-valuetext={`${Math.round(pct)}% full, ${tone.label}`}
                  className="h-2 overflow-hidden rounded-full bg-card-border"
                >
                  <div className={`h-full rounded-full ${tone.bar}`} style={{ width: `${Math.min(pct, 100)}%` }} />
                </div>
                <div className="mt-1 flex justify-between text-xs text-text-secondary">
                  <span>{tone.label}</span>
                  <span className="font-mono tabular-nums">{decimalFormatter.format(pct)}%</span>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {climate && (
        <div className="mt-5 grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-card-border bg-app-bg/50 p-3">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-text-secondary">
              <Thermometer className="h-3.5 w-3.5" aria-hidden="true" /> Temperature
            </div>
            <span className="font-mono text-lg font-bold tabular-nums text-text-primary">{climate.tempC}°C</span>
          </div>
          <div className="rounded-xl border border-card-border bg-app-bg/50 p-3">
            <div className="mb-1 flex items-center gap-1.5 text-xs text-text-secondary">
              <Droplets className="h-3.5 w-3.5" aria-hidden="true" /> Humidity
            </div>
            <span className="font-mono text-lg font-bold tabular-nums text-text-primary">{climate.humidityPct}%</span>
          </div>
          <p className="col-span-2 text-xs text-text-secondary">Sensor readings are sample data.</p>
        </div>
      )}
    </section>
  );
}

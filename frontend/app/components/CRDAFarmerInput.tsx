"use client";

import { useState, type FormEvent } from "react";
import { Plus, Save, Trash2, X } from "lucide-react";
import { glassCard, inputClass } from "@/app/components/styles";
import { CROPS, CROP_TYPES, type CropType, type Delegation, type Farmer } from "@/types";

/** Form rows hold raw strings so partially typed numbers aren't coerced. */
interface CropRow {
  key: number;
  crop: CropType;
  yieldKg: string;
  wasteKg: string;
  incomeTnd: string;
}

interface CRDAFarmerInputProps {
  delegation: Delegation;
  /** Farmer being edited; omit to register a new one. Remount (via `key`) to swap. */
  editing?: Farmer | null;
  onSave: (farmer: Farmer) => void;
  onCancelEdit?: () => void;
}

function toRows(farmer: Farmer | null | undefined): CropRow[] {
  if (!farmer) return [{ key: 0, crop: "tomatoes", yieldKg: "", wasteKg: "", incomeTnd: "" }];
  return farmer.crops.map((c, i) => ({
    key: i,
    crop: c.crop,
    yieldKg: String(c.yieldKg),
    wasteKg: String(c.wasteKg),
    incomeTnd: String(c.incomeTnd),
  }));
}

const label = "mb-1 block text-xs font-semibold text-text-secondary";

export default function CRDAFarmerInput({ delegation, editing, onSave, onCancelEdit }: CRDAFarmerInputProps) {
  const [name, setName] = useState(editing?.name ?? "");
  const [phone, setPhone] = useState(editing?.phone ?? "");
  const [storageKg, setStorageKg] = useState(editing ? String(editing.storageCapacityKg) : "");
  const [rows, setRows] = useState<CropRow[]>(() => toRows(editing));
  const [nextKey, setNextKey] = useState(rows.length);
  const [errors, setErrors] = useState<string[]>([]);

  const usedCrops = new Set(rows.map((r) => r.crop));
  const nextFreeCrop = CROP_TYPES.find((c) => !usedCrops.has(c));

  function updateRow(key: number, patch: Partial<CropRow>) {
    setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }

  function addRow() {
    if (!nextFreeCrop) return;
    setRows((prev) => [
      ...prev,
      { key: nextKey, crop: nextFreeCrop, yieldKg: "", wasteKg: "", incomeTnd: "" },
    ]);
    setNextKey((k) => k + 1);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const problems: string[] = [];
    const storage = Number(storageKg);

    if (!name.trim()) problems.push("Farmer name is required.");
    if (storageKg.trim() === "" || !Number.isFinite(storage) || storage < 0) {
      problems.push("Storage capacity must be a number of kg, 0 or more.");
    }

    const crops = rows.map((r) => ({
      crop: r.crop,
      yieldKg: Number(r.yieldKg),
      wasteKg: r.wasteKg.trim() === "" ? 0 : Number(r.wasteKg),
      incomeTnd: r.incomeTnd.trim() === "" ? 0 : Number(r.incomeTnd),
    }));
    crops.forEach((c) => {
      const cropLabel = CROPS[c.crop].label;
      if (!Number.isFinite(c.yieldKg) || c.yieldKg <= 0) problems.push(`${cropLabel}: yield must be greater than 0.`);
      else if (!Number.isFinite(c.wasteKg) || c.wasteKg < 0 || c.wasteKg > c.yieldKg) {
        problems.push(`${cropLabel}: waste must be between 0 and the yield.`);
      }
      if (!Number.isFinite(c.incomeTnd) || c.incomeTnd < 0) problems.push(`${cropLabel}: income must be 0 or more.`);
    });

    setErrors(problems);
    if (problems.length > 0) return;

    onSave({
      id: editing?.id ?? `f-${delegation.id}-${Date.now()}`,
      name: name.trim(),
      delegationId: delegation.id,
      phone: phone.trim() || undefined,
      storageCapacityKg: storage,
      crops,
      history: editing?.history ?? [],
    });
  }

  return (
    <section aria-labelledby="farmer-input-title" className={glassCard}>
      <div className="mb-4 flex items-center justify-between gap-2">
        <h2 id="farmer-input-title" className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
          {editing ? `Edit farmer · ${editing.name}` : `Register farmer · ${delegation.name}`}
        </h2>
        {editing && onCancelEdit && (
          <button
            type="button"
            onClick={onCancelEdit}
            className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-semibold text-text-secondary outline-none hover:text-text-primary focus-visible:ring-2 focus-visible:ring-accent"
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" /> Cancel
          </button>
        )}
      </div>

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <label htmlFor="farmer-name" className={label}>Farmer name</label>
            <input id="farmer-name" value={name} onChange={(e) => setName(e.target.value)} className={inputClass} placeholder="e.g. Slim Ben Salah" />
          </div>
          <div>
            <label htmlFor="farmer-phone" className={label}>Phone (optional)</label>
            <input id="farmer-phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} className={inputClass} placeholder="+216 …" />
          </div>
          <div>
            <label htmlFor="farmer-storage" className={label}>Storage capacity (kg)</label>
            <input id="farmer-storage" type="number" inputMode="decimal" min={0} value={storageKg} onChange={(e) => setStorageKg(e.target.value)} className={`${inputClass} font-mono tabular-nums`} placeholder="0" />
          </div>
        </div>

        <fieldset className="space-y-3">
          <legend className="mb-1 text-xs font-semibold text-text-secondary">Crops this period</legend>
          {rows.map((r, i) => {
            const available = CROP_TYPES.filter((c) => c === r.crop || !usedCrops.has(c));
            return (
              <div key={r.key} className="grid grid-cols-2 gap-2 rounded-xl border border-card-border p-3 sm:grid-cols-[1.2fr_1fr_1fr_1fr_auto] sm:items-end">
                <div className="col-span-2 sm:col-span-1">
                  <label htmlFor={`crop-${r.key}`} className={label}>Crop</label>
                  <select id={`crop-${r.key}`} value={r.crop} onChange={(e) => updateRow(r.key, { crop: e.target.value as CropType })} className={inputClass}>
                    {available.map((c) => (
                      <option key={c} value={c}>{CROPS[c].label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor={`yield-${r.key}`} className={label}>Yield (kg)</label>
                  <input id={`yield-${r.key}`} type="number" inputMode="decimal" min={0} value={r.yieldKg} onChange={(e) => updateRow(r.key, { yieldKg: e.target.value })} className={`${inputClass} font-mono tabular-nums`} />
                </div>
                <div>
                  <label htmlFor={`waste-${r.key}`} className={label}>Waste (kg)</label>
                  <input id={`waste-${r.key}`} type="number" inputMode="decimal" min={0} value={r.wasteKg} onChange={(e) => updateRow(r.key, { wasteKg: e.target.value })} className={`${inputClass} font-mono tabular-nums`} />
                </div>
                <div>
                  <label htmlFor={`income-${r.key}`} className={label}>Income (TND)</label>
                  <input id={`income-${r.key}`} type="number" inputMode="decimal" min={0} value={r.incomeTnd} onChange={(e) => updateRow(r.key, { incomeTnd: e.target.value })} className={`${inputClass} font-mono tabular-nums`} />
                </div>
                <button
                  type="button"
                  onClick={() => setRows((prev) => prev.filter((x) => x.key !== r.key))}
                  disabled={rows.length === 1}
                  aria-label={`Remove crop row ${i + 1}`}
                  className="inline-flex h-10 w-10 items-center justify-center justify-self-end rounded-lg text-text-secondary outline-none hover:bg-red-500/10 hover:text-red-500 focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            );
          })}

          <button
            type="button"
            onClick={addRow}
            disabled={!nextFreeCrop}
            className="inline-flex items-center gap-1.5 rounded-full border border-card-border px-3 py-1.5 text-xs font-semibold text-accent-text outline-none hover:border-accent/50 focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add crop
          </button>
        </fieldset>

        {errors.length > 0 && (
          <ul role="alert" className="space-y-1 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-600 dark:text-red-400">
            {errors.map((msg) => (
              <li key={msg}>{msg}</li>
            ))}
          </ul>
        )}

        <button
          type="submit"
          className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full bg-accent px-6 py-2.5 text-sm font-bold text-white outline-none transition-colors hover:bg-accent-hover focus-visible:ring-2 focus-visible:ring-accent"
        >
          <Save className="h-4 w-4" aria-hidden="true" />
          {editing ? "Save changes" : "Register farmer"}
        </button>
      </form>
    </section>
  );
}

"use client";

import { useState } from "react";
import { Sprout, Warehouse, AlertCircle, Play } from "lucide-react";
import type { Producer } from "@/app/lib/api";

export interface HarvestInputValues {
  harvest_kg: Producer["harvest_kg"];
  storage_capacity_kg: Producer["storage_capacity_kg"];
}

export interface HarvestInputProps {
  onSubmit?: (values: HarvestInputValues) => void;
}

type FieldErrors = {
  harvest_kg?: string;
  storage_capacity_kg?: string;
};

const card = "bg-white dark:bg-[#131B2E] border border-slate-200 dark:border-[#1E293B] rounded-xl p-6";

const fieldBaseClasses =
  "w-full min-h-[44px] rounded-xl border border-slate-200 dark:border-[#1E293B] bg-[#F8FAFC] dark:bg-[#0A140B] px-4 py-3 " +
  "font-mono text-base tabular-nums text-[#0F172A] dark:text-white placeholder:text-[#94A3B8] dark:placeholder:text-slate-500 " +
  "focus:border-[#059669] dark:focus:border-[#10B981] focus:outline-none focus:ring-2 focus:ring-[#059669]/40 dark:focus:ring-[#10B981]/40";

function FieldLabel({
  icon: Icon,
  label,
  htmlFor,
}: {
  icon: typeof Sprout;
  label: string;
  htmlFor: string;
}) {
  return (
    <label htmlFor={htmlFor} className="mb-2 flex items-center gap-2 text-sm text-[#64748B] dark:text-slate-400">
      <Icon className="h-4 w-4 text-[#059669] dark:text-[#10B981]" aria-hidden="true" />
      <span>{label}</span>
    </label>
  );
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p className="mt-2 flex items-center gap-2 text-xs font-medium text-rose-600 dark:text-rose-400" role="alert">
      <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </p>
  );
}

export default function HarvestInput({ onSubmit }: HarvestInputProps) {
  const [harvestKg, setHarvestKg] = useState("");
  const [storageCapacityKg, setStorageCapacityKg] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});

  function validate(): { values: HarvestInputValues | null; errors: FieldErrors } {
    const nextErrors: FieldErrors = {};

    const harvestValue = Number(harvestKg);
    if (!harvestKg.trim() || Number.isNaN(harvestValue) || harvestValue <= 0) {
      nextErrors.harvest_kg = "Enter the harvested quantity in kg (must be greater than 0).";
    }

    const storageValue = Number(storageCapacityKg);
    if (!storageCapacityKg.trim() || Number.isNaN(storageValue) || storageValue < 0) {
      nextErrors.storage_capacity_kg = "Enter available storage capacity in kg (0 or more).";
    }

    const hasErrors = Boolean(nextErrors.harvest_kg) || Boolean(nextErrors.storage_capacity_kg);

    if (hasErrors) {
      return { values: null, errors: nextErrors };
    }

    return {
      values: { harvest_kg: harvestValue, storage_capacity_kg: storageValue },
      errors: {},
    };
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const { values, errors: validationErrors } = validate();
    setErrors(validationErrors);
    if (values) {
      onSubmit?.(values);
    }
  }

  return (
    <div className={card}>
      <div className="mb-6 flex items-center gap-2 text-[#64748B] dark:text-slate-400">
        <Sprout className="h-5 w-5 text-[#059669] dark:text-[#10B981]" aria-hidden="true" />
        <span className="text-sm font-semibold uppercase tracking-wider">Harvest Input</span>
      </div>

      <form onSubmit={handleSubmit} noValidate className="space-y-6">
        <div>
          <FieldLabel icon={Sprout} label="Harvest Quantity (kg)" htmlFor="harvest_kg" />
          <input
            id="harvest_kg"
            name="harvest_kg"
            type="number"
            inputMode="decimal"
            min={0}
            step="any"
            placeholder="12000"
            className={fieldBaseClasses}
            value={harvestKg}
            onChange={(e) => setHarvestKg(e.target.value)}
            aria-invalid={Boolean(errors.harvest_kg)}
            aria-describedby={errors.harvest_kg ? "harvest_kg-error" : undefined}
          />
          {errors.harvest_kg && (
            <span id="harvest_kg-error">
              <FieldError message={errors.harvest_kg} />
            </span>
          )}
        </div>

        <div>
          <FieldLabel icon={Warehouse} label="Storage Capacity (kg)" htmlFor="storage_capacity_kg" />
          <input
            id="storage_capacity_kg"
            name="storage_capacity_kg"
            type="number"
            inputMode="decimal"
            min={0}
            step="any"
            placeholder="2000"
            className={fieldBaseClasses}
            value={storageCapacityKg}
            onChange={(e) => setStorageCapacityKg(e.target.value)}
            aria-invalid={Boolean(errors.storage_capacity_kg)}
            aria-describedby={
              errors.storage_capacity_kg ? "storage_capacity_kg-error" : undefined
            }
          />
          {errors.storage_capacity_kg && (
            <span id="storage_capacity_kg-error">
              <FieldError message={errors.storage_capacity_kg} />
            </span>
          )}
        </div>

        <p className="text-sm text-[#64748B] dark:text-slate-400">
          Optimal buyers are selected automatically by the optimizer — no need to enter them
          yourself.
        </p>

        <button
          type="submit"
          className="inline-flex min-h-[56px] w-full items-center justify-center gap-3 rounded-full bg-[#059669] dark:bg-[#10B981] px-6 py-4 text-lg font-bold text-white dark:text-black shadow-lg shadow-[#10B981]/20 transition-colors hover:bg-[#047857] dark:hover:bg-[#059669] focus:outline-none focus:ring-4 focus:ring-[#059669]/50 dark:focus:ring-[#10B981]/50"
        >
          <Play className="h-6 w-6" aria-hidden="true" />
          <span>Run Optimization</span>
        </button>
      </form>
    </div>
  );
}

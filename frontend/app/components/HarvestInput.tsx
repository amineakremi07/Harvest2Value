"use client";

import { useState } from "react";
import {
  Wheat,
  Warehouse,
  Users,
  Plus,
  Trash2,
  MapPin,
  DollarSign,
  Truck,
  Package,
  AlertCircle,
} from "lucide-react";
import type { Buyer, Producer } from "@/app/lib/api";

export interface HarvestInputValues {
  harvest_kg: Producer["harvest_kg"];
  storage_capacity_kg: Producer["storage_capacity_kg"];
  buyers: Buyer[];
}

export interface HarvestInputProps {
  onSubmit?: (values: HarvestInputValues) => void;
}

interface BuyerDraft {
  key: string;
  id: string;
  name: string;
  location: string;
  max_demand_kg: string;
  price_per_kg: string;
  distance_km: string;
  transport_cost_per_kg_per_km: string;
}

function emptyBuyerDraft(index: number): BuyerDraft {
  return {
    key: `buyer-${Date.now()}-${index}`,
    id: `buyer-${index + 1}`,
    name: "",
    location: "",
    max_demand_kg: "",
    price_per_kg: "",
    distance_km: "",
    transport_cost_per_kg_per_km: "",
  };
}

type FieldErrors = {
  harvest_kg?: string;
  storage_capacity_kg?: string;
  buyers?: string;
  buyerFields?: Record<string, Partial<Record<keyof BuyerDraft, string>>>;
};

const fieldBaseClasses =
  "w-full min-h-[44px] rounded-xl border-2 border-slate-700 bg-slate-800 " +
  "px-4 py-3 text-base text-slate-100 placeholder:text-slate-500 " +
  "focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-600/40";

function FieldLabel({
  icon: Icon,
  children,
  htmlFor,
}: {
  icon: typeof Wheat;
  children: React.ReactNode;
  htmlFor: string;
}) {
  return (
    <label
      htmlFor={htmlFor}
      className="mb-2 inline-flex items-center gap-2 text-base font-medium text-slate-100"
    >
      <Icon className="h-5 w-5 text-emerald-500" aria-hidden="true" />
      <span>{children}</span>
    </label>
  );
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p className="mt-2 inline-flex items-center gap-2 text-base text-rose-400" role="alert">
      <AlertCircle className="h-5 w-5 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </p>
  );
}

export default function HarvestInput({ onSubmit }: HarvestInputProps) {
  const [harvestKg, setHarvestKg] = useState("");
  const [storageCapacityKg, setStorageCapacityKg] = useState("");
  const [buyers, setBuyers] = useState<BuyerDraft[]>([emptyBuyerDraft(0)]);
  const [errors, setErrors] = useState<FieldErrors>({});

  function addBuyer() {
    setBuyers((prev) => [...prev, emptyBuyerDraft(prev.length)]);
  }

  function removeBuyer(key: string) {
    setBuyers((prev) => (prev.length > 1 ? prev.filter((b) => b.key !== key) : prev));
  }

  function updateBuyer(key: string, field: keyof BuyerDraft, value: string) {
    setBuyers((prev) =>
      prev.map((b) => (b.key === key ? { ...b, [field]: value } : b)),
    );
  }

  function validate(): { values: HarvestInputValues | null; errors: FieldErrors } {
    const nextErrors: FieldErrors = { buyerFields: {} };

    const harvestValue = Number(harvestKg);
    if (!harvestKg.trim() || Number.isNaN(harvestValue) || harvestValue <= 0) {
      nextErrors.harvest_kg = "Enter the harvested quantity in kg (must be greater than 0).";
    }

    const storageValue = Number(storageCapacityKg);
    if (!storageCapacityKg.trim() || Number.isNaN(storageValue) || storageValue < 0) {
      nextErrors.storage_capacity_kg = "Enter available storage capacity in kg (0 or more).";
    }

    if (buyers.length === 0) {
      nextErrors.buyers = "Add at least one buyer.";
    }

    const buyerFieldErrors: Record<string, Partial<Record<keyof BuyerDraft, string>>> = {};
    const validatedBuyers: Buyer[] = [];

    for (const buyer of buyers) {
      const fieldErrors: Partial<Record<keyof BuyerDraft, string>> = {};

      if (!buyer.name.trim()) fieldErrors.name = "Buyer name is required.";
      if (!buyer.location.trim()) fieldErrors.location = "Buyer location is required.";

      const maxDemand = Number(buyer.max_demand_kg);
      if (!buyer.max_demand_kg.trim() || Number.isNaN(maxDemand) || maxDemand <= 0) {
        fieldErrors.max_demand_kg = "Max demand must be greater than 0.";
      }

      const price = Number(buyer.price_per_kg);
      if (!buyer.price_per_kg.trim() || Number.isNaN(price) || price < 0) {
        fieldErrors.price_per_kg = "Price per kg must be 0 or more.";
      }

      const distance = Number(buyer.distance_km);
      if (!buyer.distance_km.trim() || Number.isNaN(distance) || distance < 0) {
        fieldErrors.distance_km = "Distance must be 0 or more.";
      }

      const transportCost = Number(buyer.transport_cost_per_kg_per_km);
      if (
        !buyer.transport_cost_per_kg_per_km.trim() ||
        Number.isNaN(transportCost) ||
        transportCost < 0
      ) {
        fieldErrors.transport_cost_per_kg_per_km = "Transport cost must be 0 or more.";
      }

      if (Object.keys(fieldErrors).length > 0) {
        buyerFieldErrors[buyer.key] = fieldErrors;
      } else {
        validatedBuyers.push({
          id: buyer.id,
          name: buyer.name.trim(),
          location: buyer.location.trim(),
          max_demand_kg: maxDemand,
          price_per_kg: price,
          distance_km: distance,
          transport_cost_per_kg_per_km: transportCost,
        });
      }
    }

    if (Object.keys(buyerFieldErrors).length > 0) {
      nextErrors.buyerFields = buyerFieldErrors;
    }

    const hasErrors =
      Boolean(nextErrors.harvest_kg) ||
      Boolean(nextErrors.storage_capacity_kg) ||
      Boolean(nextErrors.buyers) ||
      Object.keys(nextErrors.buyerFields ?? {}).length > 0;

    if (hasErrors) {
      return { values: null, errors: nextErrors };
    }

    return {
      values: {
        harvest_kg: harvestValue,
        storage_capacity_kg: storageValue,
        buyers: validatedBuyers,
      },
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
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border border-slate-700 bg-slate-900 p-4 shadow-lg md:p-6"
      noValidate
    >
      <h2 className="mb-6 inline-flex items-center gap-2 text-lg font-bold text-slate-100">
        <Wheat className="h-6 w-6 text-emerald-500" aria-hidden="true" />
        <span>Harvest Details</span>
      </h2>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div>
          <FieldLabel icon={Wheat} htmlFor="harvest_kg">
            Total Harvest (kg)
          </FieldLabel>
          <input
            id="harvest_kg"
            name="harvest_kg"
            type="number"
            inputMode="decimal"
            min={0}
            step="any"
            placeholder="e.g. 12000"
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
          <FieldLabel icon={Warehouse} htmlFor="storage_capacity_kg">
            Storage Capacity (kg)
          </FieldLabel>
          <input
            id="storage_capacity_kg"
            name="storage_capacity_kg"
            type="number"
            inputMode="decimal"
            min={0}
            step="any"
            placeholder="e.g. 2000"
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
      </div>

      <div className="mt-8">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="inline-flex items-center gap-2 text-lg font-bold text-slate-100">
            <Users className="h-6 w-6 text-emerald-500" aria-hidden="true" />
            <span>Buyers</span>
          </h3>
          <button
            type="button"
            onClick={addBuyer}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-base font-medium text-white hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-400"
          >
            <Plus className="h-5 w-5" aria-hidden="true" />
            <span>Add Buyer</span>
          </button>
        </div>

        {errors.buyers && <FieldError message={errors.buyers} />}

        <div className="space-y-6">
          {buyers.map((buyer, index) => {
            const buyerErrors = errors.buyerFields?.[buyer.key] ?? {};
            return (
              <div
                key={buyer.key}
                className="rounded-xl border border-slate-700 bg-slate-800/60 p-4"
              >
                <div className="mb-4 flex items-center justify-between">
                  <span className="text-base font-semibold text-slate-100">
                    Buyer {index + 1}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeBuyer(buyer.key)}
                    disabled={buyers.length === 1}
                    className="inline-flex min-h-[44px] items-center gap-2 rounded-xl px-3 py-2 text-base font-medium text-rose-400 hover:bg-rose-500/10 focus:outline-none focus:ring-2 focus:ring-rose-500/40 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <Trash2 className="h-5 w-5" aria-hidden="true" />
                    <span>Remove</span>
                  </button>
                </div>

                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <FieldLabel icon={Users} htmlFor={`${buyer.key}-name`}>
                      Buyer Name
                    </FieldLabel>
                    <input
                      id={`${buyer.key}-name`}
                      type="text"
                      placeholder="e.g. Local Cooperative"
                      className={fieldBaseClasses}
                      value={buyer.name}
                      onChange={(e) => updateBuyer(buyer.key, "name", e.target.value)}
                      aria-invalid={Boolean(buyerErrors.name)}
                    />
                    <FieldError message={buyerErrors.name} />
                  </div>

                  <div>
                    <FieldLabel icon={MapPin} htmlFor={`${buyer.key}-location`}>
                      Location
                    </FieldLabel>
                    <input
                      id={`${buyer.key}-location`}
                      type="text"
                      placeholder="e.g. Sfax"
                      className={fieldBaseClasses}
                      value={buyer.location}
                      onChange={(e) => updateBuyer(buyer.key, "location", e.target.value)}
                      aria-invalid={Boolean(buyerErrors.location)}
                    />
                    <FieldError message={buyerErrors.location} />
                  </div>

                  <div>
                    <FieldLabel icon={Package} htmlFor={`${buyer.key}-max_demand_kg`}>
                      Max Demand (kg)
                    </FieldLabel>
                    <input
                      id={`${buyer.key}-max_demand_kg`}
                      type="number"
                      inputMode="decimal"
                      min={0}
                      step="any"
                      placeholder="e.g. 4000"
                      className={fieldBaseClasses}
                      value={buyer.max_demand_kg}
                      onChange={(e) =>
                        updateBuyer(buyer.key, "max_demand_kg", e.target.value)
                      }
                      aria-invalid={Boolean(buyerErrors.max_demand_kg)}
                    />
                    <FieldError message={buyerErrors.max_demand_kg} />
                  </div>

                  <div>
                    <FieldLabel icon={DollarSign} htmlFor={`${buyer.key}-price_per_kg`}>
                      Price per kg
                    </FieldLabel>
                    <input
                      id={`${buyer.key}-price_per_kg`}
                      type="number"
                      inputMode="decimal"
                      min={0}
                      step="any"
                      placeholder="e.g. 0.85"
                      className={fieldBaseClasses}
                      value={buyer.price_per_kg}
                      onChange={(e) =>
                        updateBuyer(buyer.key, "price_per_kg", e.target.value)
                      }
                      aria-invalid={Boolean(buyerErrors.price_per_kg)}
                    />
                    <FieldError message={buyerErrors.price_per_kg} />
                  </div>

                  <div>
                    <FieldLabel icon={Truck} htmlFor={`${buyer.key}-distance_km`}>
                      Distance (km)
                    </FieldLabel>
                    <input
                      id={`${buyer.key}-distance_km`}
                      type="number"
                      inputMode="decimal"
                      min={0}
                      step="any"
                      placeholder="e.g. 45"
                      className={fieldBaseClasses}
                      value={buyer.distance_km}
                      onChange={(e) => updateBuyer(buyer.key, "distance_km", e.target.value)}
                      aria-invalid={Boolean(buyerErrors.distance_km)}
                    />
                    <FieldError message={buyerErrors.distance_km} />
                  </div>

                  <div>
                    <FieldLabel
                      icon={Truck}
                      htmlFor={`${buyer.key}-transport_cost_per_kg_per_km`}
                    >
                      Transport Cost (per kg/km)
                    </FieldLabel>
                    <input
                      id={`${buyer.key}-transport_cost_per_kg_per_km`}
                      type="number"
                      inputMode="decimal"
                      min={0}
                      step="any"
                      placeholder="e.g. 0.02"
                      className={fieldBaseClasses}
                      value={buyer.transport_cost_per_kg_per_km}
                      onChange={(e) =>
                        updateBuyer(
                          buyer.key,
                          "transport_cost_per_kg_per_km",
                          e.target.value,
                        )
                      }
                      aria-invalid={Boolean(buyerErrors.transport_cost_per_kg_per_km)}
                    />
                    <FieldError message={buyerErrors.transport_cost_per_kg_per_km} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <button
        type="submit"
        className="mt-8 inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-base font-semibold text-white hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-400 md:w-auto"
      >
        <Wheat className="h-5 w-5" aria-hidden="true" />
        <span>Run Optimization</span>
      </button>
    </form>
  );
}

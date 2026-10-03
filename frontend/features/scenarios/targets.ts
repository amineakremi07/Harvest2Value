import type { ChangeTargetKind, DatasetPayload } from "@/lib/api/types";

export const ALL_TARGET = "*";

type Collection = "buyers" | "harvest_lots" | "storage_facilities" | "vehicle_types" | "crops";

/** Which dataset collection each op's `target` refers to (backend `scenarios/operations.py`). */
const OP_COLLECTION: Record<string, Collection> = {
  buyer_price: "buyers",
  buyer_demand: "buyers",
  remove_buyer: "buyers",
  route: "buyers", // routes are keyed by buyer_id
  harvest_quantity: "harvest_lots",
  harvest_timing: "harvest_lots",
  storage_capacity: "storage_facilities",
  storage_cost: "storage_facilities",
  remove_storage: "storage_facilities",
  transport_cost: "vehicle_types",
  vehicle_count: "vehicle_types",
  vehicle_capacity: "vehicle_types",
  shelf_life: "crops",
};

export const OP_LABEL: Record<string, string> = {
  buyer_price: "Prix acheteur",
  buyer_demand: "Demande acheteur",
  harvest_quantity: "Quantité récoltée",
  harvest_timing: "Date de récolte",
  storage_capacity: "Capacité de stockage",
  storage_cost: "Coût de stockage",
  add_storage: "Ajouter un entrepôt",
  remove_storage: "Retirer un entrepôt",
  transport_cost: "Coût de transport",
  vehicle_count: "Nombre de véhicules",
  vehicle_capacity: "Capacité des véhicules",
  shelf_life: "Durée de conservation",
  add_buyer: "Ajouter un acheteur",
  remove_buyer: "Retirer un acheteur",
  route: "Itinéraire",
  cold_chain: "Chaîne du froid",
};

export function opLabel(op: string): string {
  return OP_LABEL[op] ?? op;
}

export interface TargetOption {
  value: string;
  label: string;
}

/** `cold_chain` targets a buyer or a crop depending on `params.entity`. */
export function targetCollection(op: string, params: Record<string, unknown>): Collection | null {
  if (op === "cold_chain") return params.entity === "crop" ? "crops" : "buyers";
  return OP_COLLECTION[op] ?? null;
}

export function targetOptions(
  op: string,
  kind: ChangeTargetKind,
  payload: DatasetPayload | undefined,
  params: Record<string, unknown> = {},
): TargetOption[] {
  if (kind === "none" || !payload) return [];
  const collection = targetCollection(op, params);
  if (!collection) return [];
  const items: TargetOption[] = (() => {
    switch (collection) {
      case "buyers":
        return payload.buyers.map((b) => ({ value: b.id, label: b.name }));
      case "harvest_lots":
        return payload.harvest_lots.map((l) => ({ value: l.id, label: `${l.id} — ${Math.round(l.quantity_kg)} kg, J${l.available_day ?? 0}` }));
      case "storage_facilities":
        return (payload.storage_facilities ?? []).map((f) => ({ value: f.id, label: f.name }));
      case "vehicle_types":
        return payload.vehicle_types.map((v) => ({ value: v.id, label: v.name }));
      case "crops":
        return payload.crops.map((c) => ({ value: c.id, label: c.name }));
    }
  })();
  return kind === "one_or_all" ? [{ value: ALL_TARGET, label: "Tous" }, ...items] : items;
}

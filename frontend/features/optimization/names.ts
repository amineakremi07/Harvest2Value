import type { DatasetPayload } from "@/lib/api/types";

/** Display names of the dataset entities referenced by id in a result. */
export interface NameIndex {
  buyers?: Record<string, string>;
  facilities?: Record<string, string>;
  vehicles?: Record<string, string>;
  lots?: Record<string, string>;
}

export function nameIndex(payload: DatasetPayload | undefined): NameIndex {
  if (!payload) return {};
  const byId = <T extends { id: string }>(items: T[] | undefined, label: (item: T) => string) =>
    Object.fromEntries((items ?? []).map((item) => [item.id, label(item)]));
  return {
    buyers: byId(payload.buyers, (b) => b.name),
    facilities: byId(payload.storage_facilities, (f) => f.name),
    vehicles: byId(payload.vehicle_types, (v) => v.name),
    lots: byId(payload.harvest_lots, (l) => `${l.id} (J${l.available_day ?? 0})`),
  };
}

export function nameOf(map: Record<string, string> | undefined, id: string | null | undefined): string {
  if (!id) return "—";
  return map?.[id] ?? id;
}

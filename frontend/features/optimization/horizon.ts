import type { DatasetPayload } from "@/lib/api/types";

/** Mirrors backend `build_instance` (optimization/instance.py) when `horizon_days` is not set. */
export const MAX_HORIZON_DAYS = 60;

/** Crops that are actually harvested (a run needs `crop_id` when there are several). */
export function harvestedCrops(payload: DatasetPayload): { id: string; name: string }[] {
  const ids = new Set(payload.harvest_lots.map((l) => l.crop_id));
  return payload.crops.filter((c) => ids.has(c.id)).map((c) => ({ id: c.id, name: c.name }));
}

/**
 * Default horizon: max over the crop's lots of (available day + longest shelf life among the
 * storage facilities usable for that crop), capped at 60 days.
 */
export function suggestedHorizon(payload: DatasetPayload, cropId?: string | null): number {
  const harvested = harvestedCrops(payload);
  const id = cropId ?? harvested[0]?.id;
  const crop = payload.crops.find((c) => c.id === id);
  if (!crop) return MAX_HORIZON_DAYS;

  const shelfLives = (payload.storage_facilities ?? [])
    .filter((f) => f.capacity_kg > 0)
    .filter((f) => f.refrigerated || !crop.requires_cold_chain)
    .map((f) =>
      f.refrigerated ? (crop.shelf_life_cold_days ?? crop.shelf_life_ambient_days) : crop.shelf_life_ambient_days,
    );
  const longestShelf = Math.max(1, ...shelfLives);
  const lots = payload.harvest_lots.filter((l) => l.crop_id === crop.id);
  const end = Math.max(...lots.map((l) => (l.available_day ?? 0) + longestShelf));
  return Math.min(MAX_HORIZON_DAYS, end);
}

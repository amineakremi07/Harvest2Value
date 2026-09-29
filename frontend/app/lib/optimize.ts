import { MOCK_OPTIMIZE_RESPONSE, type OptimizeRequest } from "@/app/lib/api";

export interface HarvestValues {
  harvest_kg: number;
  storage_capacity_kg: number;
}

/** Matches MOCK_OPTIMIZE_RESPONSE so the demo plan and its dataset agree. */
export const DEMO_INPUT: HarvestValues = {
  harvest_kg: MOCK_OPTIMIZE_RESPONSE.total_harvest_kg,
  storage_capacity_kg: MOCK_OPTIMIZE_RESPONSE.stored_kg,
};

/**
 * The backend's OptimizeRequest schema requires a non-empty `buyers` list, but
 * buyers are chosen by the optimizer, not entered by the user. Until the
 * backend exposes a buyer directory (or makes buyers optional), we submit this
 * placeholder candidate pool; the optimizer decides what each one gets.
 */
const DEFAULT_BUYER_POOL = [
  {
    id: "buyer-1",
    name: "Local Cooperative",
    location: "Nearby Market",
    max_demand_kg: 50000,
    price_per_kg: 0.8,
    distance_km: 15,
    transport_cost_per_kg_per_km: 0.01,
  },
  {
    id: "buyer-2",
    name: "Regional Distributor",
    location: "Regional Hub",
    max_demand_kg: 50000,
    price_per_kg: 0.65,
    distance_km: 60,
    transport_cost_per_kg_per_km: 0.008,
  },
];

/**
 * Builds a valid OptimizeRequest from the two numbers the UI collects. The
 * remaining fields have no form yet, so they get sensible defaults.
 * `producer` optionally labels the dataset (e.g. with a delegation name).
 */
export function buildOptimizeRequest(
  values: HarvestValues,
  producer: { name: string; region: string } = { name: "My Farm", region: "Unknown" },
): OptimizeRequest {
  return {
    producer: {
      id: "producer-1",
      name: producer.name,
      region: producer.region,
      country: producer.region === "Unknown" ? "Unknown" : "Tunisia",
      harvest_kg: values.harvest_kg,
      storage_capacity_kg: values.storage_capacity_kg,
      shelf_life_days: 14,
    },
    buyers: DEFAULT_BUYER_POOL,
    crop: { name: "Mixed Produce", type: "semi_perishable" },
    logistics: {
      available_vehicles: 1,
      vehicle_capacity_kg: Math.max(values.harvest_kg, 1000),
      refrigerated_required: false,
      road_condition: "fair",
    },
  };
}

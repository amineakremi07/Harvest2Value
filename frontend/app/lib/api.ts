// Typed API client for the Harvest2Value backend.
// Types mirror backend/app/models/schemas.py exactly — keep in sync.
// If a mismatch is found, notify Member 1 (Lead/Backend); do not edit backend files here.

const API_BASE_URL = "http://localhost:8000/api/v1";

// ---- Request types ----

export interface Producer {
  id: string;
  name: string;
  region: string;
  country: string;
  harvest_kg: number;
  storage_capacity_kg: number;
  storage_cost_per_kg_per_day?: number;
  shelf_life_days: number;
}

export interface Buyer {
  id: string;
  name: string;
  location: string;
  max_demand_kg: number;
  price_per_kg: number;
  distance_km: number;
  transport_cost_per_kg_per_km: number;
}

export interface Logistics {
  available_vehicles: number;
  vehicle_capacity_kg: number;
  refrigerated_required?: boolean;
  road_condition?: "good" | "fair" | "poor";
}

export interface Crop {
  name: string;
  type: "perishable" | "semi_perishable" | "durable";
  unit?: string;
}

export interface OptimizeRequest {
  producer: Producer;
  buyers: Buyer[];
  crop: Crop;
  logistics: Logistics;
}

export interface ScenarioRequest {
  query: string;
  data: Record<string, unknown>;
}

export interface ExplainRequest {
  result: Record<string, unknown>;
  data: Record<string, unknown>;
}

// ---- Response types ----

export interface AllocationDetail {
  buyer_name: string;
  allocated_kg: number;
  unit_price: number;
  revenue: number;
  transport_cost: number;
  net_profit: number;
  distance_km: number;
}

export interface OptimizeResponse {
  status: string;
  total_harvest_kg: number;
  allocated_kg: number;
  stored_kg: number;
  wasted_kg: number;
  total_revenue: number;
  total_transport_cost: number;
  net_profit: number;
  allocation: Record<string, AllocationDetail>;
  solver_time_seconds: number;
  metadata: Record<string, unknown>;
}

export interface ExplainResponse {
  explanation: string;
}

// ---- Error handling ----

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly cause?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function postJson<TResponse>(
  path: string,
  body: unknown,
): Promise<TResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    throw new ApiError(
      `Network error calling ${path} — is the backend running on :8000?`,
      undefined,
      err,
    );
  }

  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text().catch(() => undefined);
    }
    throw new ApiError(
      `Request to ${path} failed with status ${response.status}`,
      response.status,
      detail,
    );
  }

  try {
    return (await response.json()) as TResponse;
  } catch (err) {
    throw new ApiError(`Malformed JSON response from ${path}`, response.status, err);
  }
}

// ---- Mock fallback data for offline component development/testing ----

export const MOCK_OPTIMIZE_RESPONSE: OptimizeResponse = {
  status: "optimal",
  total_harvest_kg: 12000,
  allocated_kg: 10200,
  stored_kg: 1500,
  wasted_kg: 300,
  total_revenue: 8160,
  total_transport_cost: 612,
  net_profit: 7548,
  allocation: {
    buyer_1: {
      buyer_name: "Local Cooperative",
      allocated_kg: 6000,
      unit_price: 0.85,
      revenue: 5100,
      transport_cost: 240,
      net_profit: 4860,
      distance_km: 12,
    },
    buyer_2: {
      buyer_name: "Regional Market",
      allocated_kg: 4200,
      unit_price: 0.73,
      revenue: 3066,
      transport_cost: 372,
      net_profit: 2694,
      distance_km: 45,
    },
  },
  solver_time_seconds: 0.42,
  metadata: { mock: true, reason: "offline fallback" },
};

export const MOCK_EXPLAIN_RESPONSE: ExplainResponse = {
  explanation:
    "This is mock offline data: the solver allocated most of the harvest to the " +
    "nearest buyer to minimize transport cost, storing the remainder within the " +
    "crop's shelf life to avoid waste.",
};

// ---- Public API functions ----

export async function optimizeHarvest(
  request: OptimizeRequest,
  { useMockOnError = false }: { useMockOnError?: boolean } = {},
): Promise<OptimizeResponse> {
  try {
    return await postJson<OptimizeResponse>("/optimize", request);
  } catch (err) {
    if (useMockOnError) {
      console.warn("optimizeHarvest: falling back to mock data", err);
      return MOCK_OPTIMIZE_RESPONSE;
    }
    throw err;
  }
}

export async function runScenario(
  request: ScenarioRequest,
  { useMockOnError = false }: { useMockOnError?: boolean } = {},
): Promise<OptimizeResponse> {
  try {
    return await postJson<OptimizeResponse>("/scenario", request);
  } catch (err) {
    if (useMockOnError) {
      console.warn("runScenario: falling back to mock data", err);
      return MOCK_OPTIMIZE_RESPONSE;
    }
    throw err;
  }
}

export async function explainAllocation(
  request: ExplainRequest,
  { useMockOnError = false }: { useMockOnError?: boolean } = {},
): Promise<ExplainResponse> {
  try {
    return await postJson<ExplainResponse>("/explain", request);
  } catch (err) {
    if (useMockOnError) {
      console.warn("explainAllocation: falling back to mock data", err);
      return MOCK_EXPLAIN_RESPONSE;
    }
    throw err;
  }
}

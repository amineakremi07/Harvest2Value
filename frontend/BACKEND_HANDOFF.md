# Backend Handoff — `feature/crda-frontend`

What the frontend currently mocks or assumes, and what the backend engineer
(`feature/crda-backend-ai`) needs to provide. Everything below marked
**proposed** is a suggestion for the backend to accept or change; the frontend
adapts once the contract is agreed. Existing frozen endpoints
(`/api/v1/optimize`, `/scenario`, `/explain`, `/chat`) are unchanged.

---

## 1. Auth (`/auth/login`, `/auth/2fa`)

**Today:** fully mocked in `app/lib/auth.ts`. Nothing is sent to a server,
credentials are never checked, any 6-digit code passes, and the "session" is a
localStorage flag (`h2v.isAuthenticated`). It only gates the routes and is not a
security boundary.

**Fields the UI collects** (login form):

| Field | UI label | Notes |
|---|---|---|
| `email` | Official email | Standard email format |
| `delegation_id` | Delegation ID | Free text today (e.g. `MRN-01`); should match `Delegation.id` |
| `agent_code` | Agent code | Password input; never stored client-side |

**Proposed endpoints**

`POST /api/v1/auth/login` → step 1, triggers the emailed code
```json
// request
{ "email": "agent@crda.tn", "delegation_id": "MRN-01", "agent_code": "••••" }
// response 200
{ "challenge_id": "opaque-string", "email_hint": "a***@crda.tn", "expires_in": 300 }
```
`POST /api/v1/auth/2fa` → step 2
```json
// request
{ "challenge_id": "opaque-string", "code": "123456" }
// response 200
{ "access_token": "jwt", "token_type": "bearer", "expires_in": 3600,
  "agent": { "email": "agent@crda.tn", "delegation_id": "MRN-01" } }
```
Errors: `401` bad credentials/code, `429` too many attempts, `410` challenge
expired. Prefer an httpOnly cookie over a token in localStorage.

**Frontend changes once this exists:** `beginLogin`/`verifyCode`/`logout` in
`app/lib/auth.ts` become API calls; `DashboardShell` keeps its guard, driven by
the real session; all data endpoints below need the token and should scope
results to the agent's delegation(s).

---

## 2. Data model alignment (`types/index.ts` ↔ Pydantic)

The frontend types use **camelCase** and are mock-backed
(`MOCK_DELEGATIONS`, `MOCK_FARMERS`, `MOCK_FACILITIES`). The existing API
(`app/lib/api.ts`) uses **snake_case**. Recommendation: the backend stays
snake_case and the frontend maps at the API boundary (or use a Pydantic
`alias_generator=to_camel`; pick one and stay consistent).

### Delegation
| Frontend | Backend (proposed) |
|---|---|
| `id: string` | `id: str` (stable slug, e.g. `mornag`) |
| `name: string` | `name: str` |
| `governorate: string` | `governorate: str` |

### CropHarvest (a farmer's harvest for the current period)
| Frontend | Backend (proposed) |
|---|---|
| `crop: CropType` (`tomatoes \| wheat \| olives \| citrus`) | `crop: Literal["tomatoes","wheat","olives","citrus"]` (use an `Enum`; agree on the list, more crops are expected) |
| `yieldKg` | `yield_kg: float` (≥ 0) |
| `wasteKg` | `waste_kg: float` (≥ 0, ≤ `yield_kg`; the form enforces this) |
| `incomeTnd` | `income_tnd: float` (≥ 0) |

Crop perishability (`perishable / semi_perishable / durable`) is a frontend
constant today (`CROPS`); it should come from the backend, since the LP model
uses it.

### PeriodSnapshot (history, oldest first)
`period: str` (e.g. `2026-Q2`), `yield_kg`, `waste_kg`, `income_tnd`. The
current period is *derived* on the frontend from `crops`; the backend should
either do the same or return the current snapshot explicitly. Period format and
cadence (quarterly?) need to be fixed.

### Farmer
| Frontend | Backend (proposed) |
|---|---|
| `id` | `id: str` (server-generated; the form currently creates `f-<delegation>-<timestamp>`) |
| `name` | `name: str` |
| `delegationId` | `delegation_id: str` (FK) |
| `phone?` | `phone: str \| None` |
| `storageCapacityKg` | `storage_capacity_kg: float` |
| `crops: CropHarvest[]` | `crops: list[CropHarvest]` (one per crop; reject duplicates) |
| `history: PeriodSnapshot[]` | `history: list[PeriodSnapshot]` |

### StorageFacility
| Frontend | Backend (proposed) |
|---|---|
| `id`, `name` | `id: str`, `name: str` |
| `delegationId` | `delegation_id: str` |
| `kind: silo \| cold_storage \| warehouse` | `kind: Literal[...]` / `Enum` |
| `currentStockKg` | `current_stock_kg: float` |
| `maxCapacityKg` | `max_capacity_kg: float` (≥ `current_stock_kg`) |

### Endpoints the UI needs (proposed)
| Method & path | Used by | Notes |
|---|---|---|
| `GET /api/v1/delegations` | header selector, settings | |
| `GET /api/v1/delegations/{id}/farmers` | dashboard, farmers, analytics | include `history` |
| `POST /api/v1/farmers` | Add / Quick Add farmer | body = Farmer without `id`, returns Farmer |
| `PUT /api/v1/farmers/{id}` | Edit farmer | keeps `history` |
| `GET /api/v1/delegations/{id}/facilities` | dashboard, storage | |
| `GET /api/v1/analytics/deltas?delegation_id=&period=` | farmers table badges, analytics | see below |

### Delta metrics — who owns the calculation
Computed on the frontend today (`pctChange`, `computeDeltaMetrics` in
`types/index.ts`):
- `Δ Income % = (income_t − income_{t−1}) / income_{t−1} × 100`
- `Δ Waste %  = (waste_t − waste_{t−1}) / waste_{t−1} × 100`
- previous value `0`/missing → `null` (UI shows "—"); |Δ| < 0.05% counts as flat.
- Income ↑ is good, waste ↓ is good.

The analytics engine should own this. Proposed response shape per farmer and
per delegation: `{ income: { pct: float | null }, waste: { pct: float | null } }`;
direction and good/bad can stay derived on the frontend.

### Placeholders that need a real source
- **Regional Health / Risk Score** (`app/lib/regionStats.ts`): frontend
  heuristic `100 − 4·waste% − 0.8·max(0, fill% − 75)`. Backend to define the
  official score and serve it.
- **Weather** (header) and **temperature/humidity** (storage card): sample
  values per delegation; need a weather/sensor source.
- **Chat history** (AI Assistant sidebar): three static sample transcripts;
  needs conversation storage (`GET /api/v1/chat/history`, per agent).

---

## 3. AI assistant needs farmer-level context

**Today:** `/ai-assistant` calls `POST /api/v1/chat` with
`{ message, data, result: null, history }`. The backend validates `data` as an
`OptimizeRequest` (`validated_scenario_data` in `routers/scenario.py`), so the
frontend collapses the whole delegation into one fake producer:

```json
{
  "producer": { "name": "Mornag delegation", "region": "Mornag", "country": "Tunisia",
                "harvest_kg": <sum of all farmers' yield>,
                "storage_capacity_kg": <sum of all facilities' max capacity>,
                "shelf_life_days": 14 },
  "buyers": [ /* placeholder pool */ ],
  "crop": { "name": "Mixed Produce", "type": "semi_perishable" },
  "logistics": { ... defaults ... }
}
```
So the model cannot see individual farmers, crops, waste, facilities or
trends, and questions like "Which storage facility has the highest capacity
risk?" cannot be answered from real data.

**Requirement (proposed):** accept delegation context instead of forcing an
`OptimizeRequest`. Either a new field or a new endpoint; the frontend will send
whichever is chosen.

```json
POST /api/v1/chat   // add optional `context`, keep `data` optional when context is present
{
  "message": "Which storage facility has the highest capacity risk?",
  "history": [ { "role": "user", "content": "..." } ],
  "context": {
    "delegation_id": "mornag",
    "period": "2026-Q3",
    "farmer_ids": null          // null = whole delegation, or a subset / single farmer
  }
}
```
Preferred: the frontend sends **IDs only** and the backend loads farmers,
`CropHarvest`s, facilities and history from its own database, then builds the
Groq system prompt server-side (this also matches the plan to "inject
delegation context into the Groq system prompt"). It avoids trusting
client-supplied data and keeps payloads small. The fallback is the frontend
sending full `Farmer[]` + `StorageFacility[]` in `context`.

Also needed:
- **Multi-crop / perishability** in the What-If path (`extract_constraints`,
  `merge_constraints`, `solve_optimization`), so scenarios like "what if tomato
  prices drop 10%" or "move tomatoes to cold storage" resolve against farmers
  and facilities, not a single crop.
- **Response**: keep `{ message, type?, result?, data? }`. For farmer→facility
  transfers, a `result` shape that lists transfers
  (`farmer_id`, `facility_id`, `crop`, `kg`) so the UI can render allocation
  results (frontend task 4).
- **Errors**: keep the current mapping (`422` invalid scenario, `503` missing
  `GROQ_API_KEY`, `502` LLM failure); the UI surfaces `detail` text.
- **Auth**: require the session from section 1 and reject `delegation_id`
  values the agent is not assigned to.

---

## 4. Frontend notes for reviewers
- Sample data lives in `types/index.ts` and `app/context/DelegationProvider.tsx`
  (state is in-memory; refresh resets edits). Replace with fetches there.
- `/optimization` is the pre-CRDA optimizer page, unchanged and still wired to
  the frozen endpoints (with a placeholder buyer pool, `app/lib/optimize.ts`).
  It is reachable from the dashboard but not the sidebar.
- Known lint errors remain in `FlowChart.tsx` and `SankeyChart.tsx`
  (pre-existing: `any`, setState-in-effect, hook deps).

---

## 5. Optimization plan & per-farmer analytics (added)

`/optimization` → "Regional plan" and the farmer analytics drawer on `/farmers`
use a **frontend rule-based planner** (`app/lib/reallocation.ts`), not the
solver. It exists so the flow (input summary → run → before/after → actions)
can be built and reviewed now. It should be replaced by the backend multi-crop
solver.

**What the planner assumes (replace with real model parameters):**
- Spoilage rate per crop = `waste_kg / yield_kg`.
- Share of harvest outside a cold chain: perishable 40%, semi-perishable 30%,
  durable 15%.
- Spoilage avoided when stored in a facility type (`RECOVERY` table): e.g.
  cold storage 75% for perishable, silo 70% for durable.
- Riskiest crops are placed first; facility chosen by best recovery among those
  with free capacity. Deadlines: 48 h / 7 days / 30 days by perishability.
- Farmer risk from spoilage rate: ≥ 6% high, ≥ 3.5% medium, else low.

**Requested endpoint (proposed):** `POST /api/v1/optimize/regional`
```json
// request
{ "delegation_id": "mornag", "period": "2026-Q3" }
// response
{
  "baseline":  { "yield_kg": 0, "waste_kg": 0, "waste_pct": 0, "income_tnd": 0 },
  "optimized": { "yield_kg": 0, "waste_kg": 0, "waste_pct": 0, "income_tnd": 0 },
  "transfers": [
    { "farmer_id": "f-mornag-1", "crop": "tomatoes", "kg": 3680,
      "facility_id": "s-mornag-1", "deadline_hours": 48,
      "avoided_waste_kg": 186, "avoided_income_tnd": 223 }
  ],
  "solver_time_seconds": 0.4
}
```
The UI derives risk badges, the recommendation sentence, percentages and
projected facility fill from this. A per-farmer recommendation can also come
from the LLM (`/chat` with `context.farmer_ids`, see §3).

**Missing data:** the farmer drawer's "Storage Allocation Status" shows the
*recommended* facility allocation only. The data model has no record of which
facility currently holds which farmer's stock; add e.g.
`GET /api/v1/farmers/{id}/holdings` → `[{ facility_id, crop, kg }]` if the UI
should show current holdings.

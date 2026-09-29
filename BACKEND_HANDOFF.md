# Backend Handoff — CRDA Dashboard

For the backend & AI engineer (`feature/crda-backend-ai`). The frontend
(`feature/crda-frontend`, under `frontend/`) is complete on **mock data**. This
document says what it expects, in the order to build it.

Everything marked **proposed** is a suggestion for you to accept or change; tell
the frontend and it adapts. Existing frozen endpoints (`/api/v1/optimize`,
`/scenario`, `/explain`, `/chat`) must keep working unchanged.

---

## 1. Overview & current architecture

### How the frontend is wired today
- Domain entities live in `frontend/types/index.ts` with **mock fixtures**
  (`MOCK_DELEGATIONS`, `MOCK_FARMERS`, `MOCK_FACILITIES`). Use these as the
  reference shapes and as seed data (Task 3).
- All app state is in `frontend/app/context/DelegationProvider.tsx` (in memory).
  Swapping mocks for API calls happens there.
- Auth is a **UI-only mock** (`frontend/app/lib/auth.ts`): no request is made, any
  6-digit code passes. It gates routes only and is not security.
- The only real backend calls are the pre-existing ones in
  `frontend/app/lib/api.ts` (`/optimize`, `/chat`, …), used by `/optimization`
  (Buyer allocation tab) and `/ai-assistant`.
- Two things are computed on the frontend that should move to the backend:
  the **regional reallocation plan** (`frontend/app/lib/reallocation.ts`, a
  rule-based estimate) and **Δ metrics** (`computeDeltaMetrics` in `types/index.ts`).

### Entity alignment (TypeScript ↔ Pydantic)
The frontend types are camelCase. **Recommendation: the new API is snake_case**
(matches your specified auth fields and the existing API) and the frontend maps
at one boundary when integrating. Field-for-field:

| TS entity (`types/index.ts`) | Pydantic (proposed) |
|---|---|
| `Delegation { id, name, governorate }` | `Delegation { id: str, name: str, governorate: str }` |
| `CropHarvest { crop, yieldKg, wasteKg, incomeTnd }` | `CropHarvest { crop: CropType, yield_kg: float, waste_kg: float, income_tnd: float }` |
| `PeriodSnapshot { period, yieldKg, wasteKg, incomeTnd }` | `PeriodSnapshot { period: str, yield_kg, waste_kg, income_tnd }` |
| `Farmer { id, name, delegationId, phone?, storageCapacityKg, crops, history }` | `Farmer { id, name, delegation_id, phone: str \| None, storage_capacity_kg, crops: list[CropHarvest], history: list[PeriodSnapshot] }` |
| `StorageFacility { id, name, delegationId, kind, currentStockKg, maxCapacityKg }` | `StorageFacility { id, name, delegation_id, kind: FacilityKind, current_stock_kg, max_capacity_kg }` |
| `DeltaMetrics { income: DeltaValue, waste: DeltaValue }` | see §3.5 |

Enums: `CropType = "tomatoes" \| "wheat" \| "olives" \| "citrus"` (more crops are
expected; make it an `Enum`, not a hardcoded list in routers) and
`FacilityKind = "silo" \| "cold_storage" \| "warehouse"`. Crop **perishability**
(`perishable \| semi_perishable \| durable`) is a frontend constant today
(`CROPS`); it should come from the backend since the solver needs it.

Validation the UI already enforces (mirror it server-side): yield > 0;
`0 ≤ waste_kg ≤ yield_kg`; income ≥ 0; storage capacity ≥ 0; one `CropHarvest`
per crop per farmer; `0 ≤ current_stock_kg ≤ max_capacity_kg`.

### Conventions for all new endpoints (proposed)
- Prefix `/api/v1`, JSON, snake_case, `Authorization: Bearer <jwt>` after Task 1.
- Errors as `{ "detail": "human readable message" }` (the UI shows `detail`).
  `401` unauthenticated, `403` wrong delegation, `404`, `422` validation,
  `429` rate limit, `503` missing `GROQ_API_KEY`, `502` LLM failure.

---

## 2. Prioritized task list

| # | Task | Priority | Unblocks |
|---|---|---|---|
| 1 | Auth endpoints | **High** | route guard, per-delegation scoping of every other endpoint |
| 2 | Regional optimization endpoint | **High** | Dashboard hero, `/optimization` Regional plan, farmer analytics |
| 3 | Data ingestion & seeding | Medium | real data for everything; needed by Tasks 2 and 4 in production |
| 4 | AI assistant farmer-level context | Medium | `/ai-assistant` answers about real farmers and facilities |

Suggested order: build 1 first (small, unblocks scoping). Task 2 can start
against in-memory fixtures copied from `types/index.ts`, then read from the DB
once Task 3 lands. Task 4 depends on Task 3's data.

---

### Task 1 (High): Auth endpoints

**Today:** mocked. **Fields collected by the login form:** `email` (official CRDA
email), `delegation_id` (free text, e.g. `MRN-01`; should equal `Delegation.id` or
map to it), `agent_code` (password field, never stored client-side).

`POST /api/v1/auth/login` — step 1, verifies credentials, emails a 6-digit code.
```json
// request
{ "email": "agent@crda.tn", "delegation_id": "mornag", "agent_code": "s3cret-code" }
// 200
{ "challenge_id": "c_8f2a91d0", "email_hint": "a***@crda.tn", "expires_in": 300 }
```
`POST /api/v1/auth/2fa` — step 2, verifies the code, returns the session.
```json
// request
{ "challenge_id": "c_8f2a91d0", "code": "482913" }
// 200
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 3600,
  "agent": { "email": "agent@crda.tn", "delegation_id": "mornag" }
}
```
Errors: `401` bad credentials or wrong code, `410` challenge expired, `429` too many
attempts (rate-limit per email and per IP). Never reveal whether the email exists.
Prefer an httpOnly cookie over a token in localStorage; if a token is returned,
say so and the frontend will store it accordingly.

**Also needed:** an agent → delegation(s) assignment. Every data endpoint below
must scope to the agent's delegations and return `403` otherwise.

**Frontend on completion:** `beginLogin`/`verifyCode`/`logout` in
`app/lib/auth.ts` become API calls; `DashboardShell`'s guard keeps working off
the real session.

---

### Task 2 (High): Regional optimization endpoint

`POST /api/v1/optimize/regional` — multi-crop reallocation across a delegation's
farmers and facilities. Replaces the frontend rule-based planner.

**Request (proposed):** by IDs (server loads data), with optional overrides for
what-if runs.
```json
{
  "delegation_id": "mornag",
  "period": "2026-Q3",
  "overrides": {
    "facilities": [
      { "id": "s-mornag-1", "max_capacity_kg": 30000 }
    ],
    "crop_prices_tnd_per_kg": { "tomatoes": 1.3 }
  }
}
```
`overrides` is optional. If you prefer inline data instead of IDs, accept
`farmers: Farmer[]` and `facilities: StorageFacility[]` in the same shapes as §3.

**Solver requirements:** per-crop harvest weights (`yield_kg`, `waste_kg`) and
perishability; per-facility capacity (`max_capacity_kg − current_stock_kg`) and
`kind`; a per-kind, per-perishability spoilage-avoidance model (the frontend
placeholder is `RECOVERY` in `reallocation.ts`: e.g. cold storage 75% for
perishable, silo 70% for durable). Objective: minimize waste, then maximize net
regional revenue. Keep the response deterministic for the same input.

**Response (matches what `RegionalOptimizer` and `OptimizationHero` render):**
```json
{
  "delegation_id": "mornag",
  "period": "2026-Q3",
  "baseline":  { "yield_kg": 22400, "waste_kg": 1190, "waste_pct": 5.3, "income_tnd": 35260 },
  "optimized": { "yield_kg": 22400, "waste_kg": 900,  "waste_pct": 4.0, "income_tnd": 35660 },
  "avoided_waste_kg": 288,
  "income_gain_pct": 1.15,
  "transfers": [
    {
      "farmer_id": "f-mornag-1",
      "crop": "tomatoes",
      "kg": 3680,
      "facility_id": "s-mornag-1",
      "deadline_hours": 48,
      "avoided_waste_kg": 186,
      "avoided_income_tnd": 223
    }
  ],
  "solver_time_seconds": 0.42
}
```
The UI derives risk badges, the recommendation sentence, percentages and
projected facility fill from this. (Names are added client-side by joining
`farmer_id`/`facility_id`; include `farmer_name`/`facility_name` if you prefer.)

**Acceptance:** transfers never exceed free facility capacity; one
transfer line per (farmer, crop, facility); `optimized.waste_kg ≤ baseline.waste_kg`.

---

### Task 3 (Medium): Data ingestion & seeding

**Goal:** real, expanded Tunisian datasets for **Mornag, Tebourba, Kelibia** in
SQLite/PostgreSQL instead of the six-farmer mock.

Tables (SQLAlchemy): `delegations`, `farmers`, `crop_harvests`
(farmer × crop × period), `facilities`, `period_snapshots` (or derive from
`crop_harvests`), `agents` and their delegation assignments (Task 1).

Deliverables:
- `backend/scripts/seed.py` — **idempotent** (safe to re-run), seeds the three
  delegations, 15–30 farmers each, 4+ quarters of history, and 2–4 facilities
  per delegation. Keep it plausible per region: Mornag (tomatoes, citrus,
  olives), Tebourba (wheat, olives), Kelibia (citrus, tomatoes).
- Include the exact mock records from `frontend/types/index.ts` as a subset so
  the UI looks the same before and after the switch.
- Read endpoints the UI needs:

| Method & path | Used by |
|---|---|
| `GET /api/v1/delegations` | header selector, settings |
| `GET /api/v1/delegations/{id}/farmers` (includes `history`) | dashboard, farmers, analytics |
| `POST /api/v1/farmers` (body = Farmer without `id`) → `Farmer` | Add / Quick Add farmer |
| `PUT /api/v1/farmers/{id}` (keeps `history`) → `Farmer` | Edit farmer |
| `GET /api/v1/delegations/{id}/facilities` | dashboard, storage |
| `GET /api/v1/farmers/{id}/holdings` → `[{facility_id, crop, kg}]` | *(new)* farmer panel: which facility holds which stock |

Note the missing piece: today's data has **no record of which facility holds
which farmer's stock**; the farmer panel and drawer only show a *recommended*
facility. `holdings` fixes that.

**Example seed record** (also the exact shape returned by the farmers endpoint):
```json
{
  "id": "f-mornag-1",
  "name": "Slim Ben Salah",
  "delegation_id": "mornag",
  "phone": "+216 20 111 001",
  "storage_capacity_kg": 18000,
  "crops": [
    { "crop": "tomatoes", "yield_kg": 9200, "waste_kg": 620, "income_tnd": 11040 },
    { "crop": "citrus",   "yield_kg": 4100, "waste_kg": 180, "income_tnd": 7380 }
  ],
  "history": [
    { "period": "2025-Q3", "yield_kg": 12800, "waste_kg": 1240, "income_tnd": 17200 },
    { "period": "2025-Q4", "yield_kg": 13100, "waste_kg": 1150, "income_tnd": 17900 },
    { "period": "2026-Q1", "yield_kg": 12600, "waste_kg": 1010, "income_tnd": 18100 },
    { "period": "2026-Q2", "yield_kg": 13000, "waste_kg": 930,  "income_tnd": 18000 }
  ]
}
```
```json
{
  "id": "s-mornag-1",
  "name": "Mornag Cold Storage",
  "delegation_id": "mornag",
  "kind": "cold_storage",
  "current_stock_kg": 21000,
  "max_capacity_kg": 35000
}
```
```json
{ "id": "mornag", "name": "Mornag", "governorate": "Ben Arous" }
```
Decisions needed from you: period format/cadence (frontend assumes quarterly
`YYYY-Qn`, current period `2026-Q3`), and whether the "current period" is stored
or derived from `crop_harvests` (the frontend derives it from `crops`).

**Delta metrics** (`DeltaMetrics`), owned by the analytics engine:
`Δ Income % = (income_t − income_{t−1}) / income_{t−1} × 100`,
`Δ Waste % = (waste_t − waste_{t−1}) / waste_{t−1} × 100`. Previous value `0` or
missing → `null`. Suggested endpoint
`GET /api/v1/analytics/deltas?delegation_id=mornag&period=2026-Q3`:
```json
{
  "delegation_id": "mornag",
  "period": "2026-Q3",
  "farmers": [
    { "farmer_id": "f-mornag-1", "income": { "pct": 5.6 }, "waste": { "pct": -10.4 } }
  ],
  "delegation": { "income": { "pct": 3.1 }, "waste": { "pct": -7.5 } }
}
```
The frontend derives `direction` (`up | down | flat`, |Δ| < 0.05% is flat) and
`quality` (`good | bad | neutral`; income ↑ good, waste ↓ good) itself, so `pct`
is enough. Also wanted later: an official **Regional Risk Score** (0–100; the UI
uses a placeholder `100 − 4·waste% − 0.8·max(0, fill% − 75)`).

---

### Task 4 (Medium): AI assistant farmer-level context

**Today:** `/ai-assistant` calls `POST /api/v1/chat` with `{ message, data,
result: null, history }`. The router validates `data` as an `OptimizeRequest`
(`validated_scenario_data` in `routers/scenario.py`), so the frontend collapses a
whole delegation into one fake producer (total harvest, total capacity,
placeholder buyers). The model cannot see farmers, crops, waste, facilities or
trends, so "Which storage facility has the highest capacity risk?" cannot be
answered from real data.

**Requirement (proposed):** accept a `context` instead of forcing an
`OptimizeRequest`; keep `data` optional when `context` is present. The frontend
sends **IDs only**; the backend loads the data and builds the Groq system prompt
(this is also the planned "inject delegation context into the system prompt").
```json
POST /api/v1/chat
{
  "message": "Which storage facility has the highest capacity risk?",
  "history": [
    { "role": "user", "content": "Which crop has the most waste this quarter?" },
    { "role": "assistant", "content": "Tomatoes account for most of the waste..." }
  ],
  "context": {
    "delegation_id": "mornag",
    "period": "2026-Q3",
    "farmer_ids": null
  }
}
```
`farmer_ids: null` = whole delegation; a list = subset or one farmer (for a
"Ask about this farmer" entry point later).

**Response** (unchanged shape, so the existing client keeps working):
```json
{ "message": "Mornag Cold Storage is the fullest facility at 60% ...",
  "type": null, "result": null, "data": null }
```
For What-If questions keep `type: "what_if"` with the re-solved plan. Make the
What-If path multi-crop aware (`extract_constraints`, `merge_constraints`,
`solve_optimization`) so "what if tomato prices drop 10%" or "move tomatoes to
cold storage" resolve against real farmers and facilities, and return the
Task 2 `transfers` shape in `result`.

**Also:** chat history storage per agent (`GET /api/v1/chat/history` →
`[{ id, title, messages, created_at }]`); the UI shows three static sample
transcripts today. Require the Task 1 session; reject `delegation_id` values the
agent isn't assigned to.

---

## 3. Payload reference (matches `frontend/types/index.ts`)

### 3.1 Enums
```
CropType      "tomatoes" | "wheat" | "olives" | "citrus"
FacilityKind  "silo" | "cold_storage" | "warehouse"
Perishability "perishable" | "semi_perishable" | "durable"   (per crop; add to a Crop table)
```

### 3.2 Pydantic sketch
```python
class Delegation(BaseModel):
    id: str; name: str; governorate: str

class CropHarvest(BaseModel):
    crop: CropType
    yield_kg: float = Field(gt=0)
    waste_kg: float = Field(ge=0)
    income_tnd: float = Field(ge=0)
    # model_validator: waste_kg <= yield_kg

class PeriodSnapshot(BaseModel):
    period: str            # "2026-Q2"
    yield_kg: float; waste_kg: float; income_tnd: float

class Farmer(BaseModel):
    id: str; name: str; delegation_id: str
    phone: str | None = None
    storage_capacity_kg: float = Field(ge=0)
    crops: list[CropHarvest]           # unique by crop
    history: list[PeriodSnapshot]      # oldest first

class StorageFacility(BaseModel):
    id: str; name: str; delegation_id: str
    kind: FacilityKind
    current_stock_kg: float = Field(ge=0)
    max_capacity_kg: float = Field(ge=0)

class DeltaValue(BaseModel):
    pct: float | None                  # frontend derives direction/quality

class DeltaMetrics(BaseModel):
    income: DeltaValue; waste: DeltaValue
```

### 3.3 Farmer create / update
`POST /api/v1/farmers` body = `Farmer` without `id`; `PUT /api/v1/farmers/{id}`
body = `Farmer` (server keeps `history`). Both return the stored `Farmer`.
`422` example: `{ "detail": "Tomatoes: waste must be between 0 and the yield." }`.

### 3.3 Transfer (Task 2 response line)
See Task 2. Frontend type equivalent: `Transfer` in `app/lib/reallocation.ts`
(`farmerId, crop, kg, facilityId, urgencyHours, avoidedWasteKg, avoidedIncomeTnd`).

### 3.4 What the frontend does NOT need from you
Direction/quality of deltas, risk-level thresholds (farmer risk: ≥ 6% waste high,
≥ 3.5% medium), projected facility fill, and all formatting: derived client-side.

### 3.5 Other placeholders needing a real source
Weather (header chip) and temperature/humidity (storage card) are sample values
per delegation; provide a source if wanted. Chat history: see Task 4.

---

## 4. Frontend integration checklist (when each task ships)
- [ ] Task 1: replace `app/lib/auth.ts` internals; attach token to `app/lib/api.ts` requests.
- [ ] Task 3: replace mock state in `DelegationProvider` with fetches; add one API→camelCase mapper.
- [ ] Task 2: `RegionalOptimizer` and `OptimizationHero` call `/optimize/regional`; delete `planReallocation` usage.
- [ ] Task 4: `AssistantChat` sends `context` instead of the fake `OptimizeRequest`.
- Known lint errors remain in `FlowChart.tsx` and `SankeyChart.tsx` (pre-existing).

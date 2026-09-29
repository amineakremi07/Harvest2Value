# Harvest2Value — CRDA Regional Dashboard

Decision-support platform that is shifting from a single-farmer tool to an
administrative dashboard for the **CRDA** (Commissariat Régional au
Développement Agricole). It manages delegation-level harvest yields,
multi-crop storage allocations, and farmer analytics; optimizes harvest
allocation (MILP), explains results, and answers What-If questions in natural
language.

## Stack (do not deviate)
- **Backend**: FastAPI + PuLP (CBC) for the optimization engine (SciPy allowed
  for the multi-crop model). Pydantic v2 schemas for all I/O
  (`backend/app/models/schemas.py`). SQLAlchemy models for persistence
  (teammate scope).
- **Frontend**: Next.js (App Router, version in `frontend/package.json`) +
  TypeScript (strict) + Tailwind CSS + `next-themes` (light/dark) + Recharts.
- **LLM**: Groq, Llama-3 (OpenAI-compatible endpoint), called via `httpx`
  (no SDK) — see `backend/app/engines/nim_client.py`. Key read from
  `GROQ_API_KEY` env var only, never hardcoded.
- **Data**: JSON fixtures in `data/` validate against `data/schema.json`.

## Dev commands
```bash
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev -- -p 5173
```
Frontend commands (run in `frontend/`):
```bash
npm run dev             # dev server (add -- -p 5173 to match backend CORS)
npx tsc --noEmit        # type check (must be zero errors)
npm run lint            # ESLint
npm run build           # production build; also type checks and prerenders all routes
```
Backend CORS allows `http://localhost:5173` and `:3000`. Frontend API base is
`NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`).

## Git workflow rules
- **Claude must NOT run any git command** (no commit, add, checkout, branch,
  merge, push, pull, stash, reset — nothing that mutates or switches state).
  Only the user performs git operations. Read-only inspection is also avoided
  unless the user asks. When work is ready, tell the user what changed.
- Work happens in separate feature branches; `main` stays stable and is never
  merged into directly.
- Frontend developer branch: `feature/crda-frontend` (user also referred to it
  as `feature/crdadashboard` — confirm the final name with the user).
- Backend & AI engineer branch: `feature/crda-backend-ai`.

## Team perimeter (STRICT)
Never modify files outside your assigned scope. If a change requires touching
the other role's files (e.g. backend schemas), stop and flag it.
- **Frontend (this session)**: everything under `frontend/`.
- **Backend & AI**: everything under `backend/`, `data/` seeds, and DB models.
- Shared contract = Pydantic schemas ↔ `frontend/app/lib/api.ts` types. Frontend
  mirrors backend schemas; mismatches are reported to the backend engineer.

## Core data model (CRDA hierarchical)
- **Delegation**: regional context (e.g. Mornag, Tebourba, Kelibia).
- **Farmer profile**: personal details, delegation mapping, multi-crop yield,
  spoilage, storage capacity.
- **Crops**: Tomatoes, Wheat (Kamh), Olives, Citrus, … with perishability class.
- **CropHarvest**: farmer × crop × period yield (kg), waste (kg), income.
- **StorageFacility**: silo / cold storage / warehouse; current stock vs max
  capacity; delegation mapping.
- **Historical snapshots**: per-period farmer aggregates.
- **Delta metrics** (period-over-period):
  - Δ Income % = (income_t − income_{t−1}) / income_{t−1} × 100  (↑/↓)
  - Δ Waste %  = (waste_t − waste_{t−1}) / waste_{t−1} × 100    (↑/↓; a decrease is good)

## API contract
Existing (frozen, do not rename): `POST /api/v1/optimize`,
`POST /api/v1/scenario`, `POST /api/v1/explain`, plus `/api/v1/chat`.
New CRDA endpoints (delegations, farmers, facilities, analytics) are defined by
the backend engineer; the frontend adopts them once published.

## Task breakdown
### Frontend Developer — `feature/crda-frontend` (status: built on mock data)
1. **Schema & state migration** — done: `frontend/types/index.ts` (entities, delta
   helpers, mock fixtures) and `DelegationProvider`.
2. **Delegation & farmer data entry UI** — done: header delegation selector,
   `CRDAFarmerInput` multi-crop modal, per-farmer storage capacity.
3. **Farmer analytics** — done: delta badges, row expander, analytics drawer,
   `/analytics` trend and regional comparison charts.
4. **Optimization & AI assistant UI** — done on a frontend rule-based planner
   (`app/lib/reallocation.ts`) and the existing chat endpoint. Replace with the
   backend solver and farmer-level chat context: see `BACKEND_HANDOFF.md`.

### Backend & AI Engineer — `feature/crda-backend-ai`
1. **DB schema & endpoints**: SQLAlchemy/Pydantic models for Delegations,
   Farmers, CropHarvests, Facilities, Historical Snapshots; seed scripts with
   realistic Tunisian regional data.
2. **Analytics & spoilage engine**: Δ Income and Δ Waste calculations.
3. **LP & AI**: multi-crop capacity + perishability constraints in PuLP/SciPy;
   inject delegation context into the Groq system prompt for regional insights.

## Frontend structure (`frontend/`, Next.js App Router)
11 user-facing routes (the build also emits `/_not-found`):
```
app/page.tsx                          /               hero landing
app/auth/login/page.tsx               /auth/login     agent credentials
app/auth/2fa/page.tsx                 /auth/2fa       6-digit code
app/(dashboard)/layout.tsx            DashboardShell: auth guard + sidebar + header
app/(dashboard)/dashboard/            /dashboard      KPIs, Optimization Hero, charts, farmers
app/(dashboard)/farmers/              /farmers        table, add/edit modal, expander, drawer
app/(dashboard)/storage/              /storage        facility monitoring
app/(dashboard)/analytics/            /analytics      Δ income/waste trends, regional comparison
app/(dashboard)/ai-assistant/         /ai-assistant   chat with history panel
app/(dashboard)/optimization/         /optimization   Regional plan + Buyer allocation tabs
app/(dashboard)/settings/             /settings
app/(dashboard)/support/              /support
app/components/                       shared UI (Sidebar, Header, Modal, FarmersTable, ...)
app/context/DelegationProvider.tsx    global delegation/farmer/facility/plan state
app/lib/                              api.ts (backend client), auth.ts, optimize.ts,
                                      reallocation.ts (planner), regionStats.ts
types/index.ts                        domain types, delta helpers, mock fixtures
DESIGN.md                             design system (tokens, layout); follow it
```
`/optimization` is reachable from the dashboard hero but is not in the sidebar.

## Frontend state management
- **Theme**: `next-themes` (`.dark` class, persisted by the library in localStorage).
- **Delegation context** (`DelegationProvider`, mounted in `app/providers.tsx`):
  selected delegation, date range, that delegation's farmers and facilities,
  `upsertFarmer`, and the latest optimization plan per delegation. **In memory
  only**: a page refresh resets edits and plans. Data is mock fixtures from
  `types/index.ts` until the backend endpoints exist.
- **Mock auth** (`app/lib/auth.ts`, no backend): login stores the pending agent
  in `sessionStorage` (`h2v.pendingAgent`); a valid 6-digit code (any code passes)
  sets `localStorage` `h2v.isAuthenticated` = `"true"` and `h2v.agent` (email,
  delegation ID; the agent code is never stored). `DashboardShell` redirects
  signed-out visitors to `/auth/login`; Log Out clears all three keys and goes
  to `/`. This gates the UI only and is **not** a security boundary.
- Backend handoff (auth, regional optimizer, seeding, chat context) is in the
  root `BACKEND_HANDOFF.md`.

## Code standards
- Python: type hints everywhere, Pydantic models at I/O boundaries, no bare
  `except:`. Solver logic in `engines/`, HTTP glue in `routers/`.
- TypeScript: `strict`, no `any`, functional components, colocate types with
  the component that owns them (shared domain types in `types/index.ts`).
- Styling: theme-aware Tailwind (light/dark pairs via CSS variables in
  `globals.css`); `font-mono tabular-nums` for numerics.
- Verify with `npx tsc --noEmit`, `npm run lint`, `npm run build` in `frontend/`.

# Harvest2Value — Sprint Context (7.5h)

## V2 transition (branch `chedli`) — overrides the sprint rules below for V2 work
- **Real stack**: Next.js 16.3 (App Router) + React 19.2 + Tailwind v4 (no
  `tailwind.config`), TypeScript strict. Backend Python **3.12** in
  `backend/.venv`, FastAPI ≥0.115, Pydantic ≥2.9, PuLP 2.9 (CBC).
- **API**: new endpoints live under `/api/v2` (`backend/app/api/v2/`). `/api/v1`
  and the current frontend stay unchanged and working until V2 phase 14.
- **LLM**: provider abstraction in `backend/app/ai/providers/` —
  `LLM_PROVIDER=groq` (default) | `nvidia_nim` | `mock`, with `LLM_API_KEY`,
  `LLM_MODEL`, `LLM_BASE_URL`, `LLM_TIMEOUT_S` (`GROQ_API_KEY` accepted as a
  fallback). The v1 client in `engines/nim_client.py` actually calls Groq.
- **Perimeter**: during V2 the lead owns the whole repository on `chedli`; each
  V2 step lists the files it may touch. The member table below applies to v1 only.
- **Dependencies added in phase 0**: `pydantic-settings`; version bumps of
  fastapi, pydantic, uvicorn[standard], httpx.
- **Tests**: `cd backend && .venv/Scripts/python -m pytest tests`.
- Plan and decisions: V2 technical plan (phases 0–14).

AI-powered decision-support for smallholder farmers: allocate harvest across
buyers/storage to maximize net profit, explain the result, and answer
What-If questions in natural language.

## Stack (do not deviate)
- **Backend**: FastAPI + PuLP (CBC solver) for the MILP optimization engine.
  Pydantic v2 schemas for all request/response models (`backend/app/models/schemas.py`).
- **Frontend**: Next.js 14 (App Router) + TypeScript (strict) + Tailwind CSS.
- **LLM**: NVIDIA NIM REST API, model `meta/llama-3.1-70b-instruct`, called
  directly via `httpx` (no SDK) — see `backend/app/engines/nim_client.py`.
- **Data**: JSON fixtures in `data/` must validate against `data/schema.json`.

## Dev commands
```bash
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev -- -p 5173
```
Backend CORS already allows `http://localhost:5173` and `:3000`.

## API contract (frozen for this sprint — do not rename)
- `POST /api/v1/optimize` — `OptimizeRequest` -> `OptimizeResponse`
- `POST /api/v1/scenario` — `ScenarioRequest` (NL query + data) -> `OptimizeResponse`
- `POST /api/v1/explain` — `ExplainRequest` -> `ExplainResponse`

## Code standards
- Python: type hints everywhere, Pydantic models for all I/O boundaries, no
  bare `except:`. Keep solver logic in `engines/`, HTTP glue in `routers/`.
- TypeScript: `strict` mode, no `any`, functional components, colocate types
  with the component that owns them.
- Never hardcode the NIM API key — read from `NIM_API_KEY` env var only.

## Team ownership — STRICT PERIMETER RULE
**Never modify a file outside your assigned scope.** If a change requires
touching another member's files, stop and flag it instead of editing it
yourself. See `.claude/plans/` for each member's exact file list.

| Member | Scope | Plan |
|---|---|---|
| 1 — Lead/Backend | `backend/app/engines/solver.py`, `nim_client.py` (base), `routers/`, `models/schemas.py` | `.claude/plans/member1-backend.md` |
| 2 — Frontend Dashboard | `frontend/app/components/{HarvestInput,AllocationTable,RiskGauge}.tsx`, root layout/page | `.claude/plans/member2-frontend.md` |
| 3 — What-If & XAI | `frontend/app/components/{WhatIfChat,ExplainView}.tsx`, NIM constraint-extraction prompts | `.claude/plans/member3-whatif-xai.md` |
| 4 — Data, Viz & DevOps | `data/*.json`, `frontend/app/components/{SankeyChart,FlowChart}.tsx`, `docker-compose.yml`, `README.md` | `.claude/plans/member4-data-viz.md` |

## Ground truth
- `PLAN.md` is the sprint timeline (P1–P8). Update your row's status only.
- `data/schema.json` is the source of truth for dataset shape — validate
  new fixtures against it before committing.

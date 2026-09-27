# Member 2 — Frontend Dashboard

## Exclusive Scope
```
frontend/app/layout.tsx
frontend/app/page.tsx
frontend/app/globals.css
frontend/app/components/HarvestInput.tsx
frontend/app/components/AllocationTable.tsx
frontend/app/components/RiskGauge.tsx
frontend/app/lib/api.ts            (client fetch vers le backend)
frontend/package.json / tsconfig.json / tailwind.config.ts
```
Do NOT modify `backend/`, `data/`, @Member3 components (`WhatIfChat.tsx`, `ExplainView.tsx`), or @Member4 components (`SankeyChart.tsx`, `FlowChart.tsx`).

## MCP Tooling & Design System Guidelines (UI/UX Pro Max)
You have access to MCP tools for **21st.dev** and **UI/UX plugin**.
- **Style & Accessibility:** Minimalist, utilitarian, mobile-first Bento Grid layout. High-contrast elements optimized for outdoor sunlight readability.
- **Typography & Icons:** Large text (`text-base` minimum for labels, `text-2xl`+ for metrics). ALWAYS pair labels with explicit SVG icons (NEVER standalone icons).
- **21st.dev MCP Integration:** Use `21st_search` / `21st_get_component` to fetch and integrate React + Tailwind CSS components for:
  1. **Main Dashboard / Inputs:** `HarvestInput.tsx` (form) and `RiskGauge.tsx` (loss/storage gauge).
  2. **Supply Chain Hub:** `AllocationTable.tsx` displaying buyer demand, market prices, and net profits.
- **Golden Rule:** Read `frontend/design.md` before generating code. Strictly adapt all 21st.dev components to our Eco/Farmer palette (Forest Green, Warm Earth Brown, High-Contrast Slate). Avoid generic or improvisational styling.

## Execution Steps
1. **Scaffold & Setup:** Initialize Next.js (`create-next-app` with App Router, TS, Tailwind), set dev port to 5173. Create and review `frontend/design.md`.
2. **`lib/api.ts`:** Create typed `fetch` wrapper for `POST /api/v1/optimize`, `/scenario`, `/explain` matching backend Pydantic models.
3. **`HarvestInput.tsx`:** Producer/crop/buyers/logistics form matching `data/schema.json`. Include large touch targets, clear input validation, and explicit icons.
4. **`AllocationTable.tsx`:** Bento-style allocation data table sorted by `net_profit`. Feature status badges, market prices, and monospace metric formatting.
5. **`RiskGauge.tsx`:** High-visibility visual gauge for `wasted_kg / total_harvest_kg` (Green < 5%, Amber < 15%, Rose > 15%).
6. **`page.tsx`:** Main 12-column Bento Grid layout. Orchestrate `HarvestInput`, `RiskGauge`, and `AllocationTable`, leaving empty slot containers for @Member3 and @Member4 components.

## Development Command
```bash
cd frontend && npm run dev -- -p 5173

API Contract Compliance
All TypeScript types in lib/api.ts MUST match backend/app/models/schemas.py. If a schema discrepancy occurs, notify @Member1—do not edit backend files yourself.
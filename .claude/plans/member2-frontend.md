# Member 2 — Frontend Dashboard

## Périmètre exclusif
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
Ne pas toucher `backend/`, `data/`, les composants de @Member3
(`WhatIfChat.tsx`, `ExplainView.tsx`) ni de @Member4 (`SankeyChart.tsx`,
`FlowChart.tsx`).

## Étapes (P1 scaffolding puis P6)
1. **Scaffold** : `create-next-app` (App Router, TS, Tailwind), aligner le
   port de dev sur 5173.
2. **`lib/api.ts`** : wrapper `fetch` typé pour `POST /api/v1/optimize`,
   `/scenario`, `/explain` — types TS reflétant `OptimizeRequest` /
   `OptimizeResponse` de `backend/app/models/schemas.py`.
3. **`HarvestInput.tsx`** : formulaire producer/crop/buyers/logistics
   (correspond à `data/schema.json`). Validation client avant envoi.
4. **`AllocationTable.tsx`** : tableau des allocations par acheteur
   (`allocation: Record<buyerId, AllocationDetail>`), tri par net_profit.
5. **`RiskGauge.tsx`** : jauge visuelle wasted_kg / total_harvest_kg
   (vert < 5%, jaune < 15%, rouge au-delà).
6. **`page.tsx`** : orchestre HarvestInput -> appel API -> AllocationTable +
   RiskGauge + zone d'accueil pour WhatIfChat/ExplainView (@Member3) et
   SankeyChart (@Member4) sans implémenter leur logique interne.

## Commande de dev
```bash
cd frontend && npm run dev -- -p 5173
```

## Contrat à respecter
Les types TS des réponses API doivent matcher exactement
`backend/app/models/schemas.py` — en cas de divergence, notifier @Member1
plutôt que de modifier le backend toi-même.

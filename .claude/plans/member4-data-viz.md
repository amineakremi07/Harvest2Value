# Member 4 — Data, Viz & DevOps

## Périmètre exclusif
```
data/tunisia_olives.json
data/senegal_tomatoes.json
data/schema.json                       (évolutions, en coordination globale)
frontend/app/components/SankeyChart.tsx
frontend/app/components/FlowChart.tsx
docker-compose.yml
README.md
```
Ne pas toucher les composants dashboard/What-If ni le code backend.

## État actuel
- `data/schema.json` — DONE (contrat de forme des datasets)
- `data/tunisia_olives.json` (oliveraie, Sfax, 4 acheteurs) — DONE
- `data/senegal_tomatoes.json` (maraîchage, Niayes, 4 acheteurs, réfrigéré) — DONE
- `docker-compose.yml` (backend:8000 + frontend:5173) — DONE

## Étapes restantes (P8)
1. **`SankeyChart.tsx`** : flux harvest_kg -> {acheteurs, storage, waste}
   à partir de `OptimizeResponse.allocation` + `stored_kg`/`wasted_kg`.
   Librairie recommandée : `recharts` ou `d3-sankey` (léger, pas de SSR
   issue avec Next 14 App Router — marquer le composant `"use client"`).
2. **`FlowChart.tsx`** : vue logistique (acheteur x distance x volume),
   complémentaire au Sankey, pour visualiser le coût transport.
3. **Docker Compose** : vérifier que `docker-compose up` démarre les deux
   services sans étape manuelle ; ajouter un `Dockerfile` minimal dans
   `backend/` et `frontend/` si absent (Python 3.11-slim / node:20-alpine).
4. **README.md** : sections Setup (local + Docker), Architecture (schéma
   simple des 3 endpoints), Datasets, Crédits équipe. Garder < 150 lignes.
5. **Cleanup final** : supprimer fichiers de scaffold inutilisés, vérifier
   qu'aucun secret n'est commité (`.env` doit être dans `.gitignore`).

## Commande de lancement globale
```bash
docker-compose up --build
```

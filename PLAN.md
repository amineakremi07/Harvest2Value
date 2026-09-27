# Harvest2Value — Feuille de route Sprint (7.5h)

Statut : `TODO` / `IN PROGRESS` / `DONE`. Chaque membre ne met à jour QUE sa
propre ligne. Détails complets dans `.claude/plans/member{N}-*.md`.

| # | Phase | Durée | Owner(s) | Statut |
|---|---|---|---|---|
| P1 | Scaffolding (repo, backend/frontend skeleton, deps) | 1h | @Member1 @Member2 @Member4 | DONE |
| P2 | Mock Data (tunisia_olives.json, senegal_tomatoes.json + schema) | 30m | @Member4 | DONE |
| P3 | PuLP Solver Engine (`solver.py`, contraintes MILP) | 2h | @Member1 | DONE |
| P4 | FastAPI Endpoints (`/optimize`, `/scenario`, `/explain`) | 1.5h | @Member1 | DONE |
| P5 | NIM REST Client (extraction contraintes + explications) | 1h | @Member1 @Member3 | TODO |
| P6 | Frontend Dashboard (HarvestInput, AllocationTable, RiskGauge) | 2h | @Member2 | TODO |
| P7 | What-If Chat & XAI (WhatIfChat, ExplainView, scénarios) | 1h | @Member3 | TODO |
| P8 | Docker Compose + Viz (Sankey/Flow) + Cleanup + README | 30m | @Member4 | DONE |

## Règles du sprint
1. **Zéro dérive de périmètre** : chaque membre édite uniquement les fichiers
   listés dans son sous-plan (`.claude/plans/`). Toute dépendance croisée est
   signalée dans le canal d'équipe, pas résolue en éditant le fichier d'un
   autre membre.
2. **Contrat d'API figé** : les schémas Pydantic (`backend/app/models/schemas.py`)
   et les routes `/api/v1/*` ne changent pas de forme en cours de sprint sans
   accord du Lead (@Member1).
3. **Commits fréquents** : un commit par sous-tâche terminée, message préfixé
   par la phase (`P6: AllocationTable component`).
4. **Démo finale** : `docker-compose up` doit lancer backend (8000) + frontend
   (5173) sans étape manuelle supplémentaire.

## Dépendances entre phases
- P6/P7 (frontend) consomment les réponses JSON de P4 — utiliser les fixtures
  de P2 en attendant que P4/P5 soient stables.
- P7 (What-If) dépend du client NIM de P5 pour l'extraction de contraintes.
- P8 (Docker) dépend de P1/P6 pour connaître les ports et scripts de démarrage.

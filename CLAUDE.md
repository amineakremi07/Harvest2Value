# Harvest2Value — contexte projet (V2)

Aide à la décision pour petits producteurs : répartir la récolte entre acheteurs, stockage et
camions pour maximiser le profit réalisé (MILP), expliquer chaque décision, comparer des scénarios
« et si », et un Copilot IA dont chaque chiffre est vérifié par le backend.
La V1 (`/api/v1`, `engines/`, `routers/`, ancien frontend) a été retirée en phase 14.

## Stack (ne pas dévier)
- **Backend** : Python **3.12** (`backend/.venv`), FastAPI ≥0.115, Pydantic ≥2.9 +
  pydantic-settings, PuLP 2.9 (CBC), SQLAlchemy 2 + Alembic (SQLite par défaut).
- **Frontend** : Next.js 16.3 (App Router) + React 19.2 + Tailwind v4 (pas de `tailwind.config`),
  TypeScript strict. Lire `frontend/AGENTS.md` avant d'écrire du code Next.
- **LLM** : abstraction `backend/app/ai/providers/` — `LLM_PROVIDER=groq` (défaut) |
  `nvidia_nim` | `mock`, avec `LLM_API_KEY` (`GROQ_API_KEY` accepté), `LLM_MODEL`,
  `LLM_BASE_URL`, `LLM_TIMEOUT_S`. Sans clé, l'application fonctionne (IA désactivée).
- **Données** : format v2 = `backend/app/domain/dataset.py` ; `data/schema.v2.json` est généré
  (`backend/scripts/export_json_schema.py`), jamais édité à la main.

## Commandes
```bash
cd backend && .venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
cd backend && .venv/Scripts/python -m pytest tests          # + ruff check . ; mypy
cd frontend && npm run dev                                  # :5173
cd frontend && npm run lint && npm run typecheck && npm test && npm run test:e2e
docker compose up --build                                   # production : :3000 + :8000
```

## Contrat d'API
- Tout est sous `/api/v2` (voir `docs/api.md`). Les routes sont figées par
  `tests/integration/api/test_comparisons_and_flow.py::test_v2_route_contract_is_frozen` :
  ajouter une route = mettre à jour ce test et la doc dans le même changement.
- Toute erreur a la forme `{"error": {code, message, details, request_id}}`.
- Après un changement de schéma : `python scripts/export_openapi.py` puis `npm run gen:api`.

## Règles de code
- Python : annotations partout (mypy strict), Pydantic à chaque frontière d'E/S, pas de
  `except:` nu. HTTP dans `api/v2/`, cas d'usage dans `services/`, aucune logique métier dans
  les routeurs.
- TypeScript : `strict`, pas de `any`, composants fonctionnels, types colocalisés.
  Le frontend n'invente aucun chiffre : il affiche ce que l'API calcule.
- KPI : ne jamais additionner revenu réalisé et valeur du stock.
- IA : les chiffres passent par des références rendues par le backend ; aucune modification
  sans confirmation explicite (`copilot/actions/{id}/confirm`).
- Secrets : uniquement par variables d'environnement, jamais journalisés ni committés.

## Périmètres par module
Chaque changement reste dans un module ; un changement transverse touche le contrat (schémas
`api/v2/schemas`, types générés) en premier, dans le même commit que ses tests.

| Module | Fichiers | Tests | Doc |
|---|---|---|---|
| Données | `backend/app/domain/{dataset,validation,diff,migrations_v1}.py`, `services/datasets.py`, `api/v2/datasets.py`, `data/`, `frontend/features/datasets/` | `tests/unit/domain`, `integration/api/test_datasets_api.py`, `e2e/07-datasets` | `docs/data.md` |
| Solveur | `backend/app/optimization/`, `domain/{run_config,results}.py`, `services/optimization.py`, `api/v2/runs.py`, `frontend/features/optimization/` | `tests/unit/optimization`, `regression/`, `e2e/01`, `e2e/02` | `docs/solver.md` |
| Explicabilité & alertes | `backend/app/{explain,insights}/`, `services/{explanation,insights}.py`, `api/v2/{explain,insights}.py`, `frontend/features/{explain,insights,network}/` | `tests/unit/{explain,insights}`, `e2e/04` | `docs/solver.md` |
| Scénarios & comparaison | `backend/app/scenarios/`, `services/{scenarios,comparisons}.py`, `api/v2/{scenarios,comparisons}.py`, `analytics/comparison.py`, `frontend/features/{scenarios,compare}/` | `tests/unit/scenarios`, `integration/api/test_scenarios_api.py`, `e2e/03` | `docs/scenarios.md` |
| IA (Copilot) | `backend/app/ai/`, `services/copilot.py`, `api/v2/copilot.py`, `frontend/features/copilot/` | `tests/unit/ai`, `integration/api/test_copilot_api.py`, `e2e/05` | `docs/ai.md` |
| Analyses & rapports | `backend/app/analytics/`, `services/{analytics,reports}.py`, `api/v2/{analytics,reports}.py`, `frontend/features/{analytics,reports,dashboard}/`, `app/(print)/` | `tests/unit/analytics`, `integration/api/test_reports_api.py`, `e2e/06` | `docs/api.md` |
| Plateforme | `backend/app/{core,db,repositories}/`, `main.py`, `services/jobs.py`, `api/v2/{health,meta}.py`, `migrations/`, `frontend/{components,lib}/`, `app/(app)/layout.tsx` | `tests/unit/core`, `integration/db`, `performance/`, `e2e/08`, `e2e/09` | `docs/architecture.md` |
| DevOps & docs | `docker-compose.yml`, `*/Dockerfile`, `.env.example`, `README.md`, `docs/`, `PLAN.md` | build de production | `docs/deployment.md`, `docs/setup.md` |

## Référence
- `PLAN.md` : état des phases V2. `docs/` : documentation complète (index dans `README.md`).

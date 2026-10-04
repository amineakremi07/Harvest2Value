# Tests

## Résumé des commandes

| Côté | Commande (depuis le dossier) | Contenu |
|---|---|---|
| backend | `.venv/Scripts/python -m pytest tests` | unitaires, intégration API/DB, régressions, performance |
| backend | `.venv/Scripts/python -m ruff check .` | lint |
| backend | `.venv/Scripts/python -m mypy` | typage strict de `app/` |
| frontend | `npm run lint` | ESLint (config Next) |
| frontend | `npm run typecheck` | `tsc --noEmit`, mode strict |
| frontend | `npm test` | Vitest + Testing Library (jsdom) |
| frontend | `npm run test:e2e` | Playwright (Chromium) contre le vrai backend |
| frontend | `npm run build && npm start` | build de production |

Linux/macOS : remplacer `.venv/Scripts/python` par `.venv/bin/python`.

## Backend (`backend/tests/`)

| Dossier | Couverture |
|---|---|
| `unit/domain` | modèle v2, validation métier, différentiel de versions, conversion v1 |
| `unit/optimization` | contraintes une à une, instance, objectifs, statuts, KPI, diagnostics d'infaisabilité, sensibilité, propriétés (hypothesis) |
| `unit/scenarios` | les opérations de scénario et leur calcul côté backend |
| `unit/explain`, `unit/insights`, `unit/analytics` | cartes de décision, alertes, sections d'analyse |
| `unit/ai` | fournisseurs (URL, en-têtes, erreurs), vérification numérique, garde-fous (injection, secrets) |
| `unit/core` | configuration, empreintes, journaux sans secrets |
| `integration/api` | chaque famille d'endpoints, enveloppe d'erreur, CORS, limites, contrat de routes figé |
| `integration/db` | migrations Alembic |
| `regression` | audit V1 (R1–R4) sur les 5 modèles : chacun optimal en < 5 s (cas de 30 jours inclus), bilan de masse exact (récolte = vendu + perdu + stock final ; aussi en test de propriétés dans `unit/optimization/test_properties.py`) |
| `performance` | p95 des lectures après une exécution, création de rapport, lectures concurrentes pendant une résolution |

Les tests utilisent une base SQLite temporaire et `LLM_PROVIDER=mock` : aucun réseau.

### Régressions de l'audit V1

| Id | Défaut V1 | Test |
|---|---|---|
| R1 | stock valorisé comme s'il était vendu | `regression/test_audit_solver.py::test_r1_*` |
| R2 | `net_profit` mélangeait profit et valeur du stock | `regression/test_audit_solver.py::test_r2_*` |
| R3 | durée de conservation lue mais pas contrainte | `regression/test_audit_solver.py::test_r3_*` |
| R4 | statut du solveur jamais vérifié | `regression/test_audit_solver.py::test_r4_*` |
| R5 | le solveur bloquait la boucle d'événements | `integration/api/test_runs_api.py` |
| R6 | l'IA modifiait sans demande | `integration/api/test_copilot_api.py`, `unit/ai/test_verification_guards.py` |
| R7 | « −10 % » calculé par le LLM | `unit/scenarios/test_operations.py`, `integration/api/test_scenarios_api.py` |
| R8 | les « et si » chaînés perdaient les modifications précédentes | `integration/api/test_scenarios_api.py` |
| R10 | fournisseur LLM mal adressé | `unit/ai/test_providers.py` |
| R11 | `ready` dépendait de la clé LLM | `integration/api/test_health_meta.py` |
| R12 | CORS ouvert | `integration/api/test_errors_cors.py` |

## Frontend

- **Vitest** (`*.test.ts(x)` à côté du code) : composants, hooks, formatage, contraste des couleurs
  (`lib/color.test.ts`), coquille (navigation, palette, thème). Les réponses d'API viennent de
  `frontend/test/fixtures/`, régénérées par `backend/scripts/capture_frontend_fixtures.py`.
- **Playwright** (`frontend/e2e/`) : démarre (ou réutilise) le backend sur une base SQLite jetable
  avec le LLM simulé (`LLM_MOCK_SCRIPT=e2e/fixtures/copilot-script.json`) et le serveur Next.

| Fichier | Parcours |
|---|---|
| `01-optimize-run-result` | E2E n°1 : modèle → exécution → chaque onglet du résultat ; thème clair/sombre |
| `02-templates-m1` | les 5 modèles : données → exécution → résumé et allocation |
| `03-scenario-compare` | E2E n°3 : scénario −10 % → exécution → comparaison ; branche, duplication, périmé, rebase |
| `04-explain-network` | chaque acheteur expliqué, alerte → test de la recommandation → comparaison ; réseau |
| `05-copilot` | E2E n°4 : chiffres vérifiés, aucune modification sans confirmation |
| `06-analytics-reports` | 5 sections d'analyse ; E2E n°5 : rapport figé, exports, page d'impression |
| `07-datasets` | import v1 → édition → validation → version → différences → export → optimisation |
| `08-accessibility` | axe WCAG 2.1 A/AA (contraste inclus) sur chaque page, deux thèmes ; aucun défilement horizontal de 375 à 1440 px ; navigation complète au clavier |
| `09-performance` | chaque page principale utilisable en moins de 3 s |

Prérequis E2E : `backend/.venv` installé et `npx playwright install chromium`.

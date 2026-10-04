# Architecture

## Vue d'ensemble

```
Navigateur ──► Next.js 16 (App Router, React 19, Tailwind v4)      :3000 (prod) / :5173 (dev)
                 │  fetch JSON / SSE (le navigateur appelle l'API directement, CORS en liste blanche)
                 ▼
              FastAPI  /api/v2                                         :8000
                 │
     ┌───────────┼──────────────────────────────┬──────────────────────────┐
     ▼           ▼                              ▼                          ▼
 services    optimization (PuLP + CBC)      ai (Copilot)            repositories
 (cas d'usage) explain / insights / analytics  providers: Groq | NIM | mock   SQLAlchemy 2
                                                                         │
                                                                         ▼
                                                              SQLite (défaut) / PostgreSQL
                                                              migrations Alembic au démarrage
```

Le frontend n'a pas de logique métier : il affiche ce que l'API calcule (KPI, explications,
écarts, chiffres de l'IA). Les seuls calculs côté client sont des mises en forme (formatage FR,
écarts d'affichage dans la vue comparée des analyses).

## Backend (`backend/app/`)

| Paquet | Rôle |
|---|---|
| `api/v2/` | Couche HTTP : routeurs fins, schémas d'entrée/sortie (`schemas/`), dépendances (`api/deps.py`), enveloppe d'erreur (`api/errors.py`) |
| `core/` | Configuration typée (`config.py`, pydantic-settings), erreurs applicatives, journalisation avec identifiant de requête, sécurité (CORS, limite de taille, limitation de débit), hachage canonique |
| `db/` | Modèles SQLAlchemy, moteur, session / unité de travail, migrations au démarrage |
| `domain/` | Modèles Pydantic du domaine : jeu de données v2, configuration d'exécution, résultats, scénarios, rapports, validation métier, conversion v1 → v2 |
| `optimization/` | Instance du problème, variables, modules de contraintes, objectifs, résolution, post-traitement (KPI), diagnostics, sensibilité |
| `explain/` | Cartes de décision, facteurs limitants, alternatives, contraintes saturées |
| `insights/` | Règles déterministes d'alertes et d'opportunités (avec changement suggéré « testable ») |
| `analytics/` | Sections d'analyse, réseau logistique, marché, comparaison |
| `scenarios/` | Opérations typées, application en chaîne, différences, lignée, texte → modifications |
| `ai/` | Fournisseurs LLM, outils du Copilot, vérification des chiffres, rendu, garde-fous, récits, prompts versionnés |
| `services/` | Cas d'usage dans une transaction (datasets, exécutions, scénarios, explication, comparaisons, rapports, copilot) |
| `repositories/` | Accès aux tables |

### Flux d'une exécution

1. `POST /runs` résout l'entrée effective (version d'un jeu de données, ou version de base
   + chaîne de modifications d'un scénario) et calcule `effective_input_hash` + `config_hash`.
2. Si une exécution identique a déjà réussi, elle est réutilisée (`cache_hit`).
3. Sinon l'exécution est mise en file (`RunExecutor`, concurrence limitée) ; le solveur tourne dans
   un thread, la boucle d'événements reste libre (R5).
4. Le résultat (allocations, stocks, trajets, pertes, KPI) est enregistré ; les valeurs duales du
   LP figé, l'explication et les alertes sont calculées à la demande puis mises en cache.
5. Les sondes de valeurs marginales (`POST /runs/{id}/marginal-values`) ré-optimisent jusqu'à
   8 variantes en arrière-plan.

### Persistance

Tables : `workspaces`, `datasets`, `dataset_versions` (versions immuables, hachées),
`optimization_runs`, `optimization_results`, `insights`, `scenarios`, `scenario_changes`,
`conversations`, `messages`, `copilot_actions`, `reports`. Les migrations Alembic
(`backend/migrations/versions/0001…0006`) s'appliquent au démarrage de l'application.

## Frontend (`frontend/`)

| Dossier | Rôle |
|---|---|
| `app/(app)/` | Routes de l'application dans le shell (barre latérale, palette Ctrl+K, tiroir Copilot) |
| `app/(print)/` | Pages d'impression sans shell (rapports, CSS `@page`) |
| `features/<domaine>/` | Écrans et composants d'un domaine (datasets, optimization, explain, network, scenarios, compare, analytics, reports, copilot, dashboard, insights) |
| `components/` | Primitives UI, graphiques (Recharts), shell |
| `lib/api/` | Client HTTP typé (types générés depuis l'OpenAPI), lecteur SSE |
| `lib/theme/` | Thème clair / sombre (préférence par navigateur, script anti-flash) |

Les types TypeScript sont générés depuis le document OpenAPI du backend :
`backend/scripts/export_openapi.py` puis `npm run gen:api`.

## Choix structurants

- **Une seule source des chiffres** : le solveur et les services backend. L'IA ne produit que des
  références `{{ref:…}}` que le backend remplace par les valeurs (voir [ai.md](ai.md)).
- **Données immuables et versionnées** : une exécution pointe une version précise ; un rapport
  copie ses données au moment de sa création.
- **Explications honnêtes** : un effet est « mesuré » quand il vient d'une ré-optimisation ; une
  valeur duale est présentée comme indicateur local, avec ses limites.
- **Jobs en mémoire** : simple et suffisant pour un déploiement mono-instance ; un redémarrage
  marque les exécutions en cours comme `interrupted` (voir [deployment.md](deployment.md)).

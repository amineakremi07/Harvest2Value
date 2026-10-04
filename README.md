# Harvest2Value

Aide à la décision pour les petits producteurs : **à qui vendre la récolte, quand, faut-il stocker,
avec quels camions** — pour maximiser le profit réalisé en tenant compte de la péremption, des
capacités et des coûts. Le plan est calculé par un modèle d'optimisation (MILP, PuLP + CBC),
expliqué décision par décision, comparable entre scénarios « et si », et commenté par un copilote IA
dont **chaque chiffre est vérifié par le backend**.

## Fonctionnalités

| Domaine | Ce que l'application fait |
|---|---|
| Données | Jeux de données versionnés : créer depuis 5 modèles tunisiens, importer (format v2, ou v1 converti avec ses hypothèses), modifier (édition rapide ou JSON), valider, comparer deux versions, exporter (JSON, CSV) |
| Optimisation | 5 objectifs (profit, chiffre d'affaires, pertes, coûts, pondéré), horizon multi-jours, stockage ambiant/froid, flotte, chaîne du froid, contrats, minimums de commande ; file d'attente, cache, annulation, diagnostic d'infaisabilité |
| Explicabilité | Pour chaque acheteur : décision, facteur limitant, meilleure alternative, « pourquoi pas plus » ; contraintes saturées, goulots classés, valeurs marginales **mesurées par ré-optimisation** (la valeur duale n'est qu'un indicateur local) ; réseau logistique jour par jour |
| Scénarios | 16 opérations typées (prix, demande, récolte, stockage, transport, flotte, péremption, acheteurs, routes, chaîne du froid), aperçu, branches, détection « périmé » + rebase, comparaison d'une référence avec 1 à 3 exécutions |
| IA (Copilot) | Questions en langage naturel avec 18 outils en lecture ; chiffres rendus par le backend et marqués s'ils ne sont pas vérifiés ; propositions (scénario, exécution, rapport) **jamais appliquées sans confirmation** ; récits d'exécution et de comparaison ; « et si » en texte libre → modifications typées. Groq par défaut, NVIDIA NIM configurable, application entièrement utilisable sans clé |
| Analyses | 5 sections (financier, opérationnel, acheteurs, logistique, culture), filtre d'exécution, vue comparée |
| Rapports | Copie figée (snapshot + empreinte SHA-256), impression / PDF via le navigateur, exports CSV par table et JSON |
| Interface | Thèmes clair et sombre, palette de commandes (Ctrl+K / ⌘K), responsive 375 → 1440 px, audit d'accessibilité WCAG 2.1 AA automatisé |

## Démarrage rapide

### Docker (production)

```bash
cp .env.example .env          # facultatif : LLM_API_KEY=... pour activer l'IA
docker compose up --build
```

Application : <http://localhost:3000> · API : <http://localhost:8000/api/v2> · OpenAPI : <http://localhost:8000/docs>

### Développement local

```bash
# Backend (Python 3.12)
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # Linux/macOS : .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# Frontend (Node 22)
cd frontend
npm install
npm run dev            # http://localhost:5173
```

La base SQLite est créée et migrée au démarrage (`backend/harvest2value.db`).

## Configuration

| Variable | Défaut | Rôle |
|---|---|---|
| `LLM_PROVIDER` | `groq` | `groq`, `nvidia_nim` ou `mock` |
| `LLM_API_KEY` | — | clé du fournisseur (`GROQ_API_KEY` est aussi accepté) ; sans clé, l'IA est désactivée et le reste fonctionne |
| `LLM_MODEL` | `openai/gpt-oss-120b` (Groq), `meta/llama-3.1-70b-instruct` (NIM) | modèle |
| `LLM_BASE_URL` | URL officielle du fournisseur | proxy ou passerelle compatible OpenAI |
| `LLM_TIMEOUT_S` | `30` | délai d'un appel LLM |
| `DATABASE_URL` | `sqlite:///backend/harvest2value.db` | SQLite ou PostgreSQL (SQLAlchemy) |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | liste blanche des origines du navigateur |
| `SOLVER_TIME_LIMIT_S` / `SOLVER_MAX_CONCURRENCY` | `30` / `2` | limites du solveur |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | URL de l'API vue par le navigateur (fixée au build du frontend) |

Détails : [docs/setup.md](docs/setup.md) et [docs/deployment.md](docs/deployment.md).

## Documentation

| Document | Contenu |
|---|---|
| [docs/user-guide.md](docs/user-guide.md) | Guide utilisateur : du jeu de données au rapport |
| [docs/architecture.md](docs/architecture.md) | Couches, modules, flux d'une exécution, choix techniques |
| [docs/api.md](docs/api.md) | Endpoints `/api/v2`, enveloppe d'erreur, conventions |
| [docs/solver.md](docs/solver.md) | Modèle MILP : variables, contraintes, objectifs, KPI |
| [docs/scenarios.md](docs/scenarios.md) | Opérations, lignée, périmé/rebase, cache, comparaison |
| [docs/ai.md](docs/ai.md) | Copilot, outils, vérification des chiffres, garde-fous, fournisseurs |
| [docs/data.md](docs/data.md) | Format de données v2, import v1, modèles, validation |
| [docs/setup.md](docs/setup.md) | Installation et configuration en développement |
| [docs/testing.md](docs/testing.md) | Tests unitaires, intégration, E2E, accessibilité, performance |
| [docs/deployment.md](docs/deployment.md) | Docker Compose de production, sauvegardes, limites |

## Arborescence

```
backend/   FastAPI + PuLP : app/{api,core,db,domain,optimization,explain,insights,analytics,scenarios,ai,services,repositories}
frontend/  Next.js 16 (App Router) : app/ (routes), features/ (écrans), components/, lib/ (client API, thème)
data/      schema.v2.json et templates/ (5 jeux de données tunisiens)
docs/      documentation
```

Licence : voir [LICENSE](LICENSE).

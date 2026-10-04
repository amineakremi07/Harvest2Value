# Installation (développement)

## Prérequis

- Python **3.12** (le solveur CBC est fourni par PuLP sous Windows, macOS et Linux x86-64).
- Node.js **22** et npm.
- Facultatif : une clé Groq (ou NVIDIA NIM) pour les fonctions IA.

## Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt        # Linux/macOS : .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

- La base SQLite `backend/harvest2value.db` est créée et migrée (Alembic) au démarrage.
- `requirements.txt` = dépendances d'exécution ; `requirements-dev.txt` ajoute pytest, hypothesis,
  ruff et mypy.
- Vérification : <http://localhost:8000/api/v2/health/ready> et la documentation interactive
  <http://localhost:8000/docs>.

## Frontend

```bash
cd frontend
npm install
npm run dev              # http://localhost:5173
```

L'URL de l'API vue par le navigateur est `NEXT_PUBLIC_API_URL` (défaut `http://localhost:8000`).

## Configuration

Les variables sont lues dans l'environnement, puis dans `.env` à la racine, puis dans
`backend/.env` (le dernier l'emporte). Copier `.env.example` ; **ne jamais committer `.env`**.

| Variable | Défaut | Rôle |
|---|---|---|
| `APP_ENV` | `development` | `development`, `test`, `production` |
| `DATABASE_URL` | `sqlite:///backend/harvest2value.db` | URL SQLAlchemy |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | liste blanche, séparée par des virgules |
| `LLM_PROVIDER` | `groq` | `groq`, `nvidia_nim` ou `mock` |
| `LLM_API_KEY` | — | clé du fournisseur ; `GROQ_API_KEY` est aussi accepté |
| `LLM_MODEL` | `openai/gpt-oss-120b` (Groq) / `meta/llama-3.1-70b-instruct` (NIM) | modèle |
| `LLM_BASE_URL` | URL officielle | passerelle compatible OpenAI |
| `LLM_TIMEOUT_S` | `30` | délai d'un appel |
| `LLM_MOCK_SCRIPT` | — | avec `mock` : fichier JSON de réponses scriptées (E2E, démos hors ligne) |
| `SOLVER_TIME_LIMIT_S` | `30` | limite par résolution |
| `SOLVER_MAX_CONCURRENCY` | `2` | résolutions simultanées (au-delà : file d'attente) |
| `MAX_BODY_BYTES` | `2000000` | taille maximale d'une requête |
| `RATE_LIMITS__DEFAULT_PER_MINUTE` … | 120 / 30 / 20 / 10 | défaut, exécutions, copilot, récits |

### IA

- **Groq** est le fournisseur par défaut : renseigner `LLM_API_KEY`.
- **NVIDIA NIM** : `LLM_PROVIDER=nvidia_nim` et sa clé ; le modèle par défaut est
  `meta/llama-3.1-70b-instruct`.
- **Sans clé**, l'application reste entièrement utilisable : les écrans IA affichent
  « IA désactivée » et `/health/ready` reste `ready`.
- `LLM_PROVIDER=mock` sert aux tests et démos sans réseau.

## Outils utiles

| Commande | Effet |
|---|---|
| `python scripts/export_openapi.py` puis `npm run gen:api` | régénère les types TypeScript de l'API |
| `python scripts/export_json_schema.py` | régénère `data/schema.v2.json` |
| `python scripts/capture_frontend_fixtures.py` | régénère les fixtures des tests frontend |
| `python scripts/probe_tool_calling.py` | vérifie l'appel d'outils du fournisseur LLM configuré (réseau, clé requise) |

Les tests sont décrits dans [testing.md](testing.md), la production dans [deployment.md](deployment.md).

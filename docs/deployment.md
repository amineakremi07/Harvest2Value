# Déploiement

## Docker Compose (production)

```bash
cp .env.example .env      # facultatif : LLM_API_KEY, CORS_ORIGINS, PUBLIC_API_URL
docker compose up --build -d
docker compose ps         # les deux services passent à "healthy"
```

| Service | Image | Port | Santé |
|---|---|---|---|
| `backend` | `python:3.12-slim` + `coinor-cbc`, utilisateur non root, 1 worker uvicorn | 8000 | `GET /api/v2/health/ready` = 200 |
| `frontend` | build Next.js multi-étapes (`node:22-alpine`), servi par `next start` | 3000 | `GET /dashboard` |

- Le frontend attend que le backend soit `healthy` (`depends_on: condition: service_healthy`).
- La base SQLite est sur le volume nommé `h2v-data` (`/data/harvest2value.db`) ; les migrations
  Alembic s'appliquent au démarrage. Une exécution interrompue par un redémarrage est marquée
  « Interrompu » au démarrage suivant.
- Les variables `LLM_*` sont lues depuis l'environnement ou `.env` ; **aucun secret n'est copié
  dans les images** (`.dockerignore` exclut `.env`, bases locales et caches).

### Variables propres à Compose

| Variable | Défaut | Rôle |
|---|---|---|
| `PUBLIC_API_URL` | `http://localhost:8000` | URL de l'API vue par le navigateur ; **fixée au build** du frontend (reconstruire après changement) |
| `CORS_ORIGINS` | `http://localhost:3000` | doit contenir l'URL publique du frontend |
| `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_TIMEOUT_S` | `groq`, vide… | IA ; sans clé, l'application fonctionne sans IA |
| `SOLVER_TIME_LIMIT_S`, `SOLVER_MAX_CONCURRENCY` | `30`, `2` | limites du solveur |

Les autres réglages (limites de débit, taille des requêtes) sont décrits dans [setup.md](setup.md).

## Derrière un reverse proxy

- Exposer le frontend et l'API sous HTTPS ; reconstruire le frontend avec
  `PUBLIC_API_URL=https://api.exemple.org` et mettre `CORS_ORIGINS=https://app.exemple.org`.
- uvicorn est lancé avec `--proxy-headers` : la limitation de débit identifie le client par
  l'adresse transmise par le proxy. Ne pas exposer le port 8000 directement si un proxy est utilisé.
- Les réponses SSE du Copilot (`?stream=true`) ne doivent pas être mises en tampon par le proxy.

## Sauvegarde et restauration

```bash
docker compose stop backend
docker run --rm -v harvest2value-main_h2v-data:/data -v "$PWD":/backup alpine \
  cp /data/harvest2value.db /backup/harvest2value-$(date +%F).db
docker compose start backend
```

Le nom exact du volume est donné par `docker volume ls` (préfixé par le nom du projet Compose).
Restaurer = copier le fichier dans le volume, backend arrêté.

## Limites connues

- **Un seul processus backend** : la file des exécutions et les compteurs de limitation de débit sont
  en mémoire. Pour monter en charge, augmenter `SOLVER_MAX_CONCURRENCY` (CPU) plutôt que le nombre
  de workers.
- **SQLite** convient à un usage mono-poste ou petite équipe. `DATABASE_URL` accepte une URL
  PostgreSQL (SQLAlchemy), mais le pilote n'est pas inclus dans `requirements.txt` et ce mode n'est
  pas couvert par les tests.
- Pas d'authentification intégrée : à placer derrière un proxy authentifiant si l'instance est
  exposée.

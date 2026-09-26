# Member 1 — Lead / Backend

## Périmètre exclusif
```
backend/app/main.py
backend/app/engines/solver.py
backend/app/engines/nim_client.py       (structure de base — @Member3 ajoute les prompts What-If)
backend/app/models/schemas.py
backend/app/routers/optimize.py
backend/app/routers/scenario.py
backend/app/routers/explain.py
backend/requirements.txt
```
Ne pas toucher `frontend/`, `data/*.json`, `docker-compose.yml`.

## État actuel (déjà en place)
- FastAPI app + CORS (`main.py`) — DONE
- Solver MILP PuLP avec contraintes supply/storage/demand/shelf-life/vehicle — DONE
- Schémas Pydantic request/response — DONE
- Endpoints `/api/v1/optimize`, `/api/v1/scenario`, `/api/v1/explain` — DONE
- `NIMClient` (squelette REST httpx vers `meta/llama-3.1-70b-instruct`) — DONE

## Étapes restantes (P5)
1. Vérifier `NIM_API_KEY` / `NIM_ENDPOINT` lus depuis l'env (jamais en dur).
2. Ajouter un fallback si NIM timeout/erreur : `scenario.py` doit renvoyer
   une 502 explicite plutôt qu'un stacktrace brut.
3. Exposer `GET /api/v1/datasets` (liste des fichiers dans `data/`) pour que
   le frontend (@Member2/@Member4) puisse peupler un sélecteur de scénario.
4. Écrire 2-3 tests pytest sur `solver.py` (cas nominal + storage saturé)
   dans `backend/tests/test_solver.py`.
5. Coordination avec @Member3 : les champs attendus par
   `NIMClient.extract_constraints` (type/target/field/new_value) sont figés
   — toute modification de ce contrat doit passer par toi.

## Commande de dev
```bash
cd backend && uvicorn app.main:app --reload --port 8000
```

# Member 3 — What-If & XAI

## Périmètre exclusif
```
frontend/app/components/WhatIfChat.tsx
frontend/app/components/ExplainView.tsx
frontend/app/lib/scenarios.ts          (scénarios prédéfinis / presets)
backend/app/engines/nim_client.py      (UNIQUEMENT les prompts d'extraction
                                          de contraintes — coordination avec
                                          @Member1 pour toute autre modif)
```
Ne pas toucher les composants dashboard de @Member2, ni `solver.py`.

## Étapes (P7)
1. **`scenarios.ts`** : 4-5 presets de questions What-If en langage naturel
   ("Et si le prix des tomates chute de 20% ?", "Et si un acheteur annule ?",
   "Et si la capacité de stockage double ?") mappés à des exemples de payload
   `ScenarioRequest`.
2. **`WhatIfChat.tsx`** : zone de saisie NL + historique de conversation,
   envoie `POST /api/v1/scenario` avec `{query, data}`, affiche le nouveau
   `OptimizeResponse` en diff par rapport à l'allocation originale.
3. **Extraction de contraintes** (`nim_client.py::extract_constraints`) :
   affiner le prompt système si les tests montrent des extractions
   incorrectes — rester dans le schéma de contrainte existant
   (`modify_demand|modify_price|add_storage_limit|remove_buyer|
   modify_transport_cost|add_time_constraint`).
4. **`ExplainView.tsx`** : appelle `POST /api/v1/explain` avec le résultat
   d'optimisation courant + les données d'entrée, affiche l'explication
   XAI en langage simple (cartes "pourquoi", "risques", "actions").
5. Gérer les états de chargement/erreur (NIM peut timeout à 30s côté
   backend — afficher un fallback clair, jamais un crash silencieux).

## Contrat à respecter
Le schéma JSON des contraintes retourné par NIM est défini par @Member1
dans `nim_client.py` — ne pas changer les noms de champs sans validation
Lead, car `solver.py::merge_constraints` en dépend.

# Scénarios « et si »

Code : `backend/app/scenarios/`, `backend/app/services/scenarios.py`, écran Scenario Studio
(`frontend/features/scenarios/`).

## Modèle

Un scénario = **une version de base d'un jeu de données + une liste ordonnée de modifications
typées**. Un scénario enfant (branche) applique d'abord les modifications de ses ancêtres, puis les
siennes. Chaque écriture ré-applique toute la chaîne : une modification invalide est refusée
(`422 SCENARIO_APPLY_ERROR` avec l'index de la modification) et rien n'est enregistré.

Le backend calcule toutes les nouvelles valeurs : l'interface (ou l'IA) envoie `-10 %` sous la forme
`{"mode": "relative_pct", "value": -10}`, jamais un prix recalculé (R7).

## Opérations (16)

| Opération | Cible | Paramètres |
|---|---|---|
| `buyer_price` | un acheteur ou `*` | `mode` (`absolute`, `relative_pct`, `delta`), `value` ; s'applique aussi au calendrier de prix |
| `buyer_demand` | un acheteur ou `*` | `field` (`max_demand_kg`, `max_per_day_kg`, `min_contract_kg`), `mode`, `value` |
| `harvest_quantity` | un lot ou `*` | `mode`, `value` |
| `harvest_timing` | un lot | `shift_days` |
| `storage_capacity` | un entrepôt | `mode`, `value` |
| `storage_cost` | un entrepôt ou `*` | `mode`, `value` |
| `add_storage` / `remove_storage` | — / un entrepôt | définition complète / aucun |
| `transport_cost` | un véhicule ou `*` | `field` (`cost_per_km`, `fixed_cost_per_trip`), `mode`, `value` |
| `vehicle_count` | un véhicule | `mode` (`absolute`, `delta`), `value` entier |
| `vehicle_capacity` | un véhicule | `mode`, `value` |
| `shelf_life` | une culture | `field` (`ambient`, `cold`), `mode`, `value` |
| `add_buyer` / `remove_buyer` | — / un acheteur | acheteur + route / aucun |
| `route` | la route d'un acheteur | `field` (`distance_km`, `road_condition`, `toll_per_trip`), valeur |
| `cold_chain` | un acheteur ou une culture | `required` |

Le catalogue (avec le schéma JSON de chaque `params`) est publié par `GET /api/v2/meta` ; le
formulaire de Scenario Studio est généré à partir de ce schéma.

## Cycle de vie

- **Aperçu** : `POST /scenarios/{id}/preview` (ou `apply-preview` sans scénario) renvoie les données
  effectives, les différences champ par champ, le résumé de chaque modification et la validation.
- **Branche / duplication** : une branche hérite de la chaîne ; une copie est indépendante.
- **Périmé** : un scénario est *périmé* quand une version plus récente du jeu de données existe.
  `POST /scenarios/{id}/rebase` le déplace sur la version courante en ré-appliquant les mêmes
  modifications (refusé si une modification ne s'applique plus).
- **Exécution** : `POST /scenarios/{id}/run`. L'entrée effective est hachée : relancer le même
  scénario avec la même configuration réutilise l'exécution existante (cache), sauf `use_cache=false`.
- **Recommandations** : une alerte avec un changement suggéré peut être « testée » en un clic
  (`POST /insights/{id}/try`) : un scénario est créé (branché sur celui de l'exécution le cas échéant)
  et exécuté avec la même configuration.

## Texte libre → modifications

`POST /scenarios/parse` traduit une phrase (« et si le prix de Sfax baisse de 10 % ») en modifications
proposées, chacune validée (opération typée, cible existante, application réussie sur les données
effectives) et **ancrée dans la phrase** (toute valeur absente de la phrase est rejetée avec la
raison). Une question (« quel est le profit… ? ») ne produit aucune modification et n'appelle même
pas le LLM. Rien n'est enregistré : l'utilisateur ajoute chaque proposition dans Scenario Studio.

## Comparaison

`POST /comparisons` : une référence et 1 à 3 exécutions **de la même culture**. Le backend calcule le
tableau des indicateurs (valeurs, écarts absolus et relatifs, sens « meilleur »), la matrice des
acheteurs (kg, écarts, statut gagné / perdu) et les changements notables classés par ampleur. Un
récit IA vérifié peut être généré (`POST /comparisons/narrative`).

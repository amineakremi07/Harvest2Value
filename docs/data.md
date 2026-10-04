# Données

## Format v2 (source de vérité)

Un jeu de données est un `DatasetPayload` (`backend/app/domain/dataset.py`). Le schéma JSON
`data/schema.v2.json` en est **généré** (`backend/scripts/export_json_schema.py`) : on ne le modifie
jamais à la main.

| Bloc | Contenu principal |
|---|---|
| `schema_version` | `"2.0"` |
| `currency` | code ISO à 3 lettres (ex. `TND`) ; absent → devise de l'espace de travail (hypothèse `CURRENCY_DEFAULT`) |
| `producer` | nom, région, pays, coordonnées et surface facultatives |
| `crops[]` | prix de référence, durée de conservation ambiante / froide, perte de qualité (%/jour), pertes de stockage (%/jour), chaîne du froid obligatoire |
| `harvest_lots[]` | culture, quantité (kg), jour de disponibilité, qualité |
| `buyers[]` | cultures acceptées, prix (+ `price_schedule` daté), demande max, max/jour, contrat minimum, minimum de commande, fenêtre de livraison, chaîne du froid, priorité |
| `storage_facilities[]` | capacité, réfrigéré, coût par kg et par jour |
| `vehicle_types[]` | capacité, nombre, réfrigéré, coût fixe par trajet, coût par km, vitesse, heures par jour, chargement, trajets max par jour |
| `routes[]` | un trajet par acheteur : distance, état de la route (facteur 1,00 / 1,15 / 1,35 ou forcé), péage |

Limites : 20 cultures, 60 lots, 50 acheteurs, 20 entrepôts, 20 types de véhicules, 50 routes.
Toutes les quantités sont en kg, toutes les durées en jours (jour 0 = début de l'horizon).

## Validation

Deux niveaux, renvoyés ensemble par `POST /datasets/{id}/validate` et affichés dans l'éditeur :

1. **Schéma** (Pydantic) : types, bornes, identifiants → `SCHEMA_ERROR` avec le chemin du champ.
2. **Règles métier** (`app/domain/validation.py`) : niveaux `error`, `warning`, `assumption`.
   Exemples : `NO_VEHICLE`, `NO_BUYER_FOR_CROP`, route manquante, fenêtre incohérente, contrat
   supérieur à la récolte, `STORAGE_ZERO_CAPACITY`, chaîne du froid impossible.

Un payload non conforme au schéma est refusé à l'enregistrement (`422 DATASET_INVALID`). Une
version qui respecte le schéma mais comporte une erreur métier est enregistrée (brouillon) mais
**ne peut pas être optimisée** (`422 DATASET_INVALID` au lancement).

## Versions

Chaque modification crée une version numérotée immuable (`PUT /datasets/{id}/payload` avec
`If-Match`). L'historique, le différentiel champ par champ entre deux versions et l'export d'une
version précise sont disponibles dans l'onglet *Versions* et via l'API. Une exécution référence
toujours une version exacte : modifier les données ne change jamais un résultat passé.

## Import v1

`POST /datasets/import` (et le bouton *Importer* de la page Jeux de données) détecte le format :

- **v2** : validé tel quel.
- **v1** (ancien format de la V1, exemple conservé dans
  `backend/tests/fixtures/v1/tunisia_olives.json`) : converti par
  `app/domain/migrations_v1.py` en **mode compatibilité** — un lot unique au jour 0, conservation
  ambiante d'un jour (vendre aujourd'hui ou perdre), un type de véhicule `count = available_vehicles`
  limité à un trajet par jour, coûts de transport v1 au kg·km conservés.

Chaque valeur par défaut appliquée est renvoyée comme **hypothèse** (`source_format: "v1"`,
`assumptions[]`) et affichée après l'import, pour être remplacée par des données réelles.

## Modèles

Cinq modèles tunisiens en lecture seule dans `data/templates/` (olives, dattes, agrumes, tomates,
blé) : point de départ de `POST /datasets {"template_key": ...}`. Leur construction et toutes leurs
hypothèses sont détaillées dans [data/templates/README.md](../data/templates/README.md). Chacun est
optimal en moins de 5 s (test `tests/regression/test_audit_solver.py`).

## Exports

`GET /datasets/{id}/export?format=json|csv&version=` : JSON v2 complet, ou archive ZIP de
fichiers CSV (un par bloc). Les rapports ont leurs propres exports (voir [api.md](api.md)).

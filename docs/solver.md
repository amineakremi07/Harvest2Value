# Solveur (MILP)

Code : `backend/app/optimization/`. Modèle linéaire en nombres mixtes construit avec PuLP et résolu
par CBC, dans un thread dédié (la boucle d'événements reste disponible pendant la résolution).

## Instance (`instance.py`)

Construite à partir de la version du jeu de données et de la configuration :

- **Horizon** : `config.horizon_days`, sinon calculé (dernier lot + plus longue conservation,
  plafonné) ; les lots hors horizon sont ignorés avec un avertissement.
- **Lots** (quantité, jour de disponibilité), **acheteurs** (fenêtre de livraison, demande totale et
  journalière, contrat minimum, minimum de commande, prix éventuellement datés, chaîne du froid),
  **entrepôts** (capacité, coût / kg / jour, perte journalière, conservation ambiante ou froide),
  **véhicules** (nombre, capacité, frigorifique, heures et trajets par jour), **routes** (distance,
  état de la route, péage).
- **Prix effectif** d'un lot vendu le jour *d* : prix de l'acheteur ce jour-là × (1 − décroissance de
  qualité × âge du lot).
- Coût et durée d'un aller-retour par couple acheteur × véhicule.

## Variables (`variables.py`)

| Variable | Sens |
|---|---|
| `x[b, l, f, d]` | kg du lot *l* vendus à l'acheteur *b* le jour *d*, depuis le lieu *f* (« direct » ou un entrepôt) |
| `z[l, f]` | kg du lot placés en direct ou dans un entrepôt le jour de récolte |
| `inv[l, f, d]` | stock en fin de jour |
| `unsold`, `expired` | pertes (non vendu en direct, périmé en stock) |
| `n[b, v, d]` | nombre d'allers-retours (entier) |
| `y[b]` | acheteur servi (binaire, si minimum de commande) |

## Contraintes (`constraints/`)

Chaque contrainte porte une clé `famille|entité|jour` réutilisée par l'explication.

| Module | Contraintes |
|---|---|
| `balance` | répartition de chaque lot ; vente directe le jour de récolte (le reste est perdu) ; bilan de stock jour par jour avec perte journalière |
| `demand` | demande maximale sur l'horizon et par jour, contrat minimum, minimum de commande `MOQ·y ≤ vendu ≤ max·y` |
| `shelf_life` | aucune vente après la date limite (pas de variable) ; stock restant enregistré comme périmé, ou comme stock final si la conservation dépasse l'horizon |
| `storage` | stock de fin de jour ≤ capacité |
| `transport` | kg livrés ≤ capacité des trajets ; heures de conduite et nombre de trajets par type de véhicule et par jour ; trajet plus long qu'une journée impossible |
| `cold_chain` | culture ou acheteur sous chaîne du froid : véhicules frigorifiques et stockage froid uniquement |

**Bilan de masse exact** : pour chaque lot, récolte = vendu + perdu (non vendu, pertes de stockage,
périmé) + stock final. Vérifié par des tests de propriétés (`tests/unit/optimization/test_properties.py`).

## Objectifs (`objectives.py`)

| Objectif | Optimise |
|---|---|
| `profit` (défaut) | profit réalisé + valeur de récupération du stock final (0 par défaut) |
| `revenue` | chiffre d'affaires (départage minimal par les coûts) |
| `waste` | pertes minimales |
| `cost` | coûts minimaux sous contraintes de ventes |
| `weighted` | somme pondérée des écarts normalisés à l'idéal (profit, pertes, coûts), avec une table de gains calculée par trois résolutions mono-critère |

## Statuts et diagnostics

- Résultat du solveur : `optimal`, `feasible` (limite de temps atteinte avec une solution, écart
  rapporté), `infeasible`, `not_solved`, `error`. Aucun KPI n'est publié sans solution (R4).
- Statut d'exécution : `queued`, `running`, `succeeded`, `infeasible`, `timeout`, `failed`,
  `cancelled`, `interrupted`.
- En cas d'infaisabilité, `diagnostics.py` procède par relaxation élastique : les contraintes
  physiques (répartition, bilan, péremption) ne sont jamais relâchées ; les exigences (contrats
  minimums, niveau de service, profit plancher) reçoivent une variable de dépassement minimisée —
  celles qui restent non nulles sont les conflits, avec la quantité manquante. Si cela ne suffit pas,
  les capacités (stockage, demande, flotte) sont relâchées à leur tour.

## KPI (`postprocess.py`)

| KPI | Définition |
|---|---|
| `realized_revenue` | somme des ventes uniquement |
| `total_cost` | transport + stockage + élimination |
| `realized_profit` | `realized_revenue − total_cost` |
| `ending_inventory_value` | stock final × valeur de récupération |
| `economic_value` | `realized_profit + ending_inventory_value` — **jamais présentée comme un profit** |
| `waste_rate_pct`, `sold_rate_pct`, `storage_rate_pct`, `fulfillment_rate_pct` | taux sur la récolte / la demande |
| `vehicle_utilization_pct`, `load_factor_pct`, `trips`, `avg_transport_cost_per_kg` | logistique |

Aucun KPI ne mélange revenu réalisé et valeur du stock (R1/R2) :
`tests/regression/test_audit_solver.py`.

## Sensibilité (`sensitivity.py`)

- **Valeurs duales** du LP obtenu en fixant les variables entières de la solution (trajets,
  acheteurs servis) : indicateur local, valable pour une petite variation sans changement de
  structure du plan. Elles sont marquées non fiables quand l'exécution n'est pas prouvée optimale,
  quand la contrainte contient une variable entière, en cas de dégénérescence, ou en mode pondéré.
- **Sondes** : jusqu'à 8 ré-optimisations qui relâchent les principaux goulots (ex. +10 % de demande
  journalière chez un acheteur, +1 camion) et mesurent le gain réel de profit. L'interface montre
  l'effet mesuré en premier et la valeur duale comme « indicateur local ».

## Performance

Chaque modèle (5 jeux tunisiens) est résolu à l'optimum en moins de 5 s, ainsi qu'un cas de 30 jours
(`tests/regression/test_audit_solver.py`) ; budgets de l'API dans `tests/performance/`.

# API v2

Base : `/api/v2`. Le document OpenAPI complet est servi par le backend : `/openapi.json`,
interface interactive `/docs`. Le contrat des routes est figé par le test
`backend/tests/integration/api/test_comparisons_and_flow.py::test_v2_route_contract_is_frozen`.

L'API v1 (`/api/v1/*`, `/health`) a été retirée en phase 14.

## Conventions

- JSON en entrée et en sortie ; identifiants UUID ; dates ISO 8601 en UTC.
- Pagination : `?page=1&page_size=20` → `{items, total, page, page_size}`.
- Opérations longues : `POST /runs?wait=N` attend jusqu'à N secondes ; `200` si terminé,
  `202` sinon (suivre `GET /runs/{id}`).
- Concurrence optimiste : `PUT /datasets/{id}/payload` avec `If-Match: "<version>"` ; une version
  plus récente donne `409 VERSION_CONFLICT`.
- Identifiant de requête : en-tête `X-Request-ID` (repris s'il est sûr, sinon généré), présent dans
  les journaux et dans l'enveloppe d'erreur.

### Enveloppe d'erreur

Toute erreur sous `/api/v2` a la forme :

```json
{ "error": { "code": "RUN_NOT_FINISHED", "message": "…", "details": {}, "request_id": "…" } }
```

Codes principaux : `VALIDATION_ERROR` (422), `NOT_FOUND` (404), `CONFLICT` / `VERSION_CONFLICT` /
`RUN_NOT_FINISHED` / `ACTION_EXPIRED` (409), `SCENARIO_APPLY_ERROR` / `DATASET_INVALID` /
`INCOMPARABLE` (422), `PAYLOAD_TOO_LARGE` (413), `RATE_LIMITED` (429), `INTERNAL_ERROR` (500,
sans détail interne), `LLM_UPSTREAM_ERROR` (502), `LLM_NOT_CONFIGURED` / `SOLVER_BUSY` (503),
`LLM_TIMEOUT` (504).

## Endpoints

### Système
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/health` | Vivacité (`{"status":"ok"}`) |
| GET | `/health/ready` | Prêt : `200 {"status":"ready","checks":{"solver":…,"llm":…}}` si CBC répond, sinon `503 not_ready`. L'absence de clé LLM ne rend pas l'API « non prête » (R11) |
| GET | `/meta` | Version, environnement, fournisseur LLM (sans clé), limites, modules actifs, objectifs, statuts, catalogue des opérations de scénario |

### Jeux de données
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/templates` | Modèles disponibles |
| POST | `/datasets` | Créer depuis `template_key` ou `payload` |
| GET | `/datasets` | Lister (`q`, `archived`) |
| POST | `/datasets/import` | Importer un fichier JSON v2 ou v1 (multipart `file`, `name`) ; renvoie `source_format` et les hypothèses de conversion |
| GET / PATCH / DELETE | `/datasets/{id}` | Détail (en-tête `ETag`) ; renommer / archiver ; supprimer |
| PUT | `/datasets/{id}/payload` | Nouvelle version (`If-Match`) |
| POST | `/datasets/{id}/duplicate` | Dupliquer |
| GET | `/datasets/{id}/export?format=json\|csv&version=` | Export |
| POST | `/datasets/{id}/validate` | Valider la version courante ou un payload fourni |
| GET | `/datasets/{id}/versions`, `/versions/{n}`, `/diff?from=&to=` | Historique et différences champ par champ |
| GET | `/datasets/{id}/market` | Acheteurs classés par prix net estimé |

### Exécutions
| Méthode | Chemin | Rôle |
|---|---|---|
| POST | `/runs` | Lancer (`dataset_id` + `version_no` ou `scenario_id`, `config`, `label`, `use_cache`) |
| GET | `/runs`, `/runs/{id}` | Liste (filtres `dataset_id`, `scenario_id`, `status`), détail |
| GET | `/runs/{id}/result` | Plan complet : allocations, stocks, trajets, pertes, KPI |
| GET | `/runs/{id}/diagnostics` | Causes d'infaisabilité |
| POST | `/runs/{id}/cancel`, `/runs/{id}/rerun` | Annuler (en file), relancer avec surcharges |
| DELETE | `/runs/{id}` | Supprimer |

### Explicabilité, alertes, analyses
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/runs/{id}/explanation` | Cartes de décision (acheteurs, stockage, pertes), contraintes saturées, goulots, compromis |
| GET | `/runs/{id}/constraints?binding_only=`, `/runs/{id}/bottlenecks` | Contraintes et goulots |
| POST / GET | `/runs/{id}/marginal-values` | Lancer / lire les sondes de ré-optimisation |
| GET | `/runs/{id}/insights` ; POST `/insights/{id}/dismiss\|restore\|try` | Alertes ; « tester cette recommandation » crée un scénario et l'exécute |
| GET | `/runs/{id}/network?day=` | Graphe logistique |
| GET | `/analytics/dashboard`, `/analytics/runs/{id}/{financial\|operational\|buyers\|logistics\|crops}` | Tableau de bord et 5 sections d'analyse |

### Scénarios et comparaisons
| Méthode | Chemin | Rôle |
|---|---|---|
| POST / GET | `/scenarios` | Créer, lister |
| POST | `/scenarios/apply-preview` | Appliquer des modifications sans rien enregistrer |
| GET / PATCH / DELETE | `/scenarios/{id}` | Détail (lignée, exécutions, périmé), métadonnées, suppression (`cascade`) |
| POST | `/scenarios/{id}/duplicate`, `/branch`, `/rebase`, `/preview`, `/run` | Dupliquer, brancher, rebaser, prévisualiser, exécuter |
| POST / PUT / PATCH / DELETE | `/scenarios/{id}/changes…` | Ajouter, réordonner, modifier, supprimer une modification |
| POST | `/comparisons` | Référence + 1 à 3 exécutions de la même culture |

### IA
| Méthode | Chemin | Rôle |
|---|---|---|
| POST / GET | `/copilot/conversations` ; GET / DELETE `/copilot/conversations/{id}` | Conversations |
| POST | `/copilot/conversations/{id}/messages?stream=true` | Un tour : JSON, ou SSE (`user_message`, `tool_call`, `tool_result`, `answer`, `error`, `done`) |
| POST | `/copilot/actions/{id}/confirm`, `/reject` | Exécuter (une seule fois) ou refuser une proposition |
| GET | `/copilot/tools` | Outils disponibles et état de la clé |
| POST | `/runs/{id}/explanation/narrative`, `/comparisons/narrative` | Récits vérifiés |
| POST | `/scenarios/parse` | Texte → modifications proposées (rien n'est enregistré) |

### Rapports
| Méthode | Chemin | Rôle |
|---|---|---|
| POST / GET | `/reports` | Créer une copie figée ; lister |
| GET | `/reports/sections` | Sections et tables exportables |
| GET / DELETE | `/reports/{id}` | Lire (snapshot), supprimer |
| GET | `/reports/{id}/export.json`, `/reports/{id}/export.csv?section=&table=` | Exports |

## Sécurité

- CORS en liste blanche (`CORS_ORIGINS`), sans credentials.
- Taille maximale du corps (`MAX_BODY_BYTES`, 2 Mo par défaut) → `413`.
- Limitation de débit par client : défaut, exécutions, copilot, récits (`RATE_LIMITS__*`).
- Les clés et secrets ne sont jamais journalisés ni renvoyés ; les réponses de l'IA sont nettoyées
  de tout ce qui ressemble à une clé.

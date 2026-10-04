# Harvest2Value — feuille de route V2

Branche `chedli`. Statut : `TODO` / `IN PROGRESS` / `DONE`. Les périmètres par module sont dans
`CLAUDE.md` ; la documentation dans `docs/`.

| Phase | Contenu | Jalon | Statut |
|---|---|---|---|
| 0–2 | Socle (configuration typée, fournisseurs LLM Groq / NIM / mock, `/api/v2`, santé), domaine v2 et jeux de données versionnés, modèle MILP v2 | — | DONE |
| 3 | Exécutions et résultats (file, cache, annulation, diagnostics) | — | DONE |
| 4 | Explicabilité, alertes et analyses côté backend, valeurs marginales | — | DONE |
| 5 | Scénarios côté backend : opérations typées, aperçu, lignée, périmé / rebase | — | DONE |
| 6–8 | Frontend v2 : shell, Optimization Studio, onglets de résultat (E2E n°1) | M1 | DONE |
| 9 | Scénarios et comparaison dans l'interface (E2E n°3) | M2 | DONE |
| 10 | Explicabilité et réseau logistique | — | DONE |
| 11 | Copilot : outils, vérification des chiffres, propositions confirmées | — | DONE |
| 12 | Analytics Center : 5 sections + vue comparée | — | DONE |
| 13 | Rapports figés, impression, exports CSV / JSON | — | DONE |
| 14 | Retrait de la V1, Docker de production, docs, palette ⌘K, accessibilité, performance | M4 | DONE |

## Suite possible (hors V2)
- Valider `docker compose up` sur une machine disposant de Docker (absent du poste de développement).
- Authentification et multi-espaces de travail.
- File d'exécutions persistante pour plusieurs processus backend.

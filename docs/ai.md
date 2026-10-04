# IA : Copilot, récits, texte → scénario

Code : `backend/app/ai/`, `backend/app/services/copilot.py`, `backend/app/api/v2/copilot.py`,
`frontend/features/copilot/`.

## Fournisseurs

| `LLM_PROVIDER` | Point d'accès | Modèle par défaut |
|---|---|---|
| `groq` (défaut) | `https://api.groq.com/openai/v1` | `openai/gpt-oss-120b` |
| `nvidia_nim` | `https://integrate.api.nvidia.com/v1` | `meta/llama-3.1-70b-instruct` |
| `mock` | aucun (tests, démos hors ligne) | réponses scriptées (`LLM_MOCK_SCRIPT`) |

Les deux fournisseurs réels utilisent la même API compatible OpenAI (`/chat/completions` avec
`tools`). `LLM_MODEL` et `LLM_BASE_URL` permettent de changer de modèle ou de passer par une passerelle.
L'appel d'outils a été testé en réel avec Groq (`docs/v2/phase11-tool-calling-probe.md`) ; NIM est
configurable mais n'a pas été testé faute de clé.

**Sans clé**, l'application reste entièrement utilisable : `/meta` indique `llm.configured=false`,
les endpoints IA répondent `503 LLM_NOT_CONFIGURED`, l'interface affiche « IA désactivée » (tiroir,
récits, champ texte du Scenario Studio, option de récit des rapports). `/health/ready` reste prêt.

## Un tour de Copilot

1. Le message utilisateur est nettoyé (caractères de contrôle, longueur) ; le contexte de page
   (exécution, jeu de données, scénario, comparaison à l'écran) est joint.
2. Le modèle dispose de **18 outils** (catalogue : `GET /copilot/tools`) :
   - lecture : `get_context`, `get_dataset`, `get_market_analysis`, `get_run`, `get_allocations`,
     `get_constraints`, `get_bottlenecks`, `explain_decision`, `get_insights`, `get_buyer_analysis`,
     `get_logistics_analysis`, `get_crop_analysis`, `preview_scenario`, `compare_runs`, `list_change_ops` ;
   - proposition : `create_scenario`, `run_optimization`, `generate_report`.
   Aucun outil n'accède au shell, aux fichiers, au réseau, à la configuration ou aux secrets.
3. Les arguments sont validés (Pydantic) ; une erreur est renvoyée au modèle, qui peut réessayer
   (5 tours d'outils au plus, 6 appels par tour). Un 429 du fournisseur est réessayé une fois.
4. Chaque résultat d'outil est une table plate `clé → valeur` ; chaque nombre est enregistré sous une
   **référence** (`r1.kpis.realized_profit`). Les entités reçoivent des alias courts (`r1`, `d1`, `s1`).
5. La réponse du modèle cite les chiffres par `{{ref:clé}}` ; le backend les **remplace** par les
   valeurs formatées (FR / EN, unité et devise du jeu de données).
6. Le **NumericVerifier** contrôle tout chiffre restant : il est accepté s'il correspond (aux
   arrondis d'affichage près, formats FR et EN) à une valeur fournie par un outil ou à un nombre tapé
   par l'utilisateur. Sinon, une seule régénération est demandée avec la liste des problèmes ; ce qui
   reste non vérifié est **marqué** `⟦?…⟧` et surligné dans l'interface, jamais masqué. Chaque
   message porte un badge « Chiffres vérifiés » ou « N chiffres non vérifiés ».
7. La réponse est diffusée en SSE (activité des outils, puis réponse) et enregistrée avec la trace
   des outils, l'identifiant du prompt versionné et le modèle.

## Propositions : rien sans confirmation

- Les outils de proposition **n'écrivent rien** : ils créent une action `pending` (expiration 30 min,
  clé d'idempotence) affichée comme une carte « Confirmer / Refuser ».
- **R6** : une proposition n'est acceptée que si le message de l'utilisateur demande un changement
  (créer, simuler, lancer, générer, « et si »…). Une question, même avec un nombre, n'en crée aucune.
- Chaque valeur numérique d'une proposition doit venir de l'utilisateur ou des données ; une valeur
  inventée est refusée et le modèle doit la demander.
- Les modifications sont pré-appliquées (aperçu) : on ne confirme que quelque chose qui fonctionne.
- Confirmer exécute l'action **une seule fois** (une seconde confirmation renvoie le même résultat) ;
  une action expirée ou refusée ne peut plus être exécutée.

## Garde-fous contre l'injection (`guards.py`)

- Les données (noms d'acheteurs, fichiers importés, résultats d'outils) et l'historique sont des
  **données** : les chaînes qui ressemblent à des instructions (« ignore les instructions… », balises
  système, appels d'outils, demande de clé) sont masquées avant d'atteindre le modèle, et un
  avertissement est ajouté au résultat de l'outil.
- Les anciens messages suspects sont rejoués sous la forme « [message antérieur masqué] ».
- Toute chaîne ressemblant à une clé (`gsk_…`, `nvapi-…`, `Bearer …`) est effacée des réponses.
- Tests : `backend/tests/unit/ai/test_verification_guards.py`,
  `backend/tests/integration/api/test_copilot_api.py`.

## Récits et texte → modifications

- `POST /runs/{id}/explanation/narrative` et `POST /comparisons/narrative` : les faits sont rassemblés
  par les mêmes outils de lecture, puis un seul appel LLM, avec la même vérification.
- `POST /scenarios/parse` : voir [scenarios.md](scenarios.md).

## Prompts versionnés

`backend/app/ai/prompts/<nom>.v<N>.md` ; la version la plus haute est utilisée et son identifiant
(`copilot_system@v1`) est stocké avec chaque message ou récit.

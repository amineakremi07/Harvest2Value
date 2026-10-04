# Guide utilisateur

Harvest2Value répond à une question : **à qui vendre ma récolte, quand, faut-il stocker, et avec
quels camions, pour gagner le plus ?** Le parcours type va des données au rapport.

La navigation est à gauche (menu repliable sur mobile). **Ctrl+K / ⌘K** ouvre la palette de
commandes : aller à une page, ouvrir une exécution, un jeu de données, un scénario ou un rapport
récent, changer de thème.
Toute l'application est utilisable au clavier (lien « Aller au contenu », Tab / Maj+Tab, Échap).

## 1. Données

Page **Données** :

- **Depuis un modèle** : cinq cas tunisiens (olives, dattes, agrumes, tomates, blé), prêts à
  optimiser.
- **Importer un fichier** : JSON au format v2, ou ancien format v1. Un fichier v1 est converti et
  les **hypothèses retenues** sont listées : à remplacer par vos chiffres réels.

Dans un jeu de données :

- **Édition rapide** (tableaux : lots, acheteurs, stockage, véhicules, routes) ou édition JSON.
- **Valider** : erreurs (bloquent l'optimisation), avertissements et hypothèses, avec le champ
  concerné.
- **Enregistrer** crée une nouvelle version, avec une note facultative. L'onglet **Versions**
  montre l'historique et les différences entre deux versions.
- Exporter (JSON, CSV), dupliquer, renommer, archiver, supprimer.

## 2. Optimiser

Page **Optimiser** : choisir le jeu de données (ou un scénario), l'objectif (profit réalisé,
chiffre d'affaires, pertes minimales, coûts minimaux, pondéré), l'horizon et les options, puis
**Lancer l'optimisation**. Un calcul identique déjà fait est resservi depuis le cache.

Si le problème est impossible (par exemple un contrat minimum supérieur à la récolte), l'exécution
affiche les **causes d'infaisabilité** au lieu de chiffres.

## 3. Lire un résultat

Une exécution (page **Exécutions**) a plusieurs onglets :

| Onglet | Contenu |
|---|---|
| Résumé | KPI : revenu réalisé, coûts, **profit réalisé**, pertes, et à part la **valeur du stock restant** (jamais additionnée au revenu) |
| Allocation | quantités par acheteur et par jour |
| Stocks | niveau des entrepôts, ambiant / froid, jour par jour |
| Logistique | trajets, camions, coûts de transport |
| Explication | pour chaque acheteur : décision, facteur limitant, meilleure alternative ; contraintes saturées, goulots, valeurs marginales mesurées par ré-optimisation |
| Réseau | carte des flux producteur → entrepôts → acheteurs, avec curseur de période |
| Alertes | recommandations ; « Tester » crée un scénario, l'exécute et ouvre la comparaison |
| Données brutes | le résultat complet en JSON |

## 4. Scénarios « et si »

Page **Scénarios** → **Nouveau scénario** à partir d'un jeu de données. Ajouter des modifications
typées (prix, demande, récolte, stockage, transport, flotte, péremption, acheteurs, routes, chaîne
du froid) ou les **décrire en langage naturel** (le Copilot propose des modifications ; rien n'est
ajouté sans votre accord). L'**aperçu des données effectives** montre l'effet avant de lancer.

Un scénario peut être dupliqué ou **branché** ; l'arborescence montre la lignée. Si le jeu de
données de base a changé, le scénario est marqué **périmé** : **Rebaser** le recale sur la
dernière version.

## 5. Comparer

Page **Comparer** : une exécution de référence et 1 à 3 autres de la même culture. Écarts de KPI,
d'allocation et de logistique, et un récit vérifié si l'IA est active.

## 6. Analyses

Page **Analyses** : cinq sections (financier, opérationnel, acheteurs, logistique, culture) pour une
exécution, et une vue comparée de plusieurs exécutions.

## 7. Copilot

Page **Copilot** : posez des questions sur vos données et résultats. Le Copilot lit les données
via des outils ; chaque chiffre affiché est **rendu par le backend** et porte une citation. Un
chiffre qu'il n'a pas pu vérifier est **marqué comme non vérifié**. Quand il propose une action
(créer un scénario, lancer une exécution, créer un rapport), une carte demande **Confirmer** ou
**Refuser** : rien n'est modifié sans confirmation.

Sans clé d'API, le Copilot affiche « IA désactivée » ; tout le reste fonctionne.

## 8. Rapports

Page **Rapports** → nouveau rapport depuis une exécution : choix des sections. Le rapport est une
**copie figée** (avec empreinte SHA-256) : il ne change plus, même si les données changent.
**Imprimer / PDF** passe par l'impression du navigateur ; chaque table s'exporte en CSV, le rapport
entier en JSON.

## 9. Réglages

Thème clair / sombre / système (mémorisé dans le navigateur), adresse et version de l'API,
fournisseur et modèle IA (« configuré » ou « IA désactivée »), limite de temps du solveur.
Les montants sont affichés dans une devise unique : celle du jeu de données.

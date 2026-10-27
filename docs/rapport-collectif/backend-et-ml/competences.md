# Compétences Backend et ML

*En cours. Ticket #171.*

Cette page présente la contribution du rôle et la relie aux compétences de la grille d'auto-évaluation. Pour chaque compétence : ce qui a été fait, avec une preuve du dépôt (PR, fichier ou sortie de commande), les problèmes résolus et la limite connue. La rédaction est neutre et centrée sur les choix techniques et leur évolution.

## Rôle tenu

*À compléter : le rôle défini au début du projet, son périmètre et la façon dont il a évolué.*

## C32 Modèle de prévision

**La grille attend** : un modèle entraîné, versionné dans MLflow et déployé.

**Pistes**

- Le choix du modèle et la comparaison à une référence.
- Le versionnage, la promotion challenger puis champion et son critère.
- Ce qui est déployé et ce qui ne l'est pas encore.

**Preuves possibles** : `ml/README.md`, une capture du registre MLflow.

*À compléter.*

## C33 Suivi du modèle

**La grille attend** : une surveillance de la dérive et de la performance.

**Pistes**

- Les métriques suivies et où elles sont lues (base, vues).
- Ce qui n'est pas mesuré (dérive des entrées) et la suite.

**Preuves possibles** : les tables et vues `ml.*`, `ml/README.md`.

*À compléter.*

## C34 Documentation de l'API prédictive

**La grille attend** : une API prédictive documentée clairement.

**Pistes**

- Les routes, leur authentification et leurs contrats.
- L'état de la route de prévision (données réelles ou factices).

**Preuves possibles** : la documentation de l'API, `api/README.md`, `ml/README.md`.

*À compléter.*

## C35 Amélioration continue

**La grille attend** : des indicateurs qui mesurent l'impact du modèle sur un processus simulé.

**Pistes**

- Les indicateurs d'impact et leurs hypothèses.
- Les ajustements décidés à partir des mesures.

**Preuves possibles** : les métriques de gain dans MLflow, `ml/README.md`.

*À compléter.*

## API et authentification

**Pistes**

- Les routes, l'authentification et les choix de sécurité de l'API.
- Les tests et la couverture.

**Preuves possibles** : `api/README.md`, `api/tests`.

*À compléter.*

## Limites et évolutions envisagées

*À compléter : ce qui n'est pas fait, pourquoi, et la suite prévue.*

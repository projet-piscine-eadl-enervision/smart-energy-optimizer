# Compétences Données

*En cours. Ticket #168.*

Cette page présente la contribution du rôle et la relie aux compétences de la grille d'auto-évaluation. Pour chaque compétence : ce qui a été fait, avec une preuve du dépôt (PR, fichier ou sortie de commande), les problèmes résolus et la limite connue. La rédaction est neutre et centrée sur les choix techniques et leur évolution.

## Rôle tenu

*À compléter : le rôle défini au début du projet, son périmètre et la façon dont il a évolué.*

## C27 Architecture des données

**La grille attend** : un stockage conçu, évolutif et documenté.

**Pistes**

- Le modèle de la base (schémas, séries temporelles, agrégats) et les alternatives écartées.
- Les migrations et leur contrôle en CI.

**Preuves possibles** : `db/migrations`, `docs/migrations-base-de-donnees.md`.

*À compléter.*

## C28 ETL

**La grille attend** : un ETL qui extrait, transforme et charge correctement.

**Pistes**

- Les traitements (chargement des sites, collecte, rattrapage, historique) et leurs garanties (relance sans doublon, brut conservé).
- Les résultats mesurés sur la VM.

**Preuves possibles** : `etl/README.md`, les tests de l'ETL.

*À compléter.*

## C29 Big Data

**La grille attend** : des outils adaptés au volume.

**Pistes**

- Les volumes réels et le seuil à partir duquel le choix changerait.
- Les outils retenus et pourquoi.

**Preuves possibles** : `etl/README.md`, `docs/analyse-api-mock.md`.

*À compléter.*

## C30 BI et tableau de bord

**La grille attend** : un tableau de bord interactif, connecté aux données réelles.

**Pistes**

- Les écrans, leurs données et leurs interactions.
- Ce qui est branché sur les données réelles et ce qui ne l'est pas encore.
- Les indicateurs affichés et leur lecture.

**Preuves possibles** : `frontend/`, `frontend/README.md`, les routes de l'API.

*À compléter.*

## C31 Automatisation (RPA)

**La grille attend** : au moins une tâche répétitive automatisée dans le pipeline, avec conformité et traçabilité.

**Pistes**

- Les tâches automatisées (collecte, rattrapage, mises à jour) et leur traçabilité.
- Ce qui reste à la main.

**Preuves possibles** : le suivi des exécutions de l'ETL, les workflows.

*À compléter.*

## Limites et évolutions envisagées

*À compléter : ce qui n'est pas fait, pourquoi, et la suite prévue.*

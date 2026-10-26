# Tests

*En cours. Ticket #170.*

Cette page présente la contribution du rôle et la relie aux compétences de la grille d'auto-évaluation. Pour chaque compétence : ce qui a été fait, avec une preuve du dépôt (PR, fichier ou sortie de commande), les problèmes résolus et la limite connue. La rédaction est neutre et centrée sur les choix techniques et leur évolution.

## Rôle tenu

*À compléter : le rôle défini au début du projet, son périmètre et la façon dont il a évolué.*

## C8 Stratégie de tests

**La grille attend** : une stratégie de tests définie, idéalement des tests écrits avant le code.

**Pistes**

- Ce qui est testé à chaque niveau (unitaire, intégration, bout en bout) et pourquoi.
- L'ordre entre tests et code quand il a été respecté, et la couverture mesurée.
- Ce qui n'est pas couvert, et la suite prévue.

**Preuves possibles** : les dossiers de tests de chaque module, la couverture dans la CI, `frontend/cypress`.

*À compléter.*

## C17 Tests automatisés

**La grille attend** : des tests fonctionnels et non fonctionnels dans le pipeline.

**Pistes**

- Les tests qui tournent à chaque PR et ce qu'ils bloquent.
- Les contrôles non fonctionnels : couverture, migrations rejouées deux fois, sondes de santé.
- Les tests d'intégration sur une base migrée.

**Preuves possibles** : `.github/workflows/ci.yml`, `docs/qualite-et-securite-ci.md`, les journaux de la CI.

*À compléter.*

## Limites et évolutions envisagées

*À compléter : ce qui n'est pas fait, pourquoi, et la suite prévue.*

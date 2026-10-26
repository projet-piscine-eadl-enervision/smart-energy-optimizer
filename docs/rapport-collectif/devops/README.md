# DevOps

*En cours. Ticket #165.*

Cette page présente la contribution du rôle et la relie aux compétences de la grille d'auto-évaluation. Pour chaque compétence : ce qui a été fait, avec une preuve du dépôt (PR, fichier ou sortie de commande), les problèmes résolus et la limite connue. La rédaction est neutre et centrée sur les choix techniques et leur évolution.

## Rôle tenu

*À compléter : le rôle défini au début du projet, son périmètre et la façon dont il a évolué.*

## C16 Pipeline CI/CD

**La grille attend** : un pipeline build, test et déploiement qui fonctionne de bout en bout.

**Pistes**

- Le chemin d'une modification, de la PR au déploiement : étapes, déclencheurs, environnements.
- Le choix de construire une fois et de promouvoir la même image, et le retour arrière.
- Les évolutions de la chaîne et leurs raisons.

**Preuves possibles** : `.github/workflows/`, `docs/mise-en-production.md`, un run réel de la CI.

*À compléter.*

## C17 Tests automatisés

**La grille attend** : des tests fonctionnels et non fonctionnels dans le pipeline.

**Pistes**

- Les tests qui tournent à chaque PR et ce qu'ils bloquent.
- Les contrôles non fonctionnels : couverture, migrations rejouées deux fois, sondes de santé.
- Les tests d'intégration sur une base migrée.

**Preuves possibles** : `.github/workflows/ci.yml`, `docs/qualite-et-securite-ci.md`, les journaux de la CI.

*À compléter.*

## C18 DevSecOps

**La grille attend** : des scans de sécurité (OWASP ZAP, Trivy) intégrés au pipeline, avec les vulnérabilités traitées.

**Pistes**

- Les scans en place, ce qu'ils bloquent et ce qu'ils ne bloquent pas.
- Des vulnérabilités réellement traitées, avec la PR qui les corrige.
- Ce qui manque (par exemple un scan dynamique) et pourquoi.

**Preuves possibles** : le job `security` de la CI, le rapport de sécurisation, l'onglet Security du dépôt.

*À compléter.*

## C19 Code propre

**La grille attend** : de bonnes pratiques et un linter ou un analyseur.

**Pistes**

- Les outils : linter, hooks avant commit, convention de commits, porte de qualité.
- Les écarts connus (par exemple un module sans linter).

**Preuves possibles** : `.pre-commit-config.yaml`, le job `sonar`, l'audit du dépôt.

*À compléter.*

## C20 Documentation technique

**La grille attend** : un pipeline documenté de façon claire, complète et à jour.

**Pistes**

- Les guides de procédure et à qui ils s'adressent.
- Le moyen retenu pour que la documentation suive le code.

**Preuves possibles** : `CONTRIBUTING.md`, `docs/`, le wiki généré depuis le dépôt.

*À compléter.*

## C23 Administration par scripts

**La grille attend** : des scripts Bash ou Python d'administration.

**Pistes**

- Les scripts utilisés pour exploiter la plateforme et leurs tests.
- Ce qui est automatisé et ce qui reste manuel.

**Preuves possibles** : `infra/scripts/` et ses fichiers `test-*`.

*À compléter.*

## C24 Supervision

**La grille attend** : un outil de supervision et des indicateurs pertinents.

**Pistes**

- Ce qui existe (sondes de santé, journaux) et ce qui manque.
- La solution prévue et ce qu'elle mesurerait.

**Preuves possibles** : les routes `/health`, les `HEALTHCHECK` des images, l'audit du dépôt.

*À compléter.*

## Limites et évolutions envisagées

*À compléter : ce qui n'est pas fait, pourquoi, et la suite prévue.*

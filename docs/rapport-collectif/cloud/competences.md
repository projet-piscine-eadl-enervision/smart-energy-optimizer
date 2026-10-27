# Compétences Cloud

*En cours. Ticket #166.*

Cette page présente la contribution du rôle et la relie aux compétences de la grille d'auto-évaluation. Pour chaque compétence : ce qui a été fait, avec une preuve du dépôt (PR, fichier ou sortie de commande), les problèmes résolus et la limite connue. La rédaction est neutre et centrée sur les choix techniques et leur évolution.

## Rôle tenu

*À compléter : le rôle défini au début du projet, son périmètre et la façon dont il a évolué.*

## C21 Services cloud

**La grille attend** : des services cloud intégrés, avec leur apport justifié.

**Pistes**

- Les services utilisés et la raison de chacun.
- Le choix d'une architecture hybride (production sur AWS, staging sur la VM de l'école).

**Preuves possibles** : `infra/README.md`, `infra/terraform/aws/`.

*À compléter.*

## C22 Infrastructure as Code

**La grille attend** : un Terraform ou équivalent, fonctionnel et reproductible.

**Pistes**

- Ce que le code décrit et ce qui a été créé à la main.
- La preuve de reproductibilité : un `plan` sur l'infrastructure existante.
- Le changement de fournisseur et son effet sur le code.

**Preuves possibles** : `infra/terraform/aws/`, le job `terraform` de la CI, la sortie d'un `terraform plan`.

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

## C25 Sécurité cloud

**La grille attend** : des droits (IAM), des secrets et des accès réseau maîtrisés.

**Pistes**

- Les identités et leurs droits, les secrets, les règles réseau.
- Les limites assumées.

**Preuves possibles** : le rapport de sécurisation (section réseau et droits).

*À compléter.*

## C26 Intégrité des données (optionnel)

**La grille attend** : une traçabilité des données, par exemple par blockchain.

**Pistes**

- Dire si le critère est traité et pourquoi.
- Ce qui joue un rôle voisin : empreintes des données suivies, réponses brutes conservées, SBOM des versions.

**Preuves possibles** : `docs/donnees-dvc.md`, le schéma `raw` de la base.

*À compléter.*

## Limites et évolutions envisagées

*À compléter : ce qui n'est pas fait, pourquoi, et la suite prévue.*

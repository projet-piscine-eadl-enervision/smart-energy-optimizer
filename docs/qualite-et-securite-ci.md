# Qualité et sécurité de la CI

Ce que la CI contrôle sur chaque PR, où lire les résultats et que faire quand un contrôle échoue. Les règles de branches et de commits sont dans [`CONTRIBUTING.md`](../CONTRIBUTING.md), la livraison dans [`mise-en-production.md`](mise-en-production.md).

## Les contrôles d'une PR

| Contrôle | Ce qu'il vérifie | Bloque la PR |
|---|---|---|
| `pr-title`, `branch-name`, `commit-messages` | Conventional Commits, nom de branche | oui |
| `changes` | liste des modules touchés (voir plus bas) | oui |
| `python (api\|etl\|ml)` | `ruff` et `pytest` du module | oui |
| `frontend` | tests et build Angular | oui |
| `migrations` | migrations SQL appliquées deux fois sur une base vide | oui |
| `security` | Trivy sur le code : dépendances, secrets, Terraform, Dockerfiles | oui |
| `sonar` | analyse SonarQube Cloud et porte de qualité | oui |
| `ci-ok` | résume tous les précédents : c'est le seul contrôle exigé sur `main` | oui |

La CI ne teste que les modules dont le dossier change (`api/`, `etl/`, `ml/`, `frontend/`, `db/`) ; un changement dans `.github/`, `infra/scripts/`, les fichiers compose ou les hooks lance tout. Sur un push de `main`, tout est testé.

## Trivy

- **Code (`security`)** : bloque la PR sur toute vulnérabilité **haute ou critique corrigeable** dans les dépendances, ou sur un secret ou une mauvaise configuration. Une alerte apparaît quand une nouvelle CVE est publiée, même sans changement de code : mettre à jour la dépendance (`npm audit fix`, `./infra/scripts/compile-requirements.sh --upgrade-package <paquet>`).
- **Images** : chaque image construite sur `main` est scannée par le job `publish`. Le rapport va dans l'onglet *Security > Code scanning* du dépôt (une catégorie `trivy-image-<module>` par module). Il ne bloque pas pour l'instant.
- **SBOM** : à chaque release, le SBOM (CycloneDX) de chaque image versionnée est joint à la GitHub Release.
- Scan en local : `docker run --rm -v "$PWD":/src aquasec/trivy:0.69.3 fs --scanners vuln,secret,misconfig --severity HIGH,CRITICAL --ignore-unfixed /src`.

## SonarQube Cloud

- Organisation : https://sonarcloud.io/organizations/projet-piscine-eadl-enervision/projects
- Projet : https://sonarcloud.io/project/overview?id=projet-piscine-eadl-enervision_smart-energy-optimizer
- Connexion avec le compte GitHub. Les administrateurs de l'organisation règlent la porte de qualité et acceptent les anomalies.

**Porte de qualité `EnerVision`, appliquée au code neuf d'une PR** : couverture d'au moins **80 %**, notes de fiabilité, de sécurité et de maintenabilité à **A**, doublons sous **3 %**, points sensibles de sécurité revus à **100 %**. Le seuil se règle dans *Organization > Quality Gates*.

- Le job `sonar` échoue si la porte n'est pas franchie : le détail est dans le lien « View details » du journal du job, ou dans l'onglet *Pull requests* du projet.
- Sur `main`, l'analyse est publiée sans bloquer : un défaut déjà fusionné ne doit pas arrêter la publication des images.
- Une PR venant d'un fork n'a pas accès au jeton : le job passe sans analyser.
- La couverture vient de la CI : `pytest --cov` (un `coverage.xml` par module Python) et `ng test --coverage` (le frontend). `infra/scripts/prefix-coverage.py` y ajoute le dossier du module et une source relative, sinon Sonar ne retrouve pas les fichiers.
- L'analyse automatique de SonarQube Cloud est **désactivée** : elle est incompatible avec l'analyse de la CI.

## Quand un contrôle échoue

| Symptôme | Que faire |
|---|---|
| `security` rouge sans changement de code | nouvelle CVE : mettre à jour la dépendance indiquée (voir plus haut) |
| `sonar` : « Coverage on New Code » sous 80 % | ajouter des tests pour les lignes nouvelles ; les fichiers à compléter sont listés dans l'onglet *Code* de la PR |
| `sonar` : une anomalie de sécurité ou un point sensible | la corriger ; sinon, dans SonarQube Cloud, ouvrir l'anomalie, statut **Accept** avec un commentaire qui explique pourquoi (réservé aux administrateurs) ; relancer les jobs en échec |
| `sonar` : « Cannot resolve the file path … coverage » | la couverture n'est pas rattachée aux fichiers : vérifier que `prefix-coverage.py` a tourné (étape « Préparer la couverture pour Sonar ») |
| `sonar` : « You are running CI analysis while Automatic Analysis is enabled » | désactiver *Administration > Analysis Method > Automatic Analysis* dans le projet Sonar |
| `ci-ok` rouge | ouvrir le job en échec : `ci-ok` ne fait que résumer les autres |

Les anomalies acceptées à ce jour : « dépendances sans empreintes » (`docker:S8544`) sur les Dockerfiles de `etl` et `ml`. Les versions sont figées par `pip-compile`, il manque seulement les empreintes (`--generate-hashes`).

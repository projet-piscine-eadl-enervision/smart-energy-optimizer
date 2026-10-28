# Qualité et sécurité de la CI

Ce que la CI contrôle sur chaque PR, où lire les résultats et que faire quand un contrôle échoue. Les règles de branches et de commits sont dans [`CONTRIBUTING.md`](../CONTRIBUTING.md), la livraison dans [`mise-en-production.md`](mise-en-production.md).

## Les contrôles d'une PR

| Contrôle | Ce qu'il vérifie | Bloque la PR |
|---|---|---|
| `pr-title`, `branch-name`, `commit-messages` | Conventional Commits, nom de branche | oui |
| `changes` | liste des modules touchés (voir plus bas) | oui |
| `python (api\|etl\|ml)` | `ruff` et `pytest` du module ; pour `api`, `etl` et `ml`, sur une base TimescaleDB migrée | oui |
| `frontend` | tests et build Angular | oui |
| `e2e` | scénarios Cypress contre la vraie pile (base migrée, API, front), si `frontend/` ou `api/` change | oui |
| `dast` | scan OWASP ZAP passif de l'API sur une pile éphémère, si `api/` change ; rapport en artefact | sur les alertes hautes |
| `load` | test de charge smoke de l'API (k6) sur une pile éphémère, si `api/` ou `infra/k6/` change | oui |
| `migrations` | migrations SQL appliquées deux fois sur une base vide | oui |
| `terraform` | `terraform fmt -check` et `terraform validate` sur `infra/terraform/`, sans identifiants ni state | oui |
| `security` | Trivy sur le code : dépendances, secrets, Terraform, Dockerfiles | oui |
| `sonar` | analyse SonarQube Cloud et porte de qualité | oui |
| `ci-ok` | résume tous les précédents : c'est le seul contrôle exigé sur `main` | oui |

La CI ne teste que les modules dont le dossier change (`api/`, `etl/`, `ml/`, `frontend/`, `db/`, `infra/terraform/`) ; un changement dans `db/` lance aussi `api`, `etl` et `ml` ; un changement dans `.github/`, `infra/scripts/`, les fichiers compose ou les hooks lance tout. Sur un push de `main`, tout est testé.

## Trivy

- **Code (`security`)** : bloque la PR sur toute vulnérabilité **haute ou critique corrigeable** dans les dépendances, ou sur un secret ou une mauvaise configuration. Une alerte apparaît quand une nouvelle CVE est publiée, même sans changement de code : mettre à jour la dépendance (`npm audit fix`, `./infra/scripts/compile-requirements.sh --upgrade-package <paquet>`).
- **Images** : chaque image construite sur `main` est scannée par le job `publish`. Le rapport va dans l'onglet *Security > Code scanning* du dépôt (une catégorie `trivy-image-<module>` par module). Il ne bloque pas pour l'instant.
- **SBOM** : à chaque release, le SBOM (CycloneDX) de chaque image versionnée est joint à la GitHub Release.
- Scan en local : `docker run --rm -v "$PWD":/src aquasec/trivy:0.69.3 fs --scanners vuln,secret,misconfig --severity HIGH,CRITICAL --ignore-unfixed /src`.

## Scan DAST (OWASP ZAP)

Le job `dast` démarre une pile éphémère dans la CI (base migrée et API, comme le job `e2e`), puis lance ZAP contre l'API. Le staging est sur un réseau interne, injoignable depuis un exécuteur GitHub, et la production n'est jamais scannée.

- **Ce que fait le scan** : ZAP (`zap-api-scan.py`) importe `/openapi.json`, appelle chaque route une fois et analyse les réponses (en-têtes, cookies, fuites d'informations, erreurs…). Le scan est **passif** (option `-S`) : aucune attaque n'est envoyée. Il dure environ une minute. `/openapi.json` n'existe qu'hors production (`APP_ENV` différent de `production`), ce qui est le cas de la pile de la CI.
- **Rapport** : l'artefact `zap-report` du run (HTML à ouvrir dans un navigateur, et JSON). Le journal de l'étape « Alertes hautes » liste les alertes par niveau.
- **Blocage** : le job échoue sur toute alerte de risque **haut** (`infra/scripts/check-zap-report.py`). Les alertes basses et moyennes sont dans le rapport, sans bloquer.
- **Exceptions** : `infra/zap/rules.tsv`, une ligne par règle (id, niveau, nom, raison, séparés par des tabulations). Une règle à `IGNORE` ne bloque plus, et sa raison est obligatoire. Les id des règles sont dans le rapport et sur https://www.zaproxy.org/docs/alerts/.
- Scan en local, avec la pile démarrée : `docker compose up -d api`, puis `docker compose --profile dast run --rm zap`. Les rapports arrivent dans `infra/zap/` (ignorés par git), puis `python3 infra/scripts/check-zap-report.py infra/zap/zap-report.json infra/zap/rules.tsv`.

## Test de charge (k6)

Le job `load` démarre la même pile éphémère que `dast` (base migrée et API), crée un compte de test admin, puis lance le scénario smoke de k6 (`infra/k6/smoke.js`) : 5 utilisateurs virtuels pendant une minute, qui appellent en boucle les routes du tableau de bord (`/sites`, `/history`, `/predictions`, `/recommendations`, `/alerts`).

- **Seuils** : aucune requête en erreur, p95 sous **500 ms** sur l'ensemble et pour chaque route. Un seuil non tenu fait sortir k6 en code 99, donc le job échoue. La connexion (bcrypt, lent exprès) est faite une seule fois avant le test et n'entre pas dans les seuils.
- **Preuve que le seuil bloque** : l'étape « Le seuil de latence fait bien échouer k6 » relance 10 s avec un seuil impossible (`P95_MS=1`) et vérifie que k6 échoue bien en code 99.
- **Limite** : la base de la CI est vide. Le job repère une route cassée ou une régression nette de latence, il ne mesure pas la capacité de l'API.
- **Résultats** : le résumé de k6 est dans le journal de l'étape « Scénario smoke », avec une ligne de p95 par route.
- **Garde-fou** : le script refuse une cible `*.cloudfront.net` ou `*.amazonaws.com`, et une API dont `/health` annonce `production`. On ne charge jamais la production ; prévenir l'équipe avant de charger le staging.
- En local, avec la pile démarrée (`docker compose up -d api`) et un compte de test admin dans le `.env` (`K6_EMAIL`, `K6_PASSWORD`) : `docker compose --profile load run --rm k6`. Réglages : `-e VUS=… -e DURATION=… -e P95_MS=…`.

## Terraform

Le job `terraform` vérifie que le code de `infra/terraform/` est formaté (`terraform fmt -check -recursive`) et valide (`terraform init -backend=false` puis `terraform validate` sur `aws/`). Il n'utilise aucun identifiant AWS et ne lit pas le state. Trivy analyse en plus les fichiers Terraform (mauvaises configurations).

En local, avant de commiter : `terraform fmt -recursive` (dans `infra/terraform`), puis dans `aws/` : `terraform init -backend=false && terraform validate`.

Ce que la CI ne fait pas : `terraform plan` (il lit la production et demande un rôle AWS en lecture seule, distinct du rôle de déploiement) et `terraform apply` (toujours à la main, après relecture du plan : `infra/terraform/aws/README.md`).

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
| `terraform` : format | lancer `terraform fmt -recursive` dans `infra/terraform` et commiter le résultat |
| `sonar` : « Coverage on New Code » sous 80 % | ajouter des tests pour les lignes nouvelles ; les fichiers à compléter sont listés dans l'onglet *Code* de la PR |
| `sonar` : une anomalie de sécurité ou un point sensible | la corriger ; sinon, dans SonarQube Cloud, ouvrir l'anomalie, statut **Accept** avec un commentaire qui explique pourquoi (réservé aux administrateurs) ; relancer les jobs en échec |
| `sonar` : « Cannot resolve the file path … coverage » | la couverture n'est pas rattachée aux fichiers : vérifier que `prefix-coverage.py` a tourné (étape « Préparer la couverture pour Sonar ») |
| `sonar` : « You are running CI analysis while Automatic Analysis is enabled » | désactiver *Administration > Analysis Method > Automatic Analysis* dans le projet Sonar |
| `dast` : « Alerte ZAP haute » | ouvrir le rapport (artefact `zap-report`) et corriger ; si c'est un faux positif ou un risque accepté, ajouter la règle à `IGNORE` dans `infra/zap/rules.tsv` avec sa raison |
| `dast` : le scan sort en code 3 | ZAP n'a pas pu scanner (API injoignable, `/openapi.json` absent) : voir l'étape « Journaux de la pile » |
| `load` : seuil `http_req_duration` dépassé | une route a ralenti : la ligne en ✗ du résumé k6 dit laquelle ; comparer avec `main` avant de toucher au seuil |
| `load` : seuil `http_req_failed` ou `checks` | une route renvoie une erreur : voir l'étape « Journaux de la pile » |
| `ci-ok` rouge | ouvrir le job en échec : `ci-ok` ne fait que résumer les autres |

Les anomalies acceptées à ce jour : « dépendances sans empreintes » (`docker:S8544`) sur les Dockerfiles de `etl` et `ml`. Les versions sont figées par `pip-compile`, il manque seulement les empreintes (`--generate-hashes`).

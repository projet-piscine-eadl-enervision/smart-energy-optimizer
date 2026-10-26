# DevOps

Cette partie décrit la chaîne d'intégration et de livraison de la plateforme, de la modification d'une ligne de code au déploiement en production, avec ses contrôles de qualité et de sécurité. Elle se rattache aux compétences C16 à C20 (CI/CD), C23 (administration par scripts) et C24 (supervision) de la grille. Les références (#NNN) renvoient aux pull requests du dépôt, qui sont la trace du travail ; les commits de cette partie sont signés `Mushkhushu` et `Flavie` (même adresse). Les chiffres sont lus sur `main` à `fe0793b` et sur GitHub le 26/10/2026.

## Rôle et périmètre

Le DevOps couvre l'intégration continue, la livraison, la qualité et la sécurité de la chaîne, et les environnements de recette. Le compte AWS et la CI de déploiement en production relèvent de la partie Cloud ; les deux parties se rejoignent sur le déploiement. Le sujet rattache aussi la supervision à ce rôle : c'est l'écart principal (voir plus bas).

## Le cycle d'une modification (C16)

![Cycle d'une modification, de la branche à la production](cycle-modification.png)

*Figure 1 : du développement à la production, en dix étapes.*

Une modification suit toujours le même chemin. Elle naît dans une branche courte, créée depuis `main` : des hooks exécutés avant chaque commit appliquent les mêmes règles que la CI (convention de commits, nom de branche, `ruff`, détection de clés privées, refus de commiter sur `main`). La pull request est contrôlée par la CI, relue (une approbation, fils de discussion résolus) puis fusionnée en *squash* : son titre devient l'unique commit sur `main` et décide de la version (`feat`, `fix`, `!` pour une rupture). La fusion publie les images, que le staging récupère ; après la recette, une release manuelle promeut ces mêmes images vers la production.

## Les contrôles automatiques (C17, C18, C19)

![Contrôles d'une pull request](controles-pr.png)

*Figure 2 : les contrôles d'une pull request, résumés par `ci-ok`.*

Un job `changes` détermine les modules touchés par la PR (`api`, `etl`, `ml`, `frontend`, `db`, `infra/terraform`) : seuls ceux-là sont testés, ce qui garde la CI courte, et un changement dans `.github/`, les scripts d'infra ou les fichiers compose lance tout. Le job `ci-ok` résume tous les contrôles et reste le seul exigé par la règle de `main`, ce qui évite de modifier la règle à chaque nouveau contrôle.

**Tests automatisés (C17).** Chaque module Python passe `ruff` puis `pytest` avec couverture ; le frontend exécute ses tests et son build Angular. Sur `main`, la CI exécute 63 tests pour l'API, 125 pour l'ETL et 40 pour le ML, avec 99 % de couverture dans chaque cas, et 32 cas de test pour le frontend. Les tests d'intégration de l'ETL et du ML tournent sur une base TimescaleDB migrée, démarrée dans le job (#192) : sans elle, ces tests étaient ignorés et une requête SQL cassée passait la CI. Côté non fonctionnel, le job `migrations` applique les migrations deux fois sur une base vide (la seconde ne doit rien changer), vérifie qu'aucune migration déjà fusionnée n'est modifiée, et le collecteur de l'ETL comme les images exposent des sondes de santé. Les tests de bout en bout existent (Cypress) mais ne sont pas encore dans la CI.

**Sécurité intégrée (C18).** Trivy analyse les dépendances, les secrets, le Terraform et les Dockerfiles, et bloque la PR sur toute vulnérabilité haute ou critique pour laquelle un correctif existe, sur un secret ou sur une mauvaise configuration. Chaque image publiée est aussi scannée, avec un rapport dans l'onglet Security du dépôt, sans blocage pour l'instant. Chaque version joint le SBOM de ses images. L'action Trivy est épinglée sur un commit précis après la compromission de cette action en mars 2026, et Dependabot propose chaque lundi les mises à jour des actions, des paquets Python et npm et des images de base. Les preuves et les résultats sont dans le [rapport de sécurisation](../../rapport-securisation.md).

**Qualité du code (C19).** `ruff` couvre les modules Python, `commitlint` impose les commits conventionnels, et SonarQube Cloud applique une porte de qualité sur le code neuf : couverture d'au moins 80 %, notes A en fiabilité, sécurité et maintenabilité, doublons limités. Le frontend n'a pas encore de linter dédié (#148).

## Du staging à la production (C16)

![Environnements et circulation des images](environnements.png)

*Figure 3 : les environnements et ce qui circule entre eux.*

Après la fusion, une image par module (`frontend`, `api`, `etl`, `ml`, `db`) est publiée sur GHCR avec le tag `sha-<commit>` ; le tag `main` n'avance que si ce commit est encore la tête de `main`. Une image est reconstruite seulement si le dossier de son module a changé (clé : empreinte Git du dossier et semaine ISO, pour reprendre chaque semaine les mises à jour des images de base) ; l'image de l'API est toujours reconstruite car elle affiche le commit dans `/health`.

La VM de staging, hébergée par l'école, exécute `docker compose` avec ces images. Un minuteur systemd lance toutes les deux minutes un script qui récupère les fichiers compose de `main`, tire les nouvelles images et relance ce qui a changé, puis annonce à GitHub le commit qu'elle fait tourner (un déploiement « staging » visible dans l'onglet Deployments). La recette se fait sur ce commit.

![Release et retour arrière](release-et-retour-arriere.png)

*Figure 4 : la release manuelle, ses refus et le retour arrière.*

La release est lancée à la main. Sans commit saisi, elle prend le dernier commit annoncé par le staging. Elle refuse un commit que le staging n'a pas annoncé, dont la CI n'est pas verte, ou qui n'apporte ni `feat` ni `fix` depuis le dernier tag. Elle calcule la version à partir des commits conventionnels, crée le tag et la release GitHub, promeut les images (tag `vX.Y.Z`, SBOM joints) puis appelle le déploiement de la production. Celui-ci attend l'approbation de l'environnement GitHub `production`, vérifie que les images du tag sont publiées, puis exécute sur l'instance AWS, par Systems Manager, une sauvegarde compressée de la base (les cinq dernières sont gardées), la mise à jour des conteneurs et un test de santé. Le workflow contrôle enfin que `/health` annonce l'environnement `production` et le commit attendu. Aucune clé AWS durable n'est utilisée : le workflow échange un jeton OIDC contre un rôle limité à cette instance. Le déploiement est désactivé tant que la variable de dépôt `PRODUCTION_ENABLED` n'est pas à `true`, pour ne pas laisser de demande d'approbation en attente sans infrastructure. Le retour arrière relance ce même workflow à la main avec un tag déjà publié.

## L'administration par scripts (C23)

Les scripts d'exploitation sont versionnés dans `infra/scripts/` et testés par la CI (fichiers `test-*`) :

- `update-staging.sh`, avec son unité et son minuteur systemd, met à jour le staging ; `report-staging-deployment.sh` annonce le commit déployé à GitHub.
- `changed-modules.sh` trie les modules touchés ; `check-branch-name.sh` et `check-commit-messages.sh` appliquent les mêmes règles dans la CI et dans les hooks locaux.
- `compile-requirements.sh` régénère les dépendances Python figées ; `prefix-coverage.py` adapte les rapports de couverture à SonarQube.
- `install-tools.sh` installe l'outillage du poste (AWS CLI, Terraform, GitHub CLI) sans droits administrateur ; `setup-vm-roles.sh` crée les comptes de service de la VM.
- `sync-wiki.py` génère le wiki à partir de la documentation du dépôt.

## La supervision (C24)

Les sondes existent : `/health` publie la version, le commit et l'environnement ; les images `api`, `etl` et `frontend` ont un `HEALTHCHECK` Docker ; le collecteur de l'ETL écrit un signal de vivacité à chaque tour réussi, lu par une sonde qui le déclare `unhealthy` après trois intervalles sans tour ; le staging annonce ses déploiements à GitHub, et la production est contrôlée après chaque déploiement. Il n'y a en revanche ni collecte de métriques ni alerte (#150) : rien ne signale l'échec du minuteur de mise à jour du staging, qui se lit seulement dans le journal de l'unité systemd. L'évolution prévue est un export des métriques de l'hôte et des conteneurs vers Prometheus, un tableau Grafana (processeur, mémoire, disque, taux d'erreur, latence de `/health`) et une alerte sur l'échec du minuteur de mise à jour.

## La documentation (C20)

Les règles d'équipe sont dans `CONTRIBUTING.md` ; les procédures de bout en bout sont dans la [mise en production](../../mise-en-production.md), le [déploiement du staging](../../deploiement-staging.md), les [contrôles de la CI](../../qualite-et-securite-ci.md) et les [réglages GitHub](../../reglages-github.md). La documentation suit le code : chaque PR met à jour la sienne, et le wiki est généré depuis le dépôt à chaque fusion (#163) ; un contrôle de PR échoue si un document n'est pas rattaché au wiki.

## Évolutions

- **Fournisseur cloud.** Le premier squelette Terraform visait Azure (#60) ; il a été remplacé par AWS quand la production a changé de fournisseur (#79). La production est sur AWS et le staging sur la VM de l'école.
- **Releases.** Automatisées d'abord par une GitHub App (#23, #26, #30), puis manuelles avec retour arrière (#81), puis liées à ce que le staging a réellement déployé (#143).
- **CI.** Première CI (#3), fiabilisée (#96, #112), puis refonte avec modules touchés, SonarQube et annonce du staging (#143), et tests d'intégration sur base migrée (#192).
- **Incidents de la chaîne.** La publication des images était ignorée sur un push de `main`, parce que des contrôles réservés aux PR l'étaient aussi ; la condition du job commence désormais par `always()` (#164). Les PR de Dependabot échouaient à la CI ; le contrôle des messages de commit est exclu pour le robot et `typescript` ainsi que `@types/node` sont ignorés, car Angular fixe leur plage (#176).

## Limites et évolutions envisagées

- **Supervision** avec alertes (#150), voir plus haut.
- **Scan dynamique** de l'application, par exemple OWASP ZAP contre le staging (#149), et tests de charge.
- **Scan des images** publié mais non bloquant (#146) : il le devient une fois les deux alertes de l'image `db` assumées.
- **`terraform plan` en CI**, en lecture seule, avec un rôle AWS distinct du rôle de déploiement ; le job `terraform` contrôle aujourd'hui le format et la validité.
- **Comptes de connexion par module** pour la base (#145), **linter du frontend** (#148) et **tests de bout en bout** dans la CI.

L'[audit du dépôt](../../audit-depot.md) donne le détail de ces écarts.

*À compléter : enseignements et pistes d'amélioration retenus.*

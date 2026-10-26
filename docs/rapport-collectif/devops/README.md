# DevOps

Cette partie décrit la chaîne d'intégration et de livraison du projet, les choix qui l'ont façonnée, leurs évolutions et leurs limites. Les références (#NNN) renvoient aux pull requests du dépôt, qui sont la trace du travail. Les commits de cette partie sont signés `Mushkhushu` et `Flavie` (même adresse). Les chiffres sont lus dans l'historique de `main` et sur GitHub le 26/10/2026.

## Périmètre

Le DevOps couvre l'intégration continue, la livraison, la qualité et la sécurité de la chaîne, et les environnements de recette. Le compte AWS et la CI de déploiement en production relèvent de la partie Cloud ; les deux parties se rejoignent sur le déploiement. Le sujet rattache aussi la supervision à ce rôle : c'est l'écart principal (voir plus bas).

## Architecture de la chaîne

Une pull request déclenche des contrôles de forme (titre, nom de branche, commits conventionnels), puis les tests des seuls modules touchés : `ruff` et `pytest` avec couverture pour chaque module Python, tests et build du frontend, migrations de la base appliquées deux fois sur une base vide, format et validité du Terraform. Trivy analyse les dépendances, les secrets, le Terraform et les Dockerfiles, et SonarQube Cloud applique une porte de qualité (80 % de couverture sur le code neuf). Un seul contrôle, `ci-ok`, agrège tous les autres et reste le seul exigé par la règle de `main`.

Après la fusion, une image par module est publiée sur GHCR. La VM de staging les tire toutes les deux minutes et annonce à GitHub le commit qu'elle fait tourner. La release est manuelle : la version est calculée à partir des commits conventionnels, la release refuse un commit que le staging n'a pas annoncé ou qui n'apporte ni `feat` ni `fix` depuis le dernier tag, puis elle promeut la même image, sans reconstruction, avec son SBOM, et déploie la production par AWS Systems Manager après l'approbation de l'environnement `production`. Un retour arrière redéploie un tag déjà publié.

## Évolutions

- **Fournisseur cloud.** Le premier squelette Terraform visait Azure (#60) ; il a été remplacé par AWS quand la production a changé de fournisseur (#79). La production est sur AWS et le staging sur la VM de l'école, ce qui donne une architecture hybride.
- **Releases.** Elles ont d'abord été automatisées par une GitHub App (#23, #26, #30), puis remplacées par une release manuelle avec retour arrière (#81), et enfin liées à ce que le staging a réellement déployé (#143).
- **CI.** De la première CI (#3), fiabilisée ensuite (#96, #112), à la refonte de #143 : modules touchés, SonarQube, annonce du staging, release. Les tests d'intégration de l'ETL et du ML tournent depuis sur une base migrée (#192).
- **Incidents de la chaîne.** Sur un push de `main`, la publication des images était ignorée parce que des contrôles propres aux PR l'étaient aussi ; la condition du job commence désormais par `always()` (#164). Les PR de Dependabot échouaient à la CI : le contrôle des messages de commit est exclu pour le robot, et `typescript` et `@types/node` sont ignorés car Angular fixe leur plage (#176).

## Qualité et sécurité de la chaîne

Le durcissement de l'API, des images Docker et de la configuration (#141), la correction d'une CVE du frontend (#139), l'épinglage de l'action Trivy après la compromission de celle-ci et les mises à jour hebdomadaires de Dependabot forment la base. Les preuves, commande par commande, sont dans le [rapport de sécurisation](../../rapport-securisation.md) ; ce qui reste ouvert est dans l'[audit du dépôt](../../audit-depot.md) (#95, #199).

## Infrastructure et recette

Le Terraform de la production AWS est dans `infra/terraform/aws`. Le job `terraform` de la CI contrôle son format et sa validité, sans identifiants ni lecture du state ; le `plan` et l'`apply` restent manuels, depuis un poste, car le plan lit la production. Un plan lancé le 26/10 sur `main` ne propose aucune création, modification ni suppression. Côté staging : le service API et les variables (#68), la version et l'environnement dans `/health` (#76), les comptes de service de la VM (#124) et les migrations de la base avec dbmate (#106, #109).

## Documentation

La documentation suit le code : environnements techniques (#77), analyse de l'API Mock (#119) et un wiki généré depuis le dépôt à chaque fusion (#163). Le guide de la [mise en production](../../mise-en-production.md) et celui du [déploiement du staging](../../deploiement-staging.md) décrivent les procédures de bout en bout.

## Limites et évolutions envisagées

- **Supervision** : seules les sondes de santé existent (#150). L'évolution prévue est un export des métriques vers Prometheus et Grafana, avec une alerte sur l'arrêt du minuteur du staging.
- **Scan dynamique** de l'application, par exemple avec OWASP ZAP contre le staging (#149), et **tests de charge**.
- **Scan des images** publié mais non bloquant (#146) : il le devient une fois les deux alertes de l'image `db` assumées.
- **`terraform plan` en CI**, en lecture seule, avec un rôle AWS distinct du rôle de déploiement.
- **Comptes de connexion par module** pour la base (#145), **linter du frontend** (#148) et **tests de bout en bout** dans la CI.

## Travail en équipe

La partie DevOps a relu 25 PR des cinq autres parties, qui couvrent tous les modules : c'est le moyen par lequel les règles de la CI se sont diffusées dans l'équipe. Le module ML a reçu un appui pour son raccordement au staging et à son suivi (#183, #189, #198).

*À compléter : enseignements et pistes d'amélioration retenus.*

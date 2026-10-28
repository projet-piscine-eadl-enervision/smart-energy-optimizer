# Ressources

Schémas et captures de l'application et des outils, pris le 28/10/2026. Ils complètent les pages d'exploitation et de qualité.

## Schémas

### Cycle d'une modification

![Cycle d'une modification, de la branche à la production](rapport-collectif/devops/cycle-modification.png)

Dix étapes, de la branche courte à la production. Le retour arrière redéploie un tag déjà publié, sans repasser par les étapes 1 à 9.

### Contrôles d'une pull request

![Contrôles d'une pull request](rapport-collectif/devops/controles-pr.png)

Contrôles de forme, tests des modules touchés, sécurité et qualité, tous résumés par `ci-ok`, que la règle de `main` exige. Détail : [contrôles de la CI](qualite-et-securite-ci.md).

### Environnements et circulation des images

![Environnements et circulation des images](rapport-collectif/devops/environnements.png)

Du poste de développement à la production AWS en passant par GitHub et le staging. La production n'utilise aucun secret AWS de longue durée. Détail : [environnements techniques](environnements-techniques.md).

### Release et retour arrière

![Release et retour arrière](rapport-collectif/devops/release-et-retour-arriere.png)

Trois vérifications avant toute release (commit annoncé par le staging, CI verte, au moins un `feat` ou un `fix`), puis approbation et déploiement. Procédure : [mise en production](mise-en-production.md).

### Des données au modèle

![Des données au modèle, de l'ETL à MLflow](schema-flux-etl-ml.png)

Des sources de l'ETL aux expériences MLflow, avec les tables lues et écrites par le ML.

## Base de données

### Schémas, tables et clés

![Schémas, tables et clés](ressources/donnees-schemas-tables-cles.png)

Huit schémas, 21 tables et 5 vues du schéma `analytics`, issus des migrations dbmate au 28/10. Les couleurs distinguent les données brutes, les mesures, les référentiels, l'application et le ML. Les migrations sont décrites dans [migrations de la base](migrations-base-de-donnees.md).

### Modèle détaillé

![Modèle de données détaillé](ressources/donnees-modele-detaille.png)

Les mêmes schémas avec toutes les colonnes, les droits de chaque rôle de base (sans connexion) et les vues de suivi du modèle lues par Grafana et l'API.

### Contenu des schémas

![Schéma raw](ressources/dbeaver-raw.png)

`raw.api_response` conserve chaque réponse de l'API Mock avec son point d'accès, son état HTTP, la date de collecte et le contenu JSON, avant toute transformation.

![Schéma core](ressources/dbeaver-core.png)

Dans `core`, `sensor_status` garde les pannes de capteurs (site, capteur, début, fin prévue), à côté des mesures et des alertes.

![Schéma ref](ressources/dbeaver-ref.png)

Dans `ref`, les référentiels : ici les 23 recommandations types, rattachées à un type de site et à une règle de déclenchement (seuil, pic, plateau, chute, coupure, anomalie, capteur).

## Livraison et suivi

### CI

![Exécution de la CI sur main](ressources/ci-execution.png)

Une exécution complète de `ci.yml`. `changes` détecte les modules touchés, les contrôles utiles s'enchaînent, `ci-ok` regroupe le résultat exigé par la règle de `main`, puis `publish` construit les cinq images.

![Résultat des tests Cypress](ressources/ci-cypress.png)

Fin du job `e2e` : cinq fichiers de scénarios (garde d'authentification, tableau de bord, connexion, navigation, inscription), 26 tests passés en 18 secondes.

### Kanban

![Kanban de l'organisation](ressources/kanban.png)

Le projet « Kanban Enervision » de l'organisation, de Backlog à Done, avec une colonne Abandonned. Les cartes sont les tickets du dépôt, étiquetés par module.

![Vue exportée du Kanban](rapport-collectif/img.png)

Vue exportée du même Kanban, avec les filtres par personne et par étiquette (état au 28/10).

### SonarQube Cloud

![Synthèse SonarQube Cloud](ressources/sonarqube-synthese.png)

Synthèse du projet : porte de qualité passée, couverture de 96,2 % sur l'ensemble du code, 0 % de duplication, note de sécurité A, 13 problèmes de sécurité fermés sur 30 jours pour un délai de correction moyen de 2,5 jours.

![Risques de dépendances dans SonarQube Cloud](ressources/sonarqube-risques.png)

Vue « Dependency risks » d'une branche : chaque risque indique le paquet, la gravité, le score CVSS et le type de dépendance.

## Wiki

![Page Contribuer du wiki](ressources/wiki-contribuer.png)

Une page générée depuis `CONTRIBUTING.md`, avec son bandeau d'origine et la barre latérale par sections. Mécanisme : `docs/wiki-map.toml` et `infra/scripts/sync-wiki.py`.

## Supervision

![Dashboard Grafana du modèle ML](ressources/grafana-modele-ml.png)

Dashboard « Modèle ML » : état du modèle, délai depuis la dernière prévision, pénalités évitées sur 7 jours, version championne, contrôles de dérive par site et versions entraînées. Voir la [supervision](supervision-production.md).

## Application

### Tableau de bord

![Tableau de bord d'un site](ressources/front-tableau-de-bord.png)

Pour un site : prévision des 24 prochaines heures avec les pics en rouge, historique des mesures et recommandations chiffrées.

### Pics prévus

![Page des pics prévus](ressources/front-pics-prevus.png)

Les heures où la consommation prévue dépasse le seuil du site : synthèse en haut, une case par heure dans la vue d'ensemble, détail par jour en dessous.

### Alertes

![Page des alertes](ressources/front-alertes.png)

Alertes actives d'un site, classées par gravité (`medium`, `high`, `critical`), avec la valeur mesurée et le seuil.

## Cloud

### Console AWS

![Console AWS](ressources/aws-console.png)

Accueil de la console du compte de production : services utilisés (EC2, Systems Manager) et coût du mois en cours, dominé par le calcul EC2.

### Stockage S3

![Compartiments S3](ressources/aws-s3.png)

Deux compartiments en région Paris : les données de la production (remote DVC de production) et l'état Terraform. Voir [données et DVC](donnees-dvc.md).

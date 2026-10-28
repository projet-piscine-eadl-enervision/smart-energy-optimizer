# Ressources

Captures de l'application et des outils, prises le 28/10/2026. Elles complètent les pages d'exploitation et de qualité.

## Livraison et suivi

### CI

![Exécution de la CI sur main](ressources/ci-execution.png)

Une exécution complète de `ci.yml`. `changes` détecte les modules touchés, les contrôles utiles s'enchaînent, `ci-ok` regroupe le résultat exigé par la règle de `main`, puis `publish` construit les cinq images. Détail des jobs : [contrôles de la CI](qualite-et-securite-ci.md).

### Kanban

![Kanban de l'organisation](ressources/kanban.png)

Le projet « Kanban Enervision » de l'organisation, de Backlog à Done, avec une colonne Abandonned. Les cartes sont les tickets du dépôt, étiquetés par module.

### SonarQube Cloud

![Risques de dépendances dans SonarQube Cloud](ressources/sonarqube-risques.png)

Vue « Dependency risks » d'une branche : chaque risque indique le paquet, la gravité, le score CVSS et le type de dépendance. Règles et seuils : [contrôles de la CI](qualite-et-securite-ci.md).

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

Accueil de la console du compte de production : services utilisés (EC2, Systems Manager) et coût du mois en cours, dominé par le calcul EC2. Architecture : [environnements techniques](environnements-techniques.md).

### Stockage S3

![Compartiments S3](ressources/aws-s3.png)

Deux compartiments en région Paris : les données de la production (remote DVC de production) et l'état Terraform. Voir [données et DVC](donnees-dvc.md).

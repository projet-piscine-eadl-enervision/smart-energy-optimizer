# 5.1 DevOps

Chiffres lus sur `main` et sur GitHub le 26/10/2026. Le détail par compétence (cycle d'une modification, schémas, scripts, supervision) est dans [Compétences DevOps](competences.md).

## Livré

La chaîne qui mène une modification de la branche à la production est en place et automatisée. Des hooks locaux appliquent avant chaque commit les règles de la CI. La CI ne teste que les modules touchés et se résume en un contrôle unique, `ci-ok`, exigé par la règle de `main`. Elle exécute les tests de chaque module avec leur couverture, l'analyse de sécurité Trivy, qui bloque les vulnérabilités corrigeables et les secrets, et la porte de qualité SonarQube. Après la fusion, les images sont publiées sur GHCR et le staging de la VM de l'école les tire toutes les deux minutes, puis annonce à GitHub le commit qu'il fait tourner. La release est manuelle : elle refuse un commit que le staging n'a pas annoncé ou dont la CI n'est pas verte, calcule la version à partir des commits conventionnels et joint le SBOM des images. Le déploiement en production passe par un jeton OIDC (aucune clé AWS durable), une approbation, une sauvegarde de la base et un test de santé ; le retour arrière relance le même workflow avec un tag déjà publié. Les scripts d'exploitation sont versionnés et testés, et la documentation est publiée au wiki à chaque fusion. La sécurité de la chaîne est détaillée dans le [rapport de sécurisation](../../rapport-securisation.md) et l'[audit du dépôt](../../audit-depot.md).

## Problèmes résolus

- La publication des images était ignorée sur un push de `main`, parce que des contrôles réservés aux pull requests l'étaient aussi : la condition du job commence désormais par `always()` (#164).
- Les pull requests de Dependabot échouaient à la CI : le contrôle des messages de commit est exclu pour le robot et deux paquets dont Angular fixe la plage sont ignorés (#176).
- Les tests d'intégration de l'ETL et du ML étaient ignorés sans base de données, et une requête SQL cassée passait la CI : une base TimescaleDB migrée est maintenant démarrée dans le job (#192).
- Le premier squelette Terraform visait Azure (#60) ; il a été remplacé par AWS quand la production a changé de fournisseur (#79).

## Non livré, et pourquoi

- **Supervision, livrée en partie.** Prometheus et Grafana sont livrés (#202) : métriques de l'hôte, des conteneurs, de la base, de l'API et de l'ETL, quatre dashboards versionnés et des règles d'alerte testées avec `promtool`. La supervision est active au staging et en production (#213). Alertmanager envoie les alertes dans un canal Teams, y compris l'échec, l'arrêt ou le retard des minuteurs systemd (#221). Le modèle n'est pas dans Grafana : sa dérive est calculée chaque jour par le module ML (`ml.drift_metric`, expérience MLflow `enervision-monitoring`).
- **Scan dynamique** de l'application (#149), **scan des images non bloquant** (#146), **linter du frontend** (#148) et **`terraform plan`** en CI : repoussés après les livrables fonctionnels.

## Outils

GitHub Actions, Docker Compose, GHCR, systemd, Terraform et AWS (Systems Manager, OIDC), SonarQube Cloud, Trivy, Dependabot, pre-commit, commitlint, ruff.

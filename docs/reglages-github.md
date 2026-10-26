# Réglages GitHub et SonarQube Cloud

État des réglages qui ne sont pas dans le code, relevé par l'API GitHub le 24/10/2026. Il sert de référence quand un réglage change ou qu'un comportement surprend. Les règles de travail sont dans [`CONTRIBUTING.md`](../CONTRIBUTING.md).

Les réglages se modifient dans *Settings* du dépôt, par un administrateur. Après un changement, relire l'état avec les commandes de la dernière section et mettre ce document à jour.

## Dépôt

| Réglage | Valeur |
|---|---|
| Visibilité | publique |
| Branche par défaut | `main` |
| Méthodes de merge | **squash seulement** (merge commit et rebase désactivés) ; titre du commit = titre de la PR, message vide |
| Supprimer la branche après le merge | oui |
| « Always suggest updating pull request branches » | non (le bouton *Update branch* reste proposé quand la règle de `main` exige une branche à jour) |
| Auto-merge | non |
| Issues, Projects, Wiki | activés ; modèles d'issue `bug` et `tache`, modèle de PR dans `.github/` |

## Règle de `main`

Un *ruleset* actif sur `main`, plus la protection de branche classique :

- **toute modification passe par une PR** ; une approbation au moins, donnée par une autre personne que l'auteur ; les conversations de revue doivent être résolues ; l'approbation n'est pas retirée par un nouveau push ;
- **un seul contrôle obligatoire : `ci-ok`**, qui résume tous les autres (tests, Trivy, Sonar, migrations, titre de PR, nom de branche, messages de commit) ; la branche doit être **à jour avec `main`** avant le merge ;
- pas de force push, pas de suppression de `main`, merge en squash seulement ;
- les administrateurs sont soumis à la règle ; seule l'application GitHub `enervision-release` peut la contourner, par PR.

## Sécurité

| Réglage | État |
|---|---|
| Signalement privé de vulnérabilités (politique : [`SECURITY.md`](../SECURITY.md)) | activé |
| Alertes Dependabot | activées |
| Mises à jour de sécurité Dependabot | activées |
| Mises à jour de version Dependabot | `.github/dependabot.yml` : actions, pip (`api`, `etl`, `ml`), npm (`frontend`) et images Docker, une PR groupée par type le lundi |
| Secret scanning et protection au push | activés (motifs non fournisseurs et validité des secrets : désactivés) |
| Analyse des images et du code | Trivy dans la CI ; rapport des images dans *Security > Code scanning* ([`qualite-et-securite-ci.md`](qualite-et-securite-ci.md)) |

## Actions

| Réglage | Valeur |
|---|---|
| Actions autorisées | toutes |
| Permissions par défaut du `GITHUB_TOKEN` | lecture seule ; chaque workflow déclare ce dont il a besoin |
| Actions autorisées à créer et approuver des PR | non |
| Workflows des PR de contributeurs externes | approbation exigée pour **tous** les contributeurs externes |

## Environnements

| | `staging` | `production` |
|---|---|---|
| Relecteurs requis | aucun | l'équipe (six personnes) ; l'auteur peut approuver lui-même |
| Branches et tags autorisés | `main` | `main` et `v*` |
| Variables | aucune | `AWS_REGION`, `AWS_DEPLOY_ROLE_ARN`, `AWS_INSTANCE_ID` |
| Rôle | reçoit les déploiements que la VM de staging annonce | attend l'approbation avant le déploiement AWS ; le rôle IAM de déploiement n'accepte que les jobs de cet environnement |

## Secrets et variables

| Nom | Portée | Rôle |
|---|---|---|
| `SONAR_TOKEN` | secret du dépôt | analyse SonarQube Cloud, utilisé par le job `sonar` |
| `PRODUCTION_ENABLED` | variable du dépôt (`true`) | active le déploiement en production |
| `RELEASE_APP_PRIVATE_KEY`, `RELEASE_APP_ID` | secret et variable de l'organisation | clé de l'application `enervision-release` ; la release ne s'en sert plus (elle enchaîne elle-même promotion et déploiement), à retirer si l'application ne sert plus |

Aucun secret AWS : le déploiement passe par un jeton OIDC. Les jetons de la VM de staging et de l'instance sont décrits dans [`deploiement-staging.md`](deploiement-staging.md) et [`infra/README.md`](../infra/README.md).

## Applications installées

`enervision-release` (contournement de la règle de `main` par PR, plus utilisée par la release), `sonarqubecloud` (analyse et décoration des PR), `claude`.

## SonarQube Cloud

- Organisation `projet-piscine-eadl-enervision`, projet `projet-piscine-eadl-enervision_smart-energy-optimizer`, visibilité publique ; connexion avec le compte GitHub.
- **Analyse automatique désactivée** : seule l'analyse de la CI compte.
- Porte de qualité **`EnerVision`** (copie de « Sonar way », par défaut) : couverture du code neuf à 80 % au moins, notes A en fiabilité, sécurité et maintenabilité, doublons sous 3 %, points sensibles revus à 100 %. Elle se règle dans *Organization > Quality Gates*.
- Code neuf d'une PR : les lignes modifiées par rapport à sa branche cible. Pour `main` : « Previous version ».
- Les administrateurs de l'organisation acceptent les anomalies (voir [`qualite-et-securite-ci.md`](qualite-et-securite-ci.md)).

## Relire l'état

```bash
R=projet-piscine-eadl-enervision/smart-energy-optimizer
gh api repos/$R --jq '{allow_squash_merge, allow_merge_commit, delete_branch_on_merge, allow_update_branch}'
gh api repos/$R --jq '.security_and_analysis'
gh api repos/$R/private-vulnerability-reporting --jq .enabled
gh api repos/$R/actions/permissions/workflow
gh api repos/$R/actions/permissions/fork-pr-contributor-approval
gh api repos/$R/rulesets/$(gh api repos/$R/rulesets --jq '.[0].id')
gh api repos/$R/environments --jq '.environments[].name'
gh api repos/$R/actions/secrets --jq '[.secrets[].name]'
```

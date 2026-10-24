# Politique Git

Le projet suit un GitHub Flow avec des branches courtes. Le dépôt est un monorepo.

## Structure

```
api/        API (données, prédictions, anomalies) et ses tests (api/tests)
etl/        batch d'ingestion et nettoyage en pandas, tests (etl/tests)
ml/         entraînement, challengers, MLflow, tests (ml/tests)
frontend/   dashboard web, tests Cypress (frontend/cypress)
db/         migrations SQL de la base (db/migrations), appliquées au démarrage par dbmate
infra/      Terraform, Docker, scripts de déploiement (infra/scripts)
docs/       architecture, rapports de décision, comptes rendus
.github/    workflows CI/CD et gabarit de PR
```

Chaque composant garde ses tests. Les workflows de CI/CD vivent dans `.github/workflows/`, seul emplacement lu par GitHub Actions.

## Règles

1. `main` est toujours déployable. Aucun push direct : tout passe par une pull request.
2. Une branche par tâche, créée depuis `main` à jour, nommée directement par son sujet, sans préfixe ni `/` : minuscules et tirets, 50 caractères maximum (ex. `endpoint-readings`, `ci-trivy`). Durée de vie visée : moins d'un jour, deux au maximum.
3. Pull requests petites et ciblées, liées à une issue GitHub : `Closes #12` dans la description ferme l'issue au merge et déplace sa carte dans le Project. Une PR sans issue est tolérée pour une correction triviale.
4. Une approbation minimum, donnée par quelqu'un d'autre que l'auteur, et une CI verte avant le merge. Chacun relit au moins une PR par jour.
5. Merge en **squash**, seule méthode autorisée sur le dépôt (réglages du dépôt : merge commit et rebase désactivés, message du squash = titre de la PR). Le titre de la PR devient donc l'unique commit sur `main` : c'est lui qui décide de la version (`feat:`, `fix:`, `!` pour une rupture), et la CI le vérifie. La branche source est supprimée automatiquement au merge (réglage « Automatically delete head branches ») ; supprimer aussi la copie locale avec `git branch -d`.
6. Commits en [Conventional Commits](https://www.conventionalcommits.org/fr) avec un type parmi `feat`, `fix`, `docs`, `chore`, `infra`, `test`, `refactor`, `ci`. Le nom de branche, chaque commit et le titre de la PR sont vérifiés par la CI ; un hook local (`pre-commit`, voir le README) applique les mêmes contrôles avant le commit. Chacun commite avec son propre compte et son vrai nom, sur son poste.
7. Aucun secret dans Git : variables dans un `.env` ignoré, avec un `.env.example` versionné. Les accès (API, VM, AWS) restent hors dépôt.
8. Un conflit se résout dans la branche de la tâche (`git rebase main` ou `git merge main`), jamais en réécrivant `main`.

## Cycle d'une tâche

Une seule fois par clone, avant le premier commit : installer les hooks locaux (`pre-commit install`, étape 7 du [README](README.md)).

```
git switch main && git pull
git switch -c ma-tache
# ... travail, commits fréquents
git push -u origin ma-tache
# ouvrir la PR, demander une revue, corriger, squash merge
```

## Migrations de la base

Toute modification de la base (table, colonne, index, agrégat, données de référence) est un fichier SQL de `db/migrations/`, jamais une commande lancée à la main. Il s'applique tout seul au démarrage de la pile. Détail, création d'une migration et cas particuliers dans [`docs/migrations-base-de-donnees.md`](docs/migrations-base-de-donnees.md). Les règles :

- Nom `AAAAMMJJHHMMSS_sujet.sql` (heure de création du fichier), avec les blocs `-- migrate:up` et `-- migrate:down` (ce dernier peut rester vide).
- Une migration fusionnée ne se modifie, ne se renomme et ne se supprime jamais : on en ajoute une nouvelle. La CI refuse la PR sinon.
- On corrige en avant, il n'y a pas de retour arrière automatique. Chaque migration doit rester compatible avec la version précédente du code, car un retour arrière du staging relance l'ancienne image sur la base déjà migrée.
- Aucun mot de passe ni secret dans une migration (les rôles de connexion se créent hors dépôt).

## Revues

Relire, c'est vérifier que le code répond au ticket, qu'il est testé, lisible et sans secret. Les remarques se font dans la PR. L'auteur répond ou corrige, le reviewer approuve quand tout est réglé. Le rôle tournant (PO, Tech Lead, etc.) ne dispense personne de relire.

## Versions, tags et promotion

**Versionnage.** Une seule version pour tout le monorepo, en [SemVer](https://semver.org/lang/fr/) : `vMAJOR.MINOR.PATCH`. Les tags ne sont posés que sur `main`.

- `feat:` incrémente le MINOR, `fix:` le PATCH, un `!` après le type (`feat!:`) ou un pied `BREAKING CHANGE:` le MAJOR.
- Les commits `docs:`, `chore:`, `ci:`, `test:`, `refactor:` et `infra:` seuls ne donnent pas de version : il faut au moins un `feat:` ou un `fix:` depuis le dernier tag.
- Il n'y a pas de PR de release : la version est calculée au moment où une personne lance la release, sur le commit qu'elle a recetté.

**Promotion.** On construit une fois et on promeut le même artefact, sans le reconstruire : le merge sur `main` met à jour le staging, la release ajoute le tag de version à l'image déjà recettée, et la production déploie cette image. La procédure complète (recette, release, approbation, retour arrière) est dans [`docs/mise-en-production.md`](docs/mise-en-production.md).

**Modèles ML.** Dans MLflow, un modèle entraîné devient `challenger`. Il est promu `champion` (alias utilisé par `/predict` en production) seulement s'il bat le champion actuel sur les métriques de validation. La promotion est tracée dans le registre et mentionnée dans la PR ou le rapport de décision.

## Workflows : runners et actions

- Les jobs tournent sur `ubuntu-24.04`, pas sur `ubuntu-latest`, dont la version change sans prévenir. Changer de version de runner se fait par une PR, dans tous les workflows à la fois.
- Les actions sont référencées par version majeure (`actions/checkout@v7`), ou par SHA quand l'action est sensible (`trivy-action`, `configure-aws-credentials`), avec la version en commentaire à côté du SHA.
- Dependabot ouvre chaque lundi des PR groupées : `ci: bump ...` (actions), `chore: bump ...` pour les dépendances Python (`api`, `etl`, `ml`), npm (`frontend`) et les images de base des Dockerfile. Python 3.13 et Node 24 ne montent pas de version tout seuls. Les relire comme les autres : lire les notes de version pour les ruptures, vérifier que les paramètres `with:` utilisés existent toujours, et surveiller les avertissements Node dans les runs.
- Pour Python, Dependabot modifie `requirements.in` et `requirements.txt`. Après le merge, `./infra/scripts/compile-requirements.sh` ne doit produire aucun changement ; sinon, lancer le script et committer le résultat.

**Avertissements connus.**

- `trivy-action` reste volontairement en **v0.35.0** (SHA `57a97c7e7821a5776cebc9bb87c984fa69cba8f1`), la version sûre retenue après l'avis CVE-2026-33634. Son `actions/cache` interne tourne encore sur Node 20 : le job `security` de la CI affiche donc un avertissement de dépréciation de Node 20. Il est connu et accepté. La v0.36.0 (SHA `ed142fd0673e97e23eac54620cfb913e5ce36c25`) embarque un `actions/cache` en Node 24 et le fait disparaître : on y passera quand l'équipe aura décidé de s'écarter de la version épinglée. Dependabot ignore cette action pour cette raison.
- `actions/create-github-app-token` est en v3 avec l'entrée `app-id`, dépréciée au profit de `client-id` : le job de release affiche une annotation de dépréciation. `client-id` attend le Client ID de l'App GitHub (pas son identifiant numérique) dans une nouvelle variable de dépôt ; sans elle, le job retomberait sur `GITHUB_TOKEN` et les tags ne déclencheraient plus le déploiement. Le changement reste à faire, après création de la variable.

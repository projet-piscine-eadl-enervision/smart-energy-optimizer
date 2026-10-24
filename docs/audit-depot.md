# Audit du dépôt, état au 24/10/2026

Base : `main` à `89c7ab7` (v1.14.0, PR #97 et #134 fusionnées) plus la branche `durcissement-securite`. Mesures du 24/10 : réglages GitHub par l'API, `pip-audit`, `npm audit`, relecture du code, de Terraform et des workflows.

Légende : **P1** avant tout, **P2** bientôt, **P3** confort. **[branche]** : corrigé seulement dans `durcissement-securite`, donc encore ouvert sur `main` tant qu'elle n'est pas fusionnée.

## Ouvert

### P1

- **Signalement privé, secret scanning et protection au push désactivés** (Settings > Security). Le `SECURITY.md` [branche] renvoie vers un signalement qui n'existe pas encore. À activer par un propriétaire.
- **Aucun test ML, et la CI l'accepte.** `ml/tests` est vide et `pytest || [ $? -eq 5 ]` (`ci.yml:101`) tolère « aucun test collecté ». Ajouter un test minimal, retirer la tolérance, poser un seuil `--cov-fail-under`.

### P2

- **Les rôles de #134 ne sont pas utilisés.** `api` et `etl` se connectent avec `${POSTGRES_USER}`, le super-utilisateur (`docker-compose.staging.yml:32,42`). Créer trois comptes de connexion héritant de `enervision_api`, `enervision_etl`, `enervision_ml` et les donner aux services.
- **`python-jose` : 3 alertes `pip-audit`** (`python-jose` 3.5.0 PYSEC-2026-4298, `ecdsa` 0.19.2 PYSEC-2026-1325, sans correctif). Remplacer par `PyJWT` dans `app/core/security.py`.
- **`body-parser` (haute, déni de service)** dans le frontend, dépendance indirecte vue par `npm audit --omit=dev` : `npm audit fix`.
- **Dependabot ne couvre que `github-actions`.** Ajouter `pip` (`api`, `etl`, `ml`), `npm` et `docker`, et activer les mises à jour de sécurité (désactivées).
- **Bucket S3 de production sans protection des données.** Il porte le remote DVC `prod`, mais `force_destroy = true` et pas de versionnement : un `terraform destroy` ou une écrasure efface la référence. Activer `aws_s3_bucket_versioning`.
- **`/docs` et `/openapi.json` ouverts en production** (pas de `docs_url=None`), et `/health` publie le titre du commit et le sha. Couper la documentation hors développement.
- **`/auth/register` ouvert à tous, `/auth/login` sans limite d'essais.** À trancher : inscription fermée ou limitation de débit.
- **Release déclarative.** La case « staging vérifié » de `release.yml` n'est vérifiée par rien, et la personne qui tague peut déployer seule en production. À présenter comme un choix assumé.
- **Retour arrière du staging** : corrigé dans le script, testé seulement sur des dépôts jetables. À essayer sur la VM.
- **Aucune alerte** si le minuteur de mise à jour du staging échoue.

### P3

- **Mot de passe de plus de 72 octets : erreur 500** à l'inscription (bcrypt lève `ValueError`, mesuré). Ajouter `max_length=72` à `UserCreate`.
- **Énumération de comptes** : `/auth/register` répond 409 sur un e-mail connu, `/auth/login` saute `verify_password` quand le compte n'existe pas.
- **Ports inutiles** : `8001:8000` (ETL) en staging ; PostgreSQL de développement lié à toutes les interfaces avec le mot de passe `dev` (`docker-compose.yml:10`), le lier à `127.0.0.1`.
- **Trivy ne scanne pas les images construites.** Les actions sont épinglées par tag, sauf Trivy et `configure-aws-credentials` (sha).
- **Job `e2e` (Cypress) inutile** : le front teste avec Vitest. Supprimer le job et son entrée dans `needs` de `ci-ok`.
- **`httpx2` : licence vide sur PyPI.** À vérifier avant le rendu.
- **Fichiers `*:Zone.Identifier`** créés par les copies depuis Windows : ajouter `*:Zone.Identifier` au `.gitignore`.
- **Sondes `api` et `frontend`** [branche] jamais observées `healthy` : les conteneurs en cours datent d'avant la branche. À vérifier avec la pile reconstruite.
- **Pas de seuil de couverture global** dans la CI.

## Traité

- **Publication d'images depuis un fork** : `event == 'push'` et même dépôt exigés. Reste la politique d'approbation des workflows externes (`first_time_contributors`).
- **Course sur `:main`** : `:main` n'avance que si le commit est la tête de `main` ; `sha-<commit>` est toujours publiée.
- **Annulation de la CI sur `main`** : un groupe de concurrence par commit, seules les PR annulent.
- **Retour arrière du staging** : `update-staging.sh` ramène le compose au commit figé.
- **Dépendances de test figées** : `requirements-dev.in` et `.txt` pour `api`, `etl`, `ml`.
- **Hooks `pre-commit`** : messages de commit, nom de branche, `ruff`, clés privées, commit direct sur `main`.
- **API authentifiée** (PR #102) : JWT sur `/history`, `/predictions`, `/recommendations`, `/auth/me`.
- **Tests sur `main`** : API et ETL (79 tests ETL, couverture 99 %).
- **Pilote de base de l'API** : `asyncpg` et `sqlalchemy` présents.
- **ETL** (PR #97) : client aligné sur l'API, dossier `mock_client`, `/health` seule, sonde Docker `healthy`, plus de Swagger.
- **Base** (PR #134) : tables, hypertable, rôles, `analytics.refresh_site_baseline()` ; dix migrations rejouées sans erreur. Reste le chargeur de l'ETL.
- **Données** : DVC avec remotes `preprod` et `prod`, vérifiés de bout en bout.
- **Historique Git** : aucun `.env`, `tfvars`, `backend.hcl`, clé ni `tfstate` jamais ajouté ; aucun secret dans les fichiers suivis.
- **Branche `main` protégée** : revue obligatoire, `ci-ok` requis, ni force push ni suppression, administrateurs inclus.
- **Nettoyage du dépôt** : manifeste et changelog figés, doublons de `.env.example`, `.gitkeep` et `.prettierrc.json` superflus.
- **[branche]** `SECURITY.md`, `.dockerignore` de `api` et du frontend, `HEALTHCHECK` d'`api` et du frontend, port du job `e2e`.

## Assumé ou écarté

- **Port 8000 du staging publié** : la recette lit le sha sur `:8000/health`, la VM n'est joignable que depuis le réseau de l'école.
- **`docker-compose.staging.yml` gardé tel quel** : `deploy-production.yml` le nomme en dur, un retour vers un ancien tag échouerait après un renommage.
- **Production : auto-approbation et contournement par les administrateurs** : choix d'équipe.
- **S3 en SSE-S3 et non KMS** : coût et gestion de clé injustifiés pour un projet de deux semaines.
- **Sortie 80/443 vers `0.0.0.0/0`** : les adresses de GHCR et de SSM ne sont pas énumérables.
- **Pas de `HEALTHCHECK` sur `ml`** : ce n'est pas un service.

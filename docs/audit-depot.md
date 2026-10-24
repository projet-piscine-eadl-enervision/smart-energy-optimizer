# Audit du dépôt, état au 24/10/2026

Base : `main` à `89c7ab7` (v1.14.0, PR #97 et #134 fusionnées), avec les corrections de la PR « sécurité ». Mesures du 24/10 : réglages GitHub par l'API, `pip-audit`, `npm audit`, relecture du code, de Terraform et des workflows.

Légende : **P1** avant tout, **P2** bientôt, **P3** confort.

## Ouvert

### P1

- **Aucun test ML, et la CI l'accepte.** `ml/tests` est vide et `pytest || [ $? -eq 5 ]` (`ci.yml:101`) tolère « aucun test collecté ». Ajouter un test minimal, retirer la tolérance, poser un seuil `--cov-fail-under`.

### P2

- **Les rôles de #134 ne sont pas utilisés.** `api` et `etl` se connectent avec `${POSTGRES_USER}`, le super-utilisateur (`docker-compose.staging.yml:32,42`). Créer trois comptes de connexion héritant de `enervision_api`, `enervision_etl`, `enervision_ml` et les donner aux services.
- **`/health` publie le titre du commit et le sha**, y compris en production (le workflow de déploiement s'en sert). À assumer ou à réduire.
- **`/auth/register` ouvert à tous, `/auth/login` sans limite d'essais.** À trancher : inscription fermée ou limitation de débit.
- **Release déclarative.** La case « staging vérifié » de `release.yml` n'est vérifiée par rien, et la personne qui tague peut déployer seule en production. À présenter comme un choix assumé.
- **Retour arrière du staging** : corrigé dans le script, testé seulement sur des dépôts jetables. À essayer sur la VM.
- **Aucune alerte** si le minuteur de mise à jour du staging échoue.

### P3

- **Énumération de comptes à l'inscription** : `/auth/register` répond 409 sur un e-mail connu, lié à la décision sur l'inscription ouverte.
- **Trivy ne scanne pas les images construites.** Les actions sont épinglées par tag, sauf Trivy et `configure-aws-credentials` (sha).
- **Pas de tests de bout en bout du frontend.** Le job `e2e` (Cypress) a été supprimé : il ne faisait rien (aucune configuration, aucune dépendance). Le front n'a que des tests Vitest (un seul fichier aujourd'hui). À créer : un test de fumée sur le staging (connexion, puis lecture de `/health` par le proxy `/api`), avec Playwright ou Cypress.
- **`httpx2` : licence vide sur PyPI.** À vérifier avant le rendu.
- **Pas de seuil de couverture global** dans la CI.
- **Longueur de `SECRET_KEY` non imposée** : `PyJWT` avertit sous 32 octets, mais l'API démarre quand même. 64 caractères en staging (vérifié le 24/10) ; la production est à vérifier.

## Traité

- **Publication d'images depuis un fork** : `event == 'push'` et même dépôt exigés. Politique d'approbation passée à `all_external_contributors` (24/10).
- **Course sur `:main`** : `:main` n'avance que si le commit est la tête de `main` ; `sha-<commit>` est toujours publiée.
- **Annulation de la CI sur `main`** : un groupe de concurrence par commit, seules les PR annulent.
- **Retour arrière du staging** : `update-staging.sh` ramène le compose au commit figé.
- **Dépendances de test figées** : `requirements-dev.in` et `.txt` pour `api`, `etl`, `ml`.
- **Hooks `pre-commit`** : messages de commit, nom de branche, `ruff`, clés privées, commit direct sur `main`.
- **API authentifiée** (PR #102) : JWT sur `/history`, `/predictions`, `/recommendations`, `/auth/me`.
- **Tests sur `main`** : API et ETL (79 tests ETL, couverture 99 %).
- **`python-jose` remplacé par `PyJWT`** : `pip-audit` ne trouve plus rien sur l'API.
- **`/docs`, `/redoc` et `/openapi.json` fermés en production** (`APP_ENV=production`), ouverts en dev et staging.
- **Mot de passe de plus de 72 octets** : refusé à l'inscription (422, compté en octets) et à la connexion (401) au lieu d'une erreur 500.
- **Connexion à durée égale** : un bcrypt est toujours calculé, compte connu ou non.
- **Dépendances du frontend** : `npm audit fix` (`body-parser`, `fast-uri`), 0 alerte sur les dépendances de production ; lint, test et build repassés.
- **Ports** : l'ETL du staging ne publie plus le 8001 (batch, sonde Docker) ; PostgreSQL de développement lié à `127.0.0.1`.
- **Images `api`, `etl`, `ml`** : `pip` retiré après l'installation (ses copies embarquées de `certifi`, `urllib3`, `msgpack` causaient 1 critique et 4 hautes) ; Trivy ne trouve plus aucune alerte haute ou critique corrigeable ; `api` et `etl` repassent `healthy`.
- **Image `frontend` (cible `prod`)** : `npm`, `corepack` et `yarn` retirés (leurs `brace-expansion` et `undici` causaient 4 alertes hautes) ; Trivy ne trouve plus rien, l'image reste `healthy` et sert `/` en 200. La cible `dev` (locale, non publiée) garde 5 alertes hautes, dont `vite`.
- **Réglages GitHub (24/10, vérifiés par l'API)** : signalement privé de vulnérabilités, alertes Dependabot, mises à jour de sécurité, secret scanning et protection au push activés ; approbation des workflows de tous les contributeurs externes ; Actions ne peut plus créer ni approuver de PR ; environnement `staging` créé (branche `main`).
- **Dependabot étendu** à `pip` (`api`, `etl`, `ml`), `npm` et `docker`, une PR groupée par type le lundi (actif après le merge sur `main`).
- **Pilote de base de l'API** : `asyncpg` et `sqlalchemy` présents.
- **ETL** (PR #97) : client aligné sur l'API, dossier `mock_client`, `/health` seule, sonde Docker `healthy`, plus de Swagger.
- **Base** (PR #134) : tables, hypertable, rôles, `analytics.refresh_site_baseline()` ; dix migrations rejouées sans erreur. Reste le chargeur de l'ETL.
- **Données** : DVC avec remotes `preprod` et `prod`, vérifiés de bout en bout.
- **Historique Git** : aucun `.env`, `tfvars`, `backend.hcl`, clé ni `tfstate` jamais ajouté ; une recherche de motifs de clés (AWS, GitHub, clés privées) dans les fichiers suivis ne trouve rien. Le secret scanning de GitHub prend le relais.
- **Branche `main` protégée** : revue obligatoire, `ci-ok` requis, ni force push ni suppression, administrateurs inclus. Seule l'App `enervision-release` peut contourner la règle, et seulement par PR.
- **Nettoyage du dépôt** : manifeste et changelog figés, doublons de `.env.example`, `.gitkeep` et `.prettierrc.json` superflus.
- **Politique et configuration du dépôt** : `SECURITY.md` ajouté, `.dockerignore` de `api` et du frontend complétés, `HEALTHCHECK` d'`api` et du frontend (images reconstruites le 24/10 : les deux `healthy`), job `e2e` inactif supprimé, `*:Zone.Identifier` ignorés.

## Assumé ou écarté

- **Port 8000 du staging publié** : la recette lit le sha sur `:8000/health`, la VM n'est joignable que depuis le réseau de l'école.
- **`docker-compose.staging.yml` gardé tel quel** : `deploy-production.yml` le nomme en dur, un retour vers un ancien tag échouerait après un renommage.
- **Production : auto-approbation et contournement par les administrateurs** : choix d'équipe.
- **Bucket S3 sans versionnement et avec `force_destroy`** : le projet dure deux semaines, tout est coupé ensuite.
- **S3 en SSE-S3 et non KMS** : coût et gestion de clé injustifiés pour un projet de deux semaines.
- **Sortie 80/443 vers `0.0.0.0/0`** : les adresses de GHCR et de SSM ne sont pas énumérables.
- **`vite` (haute) dans `@angular/build`**, outil de développement seulement (serveur local, option propre à Windows) : le correctif demande `npm audit fix --force`, donc une montée de version majeure ; attendu avec la prochaine mise à jour d'Angular.
- **Image `db` : 2 alertes hautes (Trivy)**, dans le binaire de dbmate (bibliothèque Go `klauspost/compress` 1.18.5, `stdlib` 1.27.2). dbmate 2.37.0 est la dernière version (18/10) : pas de correctif possible chez nous. L'outil ne tourne qu'une fois au déploiement, sans port ouvert. À reprendre à la prochaine version de dbmate ; entrée de `.trivyignore` avec motif et échéance quand Trivy deviendra bloquant.
- **Pas de `HEALTHCHECK` sur `ml`** : ce n'est pas un service.

# Environnements techniques

Ce document décrit les trois environnements d'EnerVision (poste de développement, staging, production), leurs URLs, l'API Mock fournie par l'école et les variables qui les distinguent.

Documents liés : [déploiement du staging](deploiement-staging.md), [mise en production et release](mise-en-production.md), [infrastructure AWS](../infra/terraform/aws/README.md) et [vue d'ensemble de l'infrastructure](../infra/README.md).

## 1. Vue d'ensemble

| | dev | staging | production |
|---|---|---|---|
| Où | poste de chaque membre (WSL2 Debian + Docker Desktop) | VM Proxmox de l'école, `10.43.43.50` (nom de machine `ml-stagiaire-01`, conteneur LXC Debian 13) | AWS `eu-west-3` (Paris), instance EC2 `enervision-production` (`t3.large`, Debian 13, disque chiffré de 64 Go) |
| Compose | `docker-compose.yml` | `docker-compose.staging.yml` | le même `docker-compose.staging.yml`, avec `/etc/enervision/production.env` |
| Mise à jour | `docker compose up -d` à la main | automatique : un minuteur de la VM tire les images GHCR toutes les 2 minutes, puis annonce le déploiement à GitHub | workflow Release lancé à la main après la recette du staging, approbation de l'environnement `production`, déploiement par AWS Systems Manager ([procédure](mise-en-production.md)) |
| Origine des images | construites localement (`build:`) | publiées par la CI sur GHCR (tags `main` et `sha-<commit>`) | les mêmes images que le staging, promues par le tag de version `vX.Y.Z`, sans reconstruction |
| Administration | le poste | SSH depuis le réseau de l'école | AWS Session Manager (pas de SSH) |
| `APP_ENV` | `dev` | `staging` | `production` |
| Mock utilisé | interne ou public, au choix | interne | public (l'instance n'atteint pas le réseau de l'école) |
| État | opérationnel | opérationnel : `db`, `api`, `etl` et `frontend` (`ml` sans service) | opérationnel : le site est en ligne |

## 2. URLs

| Service | dev | staging | production |
|---|---|---|---|
| Site (frontend) | http://localhost:4000 | http://10.43.43.50:4000 | https://dvrgizboitg9p.cloudfront.net |
| Page de connexion | http://localhost:4000/login | http://10.43.43.50:4000/login | https://dvrgizboitg9p.cloudfront.net/login |
| API, documentation | http://localhost:8000/docs | http://10.43.43.50:8000/docs | fermée (404 sur `/docs`, `/redoc` et `/openapi.json`) |
| API, santé et version | http://localhost:8000/health | http://10.43.43.50:8000/health | https://dvrgizboitg9p.cloudfront.net/api/health |
| API, santé du mock | http://localhost:8000/health/mock | http://10.43.43.50:8000/health/mock | https://dvrgizboitg9p.cloudfront.net/api/health/mock |
| ETL, santé | http://localhost:8001/health | non exposé (`docker ps` : `healthy`) | non exposé |
| Base de données | `localhost:5432`, base `enervision` | non exposée (réseau interne Docker de la VM) | non exposée (réseau interne Docker de l'instance) |

Le staging n'est joignable que depuis le réseau de l'école.

**En production**, seul le frontend est exposé : Internet atteint CloudFront en HTTPS, qui transmet à l'instance sur le port 4000, ouvert aux seules adresses de CloudFront. Le frontend transmet lui-même `/api/` à l'API. Le port 8000 de l'API n'est ouvert à personne (le groupe de sécurité n'a aucune entrée dessus), ni la base, ni l'ETL. Le certificat est celui de `*.cloudfront.net` : sans nom de domaine à nous, il n'y a pas d'autre URL. Le trafic entre CloudFront et l'instance est en HTTP, non chiffré (limite connue, voir le [README Terraform](../infra/terraform/aws/README.md)).

La documentation interactive de l'API est fermée en production depuis la version qui contient la PR de sécurité du 24/10 ; `/health` reste ouvert, le workflow de déploiement s'en sert.

## 3. API Mock

L'API Mock est fournie par l'école. Elle simule les capteurs IoT de 7 sites (`SITE001` à `SITE007`), avec des pannes et des valeurs nulles simulées. Elle n'est pas à nous : ni son code, ni ses données ne sont dans ce dépôt. C'est la source de données de l'ETL, et notre API la sonde pour sa route `/health/mock`.

| | URL | Documentation | Authentification |
|---|---|---|---|
| Interne (réseau de l'école, Proxmox) | `http://10.43.43.80:8000` | `/docs` | aucune |
| Publique (Internet, AWS, poste hors école) | `https://api-mock.charlieandre.fr` | `/docs` | basique (identifiants dans les notes Teams, jamais dans le dépôt) |

| Environnement | Mock utilisé | Variables |
|---|---|---|
| dev | interne si le poste est sur le réseau de l'école, sinon public | `MOCK_API_URL`, `MOCK_API_USERNAME`, `MOCK_API_PASSWORD` dans `.env` |
| staging | interne | `MOCK_API_URL` dans `/etc/enervision/staging.env` ; identifiants à `-` (le compose exige des valeurs non vides) |
| production | public | `MOCK_API_URL` et les identifiants dans `/etc/enervision/production.env` |

Endpoints principaux :

| Route | Méthode | Rôle |
|---|---|---|
| `/health` | GET | état du mock |
| `/api/v1/sites` | GET | liste des sites |
| `/api/v1/sites/{site_id}` | GET | détail d'un site |
| `/api/v1/sites/{site_id}/current` | GET | lecture en temps réel d'un site |
| `/api/v1/readings` | GET | historique des lectures |
| `/api/v1/alerts` | GET | alertes actives |
| `/api/v1/sensors/status` | GET | état des capteurs par site |
| `/api/v1/stats/summary` | GET | statistiques globales |
| `/api/v1/simulate/spike/{site_id}` | POST | simule un pic de consommation sur un site |

La page `/docs` du mock reste la référence pour les paramètres et les formats. Les écarts mesurés entre le mock et le jeu de données historique (noms de sites, colonnes, niveaux) sont dans [`analyse-api-mock.md`](analyse-api-mock.md).

## 4. Services et images

| Service | Rôle | Image GHCR | dev | staging et production |
|---|---|---|---|---|
| `db` | PostgreSQL 16 + TimescaleDB (`timescale/timescaledb:2.30.2-pg16`, image officielle) | non | oui | oui |
| `migrate` | applique les migrations SQL de `db/migrations` (dbmate) puis s'arrête, avant `api` et `etl` ; [détail](migrations-base-de-donnees.md) | `.../db` | construit localement, dossier `db/migrations` monté (`docker compose run --rm migrate`) | image du même tag que les autres |
| `api` | API FastAPI (Python 3.13) : `/health`, `/auth/*`, `/history`, `/predictions`, `/recommendations` (jeton JWT) | `.../api` | rechargement à chaud, port 8000 | port 8000 (fermé à l'extérieur en production) |
| `etl` | traitement des données : nettoyage de l'historique, `/health` seule (pas de route métier) ; le chargement en base est à venir | `.../etl` | port 8001 (santé) | profil `apps`, sans port publié |
| `frontend` | Angular 22 (Node 24) | `.../frontend` | serveur de développement (cible `dev`), port 4000 | profil `apps` : build de production servi par le serveur SSR Node, port 4000 |
| `ml` | entraînement des modèles (tâche ponctuelle) | `.../ml` | profil `ml`, à la demande : `docker compose run --rm ml` | image publiée, aucun service |
| `mlflow` | suivi des expériences et registre des modèles (`ghcr.io/mlflow/mlflow:v3.17.2`, image officielle) | non | port 5000 | non déployé (les comptes de service `mlflow` et `monitoring` existent sur la VM de staging) |

Préfixe des images : `ghcr.io/projet-piscine-eadl-enervision/smart-energy-optimizer`, soit `ghcr.io/<organisation>/<nom du dépôt>` : les workflows le calculent depuis le nom du dépôt. Si le dépôt est renommé, les images changent de préfixe et le compose de staging doit suivre (ou `IMAGE_PREFIX` dans `staging.env`).

Le flux de données prévu : le mock alimente l'ETL, qui écrit dans la base ; l'API lit la base et sert le frontend ; le module ML s'entraîne sur la base. L'historique nettoyé est aujourd'hui un fichier suivi par DVC ([`donnees-dvc.md`](donnees-dvc.md)), le chargement en base par l'ETL reste à écrire.

## 5. Variables d'environnement

| Variable | Rôle | dev (`.env`) | staging (`staging.env`) | production (`production.env`) |
|---|---|---|---|---|
| `APP_ENV` | environnement affiché par l'API (`/health`, `/docs`) ; `production` ferme la documentation | `dev` | `staging` (défaut du compose) | `production` |
| `SECRET_KEY` | clé de signature des jetons de connexion (32 caractères au moins) | à générer | générée sur la VM | générée |
| `MOCK_API_URL` | URL de l'API Mock | à renseigner | URL interne | URL publique |
| `MOCK_API_USERNAME`, `MOCK_API_PASSWORD` | identifiants du mock | à renseigner si URL publique | `-` | identifiants du mock public |
| `POSTGRES_USER`, `POSTGRES_DB` | compte et base | `postgres`, `enervision` | `enervision`, `enervision` | `enervision`, `enervision` |
| `POSTGRES_PASSWORD` | mot de passe de la base | `dev` | généré sur la VM | généré sur l'instance, différent |
| `DATABASE_URL` | connexion de l'API à la base | calculée par le compose | calculée par le compose | calculée par le compose |
| `API_PORT`, `ETL_PORT`, `FRONTEND_PORT` | ports publiés sur l'hôte | 8000, 8001, 4000 | fixes dans le compose (l'ETL n'a aucun port publié) | idem ; le groupe de sécurité n'ouvre que 4000, à CloudFront |
| `COMPOSE_PROFILES` | active `etl` et `frontend` (profil `apps`) | sans objet | `apps` | `apps` |
| `IMAGE_TAG` | tag des images à déployer | sans objet | `main` par défaut ; une ligne `IMAGE_TAG=` fige le staging (retour arrière) | tag de version `vX.Y.Z`, passé par le workflow de déploiement |
| `NG_ALLOWED_HOSTS` | hôtes acceptés par le frontend | `localhost,127.0.0.1` | IP de la VM | nom CloudFront du site |
| `API_UPSTREAM` | adresse de l'API à laquelle le frontend transmet `/api/` | `http://api:8000` | `http://api:8000` | `http://api:8000` |
| `GIT_TITLE`, `GIT_SHA` | titre et sha du commit de l'image | `dev` | passés par la CI à la construction | idem staging |

## 6. Savoir ce qui est déployé

`GET /health` indique l'environnement et le commit déployé :

```json
{
  "status": "healthy",
  "environment": "production",
  "timestamp": "2026-10-24T11:05:07.371087+00:00",
  "version": { "commit": "fix: corriger body-parser dans le frontend (CVE-2026-111181) (#139)", "sha": "ea1de08" }
}
```

L'onglet *Deployments* du dépôt GitHub liste les mises à jour du staging (annoncées par la VM) et de la production (workflow de déploiement). L'en-tête de la page `/docs` rappelle aussi l'environnement hors production.

## 7. Secrets

| Secret | dev | staging | production |
|---|---|---|---|
| Identifiants du mock | `.env` local, non versionné | `/etc/enervision/staging.env` (droits 600, root) | `/etc/enervision/production.env` (droits 600, root) |
| Mot de passe de la base et `SECRET_KEY` | `.env.example` pour la base, clé à générer | `/etc/enervision/staging.env`, générés sur la VM | `/etc/enervision/production.env`, générés sur l'instance |
| Accès aux images GHCR | sans objet | `/root/.docker/config.json` (jeton `read:packages`, 30 jours maximum) | `/root/.docker/config.json` de l'instance (jeton `read:packages`, avec échéance) |
| Annonce du staging à GitHub | sans objet | `/etc/enervision/github-deploy.token` (jeton à grain fin, droit Deployments) | sans objet |
| Accès AWS | sans objet | sans objet | aucun secret : rôle IAM par jeton OIDC (déploiement) et profil d'instance |
| Analyse Sonar | sans objet | sans objet | secret de dépôt `SONAR_TOKEN` (CI) |

Aucun secret n'est versionné. Les procédures de renouvellement des jetons sont dans le document de déploiement du staging et dans le README Terraform.

## 8. Limites connues

- Entre CloudFront et l'instance de production, le trafic est en HTTP, et l'adresse du site est celle de CloudFront : pas de nom de domaine ni de certificat à nous.
- Le module `ml` n'a pas de service déployé, et MLflow n'existe que sur les postes.
- Le chargement de l'historique en base par l'ETL reste à écrire : la base ne contient pas encore de mesures.
- L'accès SSH de `root` et par mot de passe sur la VM de staging n'est pas encore restreint ; la production n'a pas de SSH.

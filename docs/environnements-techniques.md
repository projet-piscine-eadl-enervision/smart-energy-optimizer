# Environnements techniques

Ce document décrit les environnements sur lesquels tourne EnerVision (poste de développement, staging, production), les URLs de chacun, l'API Mock fournie par l'école et les variables qui les distinguent. Les cases marquées **WIP** sont à compléter au fil de l'avancement du projet.

Documents liés : [déploiement du staging](deploiement-staging.md), [mise en production et release](mise-en-production.md) et [infrastructure AWS](../infra/terraform/aws/README.md).

## 1. Vue d'ensemble

| | dev | staging | production |
|---|---|---|---|
| Où | poste de chaque membre (WSL2 Debian + Docker Desktop) | VM Proxmox de l'école, `10.43.43.50` (LXC Debian 13, 4 CPU, 16 Go de RAM, 64 Go) | AWS, instance EC2 Debian 13 (WIP) |
| Compose | `docker-compose.yml` | `docker-compose.staging.yml` | WIP (même compose que le staging prévu) |
| Déclenchement | `docker compose up -d` à la main | automatique : un minuteur de la VM tire les images GHCR toutes les 2 minutes, puis annonce le déploiement à GitHub | workflow Release lancé à la main après la recette du staging (tag `vX.Y.Z`, promotion des images), puis approbation de l'environnement GitHub `production` (procédure dans [`mise-en-production.md`](mise-en-production.md)) ; déploiement par AWS Systems Manager (WIP) |
| Origine des images | construites localement (`build:`) | publiées par la CI sur GHCR (tags `main` et `sha-<commit>`) | mêmes images que le staging, promues par le tag de version, sans reconstruction |
| `APP_ENV` | `dev` | `staging` | `production` |
| Mock utilisé | interne ou public, au choix | interne | public (WIP) |
| État | opérationnel | `db`, `api`, `etl` et `frontend` opérationnels (`ml` sans service) | WIP : rien n'est créé sur AWS |

## 2. URLs

| Service | dev | staging | production |
|---|---|---|---|
| API, documentation | http://localhost:8000/docs | http://10.43.43.50:8000/docs | fermée (404 sur `/docs`, `/redoc`, `/openapi.json`) |
| API, santé et version | http://localhost:8000/health | http://10.43.43.50:8000/health | WIP |
| API, santé du mock | http://localhost:8000/health/mock | http://10.43.43.50:8000/health/mock | WIP |
| ETL, santé | http://localhost:8001/health | non exposé (`docker ps` : `healthy`) | WIP |
| Frontend | http://localhost:4000 | http://10.43.43.50:4000 (l'API y est jointe par `/api/health`) | WIP |
| Base de données | `localhost:5432`, base `enervision` | non exposée (réseau interne Docker de la VM) | WIP |

Le staging n'est joignable que depuis le réseau de l'école. En production, l'exposition de l'API (HTTPS, répartiteur de charge, nom de domaine, IP publique) n'est pas encore décidée : aucune URL n'est donc fixée (WIP).

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
| production | public (l'instance AWS n'atteint pas le réseau interne de l'école) | WIP |

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

La page `/docs` du mock reste la référence pour les paramètres et les formats. Les écarts connus entre le mock et le jeu de données historique (noms, colonnes) sont à documenter ici : WIP.

## 4. Services et images

| Service | Rôle | Dockerfile | Image GHCR | dev | staging | production |
|---|---|---|---|---|---|---|
| `db` | PostgreSQL 16 + TimescaleDB (`timescale/timescaledb`) | image officielle | non | `2.30.2-pg16` | `2.30.2-pg16` | WIP |
| `migrate` | applique les migrations SQL de `db/migrations` (dbmate) puis s'arrête, avant `api` et `etl` ; [détail](migrations-base-de-donnees.md) | oui (`db/`) | `.../enervision/db` | oui, construit localement, dossier `db/migrations` monté (`docker compose run --rm migrate`) | oui, image `db` du même tag que les autres | WIP |
| `api` | API FastAPI (Python 3.13) | oui | `.../enervision/api` | oui, rechargement à chaud | oui, port 8000 | WIP |
| `etl` | collecte du mock, transformation, stockage | oui | `.../enervision/etl` | oui, sans port publié | profil `apps`, sans port publié, non activé | WIP |
| `frontend` | Angular 22 (Node 24) | oui, serveur de développement (cible `dev`) | `.../enervision/frontend` | oui, port 4000 | profil `apps`, build de production servi par le serveur SSR Node (port 4000), non activé | WIP |
| `ml` | entraînement des modèles (tâche ponctuelle) | oui | `.../enervision/ml` | profil `ml`, à la demande : `docker compose run --rm ml` (pas lancé par `up -d`) | WIP | WIP |
| `mlflow` | suivi des expériences et registre des modèles (`ghcr.io/mlflow/mlflow`) | image officielle | non | `v3.17.2`, port 5000 | WIP | WIP |

Préfixe des images : `ghcr.io/projet-piscine-eadl-enervision/smart-energy-optimizer`, soit `ghcr.io/<organisation>/<nom du dépôt>` : les workflows le calculent depuis le nom du dépôt. Si le dépôt est renommé, les images changent de préfixe et le compose de staging doit suivre (ou `IMAGE_PREFIX` dans `staging.env`).

Le flux de données prévu : le mock alimente l'ETL, qui écrit dans la base ; l'API lit la base et sert le frontend ; le module ML s'entraîne sur la base. Aujourd'hui, l'API n'expose que ses routes de santé et l'ETL la liste des sites.

## 5. Variables d'environnement

| Variable | Rôle | dev (`.env`) | staging (`staging.env`) | production |
|---|---|---|---|---|
| `APP_ENV` | environnement affiché par l'API (`/health`, `/docs`) | `dev` | `staging` (défaut du compose) | `production` (WIP) |
| `MOCK_API_URL` | URL de l'API Mock | à renseigner | URL interne | URL publique (WIP) |
| `MOCK_API_USERNAME`, `MOCK_API_PASSWORD` | identifiants du mock | à renseigner si URL publique | `-` | WIP |
| `POSTGRES_USER`, `POSTGRES_DB` | compte et base | `postgres`, `enervision` | `enervision`, `enervision` | WIP |
| `POSTGRES_PASSWORD` | mot de passe de la base | `dev` | généré sur la VM | WIP |
| `DATABASE_URL` | connexion de l'API à la base | calculée par le compose | calculée par le compose | WIP |
| `API_PORT`, `ETL_PORT`, `FRONTEND_PORT` | ports publiés sur l'hôte | 8000, 8001, 4000 | fixes dans le compose (l'ETL n'a aucun port publié) | WIP |
| `COMPOSE_PROFILES` | active `etl` et `frontend` (profil `apps`) | sans objet | `apps`, dans `staging.env` | WIP |
| `IMAGE_TAG` | tag des images à déployer (retour arrière) | sans objet | `main` par défaut | WIP |
| `NG_ALLOWED_HOSTS` | hôtes acceptés par le frontend | `localhost,127.0.0.1` | IP de la VM, dans `staging.env` | adresse AWS (WIP) |
| `API_UPSTREAM` | adresse de l'API à laquelle le frontend transmet `/api/` | `http://api:8000` | `http://api:8000` | `http://api:8000` (WIP) |
| `GIT_TITLE`, `GIT_SHA` | titre et sha du commit de l'image | `dev` | passés par la CI à la construction | idem staging |

## 6. Savoir ce qui est déployé

`GET /health` indique l'environnement et le commit déployé :

```json
{
  "status": "healthy",
  "environment": "staging",
  "timestamp": "2026-10-21T08:11:57.614388+00:00",
  "version": { "commit": "feat: conf docker du front (#67)", "sha": "b2e91b8" }
}
```

L'en-tête de la page `/docs` rappelle aussi l'environnement. En production (`APP_ENV=production`), la documentation interactive est fermée ; `/health` reste ouvert, le workflow de déploiement s'en sert.

## 7. Secrets

| Secret | dev | staging | production |
|---|---|---|---|
| Identifiants du mock | `.env` local, non versionné | `/etc/enervision/staging.env` (droits 600, root) | WIP |
| Mot de passe de la base | valeur de développement dans `.env.example` | `/etc/enervision/staging.env`, généré sur la VM | WIP |
| Accès aux images GHCR | sans objet | `/root/.docker/config.json` (jeton `read:packages`, 30 jours maximum) | WIP |

Aucun secret n'est versionné. Le détail du renouvellement du jeton GHCR est dans le document de déploiement du staging.

## 8. Reste à compléter

- URLs et accès de la production (instance AWS, réseau, répartiteur de charge, certificat).
- Stockage des secrets de la production (AWS Secrets Manager ou fichier d'environnement sur l'instance).
- Mise en route du workflow `deploy-production.yml` (écrit, désactivé par `PRODUCTION_ENABLED` : instance AWS et variables de l'environnement `production` à créer).
- Écarts entre le mock et le jeu de données historique.
- Schéma d'ensemble des trois environnements.

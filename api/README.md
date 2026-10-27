# API EnerVision

API REST du projet, en **FastAPI** (Python 3.13), connectée à **PostgreSQL 16 + TimescaleDB** via **SQLAlchemy 2.0** en asynchrone.

Elle gère l'authentification (JWT) et expose au front Angular les prédictions de pics, l'historique de consommation et les recommandations.

## Démarrer

L'API tourne dans Docker, avec la base. Depuis la **racine du projet** :

```bash
cp .env.example .env        # première fois seulement, puis renseigner SECRET_KEY
docker compose up -d
```

- Documentation interactive (Swagger) : http://localhost:8000/docs
- Santé de l'API (environnement et version) : http://localhost:8000/health
- Santé de l'API Mock : http://localhost:8000/health/mock

> Utilise `localhost` dans le navigateur, pas `0.0.0.0`.

Le dossier `api/` est monté dans le conteneur : Uvicorn recharge l'API à chaque modification.

Les dépendances se déclarent dans `requirements.in` ; `requirements.txt` est généré (versions figées), ne pas l'éditer à la main. Après un changement de dépendance :

```bash
./infra/scripts/compile-requirements.sh
docker compose up -d --build api
```

Voir les logs (erreurs 500, etc.) :

```bash
docker compose logs -f api
```

## Variables d'environnement

Lues par `app/core/config.py` (pydantic-settings). L'API refuse de démarrer si une variable obligatoire manque.

| Variable | Obligatoire | Description |
|---|---|---|
| `DATABASE_URL` | oui | Fournie par le compose. Un `postgresql://` est converti automatiquement en `postgresql+asyncpg://` (driver asynchrone) |
| `SECRET_KEY` | oui | Clé de signature des JWT. Générer avec `python3 -c "import secrets; print(secrets.token_hex(32))"`. En staging, à définir dans `staging.env` |
| `APP_ENV` | non | Environnement affiché par `/health` et `/docs` (défaut : `dev`) ; `production` ferme `/docs`, `/redoc` et `/openapi.json` |
| `GIT_TITLE`, `GIT_SHA` | non | Version affichée par `/health`, fixée par la CI à la construction de l'image |
| `MOCK_API_URL`, `MOCK_API_USERNAME`, `MOCK_API_PASSWORD` | non | Utilisées seulement par `/health/mock` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | non | Durée de validité du jeton (défaut : `60`) |
| `ALGORITHM` | non | Algorithme JWT (défaut : `HS256`) |
| `FRONTEND_ORIGIN` | non | Origine autorisée par le CORS (défaut : `http://localhost:4200`) |

## Structure

```
api/
├── app/
│   ├── main.py            # Point d'entrée : routes, CORS, création des tables
│   ├── core/
│   │   ├── config.py      # Variables d'environnement
│   │   └── security.py    # Hachage des mots de passe, création/lecture des JWT
│   ├── db/
│   │   ├── base.py        # Classe Base dont héritent tous les modèles
│   │   └── session.py     # Connexion à la base + dépendance get_db()
│   ├── models/            # Tables SQL (SQLAlchemy) — un fichier par table
│   ├── schemas/           # Données entrantes/sortantes de l'API (Pydantic)
│   └── api/
│       ├── deps.py        # Dépendances partagées : DbSession, CurrentUser, AdminUser
│       └── routes/        # Un fichier par groupe de routes
├── tests/
├── Dockerfile
├── requirements.in        # Dépendances déclarées
└── requirements.txt       # Généré par infra/scripts/compile-requirements.sh
```

**Modèle ≠ schéma** : un *modèle* (`models/`) décrit une table en base ; un *schéma* (`schemas/`) décrit ce que l'API reçoit ou renvoie. Les séparer évite par exemple d'exposer `hashed_password`.

## Routes

Les routes n'ont pas de préfixe `/api` : c'est le préfixe du proxy du front (`frontend/src/api-proxy.ts`), qui le retire avant de transmettre. Le front appelle `/api/auth/login`, l'API reçoit `/auth/login`.

| Méthode | Route | Accès | Description |
|---|---|---|---|
| `POST` | `/auth/register` | public | Inscription (email + mot de passe de 8 caractères et de 72 octets au plus) |
| `POST` | `/auth/login` | public | Connexion, renvoie un jeton JWT |
| `GET` | `/auth/me` | connecté | Profil de l'utilisateur courant |
| `GET` | `/predictions?hours=24&site_id=SITE001` | connecté | Consommation prévue heure par heure, lue dans `ml.prediction` : un site, ou le total des sites sans `site_id` (`ALL`) ; `is_peak` signale un pic du site (1,25 fois sa consommation moyenne), vide pour le total ; liste vide sans prévision à venir |
| `GET` | `/predictions/peaks?hours=24&site_id=SITE001` | connecté | Heures prévues au-dessus du seuil de pic de leur site, avec ce seuil et le dépassement (`excess_kw`) ; pour tous les sites sans `site_id` ; liste vide sans pic prévu |
| `GET` | `/history?days=7&site_id=SITE001` | connecté | Consommation par heure, lue dans `analytics.energy_hourly` (1 à 90 jours) : un site, ou la somme des sites sans `site_id`. L'heure en cours et les heures dont plus de la moitié des mesures manquent sont écartées ; pour le total, une heure où un site manque l'est aussi |
| `GET` | `/recommendations?hours=24&site_id=SITE001&limit=50` | connecté | Conseils lus dans `app.recommendation` : alertes des dernières 24 h et pics prévus dans les `hours` prochaines heures. L'économie estimée (`estimated_saving_kw`) est la part décalable du dépassement d'un pic prévu, vide pour une alerte |
| `GET` | `/alerts?status=active&site_id=SITE001&since=…&limit=50` | connecté | Alertes de `core.alert`. `status` : `active` (vue il y a moins de 15 minutes et non résolue), `resolved` ou `all`. `since` : alertes reçues après cet instant, pour le sondage du tableau de bord. Les identifiants du mock changent à chaque appel : l'état se déduit de la fraîcheur, pas de la disparition |
| `GET` | `/sites` | connecté | Sites avec leur dernière consommation non nulle, son âge (minutes) et la qualité du dernier relevé |
| `GET` | `/sites/{site_id}/consumption?period=day&days=30` | connecté | Énergie (kWh) et pointe (kW) par `hour`, `day` (Europe/Paris), `week` ou `month` ; fenêtre par défaut de 2, 30, 90 ou 365 jours. Heures peu fiables et jour en cours écartés ; 404 si le site est inconnu |
| `GET` | `/sites/{site_id}/quality?days=7` | connecté | Relevés par niveau de qualité, part de consommation manquante et pannes de capteur de la période (1 à 30 jours) |
| `GET` | `/health` | public | État, environnement et version déployée (utilisé par le staging et la release) |
| `GET` | `/health/mock` | public | Vérifie que l'API Mock répond (502/503 sinon) |

> Les routes de données lisent la base : `/history` l'agrégat horaire, `/predictions` et `/predictions/peaks` les prévisions du module ML, `/recommendations` les conseils que la base déduit des pics prévus et des alertes (`app.refresh_recommendations()`, appelée après chaque prévision).

### Tester dans Swagger

1. Ouvre http://localhost:8000/docs
2. `POST /auth/register` → **Try it out** → renseigne email et mot de passe → **Execute**
3. **Authorize** (en haut à droite) → email dans *username*, puis mot de passe
4. Les routes protégées répondent maintenant `200` (sinon `401`)

## Authentification et rôles

- Les mots de passe sont **hachés** (bcrypt), jamais stockés en clair.
- Le jeton s'envoie dans l'en-tête `Authorization: Bearer <jeton>`.
- Chaque utilisateur a un rôle : `user` (par défaut) ou `admin`.

Protéger une route dans `app/api/routes/` :

```python
from app.api.deps import AdminUser, CurrentUser, DbSession

@router.get("/exemple")
async def exemple(current_user: CurrentUser, db: DbSession):  # connecté → sinon 401
    ...

@router.get("/admin/exemple")
async def admin_exemple(admin: AdminUser, db: DbSession):     # admin → sinon 403
    ...
```

On ne devient **jamais** admin via l'API (`role` n'est pas accepté à l'inscription). Pour promouvoir un compte :

```bash
docker compose exec db psql -U postgres -d enervision \
  -c "UPDATE users SET role = 'admin' WHERE email = 'toi@mail.com';"
```

## Base de données

Ouvrir un terminal SQL :

```bash
docker compose exec db psql -U postgres -d enervision
```

```sql
\dt                     -- lister les tables
\d users                -- structure de la table users
SELECT * FROM users;
\q                      -- quitter
```

### Ajouter ou modifier une table

L'API ne crée plus de table au démarrage : le schéma ne vient que des migrations SQL de `db/migrations/` (dbmate), appliquées avant le démarrage de l'API par le service `migrate`. Il n'y a ni `create_all` ni Alembic.

1. Écrire la migration, un fichier `db/migrations/AAAAMMJJHHMMSS_ma-table.sql` (règles et exemple dans [`docs/migrations-base-de-donnees.md`](../docs/migrations-base-de-donnees.md)).
2. Créer ou modifier `app/models/ma_table.py` (classe qui hérite de `Base`, avec `__tablename__`) pour qu'il corresponde **exactement** à la migration : types, `NOT NULL`, valeurs par défaut, index.
3. `docker compose up -d` applique la migration ; Uvicorn recharge le modèle.

> ⚠️ Un modèle sans migration ne crée rien : les requêtes échouent (`relation ... does not exist`). Une colonne ajoutée dans le modèle seulement, ou dans la migration seulement, casse l'API à l'exécution. Pour changer une table existante, ajouter une nouvelle migration (`alter table ...`), sans jamais modifier une migration déjà fusionnée.

## Notes techniques

- **Asynchrone** : les routes sont en `async def` et la base est interrogée avec `await`. Ne pas oublier `await` devant les appels à `db`.
- **Commit** : `get_db()` ne valide rien automatiquement — une route qui écrit doit appeler `await db.commit()`. En cas d'erreur, tout ce qui n'est pas commité est annulé.
- **Mots de passe** : hachés en bcrypt avec `pwdlib` (remplace `passlib`, qui n'est plus maintenu et plantait avec bcrypt >= 4.1).

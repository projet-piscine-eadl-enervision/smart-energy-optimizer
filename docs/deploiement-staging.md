# Déploiement du staging

Le staging tourne sur la VM Proxmox du groupe (`10.43.43.50`). La VM n'est pas joignable depuis Internet : elle **tire** les mises à jour, rien n'est poussé vers elle et aucun code externe ne s'y exécute.

L'API du staging est accessible depuis le réseau de l'école : http://10.43.43.50:8000/docs (documentation) et http://10.43.43.50:8000/health (état et version déployée).

## Principe

```
merge sur main -> CI verte -> publish-images.yml -> image sur GHCR -> minuteur de la VM -> conteneurs relancés
```

1. Un merge sur `main` dont la CI est verte lance `publish-images.yml`, qui construit une image par module (dossier avec un `Dockerfile`) et la publie sur GHCR : `ghcr.io/projet-piscine-eadl-enervision/smart-energy-optimizer/<module>`, avec les tags `main` et `sha-<commit>`.
2. Toutes les 2 minutes, `update-staging.timer` lance `infra/scripts/update-staging.sh` sur la VM : il aligne le dépôt sur `origin/main`, tire les images puis relance les conteneurs modifiés. Un merge est donc visible sur le staging une fois la CI et la publication terminées, avec au plus 2 minutes de minuteur en plus : le sha de `/health` le confirme.

La suite (recette, release, production, retour arrière) est dans [`mise-en-production.md`](mise-en-production.md).

Seuls les modules qui ont un `Dockerfile` sont publiés. Aujourd'hui, c'est le cas de `api`, `etl`, `frontend`, `ml` et `db`. Seuls `api` et `ml` reçoivent la version à la construction (`GIT_TITLE` et `GIT_SHA`). `ml` n'a pas de service dans `docker-compose.staging.yml` : son image est publiée, mais rien ne la lance sur le staging.

L'image `db` n'est pas une base : elle contient les migrations SQL et l'outil qui les applique (dbmate). Le service `migrate` du compose la lance à chaque `up`, après que la base est saine et avant `api` et `etl`, puis s'arrête. Il ne fait rien quand tout est déjà appliqué, ce qui est le cas à presque chaque passage du minuteur. Si une migration échoue, `api` et `etl` ne démarrent pas (voir [`migrations-base-de-donnees.md`](migrations-base-de-donnees.md)).

L'image `frontend` publiée (cible `prod` du `Dockerfile`) contient le build de production d'Angular, servi par le serveur SSR Node (port 4000). C'est la même image au staging et en production : le front appelle l'API par un chemin relatif (`/api/...`) et le serveur (`frontend/src/api-proxy.ts`) le transmet à l'adresse donnée par la variable `API_UPSTREAM`, lue au lancement du conteneur (`http://api:8000` par défaut). `NG_ALLOWED_HOSTS` est lue de la même façon : elle doit contenir l'IP ou le nom sous lequel le site est joint, sinon le rendu serveur refuse la requête. Aucune adresse d'environnement n'est donc fixée à la construction. En développement, `docker-compose.yml` utilise la cible `dev` (`ng serve`).

## Savoir ce qui est déployé

`GET /health` de l'API indique le titre du commit et son sha court :

```json
{
  "status": "healthy",
  "environment": "staging",
  "timestamp": "2026-10-21T08:11:57.614388+00:00",
  "version": { "commit": "feat: conf docker du front (#67)", "sha": "b2e91b8" }
}
```

Le titre et le sha sont passés à la construction de l'image (`build-args` de `publish-images.yml`). En local, l'image est construite sans ces arguments et affiche `dev`.

L'environnement (`dev`, `staging` ou `production`) vient de la variable `APP_ENV`, lue au lancement du conteneur. Elle n'est pas dans l'image, car la même image est promue du staging vers la production. Le compose du staging la fixe à `staging` par défaut ; l'environnement de production devra définir `APP_ENV=production`. L'environnement est aussi rappelé en tête de la page `/docs`.

`GET /health/mock` vérifie séparément que l'API Mock répond (erreur 502 ou 503 sinon). L'état de notre API ne dépend pas du mock.

## Contrat pour les compose

Les services du `docker-compose.staging.yml` racine (le `docker-compose.yml` est le compose de développement : base seule, mot de passe par défaut) référencent les images publiées, par exemple `image: ghcr.io/projet-piscine-eadl-enervision/smart-energy-optimizer/etl:${IMAGE_TAG:-main}`. Un `build:` seul ne serait pas mis à jour par ce mécanisme.

## Contenu de `/etc/enervision/staging.env`

Ce fichier existe uniquement sur la VM, jamais dans le dépôt.

```
POSTGRES_PASSWORD=...
MOCK_API_URL=http://10.43.43.80:8000
MOCK_API_USERNAME=-
MOCK_API_PASSWORD=-
# Active les services etl et frontend :
COMPOSE_PROFILES=apps
# IP ou nom sous lesquels le frontend est joint (indispensable avec le profil apps) :
NG_ALLOWED_HOSTS=localhost,127.0.0.1,10.43.43.50
# Environnement affiché par l'API (staging par défaut, production sur AWS) :
# APP_ENV=staging
# Pour figer un commit précis (retour arrière d'urgence, voir mise-en-production.md) :
# IMAGE_TAG=sha-<commit complet>
```

- `POSTGRES_PASSWORD` : un mot de passe généré sur la VM (`openssl rand -base64 24 | tr -d '/+='`), différent de celui du développement.
- `MOCK_API_*` : le mock interne de l'école ne demande pas d'identifiants. Le compose exige pourtant des valeurs non vides pour toutes les variables `MOCK_API_*` (l'ETL en a besoin), d'où le `-`. Avec l'URL publique du mock (`https://api-mock.charlieandre.fr`), mettre les vrais identifiants, qui sont dans les notes Teams.
- `COMPOSE_PROFILES=apps` active `etl` et `frontend`. Leurs images doivent être publiées sur GHCR (vérifier avec `docker pull ghcr.io/projet-piscine-eadl-enervision/smart-energy-optimizer/etl:main`), sinon le `pull` échoue.
- `NG_ALLOWED_HOSTS` : liste des noms ou IP sous lesquels le frontend est joint (`10.43.43.50` en staging). Sans elle, le serveur de rendu refuse les requêtes qui arrivent avec l'IP de la VM.
- Sur l'hôte, l'API écoute sur le port 8000 et le frontend sur le 4000. L'ETL ne publie aucun port : son état se lit avec `docker ps` (`healthy`).

## Mise en place sur la VM (une seule fois)

En root sur la VM :

```bash
git clone https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer /opt/enervision
install -d -m 700 /etc/enervision
# créer /etc/enervision/staging.env (voir ci-dessus), puis :
chmod 600 /etc/enervision/staging.env
docker compose -f /opt/enervision/docker-compose.staging.yml --env-file /etc/enervision/staging.env config -q && echo "config ok"
cp /opt/enervision/infra/scripts/update-staging.{service,timer} /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now update-staging.timer
systemctl start update-staging.service
```

Ce clone est réservé au déploiement : le script le réinitialise sur `origin/main`, il ne faut pas y travailler. Le clone de travail éventuel se trouve ailleurs (par exemple `~/workspace/enervision`).

### Comptes de service de la VM

`infra/scripts/setup-vm-roles.sh` crée les comptes de service `mlflow` et `monitoring`, sans mot de passe ni shell, propriétaires de `/srv/mlflow` et de `/srv/monitoring`. À lancer en root, il peut être relancé sans risque :

```bash
/opt/enervision/infra/scripts/setup-vm-roles.sh
```

- Le script affiche leur `uid:gid`, à passer à `user:` dans le compose quand MLflow et Prometheus seront déployés ; il n'installe aucun de ces services.
- Sur la VM de staging (`ml-stagiaire-01`, créés le 24/10/2026) : `mlflow` vaut `999:991` et `monitoring` vaut `997:988`, soit `user: "999:991"` pour MLflow et `user: "997:988"` pour la supervision. L'`uid` et le `gid` diffèrent. Ces numéros sont attribués par le système : sur une autre machine, les relire avec `getent passwd mlflow monitoring` (uid et gid du compte) avant de les écrire dans le compose.
- Il ne touche à aucun compte de personne : l'administration de la VM reste faite en `root`. Des comptes individuels et leurs droits viendront dans une étape ultérieure, si besoin, ainsi que l'interdiction de la connexion SSH de `root` et par mot de passe.
- La production sur AWS n'a pas de SSH (déploiement par SSM) et n'est pas concernée.

### Accès aux images GHCR

Les images GHCR d'un dépôt public sont privées par défaut. Le staging utilise un `docker login` avec un jeton personnel plutôt qu'un passage en public :

1. Créer un jeton classique (GitHub, *Settings > Developer settings > Personal access tokens > Tokens (classic)*) avec la seule permission `read:packages` et une expiration de 30 jours au maximum (limite de l'organisation).
2. Sur la VM, en root, sans afficher le jeton :
   ```bash
   read -rs -p "Jeton GHCR : " T && echo
   echo "$T" | docker login ghcr.io -u <identifiant-github> --password-stdin
   unset T
   chmod 600 /root/.docker/config.json
   ```
3. Vérifier : `docker pull ghcr.io/projet-piscine-eadl-enervision/smart-energy-optimizer/api:main`.

Le jeton est stocké en clair dans `/root/.docker/config.json` (lisible par root seulement). Il expire : sans renouvellement, le `pull` du minuteur échoue sans bruit et le staging cesse de se mettre à jour. Le renouveler avant l'échéance en refaisant l'étape 2. Il est lié au compte qui l'a créé.

## Suivi et dépannage

```bash
systemctl list-timers update-staging.timer          # prochain passage
journalctl -u update-staging.service -n 50          # dernier déploiement
docker ps                                           # conteneurs en cours
docker compose -f /opt/enervision/docker-compose.staging.yml --env-file /etc/enervision/staging.env logs migrate   # migrations de la base
```

| Symptôme | Cause probable |
|---|---|
| `denied` ou `unauthorized` dans le journal | jeton GHCR expiré ou révoqué : refaire le `docker login` |
| `manquant dans staging.env` | variable absente ou vide dans `/etc/enervision/staging.env` |
| `manifest unknown` | l'image du tag demandé n'est pas (encore) publiée : vérifier la CI et `publish-images.yml` |
| L'ancienne version tourne encore | CI ou publication non terminée, ou minuteur arrêté |
| `api` et `etl` ne démarrent pas, `migrate` est en `Exited (2)` | une migration échoue : lire le journal de `migrate`, corriger par une nouvelle migration (voir [`migrations-base-de-donnees.md`](migrations-base-de-donnees.md)) |
| `manifest unknown` sur l'image `db`, juste après un merge | l'image `db` du commit n'est pas encore publiée : le passage suivant du minuteur suffit |

Le retour arrière du staging (PR `revert`, ou version figée par `IMAGE_TAG`) et la production sont décrits dans [`mise-en-production.md`](mise-en-production.md).

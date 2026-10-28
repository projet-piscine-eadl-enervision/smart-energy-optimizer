# Déploiement du staging

Le staging tourne sur la VM Proxmox du groupe (`10.43.43.50`). La VM n'est pas joignable depuis Internet : elle **tire** les mises à jour, rien n'est poussé vers elle et aucun code externe ne s'y exécute.

L'API du staging est accessible depuis le réseau de l'école : http://10.43.43.50:8000/docs (documentation) et http://10.43.43.50:8000/health (état et version déployée).

## Principe

```
merge sur main -> CI verte -> job publish (ci.yml) -> images sur GHCR -> minuteur de la VM -> conteneurs relancés -> déploiement « staging » annoncé à GitHub
```

1. Un merge sur `main` dont la CI est verte lance le job `publish` de `ci.yml`, qui publie sur GHCR une image par module (dossier avec un `Dockerfile`) : `ghcr.io/projet-piscine-eadl-enervision/smart-energy-optimizer/<module>`, avec les tags `sha-<commit>` et `main` (`main` n'avance que si ce commit est encore la tête de `main`). Un module dont le dossier n'a pas changé réutilise son image (étiquette `tree-<empreinte>-<semaine>`) ; seule `api` est toujours reconstruite, car son `/health` affiche le sha du commit. Tout est reconstruit chaque semaine pour reprendre les mises à jour des images de base. Chaque image construite est scannée par Trivy, dont le rapport va dans l'onglet *Security* du dépôt.
2. Toutes les 2 minutes, `update-staging.timer` lance `infra/scripts/update-staging.sh` sur la VM : il aligne le dépôt sur `origin/main`, tire les images puis relance les conteneurs modifiés. Un merge est donc visible sur le staging une fois la CI et la publication terminées, avec au plus 2 minutes de minuteur en plus : le sha de `/health` le confirme.
3. Une fois les conteneurs relancés, `report-staging-deployment.sh` annonce à GitHub le commit qui tourne : un déploiement `staging` apparaît dans l'onglet *Deployments* (voir « Annonce du staging à GitHub »). C'est le signal « la recette peut commencer ».

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

Le titre et le sha sont passés à la construction de l'image (`build-args` du job `publish` de `ci.yml`). En local, l'image est construite sans ces arguments et affiche `dev`.

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
# Active les services etl et frontend (ajouter ,collector pour collecter les mesures du mock) :
COMPOSE_PROFILES=apps
# IP ou nom sous lesquels le frontend est joint (indispensable avec le profil apps) :
NG_ALLOWED_HOSTS=localhost,127.0.0.1,10.43.43.50
# Environnement affiché par l'API (staging par défaut, production sur AWS) :
# APP_ENV=staging
# Pour figer un commit précis (retour arrière d'urgence, voir mise-en-production.md) :
# IMAGE_TAG=sha-<commit complet>
# Supervision : ajouter ,monitoring à COMPOSE_PROFILES, et :
# GRAFANA_ADMIN_PASSWORD=...
```

- `POSTGRES_PASSWORD` : un mot de passe généré sur la VM (`openssl rand -base64 24 | tr -d '/+='`), différent de celui du développement.
- `MOCK_API_*` : le mock interne de l'école ne demande pas d'identifiants. Le compose exige pourtant des valeurs non vides pour toutes les variables `MOCK_API_*` (l'ETL en a besoin) : le staging porte les identifiants du mock public (notes Teams), que le mock interne ignore, comme la production. À défaut, un `-` suffit. Avec l'URL publique du mock (`https://api-mock.charlieandre.fr`), mettre les vrais identifiants, qui sont dans les notes Teams.
- `COMPOSE_PROFILES=apps` active `etl` et `frontend`. Leurs images doivent être publiées sur GHCR (vérifier avec `docker pull ghcr.io/projet-piscine-eadl-enervision/smart-energy-optimizer/etl:main`), sinon le `pull` échoue.
- `NG_ALLOWED_HOSTS` : liste des noms ou IP sous lesquels le frontend est joint (`10.43.43.50` en staging). Sans elle, le serveur de rendu refuse les requêtes qui arrivent avec l'IP de la VM.
- Sur l'hôte, l'API écoute sur le port 8000 et le frontend sur le 4000. L'ETL ne publie aucun port : son état se lit avec `docker ps` (`healthy`).
- `ref.site` est vide à l'installation : charger les sites une fois, après la première mise à jour réussie. Relancer est sans danger.

  ```bash
  cd /opt/enervision && docker compose -f docker-compose.staging.yml --env-file /etc/enervision/staging.env \
    run --rm etl python -m pipeline load-ref      # attendu : « 7 sites loaded in ref.site »
  ```
- Historique : une fois les sites chargés, `run --rm etl python -m pipeline backfill` (mêmes options que ci-dessus) charge les mesures du mock du 2023-01-01 à maintenant, par pas d'une heure : environ une minute, 233 940 lignes (33 420 par site). Relancer est sans danger.
- Module ML : ajouter `mlflow` à `COMPOSE_PROFILES`, puis `docker compose … run --rm ml` pour entraîner et `run --rm ml python -m enervision_ml.predict` pour prévoir (détails dans `ml/README.md`). Le service `ml` n'est jamais dans `COMPOSE_PROFILES`. MLflow écoute sur `127.0.0.1:5000` de la VM, sans authentification : s'y connecter par un tunnel SSH (voir `ml/README.md`).
- Historique nettoyé (anomalies étiquetées) : le fichier parquet n'est pas dans l'image, il vient du stockage DVC de la VM. Une fois les sites chargés :

  ```bash
  cd /opt/enervision && C="docker compose -f docker-compose.staging.yml --env-file /etc/enervision/staging.env"
  H=$(awk '/energy_consumption_cleaned.parquet/{f=1} f && /md5:/{print $2; exit}' etl/dvc.lock)
  F=$(find /var/lib/enervision/dvc -type f -name "${H:2}" | head -1); echo "$F"   # doit afficher un chemin
  cp "$F" /tmp/history.parquet && chmod 644 /tmp/history.parquet
  $C run --rm -v /tmp/history.parquet:/data/history.parquet:ro \
    etl python -m pipeline load-history /data/history.parquet     # attendu : « 122647 rows written in ml.history_labeled, 0 rejected »
  rm /tmp/history.parquet
  ```

  Relancer écrit 0 ligne. Si `find` ne trouve rien, le fichier n'a pas été poussé dans DVC (`dvc push`), ou se copie depuis un poste avec `scp`.
- Collecte des mesures : ajouter `collector` à `COMPOSE_PROFILES` (`apps,collector`), puis attendre la mise à jour automatique. `docker ps` montre `collector` en `healthy` après environ 90 secondes (`unhealthy` : aucun tour réussi depuis trois minutes, mock injoignable ou base arrêtée). Les tours se lisent avec `docker compose logs --tail 5 collector` (staging : mêmes options `-f` et `--env-file` que ci-dessus).
- Supervision (Prometheus, Grafana et les exporteurs de `docker-compose.monitoring.yml`) : ajouter `monitoring` à `COMPOSE_PROFILES` (`apps,collector,monitoring`) et une ligne `GRAFANA_ADMIN_PASSWORD`, générée comme `POSTGRES_PASSWORD` (`openssl rand -base64 24 | tr -d '/+='`), plus `TEAMS_WEBHOOK_URL` pour recevoir les alertes dans Teams. `update-staging.sh` ajoute alors ce compose à ses commandes, et la mise à jour suivante lance la supervision ; retirer le mot l'arrête. Prometheus et Grafana n'écoutent que sur `127.0.0.1` de la VM : y accéder par un tunnel, `ssh -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 root@10.43.43.50`, puis http://localhost:3000 (utilisateur `admin`). Pour les commandes `docker compose` à la main, ajouter `-f docker-compose.monitoring.yml`. Détails, alertes et dashboards : [`monitoring/README.md`](../monitoring/README.md).

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

- Le script affiche leur `uid:gid`, à passer à `user:` dans le compose. MLflow est déployé (profil `mlflow`) mais sans `user:` et avec un volume Docker nommé, pas `/srv/mlflow` ; Prometheus n'est pas déployé. Le script n'installe aucun de ces services.
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

### Annonce du staging à GitHub

À chaque passage, `update-staging.sh` appelle `report-staging-deployment.sh`. Une fois la mise à jour terminée, il lit le sha affiché par l'API sur `/health` et crée un déploiement `staging` (statut `success`) pour ce commit, une seule fois par commit. C'est le signal « le staging est à jour, la recette peut commencer », visible dans l'onglet *Deployments* du dépôt ; le workflow Release s'appuie dessus. Sans jeton ou sans réseau, le script le dit dans le journal et la mise à jour continue.

Mise en place du jeton, une fois :

1. GitHub, *Settings > Developer settings > Personal access tokens > Fine-grained tokens > Generate new token*. Propriétaire : l'organisation. Dépôt : `smart-energy-optimizer` seul. Permission *Repository > Deployments* : lecture et écriture. Expiration : la fin du projet.
2. Sur la VM, en root, sans afficher le jeton :
   ```bash
   install -m 600 -o root -g root /dev/null /etc/enervision/github-deploy.token
   read -rs -p "Jeton : " T && echo && printf '%s' "$T" > /etc/enervision/github-deploy.token && unset T
   ```
3. Vérifier la lecture (réponse attendue : `200`) :
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $(cat /etc/enervision/github-deploy.token)" \
     "https://api.github.com/repos/projet-piscine-eadl-enervision/smart-energy-optimizer/deployments?environment=staging&per_page=1"
   ```
4. Au passage suivant du minuteur, `journalctl -u update-staging.service -n 20` doit montrer `annonce GitHub : staging annoncé à jour sur <sha>`.

Le jeton expire : sans renouvellement, l'annonce s'arrête sans bruit et la release sera refusée faute de déploiement `staging`. Le renouveler avant l'échéance en refaisant les étapes 1 et 2. Messages du journal : `jeton absent` (fichier manquant), `déploiement refusé` ou `réponse inattendue` (jeton expiré, permissions insuffisantes ou dépôt mal désigné, le corps de la réponse de GitHub est affiché).

### Prévision horaire du module ML

Le staging relance la prévision toutes les heures, à `hh:05` : `infra/scripts/predict-ml.timer` lance `predict-ml.service`, qui exécute `docker compose … run --rm ml python -m enervision_ml.predict`. La prévision écrit `ml.prediction`, puis recalcule les recommandations. Elle exige un modèle champion (entraînement fait), MLflow actif (`mlflow` dans `COMPOSE_PROFILES`) et des mesures de moins de 3 heures ; sinon elle s'arrête avec un message, et le journal du service l'indique. La production a ses propres minuteurs (`predict-ml-production`, `monitor-ml-production`, `train-ml-production`) : voir [`mise-en-production.md`](mise-en-production.md).

Installation, une seule fois, en `root` sur la VM de staging :

```bash
cp /opt/enervision/infra/scripts/predict-ml.service /opt/enervision/infra/scripts/predict-ml.timer /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now predict-ml.timer
systemctl list-timers predict-ml.timer                 # prochain passage
journalctl -u predict-ml.service -n 20 --no-pager      # dernier passage
```

Le minuteur de mise à jour du staging (toutes les 2 minutes) lance `up -d --remove-orphans` : il ne supprime pas un conteneur `run --rm` en cours (vérifié avec Docker Compose 5.6). Sur la VM, `docker compose version` donne la version installée ; si elle diffère, contrôler avec `journalctl -u predict-ml.service` après deux passages que la prévision n'est pas interrompue.

### Surveillance et entraînement hebdomadaire du module ML

Deux autres minuteurs, installés comme le précédent :
- `monitor-ml.timer`, chaque jour à 06:30, contrôle le champion (dérive de la consommation, erreur face à la mesure, mesures manquantes, âge de la dernière prévision). Les résultats sont dans `ml.drift_metric` (vues `ml.model_health` et `ml.model_status`) et dans MLflow (expérience `enervision-monitoring`). Une alerte donne le code de sortie 2 : `systemctl status monitor-ml.service` apparaît en échec.
- `train-ml.timer`, chaque lundi à 03:30, entraîne un candidat (`--trigger schedule`, noté dans MLflow). Il n'est promu champion que s'il bat le champion sur la même validation.

```bash
cp /opt/enervision/infra/scripts/{monitor,train}-ml.{service,timer} /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now monitor-ml.timer train-ml.timer
systemctl list-timers 'monitor-ml*' 'train-ml*'
journalctl -u monitor-ml.service -n 20 --no-pager
```

### Vérifier le module ML sur la VM

En `root`, une fois les trois minuteurs installés :

```bash
cd /opt/enervision && docker compose version
systemctl list-timers 'predict-ml*' 'monitor-ml*' 'train-ml*'     # trois lignes, NEXT renseigné
systemctl start predict-ml.service && journalctl -u predict-ml.service -n 20 --no-pager
systemctl start monitor-ml.service; journalctl -u monitor-ml.service -n 30 --no-pager   # « insufficient » est normal les premiers jours
systemctl is-failed predict-ml.service train-ml.service            # « inactive » attendu
```

La base (service `db`, utilisateur et base `enervision` par défaut) :

```bash
C="docker compose -f docker-compose.staging.yml --env-file /etc/enervision/staging.env"
$C exec -T db psql -U enervision -d enervision -c "SELECT count(*) FROM ml.prediction" -c "SELECT * FROM ml.model_status" -c "SELECT count(*) FROM app.recommendation"
```

L'API, avec un compte existant (chaque ligne doit afficher `200`) :

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -d "username=<email>&password=<mot de passe>" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
for r in "predictions?hours=24" "predictions/peaks" "history?days=1" "recommendations"; do
  curl -s -o /dev/null -w "$r %{http_code}\n" -H "Authorization: Bearer $TOKEN" "http://localhost:8000/$r"; done
```

Après deux passages des minuteurs : `LAST` renseigné dans `list-timers`, aucun service en échec (`systemctl is-failed`), et le journal du lundi (`journalctl -u train-ml.service`) indique si le champion est conservé ou remplacé.

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
| `GRAFANA_ADMIN_PASSWORD manquant` | `monitoring` est dans `COMPOSE_PROFILES` mais pas le mot de passe de Grafana : ajouter la ligne, ou retirer `monitoring` |
| `manifest unknown` | l'image du tag demandé n'est pas (encore) publiée : vérifier la CI et son job `publish` |
| La release dit que le staging n'a rien annoncé | jeton de la VM absent ou expiré, ou passage du minuteur pas encore fait : voir « Annonce du staging à GitHub » |
| L'ancienne version tourne encore | CI ou publication non terminée, ou minuteur arrêté |
| `api` et `etl` ne démarrent pas, `migrate` est en `Exited (2)` | une migration échoue : lire le journal de `migrate`, corriger par une nouvelle migration (voir [`migrations-base-de-donnees.md`](migrations-base-de-donnees.md)) |
| `manifest unknown` sur l'image `db`, juste après un merge | l'image `db` du commit n'est pas encore publiée : le passage suivant du minuteur suffit |

Le retour arrière du staging (PR `revert`, ou version figée par `IMAGE_TAG`) et la production sont décrits dans [`mise-en-production.md`](mise-en-production.md).

# Supervision

Prometheus collecte les métriques de l'hôte, des conteneurs, de la base, de l'API et de l'ETL, et
évalue les règles d'alerte. Alertmanager envoie les alertes dans un canal Teams. Grafana affiche les
métriques dans des dashboards versionnés ici. La stack est
décrite par `docker-compose.monitoring.yml`, à la racine, qui s'ajoute au compose de l'environnement.

```
monitoring/
  prometheus/prometheus.yml      cibles collectées toutes les 15 s
  prometheus/alerts.yml          règles d'alerte
  prometheus/alerts.test.yml     tests des règles (promtool test rules)
  blackbox/blackbox.yml          façons de sonder les URL (http_2xx, http_frontend)
  alertmanager/alertmanager.yml  envoi des alertes dans Teams (regroupement, rappels)
  grafana/provisioning/          sources de données (Prometheus, GitHub) et chargement des dashboards
  grafana/dashboards/*.json      dashboards, rangés dans le dossier « EnerVision » de Grafana
```

## Ce qui est surveillé

| Job Prometheus      | Source                                   | Ce qu'on y voit                                               |
|---------------------|------------------------------------------|---------------------------------------------------------------|
| `node`              | node-exporter                            | CPU, mémoire, disque, réseau de l'hôte (EC2 ou VM), et état des minuteurs systemd du projet |
| `cadvisor`          | cAdvisor                                 | CPU, mémoire, réseau, disque de chaque conteneur              |
| `postgres`          | postgres-exporter                        | connexions, transactions, cache, verrous de PostgreSQL        |
| `api`               | `/metrics` de l'API                      | requêtes par route et par code, latence, requêtes en cours    |
| `etl`               | `/metrics` de l'ETL (`etl/metrics.py`)   | dernière exécution de chaque traitement, mesure la plus récente |
| `blackbox-http`     | blackbox-exporter                        | `/health` de l'API et de l'ETL répond-il en 2xx, et en combien de temps |
| `blackbox-frontend` | blackbox-exporter                        | même chose pour le frontend                                   |
| `prometheus`        | Prometheus                               | Prometheus lui-même                                           |
| `alertmanager`      | Alertmanager                             | Alertmanager joignable (sinon plus aucune notification)       |

Les métriques de l'ETL sont lues dans la base à chaque collecte (`etl.run`, `core.energy_reading`) :
le collecteur n'ouvre aucun port, on observe ce qu'il écrit.

`/metrics` n'est jamais exposée au public : le serveur du frontend répond 404 à `/api/metrics`, et
Prometheus lit l'API et l'ETL directement sur le réseau Docker.

## Lancer la stack

`GRAFANA_ADMIN_PASSWORD` doit être présent dans `.env` (poste), `staging.env` ou `production.env`
(serveurs). Grafana ne lit ce mot de passe qu'au premier démarrage, quand le volume `grafana_data` est
vide ; pour le changer ensuite :
`docker compose ... exec grafana grafana cli admin reset-admin-password <nouveau>`.

Poste de développement :

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

- Grafana : http://localhost:3000 (utilisateur `admin`), menu *Dashboards* > *EnerVision*.
- Prometheus : http://localhost:9090 (cibles dans *Status > Targets*, alertes dans *Alerts*).

Prometheus, le blackbox et Grafana ne relisent pas toujours leur configuration à chaud : après une
modification de `monitoring/prometheus` ou `monitoring/blackbox`, redémarrer le service concerné
(`docker compose ... restart prometheus blackbox`). Grafana relit les dashboards toutes les 30 s.

Pour avoir des mesures et des exécutions de l'ETL en local, lancer aussi le collecteur :
`docker compose --profile collector up -d collector`.

### Staging et production

Prometheus et Grafana n'écoutent que sur `127.0.0.1` : rien n'est exposé sur le réseau, aucune règle
de groupe de sécurité n'est nécessaire.

- Staging (VM, réseau de l'école) : tunnel SSH,
  `ssh -L 3000:127.0.0.1:3000 root@10.43.43.50`, puis http://localhost:3000.
- Production (EC2, sans SSH) : redirection de port par SSM, depuis un poste configuré
  (`docs/aws-poste-developpeur.md`) :

  ```bash
  aws ssm start-session \
    --target "$(terraform -chdir=infra/terraform/aws output -raw instance_id)" \
    --document-name AWS-StartPortForwardingSession \
    --parameters '{"portNumber":["3000"],"localPortNumber":["3000"]}'
  ```

  puis http://localhost:3000.

> **Activation.** `monitoring` dans le `COMPOSE_PROFILES` de `staging.env` ou `production.env`, avec
> `GRAFANA_ADMIN_PASSWORD` (et `TEAMS_WEBHOOK_URL` pour les notifications) :
> `infra/scripts/update-staging.sh` et `.github/workflows/deploy-production.yml` ajoutent alors ce
> compose à leurs commandes. Pas à pas et accès de chaque développeur :
> [`docs/supervision-staging.md`](../docs/supervision-staging.md) et
> [`docs/supervision-production.md`](../docs/supervision-production.md). Ne pas démarrer
> la supervision à la main sur un serveur : les deux déploiements utilisent `--remove-orphans` et
> suppriment au passage suivant les conteneurs qu'ils ne connaissent pas.

## Alertes

`prometheus/alerts.yml` : disponibilité (cible injoignable, sonde HTTP en échec, base injoignable),
hôte (disque à 80 et 90 %, mémoire, CPU), tâches planifiées (voir ci-dessous) et application (erreurs
5xx et latence de l'API, absence de nouvelle mesure, dernière exécution de l'ETL en échec). Gravité `critical` : service indisponible ;
`warning` : à regarder avant que ça le devienne.

Les alertes se consultent dans Prometheus (*Alerts*) et dans Grafana (*Alerting > Alert rules*), et
Alertmanager les envoie dans un canal Teams (voir « Notifications Teams »).

### Tâches planifiées

Les minuteurs systemd du projet (`update-staging` sur la VM, `predict-ml`, `monitor-ml`, `train-ml` et
leurs variantes `-production`) sont lus par le collecteur systemd de node-exporter, par le bus D-Bus de
l'hôte (`/var/run/dbus/system_bus_socket`, monté en lecture seule). Seules ces unités sont collectées
(`--collector.systemd.unit-include` dans `docker-compose.monitoring.yml`) : un nouveau minuteur s'y
ajoute.

- `TachePlanifieeEnEchec` : le dernier lancement d'un service a échoué. Un service oneshot reste en
  échec jusqu'au lancement réussi suivant, l'alerte aussi (rappel toutes les 4 h) ; après correction,
  `systemctl reset-failed <service>` l'efface sans attendre. `monitor-ml` en échec signale aussi une
  dérive du modèle (code de sortie 2).
- `MinuteurArrete` : un minuteur n'est plus actif (désactivé ou arrêté).
- `MinuteurEnRetard` : pas de déclenchement depuis un peu plus que sa période (mise à jour du staging
  10 min, prévision 2 h, surveillance 26 h, entraînement 8 jours). Un minuteur jamais déclenché, juste
  après son installation, est ignoré.

Un minuteur absent de la machine ne produit aucune série et ne déclenche aucune alerte : en production,
les minuteurs doivent être installés (`docs/mise-en-production.md`). Dashboard : *Tâches planifiées*.

`EtlSansNouvelleMesure` ne sonne que si la base contient des mesures : sans collecteur (production
par défaut), la table est vide et l'alerte reste muette.

Toute nouvelle règle s'accompagne si possible d'un cas dans `alerts.test.yml` :

```bash
cd monitoring/prometheus
docker run --rm -v "$PWD:/w:ro" -w /w --entrypoint promtool prom/prometheus:v3.15.0 test rules alerts.test.yml
```

## Notifications Teams

Prometheus transmet les alertes à Alertmanager (`alertmanager:9093`), qui les poste dans un canal
Teams par un workflow (Power Automate), au format carte adaptative (`msteamsv2_configs`). Chaque
message indique l'environnement (label `environment`, tiré de `APP_ENV`), le nom de l'alerte et sa
gravité ; un second message signale la résolution. Alertes regroupées par nom et environnement,
rappel toutes les 4 h tant qu'elles durent ; une alerte `critical` masque le `warning` de même cible.

Mettre en place le webhook, une fois par environnement (un canal par environnement, ou le même) :

1. Dans Teams, sur le canal : *...* > *Workflows* > modèle **« Envoyer des alertes webhook à un
   canal »** (*Send webhook alerts to a channel*), choisir l'équipe et le canal, puis copier l'URL
   affichée à la fin.
2. La mettre dans `staging.env` ou `production.env` (ou `.env` sur le poste) :
   `TEAMS_WEBHOOK_URL=https://...`. Cette URL suffit pour écrire dans le canal : jamais dans Git ni
   dans un message.
3. Le déploiement suivant (minuteur du staging, workflow de production) démarre Alertmanager avec
   cette URL. S'il tournait déjà, il ne relit pas l'URL : sur le serveur,
   `docker compose ... up -d --force-recreate alertmanager` (mêmes options `-f` et `--env-file` que
   le déploiement). Même chose après un changement d'URL.

Les anciens « connecteurs » Office 365 (webhook entrant) sont en cours de retrait par Microsoft : ne
pas les utiliser. Sans `TEAMS_WEBHOOK_URL`, Alertmanager tourne mais chaque envoi échoue (`Notify for
alerts failed` dans ses logs) ; les alertes restent visibles dans Prometheus et Grafana.

Vérifier l'envoi : interface d'Alertmanager sur le port 9093 de la machine (tunnel comme pour Grafana,
`-L 9093:127.0.0.1:9093`), ou envoyer une alerte de test depuis le serveur :

```bash
docker compose ... exec alertmanager amtool alert add AlerteDeTest severity=warning environment=test \
  --annotation='summary="Test des notifications"' --annotation='description="À ignorer"' \
  --alertmanager.url=http://localhost:9093
```

Le message arrive après `group_wait` (30 s). Une modification de `alertmanager/alertmanager.yml`
demande `docker compose ... restart alertmanager`. Vérification locale :
`docker run --rm -v "$PWD/monitoring/alertmanager:/c:ro" -w /c --entrypoint amtool prom/alertmanager:v0.34.1 check-config alertmanager.yml`.

## Dashboard de la CI

*CI et livraisons* (`grafana/dashboards/ci.json`) ne lit pas Prometheus mais l'API GitHub, par le
plugin officiel `grafana-github-datasource` (téléchargé au démarrage de Grafana, version épinglée dans
`docker-compose.monitoring.yml`) et la source `GitHub` (`grafana/provisioning/datasources/github.yml`) :

- dernier run de `ci.yml` sur `main`, nombre de runs, réussites, échecs et durées (cycle de facturation
  GitHub en cours) ;
- les 20 derniers runs de la CI, toutes branches, avec un lien vers chacun ;
- les déploiements annoncés à GitHub (staging et production) et les PR mergées sur la période.

Il demande un jeton GitHub **en lecture seule**, dans `GRAFANA_GITHUB_TOKEN` de `staging.env`,
`production.env` ou `.env` (jamais dans le dépôt) :

1. GitHub > *Settings* > *Developer settings* > *Fine-grained tokens* > *Generate new token*.
2. *Resource owner* : `projet-piscine-eadl-enervision` ; *Repository access* : seulement
   `smart-energy-optimizer` ; expiration : fin du projet.
3. *Repository permissions*, toutes en **Read-only** : *Actions*, *Deployments*, *Pull requests*
   (*Metadata* est ajouté d'office). Rien d'autre.
4. Si l'organisation exige une approbation des jetons, un propriétaire de l'organisation la donne.
5. Coller le jeton dans `GRAFANA_GITHUB_TOKEN`, puis recréer Grafana au déploiement suivant, ou à la main :
   `docker compose ... up -d --force-recreate grafana`. Le jeton est relu à chaque démarrage.

Vérifier : *Connections* > *Data sources* > *GitHub* > *Test*, qui doit répondre « Data source is
working ». Sans jeton, ou jeton expiré, la source répond `401` et seul ce dashboard reste en erreur ; les
autres ne dépendent que de Prometheus. Pas d'alerte sur la CI : GitHub notifie déjà les échecs.
Rafraîchissement toutes les 5 minutes, bien en dessous du quota de l'API GitHub (5 000 requêtes par heure
et par jeton).

## Ajouter ou modifier un dashboard

Les dashboards ne se modifient pas dans l'interface (`allowUiUpdates: false`) : le dépôt est la seule
source.

1. Construire ou ajuster le dashboard dans Grafana, puis *Export > Export as JSON*.
2. Dans le JSON : `uid` stable et unique (`enervision-...`), toutes les sources de données sur
   `{"type": "prometheus", "uid": "prometheus"}` (ou `{"type": "grafana-github-datasource", "uid": "github"}`
   pour un dashboard GitHub), pas de variable de source (`${DS_PROMETHEUS}`), pas de
   bloc `__inputs` ni `__requires`.
3. Le déposer dans `grafana/dashboards/` et vérifier :
   `python3 infra/scripts/check-dashboards.py monitoring/grafana/dashboards`.

Les dashboards actuels viennent de grafana.com, adaptés selon ces règles : Node Exporter Full (1860),
Docker monitoring (15798), le dashboard livré avec postgres-exporter et Blackbox Exporter (13659).
Le dashboard des conteneurs s'appuie sur les labels `service` et `container`, créés par la règle
`metric_relabel_configs` du job `cadvisor`. *Tâches planifiées* (`timers.json`) est écrit pour le
projet : état de chaque minuteur, dernier lancement, dernier déclenchement et historique des échecs.

## CI

Le job `monitoring` de `ci.yml` tourne quand un fichier de `monitoring/` change (sortie `monitoring`
de `infra/scripts/changed-modules.sh`) ou qu'un fichier commun change : validation du compose,
`promtool check config` et `test rules`, `amtool check-config` d'Alertmanager, `--config.check` du blackbox, et `check-dashboards.py`. Les
images utilisées sont lues dans `docker-compose.monitoring.yml`.

## Limites connues

- **cAdvisor sous Docker Desktop (WSL2)** : il ne voit pas les conteneurs, le dashboard « Conteneurs »
  reste vide sur un poste Windows. Il fonctionne avec docker-ce sur Debian (VM de staging, EC2).
- **Notifications** : seulement si `TEAMS_WEBHOOK_URL` est renseignée. Si Alertmanager lui-même
  tombe, plus rien n'est envoyé (l'alerte `CibleInjoignable` du job `alertmanager` reste visible dans
  Prometheus et Grafana).
- **postgres-exporter** utilise l'utilisateur de l'application par défaut ; `MONITORING_DB_USER` et
  `MONITORING_DB_PASSWORD` permettent de passer à un utilisateur dédié en lecture seule (rôle
  `pg_monitor`).
- **Dashboard de la CI** : il dépend d'un jeton personnel GitHub, lié à un compte et qui expire (à
  renouveler). Grafana doit pouvoir télécharger le plugin au démarrage (sortie HTTPS, ouverte sur l'EC2).
- **Minuteurs** : node-exporter ne connaît pas l'heure du prochain déclenchement
  (`systemctl list-timers` sur la machine). Sur un poste, le dashboard *Tâches planifiées* reste vide :
  les minuteurs n'y sont pas installés.
- **Rétention** : 15 jours, 5 Go au plus, pour ne pas remplir le disque de l'instance.

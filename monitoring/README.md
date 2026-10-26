# Supervision

Prometheus collecte les métriques de l'hôte, des conteneurs, de la base, de l'API et de l'ETL, et
évalue les règles d'alerte. Grafana les affiche dans des dashboards versionnés ici. La stack est
décrite par `docker-compose.monitoring.yml`, à la racine, qui s'ajoute au compose de l'environnement.

```
monitoring/
  prometheus/prometheus.yml      cibles collectées toutes les 15 s
  prometheus/alerts.yml          règles d'alerte
  prometheus/alerts.test.yml     tests des règles (promtool test rules)
  blackbox/blackbox.yml          façons de sonder les URL (http_2xx, http_frontend)
  grafana/provisioning/          source de données Prometheus et chargement des dashboards
  grafana/dashboards/*.json      dashboards, rangés dans le dossier « EnerVision » de Grafana
```

## Ce qui est surveillé

| Job Prometheus      | Source                                   | Ce qu'on y voit                                               |
|---------------------|------------------------------------------|---------------------------------------------------------------|
| `node`              | node-exporter                            | CPU, mémoire, disque, réseau de l'hôte (EC2 ou VM)            |
| `cadvisor`          | cAdvisor                                 | CPU, mémoire, réseau, disque de chaque conteneur              |
| `postgres`          | postgres-exporter                        | connexions, transactions, cache, verrous de PostgreSQL        |
| `api`               | `/metrics` de l'API                      | requêtes par route et par code, latence, requêtes en cours    |
| `etl`               | `/metrics` de l'ETL (`etl/metrics.py`)   | dernière exécution de chaque traitement, mesure la plus récente |
| `blackbox-http`     | blackbox-exporter                        | `/health` de l'API et de l'ETL répond-il en 2xx, et en combien de temps |
| `blackbox-frontend` | blackbox-exporter                        | même chose pour le frontend                                   |
| `prometheus`        | Prometheus                               | Prometheus lui-même                                           |

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

> **Pas encore déployée automatiquement.** `infra/scripts/update-staging.sh` et
> `.github/workflows/deploy-production.yml` ne lancent que `docker-compose.staging.yml`, avec
> `--remove-orphans` : des conteneurs de supervision démarrés à la main sous le même projet seraient
> supprimés à la mise à jour suivante. Le déploiement de la stack sur les serveurs se fait en ajoutant
> `docker-compose.monitoring.yml` à ces deux commandes.

## Alertes

`prometheus/alerts.yml` : disponibilité (cible injoignable, sonde HTTP en échec, base injoignable),
hôte (disque à 80 et 90 %, mémoire, CPU) et application (erreurs 5xx et latence de l'API, absence de
nouvelle mesure, dernière exécution de l'ETL en échec). Gravité `critical` : service indisponible ;
`warning` : à regarder avant que ça le devienne.

Sans Alertmanager, aucune notification n'est envoyée : les alertes se consultent dans Prometheus
(*Alerts*) et dans Grafana (*Alerting > Alert rules*).

`EtlSansNouvelleMesure` ne sonne que si la base contient des mesures : sans collecteur (production
par défaut), la table est vide et l'alerte reste muette.

Toute nouvelle règle s'accompagne si possible d'un cas dans `alerts.test.yml` :

```bash
cd monitoring/prometheus
docker run --rm -v "$PWD:/w:ro" -w /w --entrypoint promtool prom/prometheus:v3.15.0 test rules alerts.test.yml
```

## Ajouter ou modifier un dashboard

Les dashboards ne se modifient pas dans l'interface (`allowUiUpdates: false`) : le dépôt est la seule
source.

1. Construire ou ajuster le dashboard dans Grafana, puis *Export > Export as JSON*.
2. Dans le JSON : `uid` stable et unique (`enervision-...`), toutes les sources de données sur
   `{"type": "prometheus", "uid": "prometheus"}`, pas de variable de source (`${DS_PROMETHEUS}`), pas de
   bloc `__inputs` ni `__requires`.
3. Le déposer dans `grafana/dashboards/` et vérifier :
   `python3 infra/scripts/check-dashboards.py monitoring/grafana/dashboards`.

Les dashboards actuels viennent de grafana.com, adaptés selon ces règles : Node Exporter Full (1860),
Docker monitoring (15798), le dashboard livré avec postgres-exporter et Blackbox Exporter (13659).
Le dashboard des conteneurs s'appuie sur les labels `service` et `container`, créés par la règle
`metric_relabel_configs` du job `cadvisor`.

## CI

Le job `monitoring` de `ci.yml` tourne quand un fichier de `monitoring/` change (sortie `monitoring`
de `infra/scripts/changed-modules.sh`) ou qu'un fichier commun change : validation du compose,
`promtool check config` et `test rules`, `--config.check` du blackbox, et `check-dashboards.py`. Les
images utilisées sont lues dans `docker-compose.monitoring.yml`.

## Limites connues

- **cAdvisor sous Docker Desktop (WSL2)** : il ne voit pas les conteneurs, le dashboard « Conteneurs »
  reste vide sur un poste Windows. Il fonctionne avec docker-ce sur Debian (VM de staging, EC2).
- **Pas de notification** tant qu'Alertmanager ou un point de contact Grafana n'est pas configuré.
- **postgres-exporter** utilise l'utilisateur de l'application par défaut ; `MONITORING_DB_USER` et
  `MONITORING_DB_PASSWORD` permettent de passer à un utilisateur dédié en lecture seule (rôle
  `pg_monitor`).
- **Rétention** : 15 jours, 5 Go au plus, pour ne pas remplir le disque de l'instance.

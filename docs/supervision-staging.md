# Supervision du staging

Prometheus et Grafana tournent sur la VM de staging (`10.43.43.50`), mais n'écoutent que sur
`127.0.0.1` : ils ne sont pas joignables directement depuis le réseau de l'école. Chaque développeur
ouvre **son propre tunnel SSH** depuis son poste, le temps de la consultation, et le referme ensuite.
Rien n'est à installer sur le poste, et personne ne lance ni n'arrête la supervision pour les autres.

Ce que surveille la stack, les alertes et la façon de modifier un dashboard :
[`monitoring/README.md`](../monitoring/README.md).

## Une seule fois : activer la supervision sur la VM

À faire par la personne qui administre la VM, si ce n'est pas déjà le cas (`docker ps` montre alors
`prometheus` et `grafana`).

Dans `/etc/enervision/staging.env`, en root :

```bash
COMPOSE_PROFILES=apps,collector,monitoring     # garder les profils déjà présents, ajouter monitoring
GRAFANA_ADMIN_PASSWORD=...                     # openssl rand -base64 24 | tr -d '/+='
```

Le minuteur `update-staging.timer` lance la supervision à son passage suivant (2 minutes au plus).
Ne pas la démarrer à la main : `update-staging.sh` utilise `--remove-orphans` et supprimerait au
passage suivant les conteneurs qu'il ne connaît pas. Détails : [`deploiement-staging.md`](deploiement-staging.md).

Grafana ne lit `GRAFANA_ADMIN_PASSWORD` qu'à son premier démarrage (volume `grafana_data` vide). Si la
ligne a été ajoutée ou changée après coup, réaligner le mot de passe sur celui de `staging.env`, sur la
VM :

```bash
cd /opt/enervision
docker compose -f docker-compose.staging.yml -f docker-compose.monitoring.yml \
  --env-file /etc/enervision/staging.env \
  exec grafana grafana cli admin reset-admin-password "<valeur de GRAFANA_ADMIN_PASSWORD>"
```

## Chaque fois : ouvrir sa session

Prérequis : être sur le réseau de l'école (ou son VPN) et avoir sa clé SSH autorisée sur la VM
(la même qu'utilisée pour l'administrer).

Depuis le poste (terminal WSL ou PowerShell, **pas** depuis la VM) :

```bash
ssh -N -L 3001:127.0.0.1:3000 -L 9091:127.0.0.1:9090 root@10.43.43.50
```

- `-N` : n'ouvre pas de shell, garde seulement le tunnel. Laisser la fenêtre ouverte pendant la
  consultation ; `Ctrl+C` le referme.
- Ports locaux 3001 et 9091, et pas 3000 et 9090 : ces derniers sont ceux de la supervision du poste
  (`docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d`). Si elle tourne,
  c'est elle qui répondrait, avec les métriques du poste au lieu de celles du staging. Même logique
  que MLflow (5001 pour le staging, voir [`ml/README.md`](../ml/README.md)).
- Sous WSL2, le navigateur Windows atteint directement `localhost` du tunnel ouvert dans WSL.

Puis, dans le navigateur :

| Outil      | Adresse               | Où regarder                                                   |
|------------|-----------------------|---------------------------------------------------------------|
| Grafana    | http://localhost:3001 | *Dashboards > EnerVision* : hôte, conteneurs, base, sondes HTTP |
| Prometheus | http://localhost:9091 | *Status > Targets* (toutes les cibles `UP`), *Alerts*          |

### Se connecter à Grafana

Utilisateur `admin`. Le mot de passe est celui de `staging.env`, sur la VM (il n'est écrit nulle part
ailleurs, ne pas le recopier dans un canal de discussion) :

```bash
ssh root@10.43.43.50 grep GRAFANA_ADMIN_PASSWORD /etc/enervision/staging.env
```

Plusieurs développeurs peuvent avoir un tunnel ouvert en même temps : chacun a sa session, rien n'est
partagé à part Grafana et Prometheus eux-mêmes.

Pour ne pas retaper la commande, dans `~/.ssh/config` du poste :

```
Host enervision-staging-monitoring
    HostName 10.43.43.50
    User root
    LocalForward 3001 127.0.0.1:3000
    LocalForward 9091 127.0.0.1:9090
```

puis `ssh -N enervision-staging-monitoring`.

## Dépannage

| Symptôme | Cause probable et solution |
|----------|----------------------------|
| `ssh: connect to host 10.43.43.50 port 22: Connection timed out` | Pas sur le réseau de l'école ou son VPN. |
| `Permission denied (publickey)` | Clé SSH non autorisée sur la VM : la faire ajouter par l'administrateur. |
| `bind [127.0.0.1]:3001: Address already in use` | Un autre tunnel est déjà ouvert sur le poste : le réutiliser, ou changer le port local (`-L 3002:127.0.0.1:3000`). |
| La page ne charge pas, le tunnel est ouvert | La supervision n'est pas active sur la VM : `docker ps` sur la VM doit montrer `grafana` ; sinon voir « Une seule fois ». |
| Grafana refuse le mot de passe de `staging.env` | Grafana avait démarré avant que la ligne soit ajoutée ou changée : réaligner le mot de passe (voir « Une seule fois »). |
| `channel 2: open failed: connect failed: Connection refused` dans le terminal | Même cause : rien n'écoute sur le port 3000 ou 9090 de la VM. |
| Dashboard « Conteneurs » vide | Sur le staging, cAdvisor fonctionne ; vérifier la cible `cadvisor` dans *Status > Targets*. (Il reste vide seulement sur un poste Docker Desktop.) |
| Une cible est `DOWN` | Le service correspondant est arrêté ou en erreur : `docker compose ... logs <service>` sur la VM. |

## Et la production ?

Même stack, sur l'instance AWS, activée par `monitoring` dans `COMPOSE_PROFILES` de
`/etc/enervision/production.env` (avec `GRAFANA_ADMIN_PASSWORD`) et appliquée au déploiement suivant.
L'instance n'a pas de SSH : la session passe par une redirection de port Session Manager, depuis un
poste configuré ([`aws-poste-developpeur.md`](aws-poste-developpeur.md)) :

```bash
aws ssm start-session \
  --target "$(terraform -chdir=infra/terraform/aws output -raw instance_id)" \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["3000"],"localPortNumber":["3002"]}'
```

puis http://localhost:3002 (port local différent de celui du staging, pour pouvoir ouvrir les deux).

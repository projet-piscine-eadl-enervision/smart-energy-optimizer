# Supervision de la production

Prometheus et Grafana tournent sur l'instance EC2 de production, mais n'écoutent que sur `127.0.0.1` :
ils ne sont pas joignables depuis Internet et aucun port n'est ouvert pour eux dans le groupe de
sécurité. L'instance n'a pas de SSH : chaque développeur ouvre **sa propre redirection de port
Session Manager** (AWS SSM) depuis son poste, le temps de la consultation, puis la referme.

La collecte et l'évaluation des alertes tournent en continu, que quelqu'un soit connecté ou non : la
redirection sert seulement à consulter. Ce que surveille la stack et la façon de modifier un
dashboard : [`monitoring/README.md`](../monitoring/README.md). Même chose pour le staging :
[`supervision-staging.md`](supervision-staging.md).

## Une seule fois : activer la supervision sur l'instance

À faire par une personne qui administre la production, si ce n'est pas déjà le cas.

1. Ouvrir un terminal sur l'instance, depuis la racine du dépôt :

   ```bash
   aws ssm start-session --target "$(terraform -chdir=infra/terraform/aws output -raw instance_id)"
   sudo -i
   ```

2. Dans `/etc/enervision/production.env` :

   ```bash
   COMPOSE_PROFILES=apps,collector,mlflow,monitoring   # garder les profils déjà présents, ajouter monitoring
   GRAFANA_ADMIN_PASSWORD=...                          # openssl rand -base64 24 | tr -d '/+=' ; différent du staging
   TEAMS_WEBHOOK_URL=https://...                       # alertes dans Teams, voir monitoring/README.md
   ```

   `NG_ALLOWED_HOSTS` doit aussi contenir `localhost` (en plus du nom CloudFront) : la sonde du
   frontend se présente sous ce nom. Sans lui, la cible `blackbox-frontend` reste en échec.

3. Déployer : la supervision démarre au déploiement suivant de `deploy-production.yml`, qui ajoute
   `docker-compose.monitoring.yml` quand `monitoring` est dans `COMPOSE_PROFILES`. Sans attendre une
   release, relancer la version en place : *Actions > Déploiement en production > Run workflow*,
   depuis `main`, avec le tag actuellement déployé (voir [`mise-en-production.md`](mise-en-production.md)).

Ne pas démarrer la supervision à la main sur l'instance : le déploiement utilise `--remove-orphans`
et supprimerait au passage suivant les conteneurs qu'il ne connaît pas. Si `monitoring` est présent
sans `GRAFANA_ADMIN_PASSWORD`, le déploiement s'arrête avec un message explicite.

Les alertes arrivent dans le canal Teams dont le workflow a fourni `TEAMS_WEBHOOK_URL`, préfixées par
`[production]` : c'est elles qui assurent la surveillance continue, sans que personne ait à ouvrir
Grafana (création du workflow et test : « Notifications Teams » de
[`monitoring/README.md`](../monitoring/README.md)). Si Alertmanager tournait déjà quand l'URL a été
ajoutée ou changée, le recréer, sur l'instance en root :
`docker compose -f docker-compose.staging.yml -f docker-compose.monitoring.yml --env-file /etc/enervision/production.env up -d --force-recreate alertmanager`
(avec `IMAGE_TAG` de la version en place et `COMPOSE_PROJECT_NAME=enervision`, comme le déploiement).

Grafana ne lit `GRAFANA_ADMIN_PASSWORD` qu'à son premier démarrage (volume `grafana_data` vide). Si la
ligne est changée ensuite, réaligner le mot de passe, sur l'instance en root :

```bash
cd /opt/enervision
docker compose -f docker-compose.staging.yml -f docker-compose.monitoring.yml \
  --env-file /etc/enervision/production.env \
  exec grafana grafana cli admin reset-admin-password "<valeur de GRAFANA_ADMIN_PASSWORD>"
```

## Prérequis sur le poste

Ceux de [`aws-poste-developpeur.md`](aws-poste-developpeur.md) : AWS CLI, `session-manager-plugin`,
profil SSO sur le compte du projet, et Terraform initialisé dans `infra/terraform/aws` (pour lire
l'identifiant de l'instance). Les commandes se lancent depuis la racine du dépôt, dans WSL ou sous
Linux.

```bash
aws sso login                     # si la session a expiré
aws sts get-caller-identity       # vérifie qu'on est bien connecté au compte du projet
```

## Chaque fois : ouvrir sa session

Une redirection Session Manager ne transporte qu'un port : un terminal pour Grafana, un autre pour
Prometheus si besoin. Laisser chaque terminal ouvert pendant la consultation, `Ctrl+C` le referme.

Grafana (port 3000 de l'instance, 3002 du poste) :

```bash
aws ssm start-session \
  --target "$(terraform -chdir=infra/terraform/aws output -raw instance_id)" \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["3000"],"localPortNumber":["3002"]}'
```

Prometheus (port 9090 de l'instance, 9092 du poste) :

```bash
aws ssm start-session \
  --target "$(terraform -chdir=infra/terraform/aws output -raw instance_id)" \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["9090"],"localPortNumber":["9092"]}'
```

Attendre `Waiting for connections...`, puis, dans le navigateur (sous WSL2, le navigateur Windows
atteint directement `localhost`) :

| Outil      | Adresse               | Où regarder                                                     |
|------------|-----------------------|-----------------------------------------------------------------|
| Grafana    | http://localhost:3002 | *Dashboards > EnerVision* : hôte, conteneurs, base, sondes HTTP |
| Prometheus | http://localhost:9092 | *Status > Targets* (toutes les cibles `UP`), *Alerts*           |

Alertmanager (alertes en cours, mise en sourdine pendant une intervention) : même commande avec
`{"portNumber":["9093"],"localPortNumber":["9094"]}`, puis http://localhost:9094.

Ports locaux choisis pour ne rien masquer : 3000 et 9090 sont ceux de la supervision du poste, 3001 et
9091 ceux du tunnel du staging. Les trois peuvent être ouverts en même temps. Plusieurs développeurs
peuvent aussi avoir leur redirection ouverte simultanément.

### Se connecter à Grafana

Utilisateur `admin`. Le mot de passe est celui de `production.env`, sur l'instance (il n'est écrit
nulle part ailleurs, ne pas le recopier dans un canal de discussion) :

```bash
aws ssm start-session --target "$(terraform -chdir=infra/terraform/aws output -raw instance_id)"
sudo grep GRAFANA_ADMIN_PASSWORD /etc/enervision/production.env   # sudo : on arrive en ssm-user
exit
```

## Dépannage

| Symptôme | Cause probable et solution |
|----------|----------------------------|
| `Token has expired` ou `The SSO session ... has expired` | `aws sso login`. |
| `SessionManagerPlugin is not found` | Installer le plugin : voir [`aws-poste-developpeur.md`](aws-poste-developpeur.md). |
| `terraform output` vide ou en erreur | Terraform pas initialisé dans `infra/terraform/aws` (`terraform init -backend-config=backend.hcl`, ne modifie pas l'infra), ou remplacer la sous-commande par l'identifiant de l'instance (variable `AWS_INSTANCE_ID` de l'environnement GitHub `production`). |
| `AccessDeniedException` sur `StartSession` | Le compte SSO n'a pas les droits sur le compte du projet : demander l'accès. |
| `Waiting for connections...` puis la page ne répond pas | Rien n'écoute sur le port de l'instance : la supervision n'est pas activée ou pas encore déployée (voir « Une seule fois »). |
| `Port 3002 is already in use` (ou 9092) | Une redirection est déjà ouverte sur le poste : la réutiliser, ou changer `localPortNumber`. |
| Grafana refuse le mot de passe de `production.env` | Grafana avait démarré avant que la ligne soit ajoutée ou changée : réaligner le mot de passe (voir « Une seule fois »). |
| Cible `blackbox-frontend` en échec | `localhost` absent de `NG_ALLOWED_HOSTS` dans `production.env`. |
| Une autre cible est `DOWN` | Le service correspondant est arrêté ou en erreur : sur l'instance, `docker compose ... logs <service>`. |

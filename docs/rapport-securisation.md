# Rapport de sécurisation

Ce que nous avons mis en place pour sécuriser la plateforme, avec la commande qui le prouve et son résultat. Les mesures datent du 26/10/2026 sur `main` à `fe0793b`. Ce qui reste ouvert, avec son ticket, est dans l'[audit du dépôt](audit-depot.md) ; la politique de signalement est dans [`SECURITY.md`](../SECURITY.md).

Les commandes se rejouent depuis la racine du dépôt. Les extraits de sortie sont raccourcis, `<dépôt>` désigne le dépôt GitHub du projet et les identifiants du compte AWS sont masqués.

## Authentification de l'application

L'API émet des jetons JWT (`PyJWT`), stocke les mots de passe hachés en bcrypt et protège toutes les routes de données. En production, la documentation interactive est fermée et le CORS est limité à l'origine du frontend. Un compte inconnu coûte le même calcul de hachage qu'un compte connu, ce qui empêche de deviner quels comptes existent d'après le temps de réponse.

```console
$ git grep -n "CurrentUser" -- api/app/api/routes | grep "def "
api/app/api/routes/auth.py:59:async def me(current_user: CurrentUser):
api/app/api/routes/predictions.py:18:async def get_peak_predictions(current_user: CurrentUser, db: DbSession):
api/app/api/routes/recommendations.py:11:async def get_recommendations(current_user: CurrentUser, db: DbSession):
$ git grep -n -E "openapi_url|allow_origins" -- api/app/main.py
api/app/main.py:31:        openapi_url=None if is_production else "/openapi.json",
api/app/main.py:37:        allow_origins=[settings.FRONTEND_ORIGIN],
```

Le fichier d'environnement de la production fixe `APP_ENV=production` (relevé du 26/10 sur l'instance par Session Manager, ligne `APP_ENV` seule), ce qui ferme `/docs`, `/redoc` et `/openapi.json`. Les accès sans jeton, avec un jeton invalide, ou avec un mot de passe trop long (plus de 72 octets, refusé en 422 au lieu d'une erreur 500) sont couverts par `api/tests/test_auth.py`.

Limites : `/auth/register` est ouvert à tous et `/auth/login` n'a pas de limite d'essais.

## Secrets

Aucun secret n'est dans Git. Les secrets de l'infrastructure vivent dans GitHub, ceux des services dans des fichiers d'environnement hors dépôt sur les machines.

```console
$ git log --all --diff-filter=A --name-only --format= -- '*.env' '*.tfvars' 'backend.hcl' '*.tfstate' '*.pem' | sort -u
$                                  # aucune ligne : jamais ajouté, dans aucune branche
$ gh api repos/<dépôt>/actions/secrets --jq '.secrets[].name'
SONAR_TOKEN
$ gh api repos/<dépôt>/environments/production/secrets --jq '.secrets[].name'
AWS_DEPLOY_ROLE_ARN
AWS_INSTANCE_ID
AWS_REGION
```

GitHub analyse les secrets (`secret_scanning=enabled`) et refuse les pushs qui en contiennent (`secret_scanning_push_protection=enabled`) ; le nombre d'alertes ouvertes est 0. Le hook `detect-private-key` s'exécute avant chaque commit, et Trivy cherche aussi des secrets à chaque PR. La clé de signature des jetons de l'API fait 64 caractères en staging comme en production (seule la longueur est relevée, par `awk` sur le fichier d'environnement, jamais la valeur). Aucune clé AWS n'est stockée : le déploiement s'authentifie par OIDC (voir plus bas).

## Chaîne de livraison

Une règle protège `main` : une approbation obligatoire, résolution des fils de discussion, contrôle `ci-ok` requis et branche à jour, fusion par *squash* uniquement, ni suppression ni réécriture de l'historique. Seule l'App `enervision-release` contourne la règle, uniquement par PR.

```console
$ gh api repos/<dépôt>/rulesets/<id>      # champs utiles
rules: deletion, non_fast_forward, pull_request, required_status_checks
required_approving_review_count: 1     required_review_thread_resolution: true
required_status_checks: ci-ok (strict)     allowed_merge_methods: ["squash"]
bypass: Integration (mode pull_request)
$ gh api repos/<dépôt>/actions/permissions/workflow
{"default_workflow_permissions":"read","can_approve_pull_request_reviews":false}
```

L'environnement GitHub `production` exige l'approbation d'un relecteur et ne déploie que depuis une branche autorisée. L'image mise en production est celle qui a été recettée au staging : elle est promue, pas reconstruite. Les images sont construites par la CI et scannées par Trivy, et chaque version publie le SBOM (CycloneDX) de ses images. Trois actions sont épinglées sur un commit précis : Trivy (v0.35.0, version sûre retenue après la compromission de cette action en mars 2026), SonarQube et `configure-aws-credentials` ; les autres le sont par version majeure.

## Analyse du code, des dépendances et de l'infrastructure

Trivy bloque une PR sur toute vulnérabilité haute ou critique corrigeable, sur un secret ou sur une mauvaise configuration. Mêmes commandes et même version que la CI :

```console
$ docker run --rm -v "$PWD":/src aquasec/trivy:0.69.3 config --severity HIGH,CRITICAL /src/infra/terraform
Target         Type       Misconfigurations
aws            terraform  0
aws/main.tf    terraform  0
aws/public.tf  terraform  0
aws/s3.tf      terraform  0
$ docker run --rm -v "$PWD":/src aquasec/trivy:0.69.3 fs --scanners vuln,secret,misconfig \
    --severity HIGH,CRITICAL --ignore-unfixed --skip-dirs node_modules /src
cibles : 13    constats HIGH/CRITICAL corrigeables : 0
$ for m in api etl ml; do pip-audit -r $m/requirements.txt --no-deps; done
No known vulnerabilities found     (pour les trois modules)
$ (cd frontend && npm audit --omit=dev)
found 0 vulnerabilities
```

Les exceptions du code Terraform sont écrites dans les fichiers (`#trivy:ignore:AWS-0010`, `-0011` et `-0013` dans `public.tf`) avec leur motif : pas de journaux d'accès ni de WAF sur CloudFront, et pas de version minimale de TLS réglable sans nom de domaine. SonarQube Cloud analyse le code de chaque PR ; la porte exige 80 % de couverture sur le code neuf et le job `sonar` est vert sur `fe0793b`.

Les images publiées sont scannées sur `main`, le rapport va dans l'onglet *Security* du dépôt. Deux alertes hautes restent ouvertes, sur l'image `db` : elles viennent du binaire de l'outil de migration `dbmate`, sans correctif disponible, et l'outil ne tourne qu'au déploiement. Le scan des images ne bloque pas encore (#146). Les dépendances sont mises à jour par Dependabot chaque lundi (pip, npm, Docker, Actions).

Dans les images, les cinq Dockerfiles finissent par un utilisateur non root. Les images `etl` et `ml` ne contiennent que le code exécuté, en lecture seule pour l'utilisateur de l'application ; `pip` est retiré des images Python, `npm` et `yarn` de l'image de production du frontend.

## Réseau et droits AWS

Le code Terraform (`infra/terraform/aws`) décrit l'infrastructure de production. Le port 4000 de l'instance n'est ouvert qu'aux serveurs de CloudFront, et il n'y a pas de SSH :

```hcl
# infra/terraform/aws/public.tf
resource "aws_vpc_security_group_ingress_rule" "frontend_cloudfront" {
  description    = "Frontend (port 4000), depuis CloudFront uniquement"
  prefix_list_id = data.aws_ec2_managed_prefix_list.cloudfront.id
  from_port      = 4000
  to_port        = 4000
  ip_protocol    = "tcp"
}
```

Le déploiement n'utilise aucune clé AWS durable. GitHub présente un jeton OIDC ; le rôle de déploiement n'accepte que les jobs de l'environnement `production` (donc après approbation) et ne peut que lancer une commande shell sur cette instance et lire son résultat :

```hcl
# infra/terraform/aws/main.tf (extraits)
"token.actions.githubusercontent.com:aud" = ["sts.amazonaws.com"]
"token.actions.githubusercontent.com:sub" = ["<organisation/dépôt>:environment:production"]
actions = ["ssm:SendCommand"]   # sur cette instance et le document AWS-RunShellScript
actions = ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations"]
```

L'instance impose IMDSv2 (`http_tokens = "required"`), son disque est chiffré, et le bucket S3 est privé, chiffré (SSE-S3) et bloque tout accès public (`block_public_acls`, `ignore_public_acls`, `block_public_policy`, `restrict_public_buckets`). Les commandes passent par Systems Manager.

### État réel de l'infrastructure

Relevé du 26/10 avec le compte AWS du projet, par des commandes en lecture seule (`<compte>` et `<id>` masquent le numéro du compte et des identifiants numériques). Il correspond au code ci-dessus.

```console
$ aws ec2 describe-instances --instance-ids <instance> --query '...MetadataOptions'
"HttpTokens": "required"          # IMDSv2 imposé
$ aws ec2 describe-security-groups --group-ids <groupe> --query '...{entree,sortie}'
entrée : tcp 4000, liste d'adresses de CloudFront ("Frontend (port 4000), depuis CloudFront uniquement"), aucune plage IP
sortie : tcp 80 et tcp 443 vers 0.0.0.0/0
$ aws ec2 describe-volumes --volume-ids <volume> --query '[].{chiffre,type,taille}'
{"chiffre": true, "type": "gp3", "taille": 64}
$ aws cloudfront list-distributions --query '...{viewer,origine}'
{"viewer": "redirect-to-https", "origine": "http-only"}
```

Rôle de déploiement GitHub (`enervision-production-deploy`) : aucune politique gérée, une seule politique en ligne.

```console
$ aws iam get-role --role-name enervision-production-deploy --query 'Role.AssumeRolePolicyDocument'
Federated : arn:aws:iam::<compte>:oidc-provider/token.actions.githubusercontent.com
Action    : sts:AssumeRoleWithWebIdentity
aud       : sts.amazonaws.com
sub       : repo:<organisation>@<id>/<dépôt>@<id>:environment:production
$ aws iam get-role-policy --role-name enervision-production-deploy --policy-name enervision-production-deploy
ssm:SendCommand       sur  document/AWS-RunShellScript et instance/<instance>
ssm:ListCommandInvocations, ssm:GetCommandInvocation   sur *
```

Le `sub` contient les identifiants numériques de l'organisation et du dépôt, ce qui empêche un dépôt qui reprendrait leur nom d'assumer le rôle.

Rôle de l'instance (`enervision-production-instance`), c'est-à-dire ce que reçoit un conteneur de la machine : la politique gérée `AmazonSSMManagedInstanceCore` (agent Session Manager) et une politique en ligne limitée au bucket de données.

```console
$ aws iam get-role-policy --role-name enervision-production-instance --policy-name enervision-production-instance-s3
s3:ListBucket                 sur  enervision-production-data-<compte>
s3:GetObject, s3:PutObject    sur  .../etl/*  et  .../backups/*
s3:GetObject                  sur  .../dvc/*
```

Aucun droit de suppression, et en dehors de Session Manager aucun accès à un autre service ni à un autre bucket.

Buckets S3 : le bucket de données et celui du state Terraform sont chiffrés (`SSEAlgorithm: AES256`) et bloquent tout accès public (`BlockPublicAcls`, `IgnorePublicAcls`, `BlockPublicPolicy`, `RestrictPublicBuckets` à `true`).

Reproductibilité : `terraform plan` sur le code de `main`, avec le state partagé, ne propose aucune création, modification ni suppression.

```console
$ cd infra/terraform/aws && terraform init -backend-config=backend.hcl && terraform plan
aws_instance.main: Refreshing state... [id=<instance>]
aws_cloudfront_distribution.site: Refreshing state... [id=<distribution>]
(...)
Note: Objects have changed outside of Terraform
  # aws_instance.main has changed
  ~ public_ip = "<ancienne adresse>" -> "<nouvelle adresse>"
Changes to Outputs:
  ~ instance_public_ip = "<ancienne adresse>" -> "<nouvelle adresse>"
```

Les 16 ressources du code existent telles qu'il les décrit. Le seul écart est l'adresse IP publique lue sur l'instance : l'adresse élastique du projet y est bien associée (`aws ec2 describe-addresses` renvoie l'instance et l'adresse que Terraform lit désormais), le state gardait une adresse antérieure. C'est une valeur lue et non un réglage : aucun `apply` n'est nécessaire. Le `plan` est en lecture seule ; l'`apply` reste une décision d'équipe.

Limites : le trafic entre CloudFront et l'instance est en HTTP (pas de nom de domaine ni de certificat à nous) ; le bucket n'est ni versionné ni chiffré par une clé KMS (choix de coût pour un projet de deux semaines).

## VM de staging

La VM de l'école héberge le staging. Elle n'est joignable que depuis le réseau de l'école. Relevé du 26/10, en tant que `root` :

```console
# sshd -T | grep -E '^(permitrootlogin|passwordauthentication|pubkeyauthentication)'
permitrootlogin yes
pubkeyauthentication yes
passwordauthentication yes
# stat -c '%a %U %n' /etc/enervision/staging.env
600 root /etc/enervision/staging.env
# awk -F= '/^SECRET_KEY=/{print "SECRET_KEY : " length($2) " caractères"}' /etc/enervision/staging.env
SECRET_KEY : 64 caractères
# ss -tlnp      # ports en écoute, colonnes réduites
0.0.0.0:4000   frontend (docker-proxy)
0.0.0.0:8000   API (docker-proxy)
127.0.0.1:5000 MLflow (docker-proxy)
127.0.0.1:25   messagerie locale
*:22           sshd
```

Le fichier d'environnement, qui contient les secrets, n'est lisible que par `root`, et la clé de signature des jetons fait 64 caractères. MLflow n'écoute que sur la boucle locale, on y accède par tunnel SSH. L'ETL ne publie aucun port. Les ports 4000 et 8000 sont ouverts sur le réseau de l'école : la recette lit la version sur `:8000/health`.

Limite : la VM accepte la connexion SSH de `root` et par mot de passe. Nous ne gérons pas sa configuration (machine de l'école), mais c'est le point à restreindre en premier (clé seule, `PermitRootLogin no`) si la VM sert au-delà de la démonstration.

## Base de données

Les migrations (dbmate) créent un rôle par module, `enervision_api`, `enervision_etl` et `enervision_ml`, avec des droits propres à chacun. Le test `ml/tests/test_data_db.py` exécute les requêtes du module ML avec ce rôle, et la CI le rejoue sur une base TimescaleDB migrée. Limite : ces rôles n'ont pas encore de droit de connexion, les services se connectent donc avec le compte propriétaire (#145).

## Ce qui reste

Le détail, hiérarchisé, est dans l'[audit du dépôt](audit-depot.md). Les écarts les plus visibles : comptes de connexion par module (#145), scan des images bloquant (#146). Le scan dynamique (#149, OWASP ZAP), la notification des alertes de supervision (#150) et la limite d'essais de connexion (#215) sont livrés.

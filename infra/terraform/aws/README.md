# Terraform : production AWS

Infrastructure de production d'EnerVision, **appliquée** dans le compte AWS du projet
(`eu-west-3`). Le state est partagé dans S3 : toute l'équipe travaille sur la même infra.

Contexte général (environnements, accès, secrets) : [`infra/README.md`](../../README.md).
Préparer son poste (SSO, outils) : [`docs/aws-poste-developpeur.md`](../../../docs/aws-poste-developpeur.md).

## Ressources gérées

| Ressource | Nom | Détail |
|---|---|---|
| `aws_instance.main` | `enervision-production` | Debian 13 officielle, `t3.large`, disque racine 64 Go gp3 **chiffré**, IMDSv2 obligatoire |
| `aws_security_group.instance` | `enervision-production-instance` | sortie TCP 80 et 443 vers Internet ; **une seule entrée** : voir la ligne suivante |
| `aws_vpc_security_group_ingress_rule.frontend_cloudfront` | — | port 4000 (frontend), depuis la liste d'adresses de CloudFront maintenue par AWS, et rien d'autre |
| `aws_vpc_security_group_ingress_rule.api` | — | port 8000, seulement si `api_ingress_cidrs` est renseigné (vide : l'API n'est pas ouverte, le site la joint par le frontend) |
| `aws_eip.instance` | `enervision-production` | IP Elastic : adresse fixe de l'instance, par laquelle CloudFront la joint |
| `aws_cloudfront_distribution.site` | `EnerVision production` | HTTPS en `https://<id>.cloudfront.net`, sans cache, origine HTTP sur le port 4000 de l'instance (`site_url` en sortie) |
| `aws_s3_bucket.data` + chiffrement, blocage public, cycle de vie | `enervision-production-data-<compte>` | données du projet, privé et chiffré (SSE-S3) : préfixes `dvc/` (remote DVC de production), `etl/` et `backups/` (30 jours) ; `force_destroy` activé |
| `aws_iam_role_policy.instance_s3` | `enervision-production-instance-s3` | l'instance lit et écrit `etl/` et `backups/`, lit `dvc/`, sans suppression |
| `aws_iam_role.instance` + instance profile | `enervision-production-instance` | politique `AmazonSSMManagedInstanceCore` : agent SSM, Session Manager |
| `aws_iam_openid_connect_provider.github` | — | fournisseur OIDC de GitHub (un seul possible par compte) |
| `aws_iam_role.deploy` + politique | `enervision-production-deploy` | assumable par OIDC depuis l'environnement GitHub `production` ; `ssm:SendCommand` sur **cette instance** et le document `AWS-RunShellScript`, lecture des résultats |

L'instance est dans le **VPC par défaut** du compte. Son IP Elastic lui sert à **sortir** (GHCR,
dépôts Debian, SSM, API mock) et à être jointe par CloudFront. Seul le port 4000 est ouvert en
entrée, aux adresses de CloudFront : ni l'API (8000), ni l'ETL, ni la base ne sont joignables
depuis Internet. L'administration passe par SSM, sans SSH.

**Exposition.** Internet atteint CloudFront en HTTPS (certificat `*.cloudfront.net`), qui transmet
à l'instance en HTTP sur le port 4000 : le frontend sert le site et transmet `/api/` à l'API
(`API_UPSTREAM`). Limites connues : le trafic entre CloudFront et l'instance n'est pas chiffré, et
il n'y a pas de nom de domaine. Pour passer plus tard sur un domaine : certificat ACM en
`us-east-1`, `aliases` sur la distribution et Route 53.

**Hors Terraform**, créés une fois à la main : le bucket du state
(`enervision-tfstate-dreamteam2026`), IAM Identity Center et l'alerte de budget.

## Fichiers

| Fichier | Contenu |
|---|---|
| `versions.tf` | Terraform ≥ 1.10, provider AWS `~> 6.0`, backend S3 partiel, tags par défaut |
| `variables.tf` | région, réseau, type d'instance, OIDC GitHub… (voir plus bas) |
| `main.tf` | instance, groupe de sécurité, rôles IAM, fournisseur OIDC |
| `public.tf` | IP Elastic, entrée du port 4000 pour CloudFront, distribution CloudFront |
| `s3.tf` | bucket de données, chiffrement, cycle de vie et droits de l'instance |
| `outputs.tf` | `instance_id`, `deploy_role_arn`, IP, AMI, `site_url`, `data_bucket` |
| `user_data.sh` | premier démarrage : Docker + Compose, agent SSM, clone du dépôt dans `/opt/enervision`, dossier `/etc/enervision` |
| `backend.hcl.example` | modèle de `backend.hcl` (non versionné) |
| `terraform.tfvars.example` | modèle de `terraform.tfvars` (non versionné) |
| `.terraform.lock.hcl` | versions exactes des providers : **à commiter** |

## Utilisation

Prérequis : poste préparé et `aws sts get-caller-identity` qui fonctionne
([`docs/aws-poste-developpeur.md`](../../../docs/aws-poste-developpeur.md)).

```bash
cd infra/terraform/aws
cp backend.hcl.example backend.hcl            # bucket : enervision-tfstate-dreamteam2026
# terraform.tfvars : à récupérer en message privé (vpc_id, subnet_id)
terraform init -backend-config=backend.hcl
terraform plan                                # doit afficher "No changes."
```

Pour une modification :

```bash
terraform plan -out=tfplan      # relire : + création, ~ modification, - suppression, -/+ remplacement
terraform apply tfplan          # applique exactement le plan relu
```

### Règles de l'équipe

- `plan` : autant que nécessaire, il ne modifie rien.
- `apply` : **annoncé à l'équipe**, depuis une branche **à jour avec `main`**, après relecture du
  plan, puis PR rapide pour que `main` reflète ce qui tourne sur AWS.
- Ne **jamais** appliquer un plan qui contient `aws_instance.main must be replaced` ou
  `forces replacement` sans l'avoir décidé : il détruit la VM de prod.
- `Error acquiring the state lock` : quelqu'un d'autre fait un `plan` ou un `apply`, attendre.
- Ne jamais commiter `backend.hcl`, `*.tfvars`, `*.tfstate*`, `tfplan`, `.terraform/`.

## Points d'attention (déjà rencontrés)

**Nouvelle image Debian = remplacement de l'instance.** L'AMI est cherchée avec
`most_recent = true`. Quand Debian publie une nouvelle image, Terraform voudrait remplacer
l'instance. C'est neutralisé par :

```hcl
lifecycle {
  ignore_changes = [ami, user_data]
}
```

Le système se met à jour par `apt` sur la VM. Pour repartir volontairement sur une image neuve :
`terraform apply -replace=aws_instance.main` (VM recréée : refaire la *mise en route* ci-dessous).

**`user_data.sh` ne s'exécute qu'au premier démarrage.** Le modifier n'a aucun effet sur
l'instance existante. Ce qui doit être corrigé sur la VM en place se fait par Session Manager,
et se reporte dans le script pour la prochaine création.

**Format du `sub` OIDC.** L'organisation GitHub utilise le format **immuable** (noms suivis
des identifiants numériques). La condition du rôle `deploy` s'appuie donc sur
`github_oidc_sub_prefix`, pas sur le nom du dépôt. Pour vérifier :

```bash
gh api repos/projet-piscine-eadl-enervision/smart-energy-optimizer/actions/oidc/customization/sub
```

Si le `sub` ne correspond pas, le workflow échoue avec
`Not authorized to perform sts:AssumeRoleWithWebIdentity`. **À revérifier après tout renommage
du dépôt** (il s'appelait `enervision` avant `smart-energy-optimizer`).

**Nom des images GHCR.** Les workflows publient sous `ghcr.io/<org>/<dépôt>/…`
(`github.repository`). Le déploiement passe ce préfixe à `docker compose` par `IMAGE_PREFIX` :
après un renommage du dépôt, vérifier qu'aucun ancien nom ne reste écrit en dur dans
`docker-compose.staging.yml`.

**Un seul fournisseur OIDC GitHub par compte.** S'il existe déjà (autre projet dans le même
compte), mettre `create_github_oidc_provider = false`.

**Sortie limitée aux ports 80 et 443.** Un service externe sur un autre port (API mock sur
`:8080`, par exemple) n'est pas joignable sans une règle `egress` supplémentaire.

## Variables

| Variable | Défaut | Rôle |
|---|---|---|
| `region` | `eu-west-3` | région AWS |
| `project`, `environment` | `enervision`, `production` | noms (`enervision-production-…`) et tags |
| `vpc_id`, `subnet_id` | *(aucun)* | VPC et sous-réseau par défaut du compte, dans `terraform.tfvars` |
| `instance_type` | `t3.large` | 8 Go de mémoire pour base, API, ETL et frontend |
| `root_volume_gb` | `64` | taille du disque |
| `api_ingress_cidrs` | `[]` | CIDR autorisés sur le port 8000 ; vide = l'API n'est pas ouverte (le site passe par CloudFront) |
| `github_oidc_sub_prefix` | `repo:projet-piscine-eadl-enervision@344791702/enervision@1425243299` | préfixe du `sub` OIDC (format immuable) |
| `create_github_oidc_provider` | `true` | créer le fournisseur OIDC |

## Sorties

```bash
terraform output                       # toutes
terraform output -raw instance_id      # pour Session Manager et GitHub
terraform output -raw deploy_role_arn  # pour GitHub
```

Depuis la racine du dépôt : `terraform -chdir=infra/terraform/aws output -raw instance_id`.

## Mise en route de la production

Déjà faite. À refaire **seulement si l'instance est recréée** (sauf l'étape GitHub, qui ne
change que si `instance_id` change).

1. **Après `apply`**, attendre 3 à 5 minutes (`user_data.sh`), puis vérifier que l'agent SSM est
   en ligne :
   ```bash
   aws ssm describe-instance-information \
     --query 'InstanceInformationList[].[InstanceId,PingStatus]' --output table
   ```
2. **Sur l'instance**, en root (`aws ssm start-session --target <instance-id>`, puis `sudo -i`) :
   - vérifier `cloud-init status --long` (`done`) et que `/opt/enervision` est bien un clone ;
   - `docker login ghcr.io` avec un jeton GitHub *classic* `read:packages`, **en root** (c'est
     root qui exécute les déploiements) ;
   - créer `/etc/enervision/production.env` (`umask 077`) : `APP_ENV=production`,
     `POSTGRES_PASSWORD` (neuf, lettres et chiffres uniquement), `SECRET_KEY` (32 caractères au
     moins), `MOCK_API_URL` (l'URL publique du mock), `MOCK_API_USERNAME`, `MOCK_API_PASSWORD`,
     `COMPOSE_PROFILES=apps` et `NG_ALLOWED_HOSTS` (le nom CloudFront du site, sans `https://`) ;
   - contrôler :
     `docker compose -f docker-compose.staging.yml --env-file /etc/enervision/production.env config >/dev/null`.
3. **Dans GitHub**, *Settings → Environments → `production`* :
   - *Required reviewers* : l'équipe (l'auteur de la release peut approuver lui-même) ;
   - *Deployment branches and tags* : branche `main` **et** tags `v*` ;
   - variables `AWS_REGION` (`eu-west-3`), `AWS_DEPLOY_ROLE_ARN`, `AWS_INSTANCE_ID`.
4. **Variable de dépôt** `PRODUCTION_ENABLED=true` (sans elle, `deploy-production.yml` ne fait rien).

## Supprimer l'infrastructure (fin de projet)

```bash
terraform plan -destroy        # relire la liste
terraform destroy
```

Le `destroy` vide et supprime le bucket de données (`force_destroy`) : le remote DVC de production
et les sauvegardes disparaissent avec lui, les données de référence restent dans le remote du
staging et sur les postes. Puis, **en dernier** (le `destroy` en a besoin) : vider et supprimer le
bucket du state dans la console S3 (*Empty*, puis *Delete* : il est versionné). Vérifier quelques jours plus tard dans
*Billing → Bills* qu'aucun service ne facture encore. Révoquer aussi le jeton GHCR de l'EC2.

## Reste à décider

- **Nom de domaine et chiffrement de bout en bout** : aujourd'hui CloudFront en `*.cloudfront.net`
  et HTTP jusqu'à l'instance. Voir *Exposition* plus haut.
- **Dimensionnement** : `t3.large` à confirmer d'après la consommation réelle.
- **Service ML et MLflow** : aucun n'est déployé en production.

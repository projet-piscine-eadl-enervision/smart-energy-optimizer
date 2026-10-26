# EnerVision : accès AWS et poste développeur

Ce guide est à suivre **une seule fois**, dans l'ordre, pour obtenir ton accès au compte AWS
de l'équipe et préparer ta machine (WSL Debian ou Ubuntu). Compte environ 30 minutes.

Ce qui est **déjà fait** par l'admin (rien à refaire) :

- le compte AWS et ton utilisateur IAM Identity Center ;
- le bucket S3 qui stocke le state Terraform ;
- l'infrastructure de prod (`terraform apply`) : l'EC2 tourne déjà.

Pour comprendre comment tout ça s'organise, lis aussi [`infra/README.md`](../infra/README.md).

> ⚠️ Ne lance **jamais** les commandes `aws s3api create-bucket` du tuto, ni de
> `terraform apply` sans en avoir parlé à l'équipe.

## Infos dont tu as besoin

| Quoi | Valeur |
|---|---|
| AWS access portal URL | `https://d-806769cc86.awsapps.com/start` |
| Région | `eu-west-3` (Paris) |
| Nom du profil AWS | `enervision` |
| Bucket du state Terraform | `enervision-tfstate-dreamteam2026` |
| Dépôt GitHub | `projet-piscine-eadl-enervision/smart-energy-optimizer` |

---

## 1. Activer ton compte AWS

1. Ouvre l'e-mail **« Invitation to join AWS IAM Identity Center »** (vérifie tes spams).
   Le lien **expire au bout de 7 jours** : si c'est trop tard, demande à Lea de te le renvoyer.
2. Clique sur **Accept invitation**, choisis ton mot de passe.
3. Enregistre la **double authentification (MFA)** :
   - choisis **Authenticator app** ;
   - scanne le QR code avec Google Authenticator, Authy, Microsoft Authenticator ou 1Password ;
   - saisis le code à 6 chiffres affiché.
4. Tu arrives sur le portail AWS : tu dois voir le compte du projet et le rôle
   **AdministratorAccess**. Clique dessus pour vérifier que la console s'ouvre.

Range ton mot de passe dans un gestionnaire de mots de passe, jamais dans un fichier ou
une messagerie.

## 2. Installer les outils (AWS CLI, Terraform, GitHub CLI)

Dans ton terminal WSL :

```bash
# Prérequis
sudo apt update && sudo apt install -y curl unzip python3 git

# Récupérer le dépôt (si ce n'est pas déjà fait)
mkdir -p ~/projects && cd ~/projects
git clone git@github.com:projet-piscine-eadl-enervision/smart-energy-optimizer.git
cd smart-energy-optimizer

# Installer les outils (sans sudo !)
infra/scripts/install-tools.sh
source ~/.bashrc
aws --version && terraform version && gh --version
```

Le script installe tout dans `~/.local/bin` et ajoute `export AWS_PROFILE=enervision` à ton
`~/.bashrc`.

**Si ça coince :**

| Erreur | Solution |
|---|---|
| `Permission denied` | `chmod +x infra/scripts/install-tools.sh` puis relancer |
| `$'\r': command not found` / `bad interpreter` | `sed -i 's/\r$//' infra/scripts/install-tools.sh` |
| `aws: command not found` après l'install | ouvrir un nouveau terminal |

Ne lance **pas** le script avec `sudo` : les outils s'installeraient pour `root`, pas pour toi.

## 3. Installer le plugin Session Manager

Il sert à ouvrir un terminal sur la VM de prod, sans SSH. Il demande `sudo` :

```bash
curl -fsSLo /tmp/smp.deb \
  "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb"
sudo dpkg -i /tmp/smp.deb
session-manager-plugin --version
```

(Le paquet `ubuntu_64bit` fonctionne aussi sur Debian.)

## 4. Se connecter à GitHub

```bash
gh auth login
```

**GitHub.com** → **SSH** → laisser gh générer une clé SSH (ou *Skip* si `git push` marche
déjà) → **Login with a web browser**, puis saisir le code affiché sur
<https://github.com/login/device>.

```bash
gh auth status
```

## 5. Se connecter à AWS (SSO)

```bash
aws configure sso
```

| Question | Réponse |
|---|---|
| SSO session name | `enervision` |
| SSO start URL | l'AWS access portal URL (tableau du haut) |
| SSO region | `eu-west-3` |
| SSO registration scopes | Entrée (valeur par défaut) |
| *(le navigateur s'ouvre : connexion + code MFA + Allow)* | |
| Compte / rôle | le compte du projet, `AdministratorAccess` |
| Default client Region | `eu-west-3` |
| CLI default output format | `json` |
| Profile name | **`enervision`** (exactement ce nom) |

Si la page du navigateur finit en erreur, relance avec `aws configure sso --use-device-code`
et saisis le code affiché dans ton navigateur.

**Vérification :**

```bash
aws sts get-caller-identity
```

Tu dois voir le numéro du compte et ton prénom à la fin de la ligne `Arn`.

## 6. Préparer Terraform

```bash
cd infra/terraform/aws
```

Crée ton `backend.hcl` (non versionné) à partir du modèle `backend.hcl.example` :

```bash
cp backend.hcl.example backend.hcl
cat backend.hcl     # doit afficher bucket = "enervision-tfstate-dreamteam2026"
```

Récupère `terraform.tfvars` auprès de Lea **en message privé** (il contient les identifiants
du VPC et du subnet, et n'est pas dans Git), place-le dans ce dossier, puis :

```bash
terraform init -backend-config=backend.hcl
terraform plan
```

Le `plan` doit afficher **`No changes.`** : ça veut dire que tu vois bien la même infra que
le reste de l'équipe. S'il propose de créer, modifier ou supprimer des choses, **ne fais
surtout pas `apply`** et préviens l'équipe.

> En particulier, si tu vois `aws_instance.main must be replaced` ou `forces replacement` :
> un `apply` **détruirait la VM de prod** et en recréerait une vide. La cause la plus
> fréquente est une nouvelle image Debian ; c'est normalement neutralisé par
> `lifecycle { ignore_changes = [ami, user_data] }` dans `main.tf`. Vérifie que ta branche
> est à jour avec `main` (`git pull`), puis relance le `plan`.

### Règles de l'équipe

- `terraform plan` : autant que tu veux, ça ne modifie rien.
- `terraform apply` : **jamais sans en parler à l'équipe**, toujours depuis une branche à jour
  avec `main`, et après avoir relu le plan.
- `Error acquiring the state lock` : quelqu'un d'autre fait un `plan`/`apply`, attends.
- Ne commite jamais `backend.hcl`, `*.tfvars`, `*.tfstate` ni `tfplan` (déjà dans le `.gitignore`).

## 7. Se connecter à la VM de prod

Depuis la racine du dépôt :

```bash
aws ssm start-session --target "$(terraform -chdir=infra/terraform/aws output -raw instance_id)"
```

(`terraform output` doit savoir où est le dossier Terraform : d'où le `-chdir`. Sinon, fais
d'abord `cd infra/terraform/aws` puis `aws ssm start-session --target "$(terraform output -raw instance_id)"`.)

Une fois dedans, tape `bash` pour un shell plus confortable. Tu es `ssm-user` : utilise
`sudo` pour les commandes d'admin. `exit` pour sortir.

> La VM de prod n'est pas un terrain de jeu : teste d'abord sur la VM de preprod de l'école.
> Tout ce qui est fait à la main sur la prod doit être noté (ou mieux, mis dans le code).

---

## Au quotidien

Ta session AWS expire au bout de quelques heures. Quand une commande répond
`Token has expired` ou `The SSO session ... has expired` :

```bash
aws sso login
```

C'est tout : pas besoin de refaire `aws configure sso`.

| Je veux… | Commande |
|---|---|
| vérifier qui je suis sur AWS | `aws sts get-caller-identity` |
| renouveler ma session | `aws sso login` |
| voir ce que Terraform changerait | `terraform plan` (dans `infra/terraform/aws`) |
| ouvrir un terminal sur la prod | `aws ssm start-session --target <instance-id>` |
| ouvrir la console AWS dans le navigateur | passer par l'AWS access portal URL |

Pour aller plus loin : [`infra/terraform/aws/README.md`](../infra/terraform/aws/README.md)
(modifier l'infra) et [`docs/mise-en-production.md`](mise-en-production.md) (livrer une version).

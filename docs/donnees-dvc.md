# Données volumineuses avec DVC

Les fichiers lourds ne vont pas dans Git. Git garde des pointeurs (`.dvc`, `dvc.lock`), les données vivent dans un stockage partagé.

| Stockage | Adresse |
|---|---|
| `preprod` (défaut) | `ssh://10.43.43.50/var/lib/enervision/dvc` |
| `prod` | `s3://enervision-production-data-136825753193/dvc` |

## Mise en place, une fois

```bash
# 1. DVC, hors requirements, avec les extras ssh et s3
python3 -m venv ~/.local/share/dvc-venv
~/.local/share/dvc-venv/bin/pip install "dvc[ssh,s3]"
ln -sf ~/.local/share/dvc-venv/bin/dvc ~/.local/bin/dvc

# 2. Clé SSH sur la VM (mot de passe root dans les notes Teams)
ssh-copy-id root@10.43.43.50

# 3. Réglages personnels, jamais commités (.dvc/config.local)
dvc remote modify --local preprod user root
dvc remote modify --local prod profile enervision
```

Le profil AWS `enervision` se configure avec [`aws-poste-developpeur.md`](aws-poste-developpeur.md).

## Usage

```bash
aws sso login --profile enervision --use-device-code   # avant prod, la session expire
eval "$(ssh-agent -s)" && ssh-add                       # évite la passphrase à chaque commande
dvc pull                  # depuis preprod ; dvc pull -r prod pour S3
cd etl && dvc repro       # reconstruit le parquet si le script ou le CSV a changé
dvc status                # écarts avec les pointeurs ; dvc status -c -r prod : avec S3
```

Nouveau fichier lourd : `dvc add chemin/fichier`, puis `git add chemin/fichier.dvc chemin/.gitignore`.

Quand les données changent, faire `dvc push` et `dvc push -r prod` **avant** le `git push`, sinon vos collègues récupèrent un pointeur sans fichier. Jamais de données dans Git, jamais d'identifiant dans `.dvc/config`.

## Fichiers suivis

- `etl/pipeline/provided_files/all_sites_combined.csv` et `dataset_metadata.json` : fournis par l'école, pointeurs `.dvc` à côté.
- `etl/pipeline/edited_files/energy_consumption_cleaned.parquet` : produit par `dvc repro` (`etl/dvc.yaml`, `etl/dvc.lock`), chargé dans `ml.history_labeled` par `python -m pipeline load-history`.

## Erreurs courantes

- `requires 'dvc-ssh'` : DVC installé sans extras, réinstaller `"dvc[ssh,s3]"`.
- Erreur d'identifiants AWS : relancer `aws sso login`.
- `missing cache` : la dernière personne à modifier les données n'a pas fait `dvc push`.

## À savoir

- Sur la VM, lecture directe sans SSH : `dvc remote modify --local preprod url /var/lib/enervision/dvc`. Ne pas travailler dans `/opt/enervision`, réinitialisé toutes les 2 minutes.
- `terraform destroy` vide le bucket (`force_destroy`) : repousser les données depuis `preprod`.

# Mise en production et release

Ce guide s'adresse à toute personne de l'équipe qui doit faire passer une version du staging à la production, y compris sans avoir suivi la mise en place du pipeline. Il dit quoi faire, dans quel ordre et où cliquer. Il est la seule description de cette procédure : les autres documents y renvoient.

Pour le reste : les règles de branches, de commits et de versions sont dans [`CONTRIBUTING.md`](../CONTRIBUTING.md), le fonctionnement du staging dans [`deploiement-staging.md`](deploiement-staging.md) et l'infrastructure AWS dans [`infra/terraform/aws/README.md`](../infra/terraform/aws/README.md).

> **La production est désactivée tant que la variable de dépôt `PRODUCTION_ENABLED` n'est pas à `true`** (*Settings > Secrets and variables > Actions > Variables*), ce qui suppose que l'infrastructure AWS existe. Dans cet état, les étapes 1 à 3 fonctionnent normalement. À l'étape 4, le déploiement apparaît avec le statut *skipped* et ne demande aucune approbation.

## Vocabulaire

- **Recette** : test du staging par une personne de l'équipe, avant de figer une version.
- **sha** : identifiant d'un commit (7 caractères pour la forme courte, par exemple `1824be5`). Il relie le staging, la release et la production.
- **Release** : opération qui pose un tag de version `vX.Y.Z` sur un commit, publie une GitHub Release avec ses notes, puis promeut les images et déploie la production.
- **Déploiement `staging`** : enregistrement que la VM du staging crée sur GitHub quand elle fait tourner un commit (onglet *Deployments* du dépôt).
- **GHCR** : le registre d'images Docker de GitHub, où la CI publie les images des modules.
- **SSM** (AWS Systems Manager) : service qui permet de lancer des commandes sur l'instance de production sans SSH.
- **Environnement `production`** : réglage GitHub (*Settings > Environments*) qui impose une approbation humaine avant le déploiement.

## Le parcours en quatre étapes

1. Une PR est fusionnée sur `main` : la CI publie les images, le staging se met à jour et annonce à GitHub le commit qu'il fait tourner.
2. Une personne fait la recette du staging.
3. Cette personne lance la release : version, promotion des images, déploiement.
4. Une personne approuve le déploiement en production.

## 1. Fusion et mise à jour du staging

Le merge d'une PR (squash) crée un `push` sur `main`. La CI s'exécute puis publie les images (job `publish` de `ci.yml`). La VM tire ensuite les nouvelles images (au plus 2 minutes de minuteur, mécanisme décrit dans `deploiement-staging.md`) et annonce à GitHub qu'elle fait tourner ce commit : un déploiement `staging` apparaît dans l'onglet *Deployments* du dépôt. **C'est le signal « le staging est à jour, la recette peut commencer ».** `version.sha` de http://10.43.43.50:8000/health (réseau de l'école) affiche alors le sha du commit de merge.

Si l'annonce n'apparaît pas alors que `/health` est à jour, le jeton de la VM est absent ou expiré (voir `deploiement-staging.md`, section « Annonce du staging à GitHub »).

**Ce que `/health` affiche n'est pas le numéro de version.** `version` y contient le titre du commit et son sha, et change à chaque merge. Le numéro `vX.Y.Z` n'existe qu'après l'étape 3.

## 2. Recette

Une seule personne recette à la fois. Elle annonce dans le canal de l'équipe le sha qu'elle recette (« je recette `1824be5` ») pour que personne ne lance une autre release en parallèle.

Il n'existe pas de grille de recette écrite : il s'agit de vérifier sur le staging ce qui a changé depuis la dernière version. Pour le lister, depuis un clone à jour :

```bash
git log <dernier-tag>..<sha> --oneline
```

Un merge arrivé pendant la recette fait avancer le staging. Pour livrer le commit recetté et non le plus récent, saisir son sha à l'étape 3 : la release est figée sur lui, à condition que le staging l'ait annoncé un jour.

## 3. Release

1. Ouvrir GitHub > *Actions* > *Release* (colonne de gauche) > *Run workflow*, la branche `main` étant sélectionnée. Il faut avoir le droit d'écriture sur le dépôt.
2. **Sha** : laisser vide pour livrer le dernier commit annoncé par le staging, ou saisir le sha recetté.
3. Cocher la confirmation et lancer. La case atteste que la recette est faite : le workflow ne peut pas le vérifier.

Le workflow vérifie le sha, que la CI du commit est verte et que le staging l'a annoncé avec succès. Il calcule la version selon les règles de `CONTRIBUTING.md` et crée le tag et la GitHub Release (notes générées) sur ce commit exact. Il enchaîne ensuite, dans le même run :

- la **promotion des images** : le tag de version est ajouté à l'image déjà construite pour ce commit, sans reconstruction, et un SBOM (CycloneDX) de chaque image est joint à la GitHub Release ;
- le **déploiement en production** (étape 4).

Le résumé du run affiche la version calculée et la liste des commits inclus. Si la promotion échoue, *Re-run failed jobs* sur le run de la release suffit ; elle peut aussi être relancée seule (*Actions > Promotion des images*, avec le tag).

**Si la release est refusée**, le message d'erreur du run indique pourquoi :

| Message | Cause | Que faire |
|---|---|---|
| Cocher la confirmation | la case n'était pas cochée | relancer en la cochant, après la recette |
| Aucun déploiement « staging » connu | la VM n'a jamais annoncé de commit | vérifier le jeton de la VM (`deploiement-staging.md`) |
| Le staging n'a jamais annoncé le commit | ce commit n'a pas encore (ou jamais) tourné sur le staging | attendre le passage du minuteur (2 minutes), ou choisir un commit que le staging a fait tourner |
| Le déploiement staging … n'a jamais atteint l'état success | l'annonce n'a pas abouti | attendre le passage suivant, ou vérifier la VM |
| Sha invalide, ou inconnu ou ambigu | sha mal copié | recopier le sha : 7 à 40 caractères hexadécimaux en minuscules |
| n'est pas sur `main` | le sha vient d'une autre branche | utiliser un commit de `main` |
| porte déjà la version | ce commit est déjà publié | rien à faire |
| plus ancien que `vX.Y.Z` | une version plus récente existe déjà | recetter un commit plus récent |
| La CI du commit n'est pas verte (résultat : `failure`) | la CI de ce commit a échoué, publication des images comprise | corriger par une PR, puis recetter le nouveau commit |
| La CI du commit n'est pas verte (résultat : `aucune`) | aucune CI `push` n'existe pour ce commit | arrive si GitHub perd l'événement (incident du 21/10 sur les merges de #81 et #88) : fusionner une PR suivante et utiliser son sha |
| Aucun commit `feat` ou `fix` | seuls des commits sans effet sur la version depuis le dernier tag | rien à publier |

## 4. Approbation et déploiement

Le job de déploiement de la release commence par un résumé sur la page du run : le tag, le commit et le lien vers les notes de la version. Il attend ensuite l'approbation de l'environnement `production`.

Quand la production est activée, la personne qui approuve ouvre le run *Release* (onglet *Actions*), lit le résumé et vérifie que le tag est bien celui annoncé à l'équipe. Elle clique sur *Review deployments*, coche `production`, puis *Approve and deploy*. Les relecteurs sont ceux de *Settings > Environments > production* (six personnes) et l'auteur de la release peut approuver lui-même. Les administrateurs du dépôt peuvent aussi contourner l'approbation.

Après l'approbation, le workflow vérifie que les images du tag existent, sauvegarde la base sur l'instance (`/var/backups/enervision`, les cinq dernières copies), déploie le tag par SSM puis contrôle que `/health` annonce l'environnement `production` et le commit du tag. Le détail technique est dans le README d'AWS. Un déploiement réussi se termine par « Production à jour : vX.Y.Z (sha) ». Un seul déploiement de production s'exécute à la fois.

Pour activer la production, la liste ordonnée des opérations (Terraform, `production.env`, variables GitHub) est dans `infra/terraform/aws/README.md`.

## Retour arrière

**Staging.** Le staging suit `main` : la voie normale est une PR `revert` du commit fautif, qui se déploie comme n'importe quel merge. En urgence, avec accès à la VM, ajouter `IMAGE_TAG=sha-<commit complet>` (les 40 caractères, ou un tag `vX.Y.Z`) dans `/etc/enervision/staging.env` : au passage suivant du minuteur, le staging redéploie les images de ce commit avec le fichier compose du même commit, et reste figé dessus. `update-staging.sh` écrit un avertissement à chaque passage tant que la ligne existe, visible avec `journalctl -u update-staging.service`. Pendant ce temps, les recettes des autres portent sur une version qui ne bouge plus : retirer la ligne dès que le correctif est fusionné.

**Production.** GitHub > *Actions* > *Déploiement en production* > *Run workflow*, en indiquant un tag déjà publié (par exemple `v1.4.2`, visible sur la page *Releases*). Le workflow accepte uniquement un tag `vX.Y.Z` existant et situé sur `main`, demande la même approbation que pour une mise en production, sauvegarde la base, redéploie ce tag et contrôle `/health`. Aucun tag n'est créé. Un tag antérieur à l'ajout du sha dans `/health` (la série `v1.0.x`) échouerait au contrôle final.

Revenir au code précédent ne défait pas les données écrites entre-temps : en cas de doute sur la base, les sauvegardes de l'instance sont le recours. Il ne défait pas non plus le schéma : l'image `db` de l'ancienne version ne contient pas les migrations récentes, qui restent appliquées et que `migrate` ignore. L'ancien code doit donc fonctionner sur la base migrée, ce qui est la règle de compatibilité de chaque migration (voir [`migrations-base-de-donnees.md`](migrations-base-de-donnees.md)). Ensuite, corriger par une PR `revert` ou un correctif, puis refaire une release par la procédure normale.

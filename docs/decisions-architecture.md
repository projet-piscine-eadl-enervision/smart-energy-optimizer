# Décisions d'architecture

Chaque décision structurante du projet tient en une page : contexte, choix, alternatives réellement examinées, conséquences et preuves. Les décisions ont été prises en daily, en séance à deux ou dans un ticket ; les ADR 0001 à 0004 ont été **rédigés a posteriori le 28/10/2026**, d'où deux dates par fiche : celle de la décision et celle de la rédaction. Quand aucune trace écrite n'existe, la fiche le dit.

| N° | Décision | Statut | Décidée le |
|---|---|---|---|
| 0001 | Versionner le schéma de la base avec dbmate | accepté | 22/10/2026 |
| 0002 | Publier les releases sans PR de release | accepté, prolongé par une release manuelle | 19/10/2026 |
| 0003 | Déployer le staging par un tirage depuis la VM | accepté | 20/10/2026 |
| 0004 | Héberger la production sur AWS plutôt que sur Azure | accepté | 21/10/2026 |

## Ajouter une décision

Copier le modèle ci-dessous à la suite, prendre le numéro suivant et compléter le tableau. Une décision abandonnée garde sa fiche : on change son statut et on renvoie vers la nouvelle.

```markdown
## ADR NNNN. Titre

- **Statut** : accepté | remplacé par ADR XXXX | abandonné
- **Décision prise le** : JJ/MM/AAAA, en daily | séance | ticket | PR
- **Rédigé le** : JJ/MM/AAAA (a posteriori, si la décision est antérieure)
- **Décideurs** : prénoms
- **Domaine** : CI/CD | Cloud | Données | ML | Sécurité | Organisation

**Contexte.** Le problème et les contraintes qui forçaient un choix.

**Décision.** Ce qui a été choisi, en une ou deux phrases.

**Alternatives examinées.** Seulement celles qui ont été discutées ou essayées, avec la raison de l'écart.

**Conséquences.** Positives, limites, ce que la décision impose ensuite.

**Preuves.** Tickets, PR, comptes rendus. « Décision orale, non tracée » si rien n'a été écrit.
```

## ADR 0001. Versionner le schéma de la base avec dbmate

- **Statut** : accepté
- **Décision prise le** : 22/10/2026, dans le ticket [105](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/issues/105), confirmée au daily du 23/10
- **Rédigé le** : 28/10/2026, a posteriori
- **Décideurs** : Flavie (proposition et mise en place), l'équipe
- **Domaine** : Données, CI/CD

**Contexte.** La base TimescaleDB démarrait vide depuis l'image officielle : aucun schéma n'était versionné, et le développement, le staging et la production risquaient de diverger. Trois modules s'y connectent avec des outils différents : `api` (SQLAlchemy), `ml` (psycopg) et `etl`.

**Décision.** Utiliser [dbmate](https://github.com/amacneil/dbmate). Chaque changement est un fichier SQL de `db/migrations/`, publié avec l'image `db` et appliqué au démarrage de la pile par un service `migrate` à usage unique.

**Alternatives examinées.**
- **Alembic** : écarté. Il aurait imposé un outil lié à un seul des trois modules, et sa génération automatique ne comprend pas les hypertables de TimescaleDB.
- **Flyway** : essayé sur une base TimescaleDB jetable. Il demande `outOfOrder=true` pour des PR parallèles, son image pèse environ 940 Mo et l'URL de connexion est à part. Son contrôle d'empreinte des migrations est un vrai avantage.

**Conséquences.**
- L'image fait environ 136 Mo, réutilise `DATABASE_URL` et applique toute migration manquante quel que soit l'ordre des PR.
- dbmate ne contrôle pas l'empreinte d'une migration déjà appliquée. La CI compense : elle refuse la modification, le renommage ou la suppression d'une migration fusionnée et rejoue le jeu deux fois sur une base vide.
- Les migrations voyagent avec l'image : un retour arrière relance l'ancien jeu.
- Adoption mesurée : sur 20 migrations, 13 sont écrites par d'autres membres que Flavie.

**Preuves.** Ticket [105](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/issues/105), PR [106](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/106) et [109](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/109), daily du 23/10, [migrations de la base](migrations-base-de-donnees.md).

## ADR 0002. Publier les releases sans PR de release

- **Statut** : décision du 19/10 prolongée le 21/10 par une release manuelle approuvée (PR [81](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/81))
- **Décision prise le** : 19/10/2026, en PR [30](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/30)
- **Rédigé le** : 28/10/2026, a posteriori
- **Décideurs** : Flavie, l'équipe
- **Domaine** : CI/CD

**Contexte.** Les versions devaient se calculer à partir des commits conventionnels et déclencher le déploiement. Nous avons d'abord utilisé release-please (versions 1.0.0 et 1.0.1 publiées).

**Décision.** Abandonner la PR de release : un workflow calcule la version SemVer (`feat` mineure, `fix` correctif, `!` majeure) et crée le tag et la GitHub Release. Le 21/10, la release devient un lancement manuel, avec approbation de l'environnement `production` et retour arrière.

**Alternatives examinées.**
- **release-please** : écarté. Sa PR de release, ouverte par le jeton de GitHub Actions, ne déclenche pas la CI ; elle est donc impossible à fusionner seul, car la protection de `main` exige une approbation, même avec une GitHub App en contournement.
- **GitHub App `enervision-release`** : conservée pour que les tags déclenchent le déploiement.

**Conséquences.**
- Plus aucune PR de release à traiter. Une release exige un commit annoncé par le staging et au moins un `feat` ou un `fix` depuis le dernier tag.
- Le retour arrière en production est prévu avec la release manuelle (PR 81).
- 46 releases publiées en dix jours.

**Preuves.** PR [23](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/23), [30](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/30), [81](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/81), [mise en production](mise-en-production.md).

## ADR 0003. Déployer le staging par un tirage depuis la VM

- **Statut** : accepté
- **Décision prise le** : 20/10/2026, en séance à deux, mise en œuvre dans la PR [61](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/61)
- **Rédigé le** : 28/10/2026, a posteriori
- **Décideurs** : Flavie, l'équipe
- **Domaine** : CI/CD, Cloud

**Contexte.** Le staging tourne sur la VM de l'école, dans un réseau interne. Le dépôt est public, et un utilisateur du groupe `docker` y équivaut à `root`.

**Décision.** La CI publie une image par module sur GHCR ; un minuteur de la VM exécute `infra/scripts/update-staging.sh` (récupération du dépôt, `compose pull`, `up -d`). Un tag `vX.Y.Z` ajoute son nom à l'image du commit déjà validé, sans reconstruction : la production déploie ce qui a été vu en staging.

**Alternatives examinées.**
- **Runner GitHub auto-hébergé sur la VM** : écarté. Dépôt public et VM dans le réseau de l'école : une PR malveillante pourrait y exécuter du code.

**Conséquences.**
- Aucune connexion entrante de GitHub vers la VM.
- Délai de quelques minutes entre la fusion et le déploiement, et dépendance à un jeton d'accès aux images (30 jours maximum).
- Limite constatée le 23/10 : une défaillance du minuteur est silencieuse tant qu'aucune alerte ne la couvre (renommage du dépôt, deux heures d'échec).

**Preuves.** PR [61](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/61), [68](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/68), [76](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/76), [déploiement du staging](deploiement-staging.md).

## ADR 0004. Héberger la production sur AWS plutôt que sur Azure

- **Statut** : accepté
- **Décision prise le** : 21/10/2026, en PR [79](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/79)
- **Rédigé le** : 28/10/2026, a posteriori
- **Décideurs** : l'équipe ; mise en œuvre Flavie (Terraform), Léa (accès et déploiement)
- **Domaine** : Cloud

**Contexte.** Le dossier de conception prévoyait d'abord Azure, avec un squelette Terraform (PR [60](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/60)). Les quotas Azure du groupe étaient serrés : deux machines virtuelles, une adresse IP publique.

**Décision.** Remplacer Azure par AWS pour la production : instance EC2, accès par Session Manager sans SSH, déploiement par OIDC limité à l'environnement `production`, Terraform sous `infra/terraform/aws/`.

**Alternatives examinées.**
- **Azure** : abandonné. [À confirmer : raison exacte du changement, non tracée dans le dépôt.]

**Conséquences.**
- Production isolée du staging, accès sans port d'administration ouvert.
- Le déploiement dépend de rôles AWS : le renommage du dépôt du 23/10 a bloqué la production jusqu'à la correction de la politique de confiance (PR [118](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/118) et [122](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/122)).
- Sortie réseau en HTTP et HTTPS ouvertes à tous (adresses de GHCR et de SSM non énumérables), assumée dans l'audit.

**Preuves.** PR [79](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/79), [94](https://github.com/projet-piscine-eadl-enervision/smart-energy-optimizer/pull/94), [environnements techniques](environnements-techniques.md).

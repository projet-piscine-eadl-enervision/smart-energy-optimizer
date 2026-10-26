# Politique de sécurité

## Signaler une vulnérabilité

Pas d'issue publique : onglet **Security** du dépôt, puis **Report a vulnerability** (rapport visible des seuls mainteneurs). Indiquer le composant (`api`, `etl`, `ml`, `frontend`, workflows, `infra`), les étapes de reproduction avec le sha du commit (visible sur `/health`) et l'impact. Aucun secret ni donnée personnelle dans le rapport.

## Délais

Projet pédagogique : accusé de réception sous 3 jours ouvrés, première évaluation sous 7 jours.

## Périmètre

Inclus : code du dépôt, workflows GitHub Actions, images GHCR, configuration Terraform. Exclus : API Mock et VM de l'école, vulnérabilités de dépendances sans lien avec notre code (à signaler à leurs mainteneurs), déni de service.

Seule la version de `main` (et la dernière release `vX.Y.Z`) reçoit des correctifs.

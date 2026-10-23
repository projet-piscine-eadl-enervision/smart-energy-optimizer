# Politique de sécurité

## Signaler une vulnérabilité

Ne pas ouvrir d'issue publique. Utiliser le signalement privé de GitHub : onglet **Security** du dépôt, puis **Report a vulnerability**. Le rapport n'est visible que des mainteneurs.

Merci d'indiquer :

- le composant concerné (`api`, `etl`, `ml`, `frontend`, workflows, `infra`) ;
- les étapes pour reproduire, avec la version ou le sha du commit (visible sur `/health`) ;
- l'impact estimé.

N'envoyez ni secret réel ni donnée personnelle dans le rapport.

## Délais

Projet pédagogique mené par une équipe étudiante : accusé de réception sous 3 jours ouvrés, première évaluation sous 7 jours, correctif ou mesure de contournement selon la gravité. Les échéances du projet peuvent allonger ces délais, nous le dirons dans la réponse.

## Périmètre

Dans le périmètre : le code du dépôt, les workflows GitHub Actions, les images publiées sur GHCR, la configuration Terraform.

Hors périmètre : l'API Mock et les machines virtuelles fournies par l'école, les vulnérabilités des dépendances tierces sans lien d'exploitation avec notre code (à signaler à leurs mainteneurs), les attaques par déni de service.

## Versions couvertes

Seule la version de `main` (et la dernière release `vX.Y.Z`) reçoit des correctifs.

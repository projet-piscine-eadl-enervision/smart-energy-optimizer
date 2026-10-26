# Terraform staging (VM de l'école)

**Non écrit.** Le staging est déployé sans Terraform : la VM tire elle-même les images publiées par la CI (`update-staging.timer` et `infra/scripts/update-staging.sh`), comme décrit dans [`docs/deploiement-staging.md`](../../../docs/deploiement-staging.md).

Cette note garde le périmètre qui avait été envisagé, si le sujet revient :

- La VM existe déjà : Terraform ne la créerait pas.
- Les compose restent la source de vérité des conteneurs : Terraform les déclencherait (`git pull` puis `docker compose up -d`), il ne décrirait pas les conteneurs.
- La VM n'est joignable que depuis le réseau de l'école : un `apply` partirait d'un poste de ce réseau, et la CI exigerait un runner auto-hébergé.

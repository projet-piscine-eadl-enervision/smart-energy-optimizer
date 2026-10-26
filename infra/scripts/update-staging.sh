#!/usr/bin/env bash
# Met à jour le staging : récupère les compose de main, tire les nouvelles images, relance ce qui a changé.
# Lancé toutes les 2 minutes par update-staging.timer. Sans effet si rien n'a changé.
set -euo pipefail

# Tout le script est dans une fonction : bash lit et analyse la fonction en entier avant de l'exécuter.
# Sans cela, le « git reset --hard » ci-dessous réécrit ce fichier pendant qu'il s'exécute, et bash
# lirait la suite à une position décalée de la nouvelle version.
main() {
  REPO_DIR="${REPO_DIR:-/opt/enervision}"
  ENV_FILE="${ENV_FILE:-/etc/enervision/staging.env}"
  LOCK_FILE="${LOCK_FILE:-/var/lock/update-staging.lock}"
  COMPOSE_FILE_STAGING="docker-compose.staging.yml"
  export COMPOSE_PROJECT_NAME=enervision

  exec 9>"$LOCK_FILE"
  flock -n 9 || { echo "Mise à jour déjà en cours"; exit 0; }

  [ -f "$ENV_FILE" ] || { echo "$ENV_FILE absent" >&2; exit 1; }

  cd "$REPO_DIR"
  git fetch --quiet origin main
  git reset --hard --quiet origin/main

  # Version figée à la main (retour arrière d'urgence) : le staging ne suit plus main tant que la ligne est là.
  # Les images viennent de IMAGE_TAG (lu par le compose) ; le fichier compose doit venir du même commit,
  # sinon d'anciennes images tourneraient avec un compose récent. Seul ce fichier est ramené en arrière :
  # le reste du dépôt, scripts compris, reste sur main.
  image_tag=$(sed -n 's/^[[:space:]]*IMAGE_TAG=//p' "$ENV_FILE" | tail -n 1 | tr -d "\"' \r")
  if [ -n "$image_tag" ]; then
    echo "ATTENTION : IMAGE_TAG=$image_tag est défini dans $ENV_FILE, le staging est figé sur une version et ne suit plus main. Retirer la ligne une fois le correctif fusionné." >&2
    if [[ "$image_tag" =~ ^sha-([0-9a-f]{40})$ ]]; then
      ref="${BASH_REMATCH[1]}"
    elif [[ "$image_tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
      git fetch --quiet --tags origin
      ref="refs/tags/$image_tag"
    else
      ref=""
    fi
    if [ -n "$ref" ]; then
      git cat-file -e "$ref^{commit}" 2>/dev/null || { echo "Commit ou tag $ref introuvable dans $REPO_DIR" >&2; exit 1; }
      git checkout --quiet "$ref" -- "$COMPOSE_FILE_STAGING"
    fi
  fi

  [ -f "$COMPOSE_FILE_STAGING" ] || { echo "$COMPOSE_FILE_STAGING absent à la racine" >&2; exit 1; }

  docker compose -f "$COMPOSE_FILE_STAGING" --env-file "$ENV_FILE" pull --ignore-buildable --quiet
  docker compose -f "$COMPOSE_FILE_STAGING" --env-file "$ENV_FILE" up -d --remove-orphans

  # Annonce à GitHub que le staging est à jour (déploiement « staging » pour le commit qui tourne).
  # Ne fait jamais échouer la mise à jour : sans jeton ou sans réseau, le script le dit et s'arrête.
  bash "$REPO_DIR/infra/scripts/report-staging-deployment.sh" || true
}

main "$@"
exit $?

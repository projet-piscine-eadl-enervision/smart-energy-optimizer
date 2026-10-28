#!/usr/bin/env bash
# Lint du frontend, comme le job frontend de la CI : ESLint (npm run lint) puis Prettier
# (npm run format:check). Utilisé par le hook pre-commit et par test-all.sh.
#
# Avec Node 24 dans WSL, tout tourne en local ; sinon dans le conteneur frontend (docker compose
# run), sans rien installer. Pour corriger la mise en forme : npm run format (dans frontend/).
set -euo pipefail

REQUIRED_NODE_MAJOR=24
root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
lint_command="npm run --silent lint && npm run --silent format:check"

node_major=0
command -v node >/dev/null 2>&1 && node_major="$(node -p 'process.versions.node.split(".")[0]')"

if [ "$node_major" -ge "$REQUIRED_NODE_MAJOR" ]; then
  cd "$root/frontend"
  # npm ci seulement si node_modules est absent ou plus ancien que package-lock.json
  if [ ! -f node_modules/.package-lock.json ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
    npm ci
  fi
  bash -c "$lint_command"
else
  if ! command -v docker >/dev/null 2>&1; then
    echo "Node $REQUIRED_NODE_MAJOR et Docker introuvables : impossible de linter le frontend." >&2
    exit 1
  fi
  echo "Node $REQUIRED_NODE_MAJOR absent de WSL : lint dans le conteneur frontend."
  cd "$root"
  # node_modules vient de l'image : la reconstruire si package-lock.json a changé (rapide sinon).
  # Même contexte et même cible que le service frontend de docker-compose.yml ; docker build -q
  # renvoie l'identifiant de l'image (docker compose config --images liste aussi les dépendances).
  image="$(docker build -q --target dev "$root/frontend")"
  # docker run plutôt que docker compose run : le lint n'a besoin d'aucun réseau, et le sous-réseau
  # fixe du compose empêche de créer celui d'un second clone (worktree) quand la pile tourne déjà.
  docker run --rm --network none -v "$root/frontend:/app" -v /app/node_modules "$image" \
    sh -c "$lint_command"
fi

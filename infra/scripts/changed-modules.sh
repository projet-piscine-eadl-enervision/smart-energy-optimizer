#!/usr/bin/env bash
# Dit quels modules sont touchés entre deux commits, pour que la CI ne teste que ceux-là.
#
# Usage : infra/scripts/changed-modules.sh <commit-de-base> <commit-de-tête>
# Sortie (une ligne clé=valeur, format de $GITHUB_OUTPUT) :
#   python=["api","etl"]   modules Python à tester (liste JSON, vide : [])
#   frontend=true|false    migrations=true|false
#
# Tout est actif quand la base est absente ou inconnue (première publication d'une branche, commit
# introuvable) et quand un fichier commun change : workflows, scripts d'infra, compose, hooks.
# Dans le doute, on teste tout.
set -euo pipefail

base="${1:-}"
head="${2:-HEAD}"

api=false etl=false ml=false frontend=false db=false
everything=false

if [ -z "$base" ] || [[ "$base" =~ ^0+$ ]] || ! git cat-file -e "${base}^{commit}" 2>/dev/null; then
  everything=true
elif ! files=$(git diff --name-only --no-renames "$base...$head" 2>/dev/null); then
  everything=true
else
  while IFS= read -r path; do
    case "$path" in
      api/*) api=true ;;
      etl/*) etl=true ;;
      ml/*) ml=true ;;
      frontend/*) frontend=true ;;
      db/*) db=true ;;
      .github/*|infra/scripts/*|docker-compose*.yml|.pre-commit-config.yaml|.commitlintrc.yml) everything=true ;;
    esac
  done <<<"$files"
fi

if [ "$everything" = true ]; then
  api=true etl=true ml=true frontend=true db=true
fi

python=()
[ "$api" = true ] && python+=('"api"')
[ "$etl" = true ] && python+=('"etl"')
[ "$ml" = true ] && python+=('"ml"')

echo "python=[$(IFS=,; echo "${python[*]:-}")]"
echo "frontend=$frontend"
echo "migrations=$db"

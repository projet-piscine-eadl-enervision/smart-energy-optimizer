#!/usr/bin/env bash
# Vérifie changed-modules.sh sur un dépôt jetable. Lancé par la CI avant le tri des modules.
set -euo pipefail

script="$(cd "$(dirname "$0")" && pwd)/changed-modules.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cd "$tmp"
git init -q -b main .
git config user.email test@example.com
git config user.name test
mkdir -p api etl ml frontend db docs .github/workflows infra/scripts infra/terraform
for f in api/a etl/a ml/a frontend/a db/a docs/a .github/workflows/a infra/scripts/a infra/terraform/a docker-compose.yml; do
  echo x > "$f"
done
git add -A && git commit -q -m base
base="$(git rev-parse HEAD)"

fail=0
# attendu <description> <fichiers modifiés> <python> <frontend> <migrations>
attendu() {
  local description="$1" files="$2" python="$3" frontend="$4" migrations="$5" file
  git reset -q --hard "$base"
  for file in $files; do echo "$RANDOM" >> "$file"; done
  git add -A && git commit -q --allow-empty -m change
  local got want
  got="$("$script" "$base" HEAD)"
  want="python=$python
frontend=$frontend
migrations=$migrations"
  if [ "$got" = "$want" ]; then
    echo "ok   $description"
  else
    echo "ÉCHEC $description"; echo "  attendu :"; echo "$want" | sed 's/^/    /'; echo "  obtenu :"; echo "$got" | sed 's/^/    /'
    fail=1
  fi
}

attendu "api seul" "api/a" '["api"]' false false
attendu "etl et ml" "etl/a ml/a" '["etl","ml"]' false false
attendu "frontend seul" "frontend/a" '[]' true false
attendu "base de données seule" "db/a" '[]' false true
attendu "documentation seule" "docs/a" '[]' false false
attendu "terraform seul" "infra/terraform/a" '[]' false false
attendu "workflow : tout" ".github/workflows/a" '["api","etl","ml"]' true true
attendu "scripts d'infra : tout" "infra/scripts/a" '["api","etl","ml"]' true true
attendu "compose : tout" "docker-compose.yml" '["api","etl","ml"]' true true

# Bases inutilisables : tout est testé
for bad in "" 0000000000000000000000000000000000000000 deadbeefdeadbeefdeadbeefdeadbeefdeadbeef; do
  got="$("$script" "$bad" HEAD)"
  want='python=["api","etl","ml"]
frontend=true
migrations=true'
  if [ "$got" = "$want" ]; then echo "ok   base « ${bad:-vide} »"; else echo "ÉCHEC base « ${bad:-vide} »"; fail=1; fi
done

exit "$fail"

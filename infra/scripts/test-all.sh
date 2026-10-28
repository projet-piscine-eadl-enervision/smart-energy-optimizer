#!/usr/bin/env bash
# Lance le lint et les tests de chaque module, avec la couverture, comme la CI. S'arrête à la
# première erreur et affiche un récapitulatif (résultat et couverture par module).
#
# Usage, depuis n'importe quel dossier du projet :
#   ./infra/scripts/test-all.sh                 # api, etl, ml puis frontend
#   ./infra/scripts/test-all.sh etl frontend    # seulement ces modules, dans cet ordre
#
# Python (api, etl, ml) : un environnement par module dans .venv-tests/<module>, car les versions
# figées diffèrent d'un module à l'autre (fastapi, pandas...). Il est créé au premier lancement et
# réinstallé seulement quand requirements.txt ou requirements-dev.txt change. Python 3.13 requis,
# comme la CI (variable PYTHON pour en choisir un autre exécutable).
#
# Frontend : ESLint et Prettier (infra/scripts/lint-frontend.sh) puis les tests. Avec Node 24 dans
# WSL, tout tourne en local ; sinon dans le conteneur frontend (docker compose run), sans rien installer.
#
# Base de données : les tests qui la touchent (etl, ml) sont ignorés sans DATABASE_URL, comme
# l'indique pytest. Pour les inclure, sur la base de dev :
#   DATABASE_URL=postgresql://postgres:dev@localhost:5432/enervision ./infra/scripts/test-all.sh etl ml
#
# Rapports : <module>/coverage.xml (Python) et frontend/coverage/enervision/ (lcov, html).

set -euo pipefail

ALL_MODULES=(api etl ml frontend)
REQUIRED_PYTHON="3.13"
REQUIRED_NODE_MAJOR=24

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
venv_root="$root/.venv-tests"

summary=()
current_module=""

bold() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
fail() { printf '\033[31mErreur : %s\033[0m\n' "$*" >&2; exit 1; }

print_summary() {
  local status=$?
  if [ -n "$current_module" ]; then
    summary+=("$(printf '%-10s %-8s %s' "$current_module" "KO" "-")")
  fi
  if [ ${#summary[@]} -gt 0 ]; then
    bold "Récapitulatif"
    printf '%-10s %-8s %s\n' "Module" "Résultat" "Couverture"
    printf '%s\n' "${summary[@]}"
  fi
  exit "$status"
}
trap print_summary EXIT

find_python() {
  local candidate
  for candidate in "${PYTHON:-}" "python$REQUIRED_PYTHON" python3; do
    [ -n "$candidate" ] || continue
    if command -v "$candidate" >/dev/null 2>&1 \
      && [ "$("$candidate" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')" = "$REQUIRED_PYTHON" ]; then
      echo "$candidate"
      return 0
    fi
  done
  fail "Python $REQUIRED_PYTHON introuvable (la CI utilise $REQUIRED_PYTHON). Indique-le avec PYTHON=/chemin/vers/python3.13."
}

# Crée ou met à jour l'environnement du module ; ne réinstalle que si ses requirements ont changé.
prepare_venv() {
  local module="$1" venv="$venv_root/$1" python
  local requirements=("$root/$module/requirements.txt")
  [ -f "$root/$module/requirements-dev.txt" ] && requirements+=("$root/$module/requirements-dev.txt")
  local fingerprint
  fingerprint="$(cat "${requirements[@]}" | sha256sum | cut -d' ' -f1)"

  if [ ! -x "$venv/bin/python" ]; then
    python="$(find_python)"
    echo "Création de l'environnement $venv"
    "$python" -m venv "$venv"
  fi
  if [ "$(cat "$venv/.requirements.sha256" 2>/dev/null)" != "$fingerprint" ]; then
    echo "Installation des dépendances de $module"
    "$venv/bin/python" -m pip install -q --upgrade pip
    local args=()
    for file in "${requirements[@]}"; do args+=(-r "$file"); done
    # Sans requirements-dev.txt, mêmes outils que la CI, en version du jour
    [ -f "$root/$module/requirements-dev.txt" ] || args+=(ruff pytest pytest-cov)
    "$venv/bin/python" -m pip install -q "${args[@]}"
    echo "$fingerprint" >"$venv/.requirements.sha256"
  fi
}

run_python_module() {
  local module="$1" venv="$venv_root/$1" status=0
  prepare_venv "$module"
  cd "$root/$module"
  # Cache ruff dans .venv-tests : un ml/.ruff_cache créé par un conteneur (root) ne bloque plus le lint
  RUFF_CACHE_DIR="$venv/.ruff_cache" "$venv/bin/ruff" check .
  # Code 5 = aucun test collecté : toléré, comme en CI
  "$venv/bin/python" -m pytest --cov=. --cov-report=term-missing:skip-covered --cov-report=xml || status=$?
  [ "$status" -eq 0 ] || [ "$status" -eq 5 ] || return "$status"
  local total="-"
  [ -f .coverage ] && total="$("$venv/bin/python" -m coverage report --format=total 2>/dev/null)%"
  summary+=("$(printf '%-10s %-8s %s' "$module" "OK" "$total")")
}

# Couverture des lignes lue dans le rapport lcov (lignes couvertes / lignes trouvées).
lcov_total() {
  awk -F: '/^LF:/ {found += $2} /^LH:/ {hit += $2}
    END {if (found > 0) printf "%.0f%%", 100 * hit / found; else print "-"}' "$1"
}

run_frontend() {
  local test_args=(--watch=false --coverage --coverage-reporters=lcov --coverage-reporters=text-summary --coverage-reporters=html)
  local node_major=0
  command -v node >/dev/null 2>&1 && node_major="$(node -p 'process.versions.node.split(".")[0]')"
  bash "$root/infra/scripts/lint-frontend.sh"
  cd "$root/frontend"

  if [ "$node_major" -ge "$REQUIRED_NODE_MAJOR" ]; then
    # npm ci seulement si node_modules est absent ou plus ancien que package-lock.json
    if [ ! -f node_modules/.package-lock.json ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
      npm ci
    fi
    CI=true npx --no-install ng test "${test_args[@]}"
  else
    command -v docker >/dev/null 2>&1 || fail "Node $REQUIRED_NODE_MAJOR et Docker introuvables : impossible de tester le frontend."
    echo "Node $REQUIRED_NODE_MAJOR absent de WSL : tests dans le conteneur frontend."
    # --build : node_modules vient de l'image, à reconstruire si package-lock.json a changé (rapide sinon, grâce au cache)
    cd "$root"
    docker compose build -q frontend
    docker compose run --rm --no-deps -T -e CI=true frontend npx --no-install ng test "${test_args[@]}"
    cd "$root/frontend"
  fi

  local total="-"
  [ -f coverage/enervision/lcov.info ] && total="$(lcov_total coverage/enervision/lcov.info)"
  summary+=("$(printf '%-10s %-8s %s' frontend "OK" "$total")")
}

modules=("$@")
[ ${#modules[@]} -gt 0 ] || modules=("${ALL_MODULES[@]}")
for module in "${modules[@]}"; do
  case " ${ALL_MODULES[*]} " in
    *" $module "*) ;;
    *) fail "module inconnu « $module » (attendus : ${ALL_MODULES[*]})" ;;
  esac
done

for module in "${modules[@]}"; do
  bold "$module"
  current_module="$module"
  if [ "$module" = frontend ]; then
    run_frontend
  else
    run_python_module "$module"
  fi
  current_module=""
done

#!/usr/bin/env bash
# Vérifie staging-deployment.sh avec un faux gh qui répond depuis des fichiers JSON.
set -uo pipefail

script="$(cd "$(dirname "$0")" && pwd)/staging-deployment.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/bin" "$tmp/data"

# Faux gh : « gh api <chemin> » renvoie le fichier data/<dernier segment utile> selon le chemin.
cat > "$tmp/bin/gh" <<'SH'
#!/usr/bin/env bash
path="$2"
case "$path" in
  *"/deployments?environment=staging&sha=AAA"*) cat "$DATA/dep-AAA.json" ;;
  *"/deployments?environment=staging&sha=BBB"*) cat "$DATA/dep-BBB.json" ;;
  *"/deployments?environment=staging&sha="*)    echo '[]' ;;
  *"/deployments?environment=staging&per_page=1") cat "$DATA/latest.json" ;;
  *"/deployments/1/statuses"*) cat "$DATA/status-1.json" ;;
  *"/deployments/2/statuses"*) cat "$DATA/status-2.json" ;;
  *) echo "chemin inattendu : $path" >&2; exit 1 ;;
esac
SH
chmod +x "$tmp/bin/gh"
echo '[{"id":1,"sha":"AAA"}]' > "$tmp/data/dep-AAA.json"
echo '[{"id":2,"sha":"BBB"}]' > "$tmp/data/dep-BBB.json"
echo '[{"id":1,"sha":"AAA"}]' > "$tmp/data/latest.json"
echo '[{"state":"inactive"},{"state":"success"}]' > "$tmp/data/status-1.json"   # annoncé, puis remplacé
echo '[{"state":"in_progress"}]' > "$tmp/data/status-2.json"                    # jamais réussi

run() { env PATH="$tmp/bin:$PATH" DATA="$tmp/data" GITHUB_REPOSITORY=o/r bash "$script" "$@"; }
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "ÉCHEC $1"; fail=1; fi; }

out="$(run latest 2>&1)"; check "latest : donne le sha du dernier déploiement" '[ "$out" = AAA ]'
echo '[]' > "$tmp/data/latest.json"
out="$(run latest 2>&1)"; code=$?; check "latest : aucun déploiement, erreur claire" '[ $code -eq 1 ] && grep -q "Aucun déploiement" <<<"$out"'
run check AAA >/dev/null 2>&1; code=$?; check "check : success puis inactive, accepté" '[ $code -eq 0 ]'
out="$(run check BBB 2>&1)"; code=$?; check "check : jamais success, refusé" '[ $code -eq 1 ] && grep -q "jamais atteint" <<<"$out"'
out="$(run check CCC 2>&1)"; code=$?; check "check : commit jamais annoncé, refusé" '[ $code -eq 1 ] && grep -q "jamais annoncé" <<<"$out"'
run bogus >/dev/null 2>&1; code=$?; check "usage invalide : code 2" '[ $code -eq 2 ]'

exit "$fail"

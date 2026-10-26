#!/usr/bin/env bash
# Annonce à GitHub que le staging fait tourner un commit : crée un déploiement « staging » pour ce
# commit, avec le statut « success ». C'est le signal « le staging est à jour, la recette peut
# commencer », et c'est ce que le workflow Release vérifie avant de figer une version.
#
# Appelé par update-staging.sh à chaque passage. L'annonce ne doit jamais faire échouer la mise à
# jour : sans jeton, sans réseau ou sur une erreur de l'API, le script le dit et s'arrête sans
# erreur. Il n'annonce un commit qu'une fois : si GitHub connaît déjà un déploiement staging pour
# ce commit, il ne fait rien.
#
# Le commit annoncé est celui que l'API affiche sur /health (sha compilé dans l'image), pas celui
# du dépôt : on annonce ce qui tourne vraiment. Jeton : voir docs/deploiement-staging.md.
set -uo pipefail

REPO="${GITHUB_REPOSITORY:-projet-piscine-eadl-enervision/smart-energy-optimizer}"
API="${GITHUB_API_URL:-https://api.github.com}"
TOKEN_FILE="${GITHUB_TOKEN_FILE:-/etc/enervision/github-deploy.token}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
REPO_DIR="${REPO_DIR:-/opt/enervision}"
WAIT_SECONDS="${WAIT_SECONDS:-60}"

say() { echo "annonce GitHub : $*"; }

[ -r "$TOKEN_FILE" ] || { say "ignorée, jeton absent ($TOKEN_FILE)"; exit 0; }
command -v curl >/dev/null && command -v python3 >/dev/null || { say "ignorée, curl ou python3 manquant"; exit 0; }
token="$(tr -d ' \r\n' < "$TOKEN_FILE")"

# L'API vient d'être relancée : on lui laisse un peu de temps pour répondre.
sha=""
for _ in $(seq 1 $((WAIT_SECONDS / 2 + 1))); do
  sha="$(curl -fsS --max-time 5 "$HEALTH_URL" 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"]["sha"])' 2>/dev/null)" && [ -n "$sha" ] && break
  sha=""; sleep 2
done
[ -n "$sha" ] && [ "$sha" != dev ] || { say "ignorée, /health ne donne pas de sha"; exit 0; }

full="$(git -C "$REPO_DIR" rev-parse --verify --quiet "${sha}^{commit}")" || { say "ignorée, commit $sha inconnu du dépôt"; exit 0; }

api() { # api <méthode> <chemin> [corps JSON]
  curl -sS --max-time 15 -X "$1" "$API/repos/$REPO/$2" \
    -H "Authorization: Bearer $token" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    ${3:+-H "Content-Type: application/json" -d "$3"}
}

known="$(api GET "deployments?environment=staging&sha=$full&per_page=1" | tr -d ' \r\n')" \
  || { say "ignorée, GitHub injoignable"; exit 0; }
[ "$known" = "[]" ] || {
  case "$known" in "["*) exit 0 ;; *) say "ignorée, réponse inattendue de GitHub : ${known:0:120}"; exit 0 ;; esac
}

deployment="$(api POST deployments "$(python3 -c '
import json,sys
print(json.dumps({"ref": sys.argv[1], "environment": "staging", "auto_merge": False,
  "required_contexts": [], "transient_environment": False, "production_environment": False,
  "description": "Staging à jour sur " + sys.argv[2]}))' "$full" "${full:0:7}")")" \
  || { say "échec de la création du déploiement"; exit 0; }
id="$(printf '%s' "$deployment" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' 2>/dev/null)" \
  || { say "déploiement refusé : $(printf '%s' "$deployment" | tr -d '\n' | cut -c1-200)"; exit 0; }

api POST "deployments/$id/statuses" \
  "{\"state\":\"success\",\"description\":\"Staging à jour sur ${full:0:7}\",\"auto_inactive\":true}" >/dev/null \
  && say "staging annoncé à jour sur ${full:0:7}" \
  || say "déploiement $id créé, mais statut non posé"
exit 0

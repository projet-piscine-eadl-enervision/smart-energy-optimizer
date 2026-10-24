#!/usr/bin/env bash
# Lit les déploiements « staging » que la VM annonce à GitHub (report-staging-deployment.sh).
#   staging-deployment.sh latest        sha complet du dernier commit annoncé sur le staging
#   staging-deployment.sh check <sha>   code 0 si ce commit a été annoncé « success » sur le staging
# Utilise gh (GH_TOKEN) et GITHUB_REPOSITORY. Appelé par le workflow Release.
set -euo pipefail

repo="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY manquant}"

# Lit un champ d'une réponse JSON de gh, sur l'entrée standard.
json() { python3 -c "$1"; }

case "${1:-}" in
  latest)
    sha="$(gh api "repos/$repo/deployments?environment=staging&per_page=1" \
      | json 'import json,sys; d=json.load(sys.stdin); print(d[0]["sha"] if d else "")')"
    [ -n "$sha" ] || { echo "Aucun déploiement « staging » connu : la VM n'a encore rien annoncé (voir docs/deploiement-staging.md)." >&2; exit 1; }
    echo "$sha"
    ;;
  check)
    full="${2:?commit manquant}"
    id="$(gh api "repos/$repo/deployments?environment=staging&sha=$full&per_page=1" \
      | json 'import json,sys; d=json.load(sys.stdin); print(d[0]["id"] if d else "")')"
    [ -n "$id" ] || { echo "Le staging n'a jamais annoncé le commit $full : attendre la mise à jour de la VM (2 minutes) ou vérifier le jeton." >&2; exit 1; }
    # Un statut « success » suffit, même s'il est devenu « inactive » depuis (un commit plus récent
    # a pris la place sur le staging) : ce commit a bien tourné et été recetté.
    gh api "repos/$repo/deployments/$id/statuses?per_page=20" \
      | json 'import json,sys; print("oui" if any(s["state"]=="success" for s in json.load(sys.stdin)) else "non")' \
      | grep -qx oui \
      || { echo "Le déploiement staging de $full n'a jamais atteint l'état success." >&2; exit 1; }
    ;;
  *)
    echo "Usage : $0 latest | check <sha>" >&2
    exit 2
    ;;
esac

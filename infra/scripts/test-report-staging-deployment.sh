#!/usr/bin/env bash
# Vérifie report-staging-deployment.sh contre un faux GitHub (serveur HTTP local) et un dépôt jetable.
set -uo pipefail

script="$(cd "$(dirname "$0")" && pwd)/report-staging-deployment.sh"
tmp="$(mktemp -d)"
trap 'kill "${server:-0}" 2>/dev/null; rm -rf "$tmp"' EXIT

# Faux GitHub + faux /health. Journal des requêtes dans $tmp/requests.log.
cat > "$tmp/mock.py" <<'PY'
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

tmp, short = sys.argv[1], sys.argv[2]
deployments = []

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")
    def handle_any(self, method):
        data = self.body() if method == "POST" else None
        open(f"{tmp}/requests.log", "a").write(f"{method} {self.path} {json.dumps(data)}\n")
        if self.path == "/health":
            return self.reply(200, {"version": {"sha": open(f"{tmp}/health-sha").read().strip()}})
        if self.headers.get("Authorization") != "Bearer jeton-de-test":
            return self.reply(401, {"message": "Bad credentials"})
        if method == "GET" and "/deployments?" in self.path:
            sha = self.path.split("sha=")[1].split("&")[0]
            return self.reply(200, [d for d in deployments if d["sha"] == sha])
        if method == "POST" and self.path.endswith("/deployments"):
            deployments.append({"id": len(deployments) + 1, "sha": data["ref"]})
            return self.reply(201, {"id": len(deployments)})
        if method == "POST" and self.path.endswith("/statuses"):
            return self.reply(201, {})
        self.reply(404, {"message": "Not Found"})
    def do_GET(self): self.handle_any("GET")
    def do_POST(self): self.handle_any("POST")

server = HTTPServer(("127.0.0.1", 0), Handler)
open(f"{tmp}/port", "w").write(str(server.server_port))
server.serve_forever()
PY

# Dépôt jetable : un commit dont le sha court sert de version affichée par /health.
repo="$tmp/repo"
git init -q -b main "$repo" && git -C "$repo" -c user.email=t@t -c user.name=t commit -q --allow-empty -m un
full="$(git -C "$repo" rev-parse HEAD)"; short="${full:0:7}"
echo "$short" > "$tmp/health-sha"

python3 "$tmp/mock.py" "$tmp" "$short" & server=$!
for _ in $(seq 50); do [ -s "$tmp/port" ] && break; sleep 0.1; done
port="$(cat "$tmp/port")"

run() { # run [variables d'environnement...]
  env GITHUB_API_URL="http://127.0.0.1:$port" HEALTH_URL="http://127.0.0.1:$port/health" \
      GITHUB_TOKEN_FILE="$tmp/token" REPO_DIR="$repo" WAIT_SECONDS=2 "$@" bash "$script"
}
fail=0
check() { # check <description> <commande de test>
  if eval "$2"; then echo "ok   $1"; else echo "ÉCHEC $1"; fail=1; fi
}
posts() { grep -c '^POST' "$tmp/requests.log" 2>/dev/null || true; }
: > "$tmp/requests.log"

out="$(run 2>&1)"; code=$?
check "sans jeton : ignoré, sans erreur, sans requête" '[ $code -eq 0 ] && grep -q "jeton absent" <<<"$out" && [ ! -s "$tmp/requests.log" ]'

echo "jeton-de-test" > "$tmp/token"
echo "dev" > "$tmp/health-sha"; out="$(run 2>&1)"; code=$?
check "version dev : ignorée" '[ $code -eq 0 ] && grep -q "ne donne pas de sha" <<<"$out"'

echo "abcdef0" > "$tmp/health-sha"; out="$(run 2>&1)"; code=$?
check "commit inconnu du dépôt : ignoré" '[ $code -eq 0 ] && grep -q "inconnu du dépôt" <<<"$out"'

echo "$short" > "$tmp/health-sha"; : > "$tmp/requests.log"
out="$(run 2>&1)"; code=$?
check "première annonce : succès" '[ $code -eq 0 ] && grep -q "staging annoncé à jour sur $short" <<<"$out"'
check "déploiement créé pour le sha complet, environnement staging" 'grep -q "\"ref\": \"$full\"" "$tmp/requests.log" && grep -q "\"environment\": \"staging\"" "$tmp/requests.log"'
check "statut success posé" 'grep -q "statuses.*success" "$tmp/requests.log"'
check "deux écritures exactement (déploiement, statut)" '[ "$(posts)" = 2 ]'

: > "$tmp/requests.log"; out="$(run 2>&1)"; code=$?
check "seconde exécution : rien de plus à écrire" '[ $code -eq 0 ] && [ "$(posts)" = 0 ]'

echo "mauvais" > "$tmp/token"; rm -f "$tmp/requests.log"; out="$(run 2>&1)"; code=$?
check "jeton refusé : message, sans erreur" '[ $code -eq 0 ] && grep -q "ignorée" <<<"$out"'

echo "jeton-de-test" > "$tmp/token"
out="$(run GITHUB_API_URL=http://127.0.0.1:9 2>&1)"; code=$?
check "GitHub injoignable : sans erreur" '[ $code -eq 0 ]'

exit "$fail"

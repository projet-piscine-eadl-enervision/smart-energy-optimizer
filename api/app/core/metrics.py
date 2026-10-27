"""Métriques Prometheus propres à l'API, exposées sur /metrics avec celles de l'instrumentation HTTP."""
from prometheus_client import Counter

# Résultat de chaque tentative sur /auth/login : success, invalid_credentials, inactive_account,
# ip_blocked, account_blocked. Sert à l'alerte ConnexionsEnEchec (monitoring/prometheus/alerts.yml).
LOGIN_ATTEMPTS = Counter(
    "auth_login_attempts",
    "Tentatives de connexion à /auth/login, par résultat",
    ["outcome"],
)

LOGIN_OUTCOMES = ("success", "invalid_credentials", "inactive_account", "ip_blocked", "account_blocked")
for _outcome in LOGIN_OUTCOMES:
    # Séries créées à 0 dès le démarrage : increase() voit aussi le premier échec
    LOGIN_ATTEMPTS.labels(_outcome)

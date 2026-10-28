#!/usr/bin/env python3
"""Bloque la CI sur les alertes hautes du scan DAST (OWASP ZAP), sauf exception motivée.

ZAP écrit toutes ses alertes dans le rapport JSON, y compris celles des règles mises à IGNORE dans
infra/zap/rules.tsv : le filtrage se fait donc ici. Chaque règle ignorée doit donner sa raison
(quatrième colonne, après le nom de la règle), sinon le script échoue aussi.

Usage : check-zap-report.py <zap-report.json> <rules.tsv>
"""
import json
import sys

HIGH_RISK = 3
RISK_LABELS = {0: "info", 1: "basse", 2: "moyenne", 3: "haute"}


def load_ignored_rules(text: str) -> tuple[set[str], list[str]]:
    """Renvoie les règles à IGNORE et les lignes IGNORE sans raison."""
    ignored, missing_reason = set(), []
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) >= 2 and fields[1] == "IGNORE":
            ignored.update(fields[0].split(","))
            if len(fields) < 4 or not fields[3].strip():
                missing_reason.append(line)
    return ignored, missing_reason


def collect_alerts(report: dict) -> list[dict]:
    alerts = []
    for site in report.get("site", []):
        for alert in site.get("alerts", []):
            alerts.append(
                {
                    "rule_id": str(alert.get("pluginid", "")),
                    "name": alert.get("name", ""),
                    "risk": int(alert.get("riskcode", 0)),
                    "count": int(alert.get("count", len(alert.get("instances", [])))),
                }
            )
    return alerts


def blocking_alerts(alerts: list[dict], ignored: set[str]) -> list[dict]:
    return [a for a in alerts if a["risk"] >= HIGH_RISK and a["rule_id"] not in ignored]


def main(report_path: str, rules_path: str) -> int:
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)
    with open(rules_path, encoding="utf-8") as f:
        ignored, missing_reason = load_ignored_rules(f.read())

    alerts = collect_alerts(report)
    for alert in sorted(alerts, key=lambda a: -a["risk"]):
        status = " (exception)" if alert["rule_id"] in ignored else ""
        print(f"{RISK_LABELS.get(alert['risk'], alert['risk']):8} {alert['rule_id']:>6} {alert['name']} x{alert['count']}{status}")

    exit_code = 0
    for line in missing_reason:
        print(f"::error::Exception ZAP sans raison dans {rules_path} : {line!r}")
        exit_code = 1
    for alert in blocking_alerts(alerts, ignored):
        print(f"::error::Alerte ZAP haute : {alert['name']} (règle {alert['rule_id']}), voir le rapport HTML")
        exit_code = 1
    if exit_code == 0:
        print("Aucune alerte haute hors exceptions.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))

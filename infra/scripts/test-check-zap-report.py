#!/usr/bin/env python3
"""Vérifie check-zap-report.py. Lancé par la CI."""
import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location("check_zap_report", pathlib.Path(__file__).with_name("check-zap-report.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

rules = (
    "# commentaire\n"
    "\n"
    "10021\tIGNORE\t(X-Content-Type-Options)\tAPI JSON seulement\n"
    "40012,40014\tIGNORE\t(XSS)\tfaux positif connu\n"
    "10038\tIGNORE\t(CSP)\n"
    "10020\tWARN\t(Anti-clickjacking)\n"
)
ignored, missing_reason = module.load_ignored_rules(rules)
assert ignored == {"10021", "40012", "40014", "10038"}, ignored
assert missing_reason == ["10038\tIGNORE\t(CSP)"], missing_reason
print("ok   check-zap-report : exceptions lues, raison exigée")

report = {
    "site": [
        {
            "alerts": [
                {"pluginid": "40012", "name": "XSS", "riskcode": "3", "count": "2"},
                {"pluginid": "90019", "name": "SSI", "riskcode": "3", "instances": [{}]},
                {"pluginid": "10020", "name": "Clickjacking", "riskcode": "2", "count": "1"},
            ]
        }
    ]
}
alerts = module.collect_alerts(report)
assert [a["count"] for a in alerts] == [2, 1, 1], alerts
blocking = module.blocking_alerts(alerts, ignored)
assert [a["rule_id"] for a in blocking] == ["90019"], blocking
assert module.blocking_alerts(module.collect_alerts({"site": []}), set()) == []
print("ok   check-zap-report : seule une alerte haute hors exception bloque")

#!/usr/bin/env python3
"""Vérifie les dashboards Grafana versionnés avant leur chargement par le provisioning.

Contrôles : chaque fichier est un JSON lisible, porte un uid unique, et toutes ses sources de données
sont une source provisionnée (uid prometheus, github pour le dashboard de la CI, timescaledb-ml pour
celui du modèle) ou une source interne de Grafana (annotations). Un dashboard importé de grafana.com sans adaptation garde ${DS_PROMETHEUS} et reste vide
une fois chargé.

Usage : check-dashboards.py <dossier-des-dashboards>
"""
import json
import sys
from pathlib import Path

GRAFANA_BUILTIN = {"grafana", "datasource"}
# Sources de monitoring/grafana/provisioning/datasources : (type, uid)
PROVISIONED = {
    ("prometheus", "prometheus"),
    ("grafana-github-datasource", "github"),
    ("grafana-postgresql-datasource", "timescaledb-ml"),
}


def bad_datasources(node, path="$"):
    """Chemins JSON des sources de données qui ne sont ni une source provisionnée, ni une source interne."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "datasource" and not is_allowed(value):
                yield f"{path}.{key} = {json.dumps(value)}"
            yield from bad_datasources(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from bad_datasources(item, f"{path}[{index}]")


def is_allowed(datasource) -> bool:
    if datasource is None or datasource in ("prometheus", "-- Grafana --"):
        return True
    if isinstance(datasource, dict):
        if datasource.get("type") in GRAFANA_BUILTIN:
            return True
        return (datasource.get("type"), datasource.get("uid")) in PROVISIONED
    return False


def main(folder: str) -> int:
    errors, uids = [], {}
    files = sorted(Path(folder).glob("*.json"))
    if not files:
        errors.append(f"aucun dashboard dans {folder}")
    for file in files:
        try:
            dashboard = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{file}: JSON illisible ({exc})")
            continue
        uid = dashboard.get("uid")
        if not uid:
            errors.append(f"{file}: uid manquant")
        elif uid in uids:
            errors.append(f"{file}: uid {uid} déjà utilisé par {uids[uid]}")
        else:
            uids[uid] = file
        errors.extend(f"{file}: source de données inattendue {bad}" for bad in bad_datasources(dashboard))
    for error in errors:
        print(f"ÉCHEC {error}")
    print(f"{len(files)} dashboard(s), {len(errors)} erreur(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip().splitlines()[-1])
    sys.exit(main(sys.argv[1]))

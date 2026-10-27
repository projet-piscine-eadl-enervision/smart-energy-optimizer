"""Traitement : charge l'historique nettoyé (parquet) dans ml.history_labeled.

Usage, depuis etl/ (DATABASE_URL requis ; le fichier vient de `dvc pull` puis `dvc repro`) :
    python -m pipeline load-history [fichier.parquet]

La source est un fichier, pas le mock : aucune réponse n'est gardée dans raw.api_response. Les sites
doivent déjà être dans ref.site (`load-ref`). La table reçoit l'historique et ses anomalies étiquetées
pour la détection d'anomalies ; elle n'alimente ni core.energy_reading ni analytics. Une clé
(site_id, time) déjà présente est mise à jour seulement si une valeur a changé : relancer est sans
danger, et la relance du même fichier ne charge rien.
"""
import argparse
import logging
from pathlib import Path

import pandas as pd
import psycopg

from pipeline import db, runs
from pipeline.jobs.clean_history import DEFAULT_OUTPUT
from pipeline.rows import HISTORY_COLUMNS, history_rows

logger = logging.getLogger(__name__)

RUN_TYPE = "history_load"
SOURCES = {"measured", "interpolated", "recovered_from_euros", "missing"}

SITE_IDS = "SELECT site_id FROM ref.site"
ALERT_TYPES = "SELECT alert_type FROM ref.alert_type"
SEVERITIES = "SELECT severity FROM ref.severity"
UPSERT = """
INSERT INTO ml.history_labeled (site_id, time, consumption_kw, consumption_source, temperature_celsius,
    humidity_percent, solar_irradiance_wm2, anomaly_type, anomaly_severity)
VALUES (%(site_id)s, %(time)s, %(consumption_kw)s, %(consumption_source)s, %(temperature_celsius)s,
    %(humidity_percent)s, %(solar_irradiance_wm2)s, %(anomaly_type)s, %(anomaly_severity)s)
ON CONFLICT (site_id, time) DO UPDATE SET
    consumption_kw = EXCLUDED.consumption_kw,
    consumption_source = EXCLUDED.consumption_source,
    temperature_celsius = EXCLUDED.temperature_celsius,
    humidity_percent = EXCLUDED.humidity_percent,
    solar_irradiance_wm2 = EXCLUDED.solar_irradiance_wm2,
    anomaly_type = EXCLUDED.anomaly_type,
    anomaly_severity = EXCLUDED.anomaly_severity
WHERE (ml.history_labeled.consumption_kw, ml.history_labeled.consumption_source,
       ml.history_labeled.temperature_celsius, ml.history_labeled.humidity_percent,
       ml.history_labeled.solar_irradiance_wm2, ml.history_labeled.anomaly_type,
       ml.history_labeled.anomaly_severity)
    IS DISTINCT FROM (EXCLUDED.consumption_kw, EXCLUDED.consumption_source, EXCLUDED.temperature_celsius,
       EXCLUDED.humidity_percent, EXCLUDED.solar_irradiance_wm2, EXCLUDED.anomaly_type,
       EXCLUDED.anomaly_severity)
"""


def read_history(path: Path) -> pd.DataFrame:
    """Lit le parquet et refuse un fichier sans les colonnes attendues ou avec des clés en double."""
    frame = pd.read_parquet(path)
    missing = [column for column in HISTORY_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"columns missing from {path}: {missing}")
    duplicates = int(frame.duplicated(["site_id", "timestamp"]).sum())
    if duplicates:
        raise ValueError(f"{duplicates} duplicated (site_id, timestamp) keys in {path}")
    return frame


def values_of(conn: psycopg.Connection, query: str) -> set[str]:
    return {row[0] for row in conn.execute(query).fetchall()}


def split_rows(rows: list[dict], alert_types: set[str], severities: set[str]) -> tuple[list[dict], list[dict]]:
    """Sépare les lignes acceptées des rejetées : source de nettoyage, type ou gravité inconnus."""
    accepted, rejected = [], []
    for row in rows:
        valid = (
            row["consumption_source"] in SOURCES
            and (row["anomaly_type"] is None or row["anomaly_type"] in alert_types)
            and (row["anomaly_severity"] is None or row["anomaly_severity"] in severities)
            and (row["anomaly_type"] is None) == (row["anomaly_severity"] is None)
        )
        (accepted if valid else rejected).append(row)
    return accepted, rejected


def run(conn: psycopg.Connection, path: Path) -> tuple[int, int]:
    """Charge le fichier ; renvoie (lignes écrites ou modifiées, lignes rejetées)."""
    run_id = runs.start_run(conn, RUN_TYPE)
    try:
        frame = read_history(path)
        unknown = sorted(set(frame["site_id"]) - values_of(conn, SITE_IDS))
        if unknown:
            raise RuntimeError(f"sites missing from ref.site: {unknown}; run load-ref first")
        rows, rejected = split_rows(
            history_rows(frame), values_of(conn, ALERT_TYPES), values_of(conn, SEVERITIES)
        )
        for row in rejected[:5]:
            logger.warning("rejected %s %s: source %s, anomaly %s/%s", row["site_id"], row["time"],
                           row["consumption_source"], row["anomaly_type"], row["anomaly_severity"])
        with conn.transaction(), conn.cursor() as cursor:
            cursor.executemany(UPSERT, rows)
            loaded = cursor.rowcount
    except Exception as exc:
        runs.finish_run(conn, run_id, error=str(exc))
        raise
    runs.finish_run(conn, run_id, rows_loaded=loaded, rows_rejected=len(rejected))
    return loaded, len(rejected)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("file", nargs="?", type=Path, default=DEFAULT_OUTPUT, help="cleaned parquet file")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    with db.connect() as conn:
        loaded, rejected = run(conn, args.file)
    logger.info("%d rows written in ml.history_labeled, %d rejected", loaded, rejected)

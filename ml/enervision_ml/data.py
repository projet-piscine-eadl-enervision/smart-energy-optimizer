"""Accès à la base : le seul module qui connaît le schéma.

Le ML lit analytics.energy_hourly (agrégat horaire de core.energy_reading, calculé par
TimescaleDB) et ref.site, et écrit ml.prediction. Ce sont les droits du rôle enervision_ml.
"""

from datetime import datetime

import pandas as pd
import psycopg

HOURLY_COLUMNS = [
    "hour",
    "site_id",
    "site_type",
    "capacity_kw",
    "consumption_kw",
    "temperature_celsius",
    "nb_readings",
    "nb_missing",
]

HOURLY_QUERY = """
SELECT h.hour,
       h.site_id,
       s.site_type,
       s.capacity_kw::float              AS capacity_kw,
       h.avg_consumption_kw::float       AS consumption_kw,
       h.avg_temperature_celsius::float  AS temperature_celsius,
       h.nb_readings,
       h.nb_missing
FROM analytics.energy_hourly h
JOIN ref.site s USING (site_id)
WHERE %(start)s::timestamptz IS NULL OR h.hour >= %(start)s
ORDER BY h.site_id, h.hour
"""

UPSERT_PREDICTION = """
INSERT INTO ml.prediction (target_time, site_id, model_version, predicted_kw, is_peak)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (target_time, site_id, model_version)
DO UPDATE SET predicted_kw = EXCLUDED.predicted_kw,
              is_peak      = EXCLUDED.is_peak,
              predicted_at = now()
"""


def load_hourly(database_url: str, start: datetime | None = None) -> pd.DataFrame:
    """Consommation horaire de chaque site, depuis start (tout l'historique par défaut)."""
    with psycopg.connect(database_url) as conn:
        rows = conn.execute(HOURLY_QUERY, {"start": start}).fetchall()
    df = pd.DataFrame(rows, columns=HOURLY_COLUMNS)
    df["hour"] = pd.to_datetime(df["hour"], utc=True)
    return df


def latest_hour(database_url: str) -> datetime | None:
    """Dernière heure disponible dans l'agrégat, None si la base est vide."""
    with psycopg.connect(database_url) as conn:
        return conn.execute("SELECT max(hour) FROM analytics.energy_hourly").fetchone()[0]


def save_predictions(database_url: str, predictions: pd.DataFrame, model_version: str) -> int:
    """Écrit les prédictions ; relancer sur les mêmes heures met à jour au lieu de dupliquer."""
    rows = [
        (row.target_time, row.site_id, model_version, float(row.predicted_kw), bool(row.is_peak))
        for row in predictions.itertuples(index=False)
    ]
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.executemany(UPSERT_PREDICTION, rows)
    return len(rows)

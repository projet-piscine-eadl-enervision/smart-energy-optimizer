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
WHERE (%(start)s::timestamptz IS NULL OR h.hour >= %(start)s)
  AND (%(end)s::timestamptz IS NULL OR h.hour < %(end)s)
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


UPSERT_MODEL_RUN = """
INSERT INTO ml.model_run (model_version, run_id, model, train_start, train_end, promoted,
                          decision, shiftable_ratio, peak_penalty_eur_kwh)
VALUES (%(model_version)s, %(run_id)s, %(model)s, %(train_start)s, %(train_end)s, %(promoted)s,
        %(decision)s, %(shiftable_ratio)s, %(peak_penalty_eur_kwh)s)
ON CONFLICT (model_version)
DO UPDATE SET run_id = EXCLUDED.run_id, model = EXCLUDED.model, trained_at = now(),
              train_start = EXCLUDED.train_start, train_end = EXCLUDED.train_end,
              promoted = EXCLUDED.promoted, decision = EXCLUDED.decision,
              shiftable_ratio = EXCLUDED.shiftable_ratio,
              peak_penalty_eur_kwh = EXCLUDED.peak_penalty_eur_kwh
"""

UPSERT_MODEL_METRIC = """
INSERT INTO ml.model_metric (model_version, metric, value) VALUES (%s, %s, %s)
ON CONFLICT (model_version, metric) DO UPDATE SET value = EXCLUDED.value
"""

UPSERT_PEAK_THRESHOLD = """
INSERT INTO ml.peak_threshold (model_version, site_id, threshold_kw) VALUES (%s, %s, %s)
ON CONFLICT (model_version, site_id) DO UPDATE SET threshold_kw = EXCLUDED.threshold_kw
"""


def load_hourly(
    database_url: str, start: datetime | None = None, end: datetime | None = None
) -> pd.DataFrame:
    """Consommation horaire de chaque site, de start à end exclu (tout l'historique par défaut)."""
    with psycopg.connect(database_url) as conn:
        rows = conn.execute(HOURLY_QUERY, {"start": start, "end": end}).fetchall()
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


def save_model_run(
    database_url: str, run: dict, metrics: dict[str, float], thresholds: dict[str, float]
) -> None:
    """Copie un entraînement en base pour le suivi en SQL, en une seule transaction.

    Rejouable : une version déjà connue est mise à jour (le registre MLflow remis à zéro
    repart de la version 1). Le rôle ML n'a pas le droit de supprimer : on écrase, on ne purge pas.
    """
    version = run["model_version"]
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(UPSERT_MODEL_RUN, run)
        cur.executemany(
            UPSERT_MODEL_METRIC, [(version, name, float(value)) for name, value in metrics.items()]
        )
        cur.executemany(
            UPSERT_PEAK_THRESHOLD,
            [(version, site_id, float(value)) for site_id, value in thresholds.items()],
        )
